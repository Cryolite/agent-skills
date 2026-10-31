#!/usr/bin/env python3
"""Create and remove a temporary pre-fix tree for regression-test checks.

`create` adds a detached Git worktree at the pre-fix revision, inside a new
temporary directory outside the repository, and copies the given test paths
from the current working tree into it. The tree then combines the pre-fix
production code with the final test code. `create` also reports which
copied paths differ from the revision and which other paths still differ
from the working tree; the latter should be exactly the fix.

`remove` deletes a tree made by `create`, including its worktree metadata.

Neither command changes the working tree, index, branches, or history of the
checkout it is run from. Repository hooks do not run while the tree is
checked out.

Examples:
    pre_fix_tree.py create --rev HEAD --copy tests/test_parser.py
    pre_fix_tree.py create --rev 1a2b3c4^ --copy tests --json
    pre_fix_tree.py remove /tmp/write-tests-pre-fix-abcd1234/tree
"""

from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

PREFIX = "write-tests-pre-fix-"
MARKER = "pre-fix-tree.json"
LIST_LIMIT = 100
IGNORED = shutil.ignore_patterns(
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache")


class Failure(Exception):
    """A problem with the arguments, the repository, or the file system."""


def git(arguments, cwd, check=True):
    command = ["git", "--no-optional-locks", *arguments]
    try:
        result = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", errors="surrogateescape")
    except FileNotFoundError as error:
        raise Failure("git is not installed or not on PATH") from error
    if check and result.returncode != 0:
        raise Failure(f"{shlex.join(command)} failed: {result.stderr.strip()}")
    return result


def split_nul(output):
    return [item for item in output.split("\0") if item]


def literal(paths):
    return [f":(literal){path}" for path in paths]


def repository_root(directory):
    result = git(["rev-parse", "--show-toplevel"], directory, check=False)
    if result.returncode != 0:
        raise Failure(f"not inside a Git working tree: {directory}")
    return Path(result.stdout.strip()).resolve()


def resolve_commit(root, revision):
    if not revision or revision.startswith("-"):
        raise Failure(f"invalid revision: {revision!r}")
    result = git(["rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}"],
                 root, check=False)
    commit = result.stdout.strip()
    if result.returncode != 0 or not commit:
        raise Failure(f"not a commit: {revision!r}")
    return commit


def repository_relative(root, path):
    """Return PATH relative to ROOT, without following a final symlink."""
    absolute = Path(os.path.abspath(path))
    real = absolute.parent.resolve() / absolute.name
    try:
        relative = real.relative_to(root)
    except ValueError:
        raise Failure(f"outside the repository: {path}") from None
    if relative == Path("."):
        raise Failure("copying the whole repository would copy the fix too; "
                      "name the test paths")
    if relative.parts[0] == ".git":
        raise Failure(f"inside .git: {path}")
    if not (real.exists() or real.is_symlink()):
        raise Failure(f"not in the working tree: {path}")
    return relative.as_posix()


def is_within(path, prefixes):
    plain = path.rstrip("/")
    return any(plain == prefix or plain.startswith(prefix + "/")
               for prefix in prefixes)


def tracked_changes(root, commit, paths=None):
    """Tracked paths whose working-tree state differs from COMMIT."""
    arguments = ["diff", "--name-status", "--no-renames", "-z", commit, "--"]
    if paths is not None:
        arguments.extend(literal(paths))
    items = split_nul(git(arguments, root).stdout)
    return [{"status": status, "path": path}
            for status, path in zip(items[0::2], items[1::2])]


def untracked(root, paths=None):
    """Untracked, non-ignored paths; whole directories are collapsed unless
    PATHS limits the listing."""
    arguments = ["ls-files", "--others", "--exclude-standard", "-z"]
    if paths is None:
        arguments.append("--directory")
    else:
        arguments.append("--")
        arguments.extend(literal(paths))
    return split_nul(git(arguments, root).stdout)


def by_path(entries):
    return sorted(entries, key=lambda entry: entry["path"])


def copied_changes(root, commit, copied):
    if not copied:
        return []
    changes = tracked_changes(root, commit, copied)
    changes += [{"status": "?", "path": path} for path in untracked(root, copied)]
    return by_path(changes)


def kept_at_revision(root, commit, copied):
    kept = [change for change in tracked_changes(root, commit)
            if not is_within(change["path"], copied)]
    for entry in untracked(root):
        if is_within(entry, copied):
            continue
        if entry.endswith("/") and any(path.startswith(entry) for path in copied):
            # A partly copied untracked directory: list what was left out.
            kept += [{"status": "?", "path": path}
                     for path in untracked(root, [entry.rstrip("/")])
                     if not is_within(path, copied)]
        else:
            kept.append({"status": "?", "path": entry})
    return by_path(kept)


def copy_into_tree(root, tree, relative):
    source = root / relative
    target = tree / relative
    for parent in reversed(target.relative_to(tree).parents):
        if parent != Path(".") and (tree / parent).is_symlink():
            raise Failure(f"{parent.as_posix()} is a symbolic link at the "
                          f"revision; refusing to copy {relative} through it")
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.is_dir():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir() and not source.is_symlink():
        shutil.copytree(source, target, symlinks=True, ignore=IGNORED)
    else:
        shutil.copy2(source, target, follow_symlinks=False)


def forget_worktree(root, tree):
    """Delete the worktree metadata that points at TREE, if any is left."""
    result = git(["rev-parse", "--git-common-dir"], root, check=False)
    if result.returncode != 0:
        return
    common = Path(result.stdout.strip())
    if not common.is_absolute():
        common = root / common
    administrative = common / "worktrees"
    if not administrative.is_dir():
        return
    for entry in administrative.iterdir():
        gitdir = entry / "gitdir"
        if not gitdir.is_file():
            continue
        target = Path(gitdir.read_text(encoding="utf-8").strip())
        if not target.is_absolute():
            target = entry / target
        if Path(os.path.realpath(target)) == tree / ".git":
            shutil.rmtree(entry)


def discard(root, tree, parent):
    if tree.exists():
        git(["worktree", "remove", "--force", str(tree)], root, check=False)
    forget_worktree(root, tree)
    shutil.rmtree(parent, ignore_errors=True)


def create(args):
    root = repository_root(Path(args.repo))
    commit = resolve_commit(root, args.rev)
    copied = []
    for path in args.copy:
        relative = repository_relative(root, path)
        if relative not in copied:
            copied.append(relative)
    # A copied directory already covers the paths below it.
    copied = [path for path in copied
              if not any(path.startswith(other + "/") for other in copied)]

    parent = Path(tempfile.mkdtemp(prefix=PREFIX)).resolve()
    tree = parent / "tree"
    try:
        if parent == root or root in parent.parents:
            raise Failure(f"the temporary directory {parent} is inside the "
                          "repository; point TMPDIR elsewhere")
        record = {"repository": str(root), "tree": str(tree), "revision": commit}
        (parent / MARKER).write_text(json.dumps(record, indent=2) + "\n",
                                     encoding="utf-8")
        git(["-c", f"core.hooksPath={os.devnull}",
             "worktree", "add", "--detach", str(tree), commit], root)
        for relative in copied:
            copy_into_tree(root, tree, relative)
        changes = copied_changes(root, commit, copied)
        kept = kept_at_revision(root, commit, copied)
    except BaseException:
        discard(root, tree, parent)
        raise
    notes = []
    if (tree / ".gitmodules").exists():
        notes.append(
            "The revision has submodules; they are not initialized in the tree.")
    if not kept:
        notes.append(
            "Nothing outside the copied paths differs from the working tree, so "
            "the tree equals the final state and a regression test cannot fail "
            "in it. Check --rev.")
    return {
        "tree": str(tree),
        "repository": str(root),
        "revision": commit,
        "requested_revision": args.rev,
        "copied": copied,
        "copied_changes": changes,
        "kept_at_revision": kept,
        "notes": notes,
    }


def remove(args):
    tree = Path(os.path.realpath(args.tree))
    parent = tree.parent
    marker = parent / MARKER
    if not parent.name.startswith(PREFIX) or not marker.is_file():
        raise Failure(f"not a tree created by this script: {args.tree}")
    try:
        record = json.loads(marker.read_text(encoding="utf-8"))
        recorded = Path(record["tree"])
        root = Path(record["repository"])
    except (ValueError, KeyError, TypeError) as error:
        raise Failure(f"unreadable marker {marker}: {error}") from None
    if recorded != tree:
        raise Failure(f"{marker} describes {recorded}, not {tree}")
    if root.is_dir():
        discard(root, tree, parent)
    else:
        shutil.rmtree(parent, ignore_errors=True)
    if parent.exists():
        raise Failure(f"could not delete {parent}")
    return {"removed": str(tree)}


def print_entries(entries):
    for entry in entries[:LIST_LIMIT]:
        print(f"  {entry['status']} {entry['path']}")
    if len(entries) > LIST_LIMIT:
        print(f"  ... and {len(entries) - LIST_LIMIT} more "
              "(use --json for the full list)")
    if not entries:
        print("  (none)")


def print_created(report):
    print(f"Pre-fix tree: {report['tree']}")
    print(f"Revision: {report['revision']} ({report['requested_revision']})")
    print()
    if report["copied"]:
        print("Copied from the working tree:")
        for path in report["copied"]:
            print(f"  {path}")
        print("Copied paths that differ from the revision "
              "(all of them must be test code):")
        print_entries(report["copied_changes"])
    else:
        print("Nothing was copied; the tree is the revision as committed.")
    print()
    print("Kept at the revision although the working tree differs "
          "(this should be exactly the fix):")
    print_entries(report["kept_at_revision"])
    for note in report["notes"]:
        print()
        print(f"Note: {note}")
    print()
    print("Remove it when done:")
    script = shlex.quote(os.path.realpath(__file__))
    print(f"  python3 {script} remove {shlex.quote(report['tree'])}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Create or remove a temporary pre-fix tree for "
                    "regression-test checks.")
    commands = parser.add_subparsers(dest="command", required=True)
    create_parser = commands.add_parser(
        "create", help="create a pre-fix tree")
    create_parser.add_argument(
        "--rev", required=True,
        help="the pre-fix revision, such as HEAD, <fix>^, or a merge-base")
    create_parser.add_argument(
        "--copy", action="append", default=[], metavar="PATH",
        help="a test file or directory to copy from the working tree, "
             "relative to the current directory; repeat as needed")
    create_parser.add_argument(
        "--repo", default=".", metavar="DIR",
        help="a directory inside the repository (default: the current one)")
    create_parser.add_argument(
        "--json", action="store_true", help="print a JSON report")
    remove_parser = commands.add_parser(
        "remove", help="remove a tree made by create")
    remove_parser.add_argument("tree", help="the tree path printed by create")
    remove_parser.add_argument(
        "--json", action="store_true", help="print a JSON report")
    args = parser.parse_args(argv)
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(errors="backslashreplace")

    try:
        report = create(args) if args.command == "create" else remove(args)
    except (Failure, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, indent=2))
    elif args.command == "create":
        print_created(report)
    else:
        print(f"Removed {report['removed']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
