#!/usr/bin/env python3
"""Behavioral tests for pre_fix_tree.py through its command-line interface.

Every test builds a throwaway Git repository with Git's global and system
configuration disabled, and points TMPDIR at its own scratch directory, so
nothing outside the test's temporary directory is touched. Run with:

    python3 test_pre_fix_tree.py
"""

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().with_name("pre_fix_tree.py")

BUGGY = "def last_index(items):\n    return len(items)\n"
FIXED = "def last_index(items):\n    return len(items) - 1\n"
REGRESSION = (
    "from calc import last_index\n\n\n"
    "def test_last_index_of_three_items_is_two():\n"
    "    assert last_index([1, 2, 3]) == 2\n")


class PreFixTreeTest(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="test-pre-fix-tree-")).resolve()
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.repo = self.base / "repo"
        self.scratch = self.base / "scratch"
        self.repo.mkdir()
        self.scratch.mkdir()
        self.env = {
            name: value for name, value in os.environ.items()
            if not name.startswith("GIT_")}
        self.env.update(
            TMPDIR=str(self.scratch),
            GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
            GIT_AUTHOR_NAME="Test", GIT_AUTHOR_EMAIL="test@example.com",
            GIT_COMMITTER_NAME="Test", GIT_COMMITTER_EMAIL="test@example.com")
        self.git("init", "-q", "-b", "main")
        self.write("src/calc.py", BUGGY)
        self.write("tests/test_calc.py", "from calc import last_index\n")
        self.write("tests/helpers.py", "HELPER = 1\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "Initial commit")

    def git(self, *arguments, cwd=None):
        return subprocess.run(
            ["git", *arguments], cwd=cwd or self.repo, env=self.env,
            check=True, capture_output=True, text=True).stdout

    def write(self, relative, content, root=None):
        path = (root or self.repo) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def script(self, *arguments, cwd=None, env=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *arguments], cwd=cwd or self.repo,
            env=env or self.env, capture_output=True, text=True)

    def create(self, *arguments, cwd=None):
        result = self.script("create", "--json", *arguments, cwd=cwd)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        # Clean up even when an assertion fails; a second removal is harmless.
        self.addCleanup(self.script, "remove", report["tree"])
        return report

    def checkout_state(self, root=None):
        """Everything a careless pre-fix setup could change in a checkout."""
        root = root or self.repo
        files = {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file() and ".git" not in path.relative_to(root).parts}
        return {
            "files": files,
            "status": self.git("status", "--porcelain=v1", "-z",
                               "--untracked-files=all", cwd=root),
            "staged": self.git("diff", "--cached", cwd=root),
            "head": self.git("rev-parse", "HEAD", cwd=root),
            "branches": self.git("branch", "--list", cwd=root),
        }

    def worktrees(self):
        return [line for line in self.git("worktree", "list", "--porcelain")
                .splitlines() if line.startswith("worktree ")]

    def test_uncommitted_fix_combines_committed_code_with_final_tests(self):
        self.write("src/calc.py", FIXED)
        self.write("tests/test_regression.py", REGRESSION)
        self.write("tests/helpers.py", "HELPER = 2\n")
        before = self.checkout_state()

        report = self.create("--rev", "HEAD", "--copy", "tests/test_regression.py",
                             "--copy", "tests/helpers.py")

        tree = Path(report["tree"])
        self.assertTrue(tree.is_relative_to(self.scratch))
        self.assertEqual((tree / "src/calc.py").read_text(), BUGGY)
        self.assertEqual((tree / "tests/test_regression.py").read_text(), REGRESSION)
        self.assertEqual((tree / "tests/helpers.py").read_text(), "HELPER = 2\n")
        self.assertEqual(report["kept_at_revision"],
                         [{"status": "M", "path": "src/calc.py"}])
        self.assertEqual(report["copied_changes"], [
            {"status": "M", "path": "tests/helpers.py"},
            {"status": "?", "path": "tests/test_regression.py"}])
        self.assertEqual(self.checkout_state(), before)

    def test_committed_fix_is_checked_against_its_parent(self):
        self.write("src/calc.py", FIXED)
        self.write("tests/test_regression.py", REGRESSION)
        self.git("add", ".")
        self.git("commit", "-q", "-m", "Fix last_index")

        report = self.create("--rev", "HEAD~1", "--copy", "tests/test_regression.py")

        tree = Path(report["tree"])
        self.assertEqual((tree / "src/calc.py").read_text(), BUGGY)
        self.assertEqual((tree / "tests/test_regression.py").read_text(), REGRESSION)
        self.assertEqual(report["kept_at_revision"],
                         [{"status": "M", "path": "src/calc.py"}])
        self.assertEqual(report["copied_changes"],
                         [{"status": "A", "path": "tests/test_regression.py"}])

    def test_remove_deletes_the_tree_and_its_worktree_entry(self):
        self.write("src/calc.py", FIXED)
        before = self.checkout_state()
        report = self.create("--rev", "HEAD")
        self.assertEqual(len(self.worktrees()), 2)

        result = self.script("remove", report["tree"])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(self.scratch.iterdir()), [])
        self.assertEqual(len(self.worktrees()), 1)
        self.assertEqual(self.checkout_state(), before)

    def test_remove_also_cleans_up_a_tree_deleted_by_hand(self):
        report = self.create("--rev", "HEAD")
        shutil.rmtree(report["tree"])

        result = self.script("remove", report["tree"])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(self.scratch.iterdir()), [])
        self.assertEqual(len(self.worktrees()), 1)

    def test_copied_directory_mirrors_deletions_in_the_working_tree(self):
        self.write("src/calc.py", FIXED)
        (self.repo / "tests/helpers.py").unlink()
        self.write("tests/test_regression.py", REGRESSION)

        report = self.create("--rev", "HEAD", "--copy", "tests")

        tree = Path(report["tree"])
        self.assertFalse((tree / "tests/helpers.py").exists())
        self.assertEqual((tree / "tests/test_regression.py").read_text(), REGRESSION)
        self.assertEqual(report["kept_at_revision"],
                         [{"status": "M", "path": "src/calc.py"}])

    def test_untracked_directory_is_listed_once_unless_partly_copied(self):
        self.write("newpkg/a.py", "")
        self.write("newpkg/b.py", "")
        self.write("tests/new/test_a.py", REGRESSION)
        self.write("tests/new/data.json", "{}")

        report = self.create("--rev", "HEAD", "--copy", "tests/new/test_a.py")

        self.assertEqual(report["kept_at_revision"], [
            {"status": "?", "path": "newpkg/"},
            {"status": "?", "path": "tests/new/data.json"}])

    def test_warns_when_only_copied_paths_differ(self):
        self.write("tests/test_regression.py", REGRESSION)

        report = self.create("--rev", "HEAD", "--copy", "tests/test_regression.py")

        self.assertEqual(report["kept_at_revision"], [])
        self.assertTrue(any("cannot fail" in note for note in report["notes"]),
                        report["notes"])

    @unittest.skipIf(os.name == "nt", "the hook is a POSIX shell script")
    def test_repository_hooks_do_not_run(self):
        ran = self.base / "hook-ran"
        hook = self.repo / ".git/hooks/post-checkout"
        hook.write_text(f"#!/bin/sh\ntouch '{ran}'\n")
        hook.chmod(hook.stat().st_mode | stat.S_IXUSR)

        self.create("--rev", "HEAD")

        self.assertFalse(ran.exists())

    def test_works_from_a_linked_worktree(self):
        work = self.base / "work"
        self.git("worktree", "add", "-q", "-b", "fix", str(work))
        self.write("src/calc.py", FIXED, root=work)
        self.write("tests/test_regression.py", REGRESSION, root=work)
        before_main = self.checkout_state()
        before_work = self.checkout_state(work)

        report = self.create("--rev", "HEAD", "--copy", "tests/test_regression.py",
                             cwd=work)
        tree = Path(report["tree"])
        self.assertEqual((tree / "src/calc.py").read_text(), BUGGY)
        self.assertEqual((tree / "tests/test_regression.py").read_text(), REGRESSION)
        self.assertEqual(report["kept_at_revision"],
                         [{"status": "M", "path": "src/calc.py"}])
        result = self.script("remove", report["tree"], cwd=work)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.worktrees()), 2)
        self.assertEqual(self.checkout_state(), before_main)
        self.assertEqual(self.checkout_state(work), before_work)

    def test_text_report_names_the_tree_and_the_removal_command(self):
        self.write("src/calc.py", FIXED)

        result = self.script("create", "--rev", "HEAD")

        self.assertEqual(result.returncode, 0, result.stderr)
        tree = next(line.removeprefix("Pre-fix tree: ")
                    for line in result.stdout.splitlines()
                    if line.startswith("Pre-fix tree: "))
        self.addCleanup(self.script, "remove", tree)
        self.assertIn("  M src/calc.py", result.stdout)
        self.assertIn(f" remove {tree}", result.stdout)

    def test_rejected_arguments_leave_no_trace(self):
        self.write("src/calc.py", FIXED)
        outside = self.base / "outside.py"
        outside.write_text("")
        before = self.checkout_state()
        cases = {
            "unknown revision": ["--rev", "no-such-revision"],
            "option-like revision": ["--rev=--all"],
            "missing copy path": ["--rev", "HEAD", "--copy", "tests/missing.py"],
            "path outside the repository": ["--rev", "HEAD", "--copy", str(outside)],
            "whole repository": ["--rev", "HEAD", "--copy", "."],
            "Git directory": ["--rev", "HEAD", "--copy", ".git/config"],
        }
        for name, arguments in cases.items():
            with self.subTest(name):
                result = self.script("create", *arguments)

                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("error:", result.stderr)
                self.assertEqual(list(self.scratch.iterdir()), [])
                self.assertEqual(len(self.worktrees()), 1)
                self.assertEqual(self.checkout_state(), before)

    def test_temporary_directory_inside_the_repository_is_rejected(self):
        inside = self.repo / "tmp"
        inside.mkdir()

        result = self.script("create", "--rev", "HEAD",
                             env=dict(self.env, TMPDIR=str(inside)))

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("inside the repository", result.stderr)
        self.assertEqual(list(inside.iterdir()), [])
        self.assertEqual(len(self.worktrees()), 1)

    def test_refuses_to_copy_through_a_symbolic_link_of_the_revision(self):
        elsewhere = self.base / "elsewhere"
        elsewhere.mkdir()
        (self.repo / "linked").symlink_to(elsewhere, target_is_directory=True)
        self.git("add", "linked")
        self.git("commit", "-q", "-m", "Add a link")
        (self.repo / "linked").unlink()
        self.write("linked/test_x.py", REGRESSION)

        result = self.script("create", "--rev", "HEAD", "--copy", "linked/test_x.py")

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("symbolic link", result.stderr)
        self.assertEqual(list(elsewhere.iterdir()), [])
        self.assertEqual(list(self.scratch.iterdir()), [])
        self.assertEqual(len(self.worktrees()), 1)

    def test_remove_refuses_a_directory_it_did_not_create(self):
        foreign = self.scratch / "write-tests-pre-fix-foreign" / "tree"
        foreign.mkdir(parents=True)

        result = self.script("remove", str(foreign))

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("not a tree created by this script", result.stderr)
        self.assertTrue(foreign.is_dir())


if __name__ == "__main__":
    unittest.main()
