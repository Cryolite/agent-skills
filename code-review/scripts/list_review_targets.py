#!/usr/bin/env python3
"""レビュー対象のファイルと変更箇所を一覧にする（リポジトリは変更しない）．

コードレビューでの読み漏らしを防ぐため，レビュー対象に含まれるファイルを列挙し，
状態，分類，追加・削除行数，変更後の行番号の範囲，注意すべき点（秘密情報らしき
文字列，競合マーカー，デバッグ用コード，実行権限の変更など）を表示する．

サブコマンド:
  detect             リポジトリの状態を調べ，レビュー対象の候補を示す
  worktree           未コミットの変更（ステージ済み，未ステージ，未追跡）
  staged             ステージ済みの変更
  branch [BASE]      BASE と HEAD の merge-base から HEAD までの変更
                     （BASE を省略すると既定のブランチを自動で検出する）
  range A..B         コミット範囲の変更（A...B は merge-base から B まで）
  commit REV         一つのコミットの変更（マージコミットは第 1 親との差分）
  files [PATH ...]   ファイル全体（Git リポジトリの外でも使える）

差分を扱うサブコマンドでは，`--` の後にパスを並べて対象を絞り込める．

終了ステータス: 0 = 成功，2 = 使い方の誤り，または git の実行に失敗
"""

import argparse
import json
import os
import re
import subprocess
import sys

READ_LIMIT = 5 * 1024 * 1024
HEAD_LIMIT = 4096
MARKER_LINES = 10
LARGE_FILE = 1024 * 1024
SCAN_LINE_LIMIT = 4096
MAX_NOTE_LINES = 5
LARGE_CHANGE_FILES = 100
LARGE_CHANGE_LINES = 3000
LARGE_TREE_FILES = 500

STATUS_LABELS = {
    "A": "追加", "C": "複製", "D": "削除", "M": "変更", "R": "改名",
    "T": "種別変更", "U": "未マージ", "X": "不明", "?": "追加（未追跡）",
}
MODE_NAMES = {
    "100644": "通常ファイル", "100755": "実行可能ファイル",
    "120000": "シンボリックリンク", "160000": "サブモジュール",
}

CATEGORY_ORDER = (
    "ソース", "テスト", "ビルド・CI", "依存関係", "設定", "ドキュメント",
    "ロックファイル", "生成物", "ベンダー", "バイナリ", "シンボリックリンク",
    "サブモジュール",
)
OVERVIEW_CATEGORIES = ("ロックファイル", "生成物", "ベンダー")
POLICY = (
    "レビュー方針: ソース，テスト，ビルド・CI，依存関係，設定，ドキュメントは全行を"
    "精読する．ロックファイル，生成物，ベンダーは概観し，バイナリ，シンボリック"
    "リンク，サブモジュールは存在と参照先の妥当性を確認する．分類と「注意」欄は"
    "ファイル名と内容からの機械的な推定なので，必ず該当箇所を読んで確かめる．"
)

VENDOR_DIRS = {
    "vendor", "vendors", "third_party", "third-party", "thirdparty",
    "3rdparty", "node_modules", "bower_components", "Pods", "Carthage",
}
GENERATED_DIRS = {"__generated__", "generated", "dist"}
TEST_NAME_RE = re.compile(
    r"(^test_.*\.py$|_test\.py$|^conftest\.py$|_test\.go$"
    r"|\.(test|spec)\.[cm]?[jt]sx?$"
    r"|(Test|Tests|IT)\.(java|kt|kts|scala|groovy)$|(Test|Tests)\.cs$"
    r"|_spec\.rb$|_test\.rb$|_test\.(c|cc|cpp|cxx|rs|exs|dart)$"
    r"|Tests?\.swift$|Test\.php$)")
TEST_DIRS = {
    "test", "tests", "__tests__", "__test__", "spec", "specs", "testdata",
    "test_data", "e2e", "__mocks__",
}
LOCK_FILES = {
    "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml",
    "bun.lockb", "bun.lock", "deno.lock", "Cargo.lock", "Gemfile.lock",
    "poetry.lock", "Pipfile.lock", "pdm.lock", "uv.lock", "pixi.lock",
    "composer.lock", "go.sum", "go.work.sum", "mix.lock", "pubspec.lock",
    "Podfile.lock", "Package.resolved", "flake.lock", "gradle.lockfile",
    "packages.lock.json", "conan.lock", ".terraform.lock.hcl", "renv.lock",
    "Cartfile.resolved",
}
BUILD_NAMES = {
    "Makefile", "makefile", "GNUmakefile", "CMakeLists.txt", "Dockerfile",
    "Containerfile", "Jenkinsfile", "Vagrantfile", "Earthfile", "Justfile",
    "justfile", "Taskfile.yml", "Taskfile.yaml", "Rakefile", "build.gradle",
    "build.gradle.kts", "settings.gradle", "settings.gradle.kts", "gradlew",
    "gradlew.bat", "build.xml", "meson.build", "meson_options.txt",
    "meson.options", "BUILD", "BUILD.bazel", "WORKSPACE", "WORKSPACE.bazel",
    "MODULE.bazel", "SConstruct", "SConscript", "configure.ac", "Makefile.am",
    "build.rs", "build.sbt", "noxfile.py", "tox.ini", ".gitlab-ci.yml",
    ".travis.yml", "azure-pipelines.yml", "bitbucket-pipelines.yml",
    "cloudbuild.yaml", "cloudbuild.yml", "appveyor.yml",
    ".pre-commit-config.yaml", "docker-compose.yml", "docker-compose.yaml",
    "compose.yml", "compose.yaml", "skaffold.yaml", "Procfile",
}
BUILD_NAME_RE = re.compile(
    r"(^Dockerfile\..+|\.dockerfile$|\.(cmake|bzl|mk|mak)$"
    r"|^docker-compose\..+\.ya?ml$)")
BUILD_DIR_PREFIXES = (
    ".github/workflows/", ".github/actions/", ".circleci/", ".buildkite/",
    ".gitlab/ci/",
)
DEPENDENCY_NAMES = {
    "package.json", "pyproject.toml", "setup.py", "setup.cfg", "Pipfile",
    "go.mod", "go.work", "Cargo.toml", "Gemfile", "pom.xml", "composer.json",
    "mix.exs", "pubspec.yaml", "Package.swift", "Podfile", "Cartfile",
    "Brewfile", "environment.yml", "environment.yaml", "conanfile.txt",
    "conanfile.py", "vcpkg.json", "packages.config",
    "Directory.Packages.props", "Directory.Build.props", "deno.json",
    "deno.jsonc", "stack.yaml",
}
DEPENDENCY_NAME_RE = re.compile(
    r"(^requirements.*\.(txt|in)$|^constraints.*\.txt$|\.gemspec$"
    r"|\.(csproj|fsproj|vbproj|nuspec)$|\.cabal$)")
GENERATED_NAME_RE = re.compile(
    r"(\.min\.(js|mjs|cjs|css)|\.(js|mjs|cjs|css)\.map|_pb2(_grpc)?\.pyi?"
    r"|\.pb(\.gw)?\.go|\.pb\.(cc|h|swift)|\.(g|freezed|gr)\.dart"
    r"|\.designer\.cs|\.g(\.i)?\.cs|[._-]generated\.[A-Za-z0-9]+)$")
GENERATED_MARKER_RE = re.compile(
    r"@generated|DO NOT EDIT|Code generated .* DO NOT EDIT"
    r"|(?i:auto-?generated|automatically generated"
    r"|this file (?:was|is) generated)")
DOC_EXTS = {
    ".md", ".markdown", ".mdx", ".rst", ".adoc", ".asciidoc", ".txt", ".org",
    ".rdoc",
}
DOC_NAME_RE = re.compile(
    r"^(README|CHANGELOG|CHANGES|HISTORY|NEWS|LICENSE|LICENCE|COPYING"
    r"|NOTICE|AUTHORS|CONTRIBUTORS|CONTRIBUTING|CODE_OF_CONDUCT|SECURITY"
    r"|MAINTAINERS|SUPPORT)(\.(md|markdown|rst|txt|adoc|org))?$",
    re.IGNORECASE)
LICENSE_NAME_RE = re.compile(r"^(LICENSE|LICENCE|COPYING)[-_.][A-Za-z0-9.-]+$")
CONFIG_EXTS = {
    ".yml", ".yaml", ".json", ".jsonc", ".json5", ".toml", ".ini", ".cfg",
    ".conf", ".properties", ".env", ".xml", ".plist", ".tfvars",
}
CONFIG_NAMES = {"CODEOWNERS", "OWNERS"}
SECRET_NAME_RE = re.compile(
    r"(^\.env(\..+)?$|\.(pem|key|p12|pfx|jks|keystore|ppk|kdbx|tfstate"
    r"|tfstate\.backup)$|^id_(rsa|dsa|ecdsa|ed25519)$"
    r"|^(credentials|secrets?)(\..+)?$"
    r"|^\.(netrc|pgpass|pypirc|npmrc|htpasswd|git-credentials)$"
    r"|^service[-_]?account.*\.json$)", re.IGNORECASE)
SECRET_NAME_EXCLUDE_RE = re.compile(
    r"\.(example|sample|template|dist|defaults?|tmpl)$", re.IGNORECASE)
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    ".tox", ".nox", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".gradle",
    ".idea",
}

SECRET_RE = re.compile(
    r"(?:AKIA|ASIA)[0-9A-Z]{16}"
    r"|-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"
    r"|\bgh[pousr]_[A-Za-z0-9]{36,}"
    r"|\bgithub_pat_[A-Za-z0-9_]{22,}"
    r"|\bglpat-[A-Za-z0-9_-]{20,}"
    r"|\bxox[abprs]-[A-Za-z0-9-]{10,}"
    r"|\bAIza[0-9A-Za-z_-]{35}"
    r"|\bsk_live_[0-9A-Za-z]{16,}"
    r"|\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
    r"|[A-Za-z][A-Za-z0-9+.-]*://[^/\s:@'\"]+:[^/\s@'\"$<{%]{3,}@"
    r"|(?i:\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?key"
    r"|auth[_-]?token|client[_-]?secret|private[_-]?key)\b[\"']?\s*[:=]"
    r"\s*[\"'](?![$<{%])[^\"'\s]{8,}[\"'])")

LINE_CHECKS = (
    ("競合マーカー", re.compile(r"^(<<<<<<<|>>>>>>>)( |$)")),
    ("秘密情報らしき文字列", SECRET_RE),
    ("デバッグ用コードの疑い", re.compile(
        r"\b(?:i?pdb\.set_trace\(|breakpoint\(\)|binding\.pry\b|byebug\b"
        r"|dbg!\(|var_dump\()|^\s*debugger\s*;?\s*$")),
    ("TODO・FIXME", re.compile(r"\b(?:TODO|FIXME|HACK|XXX)\b(?=[\s:(\]]|$)")),
)


def classify(path, head=None, binary=False, mode=None):
    """パスと先頭部分の内容から分類と補足を返す．"""
    if mode == "160000":
        return "サブモジュール", None
    if mode == "120000":
        return "シンボリックリンク", None
    parts = path.rstrip("/").split("/")
    dirs, name = parts[:-1], parts[-1]
    if any(d in VENDOR_DIRS for d in dirs):
        return "ベンダー", None
    if name in LOCK_FILES or name.endswith(".lock"):
        return "ロックファイル", None
    if GENERATED_NAME_RE.search(name) or any(d in GENERATED_DIRS for d in dirs):
        return "生成物", None
    if binary:
        return "バイナリ", None
    if head:
        top = "\n".join(head.splitlines()[:MARKER_LINES])
        if GENERATED_MARKER_RE.search(top):
            return "生成物", "先頭に生成マーカーあり（生成物と推定）"
    if TEST_NAME_RE.search(name) or any(d in TEST_DIRS for d in dirs):
        return "テスト", None
    if (name in BUILD_NAMES or BUILD_NAME_RE.search(name)
            or path.startswith(BUILD_DIR_PREFIXES)):
        return "ビルド・CI", None
    if name in DEPENDENCY_NAMES or DEPENDENCY_NAME_RE.search(name):
        return "依存関係", None
    ext = os.path.splitext(name)[1].lower()
    if DOC_NAME_RE.match(name) or LICENSE_NAME_RE.match(name) or ext in DOC_EXTS:
        return "ドキュメント", None
    if ext in CONFIG_EXTS or name.startswith(".") or name in CONFIG_NAMES:
        return "設定", None
    return "ソース", None


def secret_name_note(path):
    name = path.rstrip("/").split("/")[-1]
    if SECRET_NAME_RE.search(name) and not SECRET_NAME_EXCLUDE_RE.search(name):
        return "秘密情報を含みうるファイル名"
    return None


class GitError(Exception):
    pass


def fsdecode(data):
    return data.decode("utf-8", "surrogateescape")


def shown(text):
    """表示用に，復号できなかったバイトを置換文字にする．"""
    return text.encode("utf-8", "surrogateescape").decode("utf-8", "replace")


URL_USERINFO_RE = re.compile(
    r"^(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*)://(?P<userinfo>[^/@]*)@")


def redact(text):
    """URL の認証情報や秘密情報らしき文字列を伏せる．"""
    if not text:
        return text
    match = URL_USERINFO_RE.match(text)
    if match:
        scheme = match.group("scheme").lower()
        if ":" in match.group("userinfo") or "ssh" not in scheme:
            text = "%s://***@%s" % (match.group("scheme"), text[match.end():])
    return SECRET_RE.sub("***", text)


class Git(object):
    """読み取り専用で git を実行する．"""

    def __init__(self, cwd):
        self.cwd = cwd
        self.env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_PAGER="cat",
                        PAGER="cat", GIT_TERMINAL_PROMPT="0")

    def run(self, args, cwd=None, check=True, stdin_data=None):
        command = ["git", "--no-pager", "-c", "core.quotepath=false",
                   "-c", "color.ui=never", "-c", "diff.relative=false"] + args
        try:
            proc = subprocess.run(command, cwd=cwd or self.cwd, env=self.env,
                                  input=stdin_data,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
        except OSError as exc:
            raise GitError("git を実行できません: %s" % exc)
        if check and proc.returncode != 0:
            message = proc.stderr.decode("utf-8", "replace").strip()
            raise GitError("`git %s` が失敗しました: %s"
                           % (" ".join(shown(a) for a in args), message))
        return proc

    def out(self, args, cwd=None):
        return self.run(args, cwd=cwd).stdout

    def text(self, args, cwd=None):
        """成功すれば出力の文字列を，失敗すれば None を返す．"""
        proc = self.run(args, cwd=cwd, check=False)
        if proc.returncode != 0:
            return None
        return fsdecode(proc.stdout).strip()

    def lines_z(self, args, cwd=None):
        return [fsdecode(p) for p in self.out(args, cwd=cwd).split(b"\0") if p]

    def stream(self, args, cwd=None):
        """出力を行単位で返す（大きな出力をメモリに溜めない）．"""
        command = ["git", "--no-pager", "-c", "core.quotepath=false",
                   "-c", "color.ui=never", "-c", "diff.relative=false"] + args
        try:
            proc = subprocess.Popen(command, cwd=cwd or self.cwd, env=self.env,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL)
        except OSError as exc:
            raise GitError("git を実行できません: %s" % exc)
        try:
            for raw in proc.stdout:
                yield raw.rstrip(b"\n")
        finally:
            proc.stdout.close()
            status = proc.wait()
        if status != 0:
            raise GitError("`git %s` が失敗しました（終了ステータス %d）"
                           % (" ".join(shown(a) for a in args), status))

    def blob_head(self, sha, limit=HEAD_LIMIT):
        try:
            proc = subprocess.Popen(["git", "cat-file", "blob", sha],
                                    cwd=self.cwd, env=self.env,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL)
        except OSError:
            return b""
        data = proc.stdout.read(limit)
        proc.stdout.close()
        proc.wait()
        return data

    def blob_sizes(self, shas):
        if not shas:
            return {}
        proc = subprocess.run(
            ["git", "cat-file", "--batch-check=%(objectname) %(objectsize)"],
            cwd=self.cwd, env=self.env, input="\n".join(shas).encode() + b"\n",
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        sizes = {}
        for line in proc.stdout.decode("ascii", "replace").splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1].isdigit():
                sizes[parts[0]] = int(parts[1])
        return sizes


def is_null_sha(sha):
    return not sha or set(sha) == {"0"}


def is_binary(data):
    return b"\0" in data[:8000]


def count_lines(data):
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def human_size(size):
    if size >= 1024 * 1024:
        return "%.1f MiB" % (size / 1024.0 / 1024.0)
    return "%.1f KiB" % (size / 1024.0)


def scan_lines(numbered_lines):
    """(行番号, 文字列) の並びを検査し，「注意」欄の文言を返す．"""
    hits = [[] for _ in LINE_CHECKS]
    for number, text in numbered_lines:
        text = text[:SCAN_LINE_LIMIT]
        for index, (_, regex) in enumerate(LINE_CHECKS):
            if regex.search(text):
                hits[index].append(number)
    notes = []
    for (label, _), numbers in zip(LINE_CHECKS, hits):
        if numbers:
            listed = ", ".join(str(n) for n in numbers[:MAX_NOTE_LINES])
            rest = len(numbers) - MAX_NOTE_LINES
            notes.append("%s: %s 行目%s" % (
                label, listed, "ほか %d 箇所" % rest if rest > 0 else ""))
    return notes


def numbered_text_lines(data):
    text = data.decode("utf-8", "replace")
    return list(enumerate(text.splitlines(), 1))


HUNK_RE = re.compile(rb"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def parse_patch(lines, hunks):
    """-U0 のパッチの行を読み，ハンクを hunks に追加しながら追加行を返す．

    追加行は (変更後の行番号, 先頭 SCAN_LINE_LIMIT バイトの文字列) として
    順に返す．行を保持しないので，大きなパッチでもメモリを消費しない．
    """
    new_line = None
    for raw in lines:
        match = HUNK_RE.match(raw)
        if match:
            old_start, old_lines, new_start, new_lines = match.groups()
            hunks.append({
                "old_start": int(old_start),
                "old_lines": 1 if old_lines is None else int(old_lines),
                "new_start": int(new_start),
                "new_lines": 1 if new_lines is None else int(new_lines),
            })
            new_line = int(new_start)
            continue
        if new_line is None:
            continue
        if raw.startswith(b"+"):
            yield new_line, raw[1:SCAN_LINE_LIMIT + 1].decode("utf-8", "replace")
            new_line += 1


def parse_raw(data):
    """`git diff --raw -z` の出力を解析する．"""
    parts = data.split(b"\0")
    entries = []
    index = 0
    while index < len(parts):
        meta = parts[index]
        if not meta:
            index += 1
            continue
        if not meta.startswith(b":"):
            raise GitError("`git diff --raw` の出力を解析できません")
        fields = meta[1:].decode("ascii", "replace").split()
        old_mode, new_mode, old_sha, new_sha, status = fields[:5]
        letter = status[:1]
        if letter in ("R", "C"):
            old_path, path = fsdecode(parts[index + 1]), fsdecode(parts[index + 2])
            index += 3
        else:
            old_path = path = fsdecode(parts[index + 1])
            index += 2
        entries.append({
            "status": letter, "score": status[1:], "old_mode": old_mode,
            "new_mode": new_mode, "old_sha": old_sha, "new_sha": new_sha,
            "old_path": old_path, "path": path,
        })
    return entries


def parse_numstat(data):
    """`git diff --numstat -z` の出力を，変更後のパスをキーとする辞書にする．"""
    parts = data.split(b"\0")
    stats = {}
    index = 0
    while index < len(parts):
        token = parts[index]
        index += 1
        if not token:
            continue
        fields = token.split(b"\t", 2)
        if len(fields) != 3:
            continue
        added, deleted, path = fields
        if not path:
            if index + 1 >= len(parts):
                break
            path = parts[index + 1]
            index += 2
        if added == b"-" or not added.isdigit() or not deleted.isdigit():
            counts = (None, None)
        else:
            counts = (int(added), int(deleted))
        stats[fsdecode(path)] = counts
    return stats


class Repo(object):
    def __init__(self, cwd):
        self.cwd = cwd
        self.git = Git(cwd)
        try:
            self.root = self.git.text(["rev-parse", "--show-toplevel"]) or None
        except GitError:
            self.root = None

    def require(self):
        if not self.root:
            raise GitError("Git リポジトリではありません（`files` サブコマンドは"
                           "リポジトリの外でも使えます）")

    def head(self):
        return self.git.text(["rev-parse", "--verify", "-q", "HEAD^{commit}"])

    def resolve(self, rev):
        if not rev or rev.startswith("-"):
            raise GitError("リビジョン `%s` の指定が不正です" % shown(rev))
        sha = self.git.text(["rev-parse", "--verify", "-q", rev + "^{commit}"])
        if not sha:
            raise GitError("リビジョン `%s` が見つかりません" % shown(rev))
        return sha

    def merge_base(self, left, right):
        base = self.git.text(["merge-base", left, right])
        if not base:
            raise GitError("`%s` と `%s` の merge-base が見つかりません"
                           % (shown(left), shown(right)))
        return base

    def empty_tree(self):
        proc = self.git.run(["hash-object", "-t", "tree", "--stdin"],
                            stdin_data=b"")
        return proc.stdout.decode("ascii").strip()

    def detect_base(self):
        ref = self.git.text(["symbolic-ref", "-q", "--short",
                             "refs/remotes/origin/HEAD"])
        if ref:
            return ref
        for candidate in ("origin/main", "origin/master", "main", "master"):
            if self.git.text(["rev-parse", "--verify", "-q",
                              candidate + "^{commit}"]):
                return candidate
        return None

    def commits(self, base, head, limit=50):
        output = self.git.text(["log", "--no-color", "--format=%h%x09%s",
                                "-n", str(limit + 1), "%s..%s" % (base, head)])
        lines = [line.split("\t", 1) for line in (output or "").splitlines()]
        return [(c[0], redact(c[1]) if len(c) > 1 else "")
                for c in lines[:limit]], len(lines) > limit


def short(sha):
    return sha[:7]


def target_worktree(repo):
    head = repo.head()
    if head:
        return {"mode": "worktree", "diff_args": ["HEAD"], "untracked": True,
                "index": True,
                "title": "未コミットの変更（ステージ済み，未ステージ，未追跡）",
                "compare": "`HEAD`（`%s`）→ 作業ツリー" % short(head)}
    return {"mode": "worktree", "diff_args": [repo.empty_tree()],
            "untracked": True, "index": True,
            "title": "未コミットの変更（ステージ済み，未ステージ，未追跡）",
            "compare": "空のツリー（コミットなし）→ 作業ツリー"}


def target_staged(repo):
    head = repo.head()
    return {"mode": "staged", "diff_args": ["--cached"], "untracked": False,
            "index": True,
            "title": "ステージ済みの変更",
            "compare": ("`HEAD`（`%s`）→ インデックス" % short(head)) if head
            else "空のツリー（コミットなし）→ インデックス"}


def target_branch(repo, base, with_worktree):
    if base is None:
        base = repo.detect_base()
        if base is None:
            raise GitError("ベースのブランチを検出できませんでした．"
                           "`branch <BASE>` の形で指定してください")
    head = repo.head()
    if not head:
        raise GitError("HEAD にコミットがありません")
    merge_base = repo.merge_base(repo.resolve(base), head)
    target = {"mode": "branch", "log": (merge_base, head)}
    if with_worktree:
        target.update({
            "diff_args": [merge_base], "untracked": True, "index": True,
            "title": "ブランチの差分と未コミットの変更（`%s` との merge-base "
                     "から作業ツリーまで）" % shown(base),
            "compare": "`%s`（merge-base）→ 作業ツリー" % short(merge_base)})
    else:
        target.update({
            "diff_args": [merge_base, head], "untracked": False,
            "title": "ブランチの差分（`%s...HEAD`）" % shown(base),
            "compare": "`%s`（merge-base）→ `HEAD`（`%s`）"
                       % (short(merge_base), short(head))})
    return target


def target_range(repo, spec):
    if "..." in spec:
        left, right = spec.split("...", 1)
        right_sha = repo.resolve(right or "HEAD")
        base = repo.merge_base(repo.resolve(left or "HEAD"), right_sha)
        compare = "`%s`（merge-base）→ `%s`（`%s`）" % (
            short(base), shown(right or "HEAD"), short(right_sha))
    elif ".." in spec:
        left, right = spec.split("..", 1)
        base = repo.resolve(left or "HEAD")
        right_sha = repo.resolve(right or "HEAD")
        compare = "`%s`（`%s`）→ `%s`（`%s`）" % (
            shown(left or "HEAD"), short(base), shown(right or "HEAD"),
            short(right_sha))
    else:
        raise GitError("範囲は `A..B` または `A...B` の形で指定してください"
                       "（一つのコミットには `commit` を使います）")
    return {"mode": "range", "diff_args": [base, right_sha], "untracked": False,
            "title": "コミット範囲 `%s`" % shown(spec), "compare": compare,
            "log": (base, right_sha)}


def target_commit(repo, rev):
    sha = repo.resolve(rev)
    parents = (repo.git.text(["rev-list", "--parents", "-n", "1", sha])
               or "").split()[1:]
    subject = redact(repo.git.text(["log", "-n", "1", "--no-color",
                                    "--format=%s", sha]) or "")
    if parents:
        base = parents[0]
        compare = "`%s`（第 1 親）→ `%s`" % (short(base), short(sha))
        if len(parents) > 1:
            compare += "（マージコミットのため第 1 親との差分）"
    else:
        base = repo.empty_tree()
        compare = "空のツリー → `%s`（ルートコミット）" % short(sha)
    return {"mode": "commit", "diff_args": [base, sha], "untracked": False,
            "title": "コミット `%s`" % short(sha), "compare": compare,
            "commit_list": [(short(sha), subject)]}


def mode_notes(entry):
    old_mode, new_mode = entry["old_mode"], entry["new_mode"]
    notes = []
    if entry["status"] == "T":
        notes.append("種別の変更（%s → %s）" % (
            MODE_NAMES.get(old_mode, old_mode), MODE_NAMES.get(new_mode, new_mode)))
    elif old_mode == "100644" and new_mode == "100755":
        notes.append("実行権限を付与")
    elif old_mode == "100755" and new_mode == "100644":
        notes.append("実行権限を削除")
    elif entry["status"] == "A" and new_mode == "100755":
        notes.append("実行権限あり")
    return notes


def read_worktree_head(path, limit=HEAD_LIMIT):
    try:
        if os.path.islink(path):
            return os.readlink(path).encode("utf-8", "surrogateescape")
        with open(path, "rb") as stream:
            return stream.read(limit)
    except (IOError, OSError):
        return b""


def diff_entry(repo, target, entry, counts, sizes):
    status = entry["status"]
    deleted = status == "D"
    path = entry["path"]
    mode = entry["old_mode"] if deleted else entry["new_mode"]
    full = os.path.join(repo.root, path)
    added_count, deleted_count = counts
    binary = added_count is None and status != "U" and mode != "160000"
    item = {
        "path": path, "old_path": None, "status": status,
        "status_label": STATUS_LABELS.get(status, status),
        "similarity": None, "category": None, "added": added_count,
        "deleted": deleted_count, "binary": binary, "size": None,
        "hunks": [], "notes": [],
    }
    if status in ("R", "C"):
        item["old_path"] = entry["old_path"]
        if entry["score"].isdigit():
            item["similarity"] = int(entry["score"])
    notes = item["notes"]

    head = b""
    if not deleted and mode != "160000":
        if is_null_sha(entry["new_sha"]):
            head = read_worktree_head(full)
            if os.path.isfile(full) and not os.path.islink(full):
                item["size"] = os.path.getsize(full)
        else:
            head = repo.git.blob_head(entry["new_sha"])
            item["size"] = sizes.get(entry["new_sha"])
    head_text = None if binary else head.decode("utf-8", "replace")
    category, category_note = classify(path, head_text, binary, mode)
    item["category"] = category

    if status == "U":
        notes.append("未解決のコンフリクト")
    if category_note:
        notes.append(category_note)
    notes.extend(mode_notes(entry))
    if mode == "160000":
        old_sha, new_sha = entry["old_sha"], entry["new_sha"]
        if is_null_sha(new_sha) and not deleted and os.path.isdir(full):
            new_sha = repo.git.text(["-C", full, "rev-parse", "HEAD"]) or new_sha
        if old_sha == new_sha:
            notes.append("参照先は同じ（サブモジュール内に未コミットの変更）")
        else:
            notes.append("参照先: %s → %s" % (
                "（なし）" if is_null_sha(old_sha) else short(old_sha),
                "（削除）" if deleted else
                "（不明）" if is_null_sha(new_sha) else short(new_sha)))
    elif mode == "120000" and not deleted:
        notes.append("リンク先: `%s`" % shown(head_text or ""))
    secret = secret_name_note(path)
    if secret:
        notes.append(secret)
    if item["size"] is not None and item["size"] >= LARGE_FILE:
        notes.append("大きなファイル（%s）" % human_size(item["size"]))

    if not binary and status != "U" and mode != "160000":
        paths = [entry["old_path"], path] if entry["old_path"] != path else [path]
        patch = repo.git.stream(
            ["--literal-pathspecs", "diff", "-U0", "--no-color", "--no-ext-diff",
             "--no-textconv", "-M"] + target["diff_args"] + ["--"] + paths,
            cwd=repo.root)
        notes.extend(scan_lines(parse_patch(patch, item["hunks"])))
    return item


def untracked_entry(repo, path):
    full = os.path.join(repo.root, path)
    item = {
        "path": path, "old_path": None, "status": "?",
        "status_label": STATUS_LABELS["?"], "similarity": None,
        "category": None, "added": None, "deleted": 0, "binary": False,
        "size": None, "hunks": [], "notes": [],
    }
    notes = item["notes"]
    if path.endswith("/"):
        item["category"] = "サブモジュール"
        notes.append("入れ子の Git リポジトリ（未追跡）")
        return item
    if os.path.islink(full):
        item["category"] = "シンボリックリンク"
        notes.append("リンク先: `%s`" % shown(os.readlink(full)))
        return item
    try:
        item["size"] = os.path.getsize(full)
        with open(full, "rb") as stream:
            data = stream.read(READ_LIMIT)
    except (IOError, OSError) as exc:
        item["category"], _ = classify(path)
        notes.append("読み込めません（%s）" % exc.strerror)
        return item
    item["binary"] = is_binary(data)
    item["category"], category_note = classify(
        path, None if item["binary"] else data[:HEAD_LIMIT].decode(
            "utf-8", "replace"), item["binary"])
    if category_note:
        notes.append(category_note)
    if os.access(full, os.X_OK):
        notes.append("実行権限あり")
    secret = secret_name_note(path)
    if secret:
        notes.append(secret)
    if item["size"] >= LARGE_FILE:
        notes.append("大きなファイル（%s）" % human_size(item["size"]))
    if item["binary"]:
        item["added"] = None
        item["deleted"] = None
    elif item["size"] > READ_LIMIT:
        notes.append("大きすぎるため行数と内容を検査していません")
    else:
        item["added"] = count_lines(data)
        if item["added"]:
            item["hunks"] = [{"old_start": 0, "old_lines": 0, "new_start": 1,
                              "new_lines": item["added"]}]
        notes.extend(scan_lines(numbered_text_lines(data)))
    return item


def collect_diff(repo, target, pathspecs):
    common = ["--no-color", "--no-ext-diff", "--no-textconv", "-M"]
    common += target["diff_args"] + ["--"] + pathspecs
    entries = parse_raw(repo.git.out(["diff", "--raw", "-z", "--no-abbrev"]
                                     + common))
    numstat = parse_numstat(repo.git.out(["diff", "--numstat", "-z"] + common))
    merged = {}
    order = []
    for entry in entries:
        key = entry["path"]
        if key in merged:
            if entry["status"] == "U":
                merged[key]["status"] = "U"
            continue
        merged[key] = entry
        order.append(key)
    sizes = repo.git.blob_sizes(sorted({
        e["new_sha"] for e in merged.values()
        if not is_null_sha(e["new_sha"]) and e["new_mode"] != "160000"}))
    files = [diff_entry(repo, target, merged[key],
                        numstat.get(key, (None, None)), sizes)
             for key in order]
    if target["untracked"]:
        listed = set(order)
        for path in repo.git.lines_z(
                ["ls-files", "-z", "--others", "--exclude-standard",
                 "--full-name", "--"] + (pathspecs or [":/"])):
            if path not in listed:
                files.append(untracked_entry(repo, path))
    if target.get("index"):
        unmerged = set(repo.git.lines_z(["diff", "--name-only",
                                         "--diff-filter=U", "-z"]))
        for item in files:
            if item["path"] in unmerged and "未解決のコンフリクト" not in item["notes"]:
                item["notes"].insert(0, "未解決のコンフリクト")
    files.sort(key=lambda item: item["path"])
    return files


def walk_paths(paths):
    """Git リポジトリの外で，パス以下のファイルを列挙する．"""
    listed, skipped = [], []
    for top in paths:
        if not os.path.isdir(top) or os.path.islink(top):
            listed.append(os.path.normpath(top))
            continue
        for dirpath, dirnames, filenames in os.walk(top):
            keep = []
            for name in sorted(dirnames):
                full = os.path.normpath(os.path.join(dirpath, name))
                if name in SKIP_DIRS:
                    skipped.append(full)
                elif os.path.islink(full):
                    listed.append(full)
                else:
                    keep.append(name)
            dirnames[:] = keep
            listed.extend(os.path.normpath(os.path.join(dirpath, name))
                          for name in sorted(filenames))
    return listed, skipped


def file_item(base, path, state=None):
    full = path if os.path.isabs(path) else os.path.join(base, path)
    shown_path = path.replace(os.sep, "/")
    item = {"path": shown_path, "category": None, "lines": None, "size": None,
            "binary": False, "notes": []}
    notes = item["notes"]
    if state:
        notes.append(state)
    if os.path.islink(full):
        item["category"] = "シンボリックリンク"
        notes.append("リンク先: `%s`" % shown(os.readlink(full)))
        return item
    if os.path.isdir(full):
        item["category"] = "サブモジュール"
        notes.append("ディレクトリ（サブモジュールまたは入れ子のリポジトリ）")
        return item
    try:
        item["size"] = os.path.getsize(full)
        with open(full, "rb") as stream:
            data = stream.read(READ_LIMIT)
    except (IOError, OSError) as exc:
        item["category"], _ = classify(shown_path)
        notes.append("読み込めません（%s）" % (exc.strerror or exc))
        return item
    item["binary"] = is_binary(data)
    item["category"], category_note = classify(
        shown_path, None if item["binary"] else data[:HEAD_LIMIT].decode(
            "utf-8", "replace"), item["binary"])
    if category_note:
        notes.append(category_note)
    secret = secret_name_note(shown_path)
    if secret:
        notes.append(secret)
    if item["size"] >= LARGE_FILE:
        notes.append("大きなファイル（%s）" % human_size(item["size"]))
    if not item["binary"]:
        if item["size"] > READ_LIMIT:
            notes.append("大きすぎるため行数と内容を検査していません")
        else:
            item["lines"] = count_lines(data)
            notes.extend(scan_lines(numbered_text_lines(data)))
    return item


def collect_files(repo, paths):
    for path in paths:
        if not os.path.lexists(path):
            raise GitError("パス `%s` が存在しません" % shown(path))
    skipped = []
    if repo.root:
        spec = paths or [":/"]
        ls_files = ["ls-files", "-z", "--full-name"]
        tracked = repo.git.lines_z(ls_files + ["--cached", "--"] + spec)
        others = repo.git.lines_z(ls_files + ["--others", "--exclude-standard",
                                              "--"] + spec)
        explicit = [p for p in paths if os.path.isfile(p)]
        ignored_files = repo.git.lines_z(
            ls_files + ["--others", "--ignored", "--exclude-standard", "--"]
            + explicit) if explicit else []
        base = repo.root
        listed, seen = [], set()
        for path, state in ([(p, None) for p in tracked]
                            + [(p, "未追跡") for p in others]
                            + [(p, "Git の無視対象（明示的に指定）")
                               for p in ignored_files]):
            path = path.rstrip("/")
            if path not in seen:
                seen.add(path)
                listed.append((path, state))
        skipped = [p for p in repo.git.lines_z(
            ls_files + ["--others", "--ignored", "--exclude-standard",
                        "--directory", "--"] + spec)
            if p.rstrip("/") not in seen]
    else:
        base = os.getcwd()
        walked, skipped = walk_paths(paths or ["."])
        listed = [(path, None) for path in walked]
    items = [file_item(base, path, state) for path, state in listed]
    items.sort(key=lambda item: item["path"])
    return base, items, skipped


IN_PROGRESS = (
    ("MERGE_HEAD", "マージ"), ("CHERRY_PICK_HEAD", "cherry-pick"),
    ("REVERT_HEAD", "revert"), ("BISECT_LOG", "bisect"),
    ("rebase-merge", "rebase"), ("rebase-apply", "rebase または am"),
)


def in_progress(repo):
    args = []
    for name, _ in IN_PROGRESS:
        args += ["--git-path", name]
    output = repo.git.text(["rev-parse"] + args) or ""
    found = []
    for (_, label), path in zip(IN_PROGRESS, output.splitlines()):
        full = path if os.path.isabs(path) else os.path.join(repo.cwd, path)
        if os.path.exists(full) and label not in found:
            found.append(label)
    return found


def hosting(url):
    if not url:
        return None
    match = (re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://(?:[^@/]*@)?([^/:]+)", url)
             or re.match(r"^(?:[^@/]*@)?([^/:]+):", url))
    host = match.group(1).lower() if match else ""
    if "github" in host:
        return "GitHub"
    if "gitlab" in host:
        return "GitLab"
    return "不明"


def detect(repo):
    if not repo.root:
        return {
            "git": False, "ask_user": False,
            "message": "Git リポジトリではありません．ファイル全体をレビューする"
                       "場合は `files [PATH...]` を使います．",
            "recommendations": [{"label": "ファイル全体",
                                 "command": "files [PATH...]"}],
        }
    git = repo.git
    head = repo.head()
    info = {
        "git": True, "root": repo.root, "head": head,
        "branch": git.text(["symbolic-ref", "--short", "-q", "HEAD"]),
        "upstream": git.text(["rev-parse", "--abbrev-ref",
                              "--symbolic-full-name", "@{upstream}"])
        if head else None,
        "base": repo.detect_base(), "merge_base": None, "ahead": None,
        "behind": None,
        "staged": len(git.lines_z(["diff", "--cached", "--name-only", "-z"])),
        "unstaged": len(git.lines_z(["diff", "--name-only", "-z"])),
        "untracked": len(git.lines_z(["ls-files", "-z", "--others",
                                      "--exclude-standard", "--", ":/"])),
        "in_progress": in_progress(repo),
        "origin": git.text(["remote", "get-url", "origin"]),
    }
    info["hosting"] = hosting(info["origin"])
    info["origin"] = redact(info["origin"])
    if info["base"] and head:
        base_sha = git.text(["rev-parse", "--verify", "-q",
                             info["base"] + "^{commit}"])
        if base_sha:
            info["merge_base"] = git.text(["merge-base", base_sha, head])
            counts = git.text(["rev-list", "--left-right", "--count",
                               "%s...%s" % (base_sha, head)])
            if counts and len(counts.split()) == 2:
                info["behind"], info["ahead"] = [int(n) for n in counts.split()]

    uncommitted = info["staged"] + info["unstaged"] + info["untracked"]
    base = info["base"]
    recs, ask, messages = [], False, []
    if head and info["ahead"] is None:
        ask = True
        messages.append("ベースのブランチ（統合先）を特定できないため，このブランチ"
                        "のコミットをレビューに含めるべきか判断できません．統合先"
                        "のブランチとレビュー対象をユーザに確認してください．")
        if uncommitted:
            recs.append({"label": "統合先との差分と未コミットの変更（BASE を"
                                  "確認して指定）",
                         "command": "branch <BASE> --with-worktree"})
        recs.append({"label": "統合先との差分（BASE を確認して指定）",
                     "command": "branch <BASE>"})
        if uncommitted:
            recs.append({"label": "未コミットの変更のみ", "command": "worktree"})
        recs.append({"label": "最新のコミット", "command": "commit HEAD"})
    elif head and info["ahead"] and uncommitted:
        ask = True
        messages.append("ブランチのコミットと未コミットの変更の両方があります．"
                        "どれをレビューするか，選択肢を示してユーザに確認して"
                        "ください．")
        recs = [
            {"label": "ブランチのコミットと未コミットの変更の両方",
             "command": "branch %s --with-worktree" % base},
            {"label": "ブランチのコミットのみ", "command": "branch %s" % base},
            {"label": "未コミットの変更のみ", "command": "worktree"},
        ]
    elif uncommitted:
        messages.append("未コミットの変更をレビューします．")
        recs = [{"label": "未コミットの変更（ステージ済み，未ステージ，未追跡）",
                 "command": "worktree"}]
        if info["staged"] and (info["unstaged"] or info["untracked"]):
            recs.append({"label": "ステージ済みの変更のみ（コミット前の確認を"
                                  "依頼された場合）", "command": "staged"})
    elif head and info["ahead"]:
        messages.append("`%s` から分岐した後のコミットをレビューします（統合先が"
                        "`%s` でない場合は BASE を指定してください）．"
                        % (base, base))
        recs = [{"label": "ブランチのコミット（%d 件）" % info["ahead"],
                 "command": "branch %s" % base}]
    else:
        ask = True
        messages.append("レビューできる変更が見つかりません．レビュー対象（コミット"
                        "範囲，PR・MR，ファイルなど）をユーザに確認してください．")
        if head:
            recs.append({"label": "最新のコミット", "command": "commit HEAD"})
        recs.append({"label": "ファイル全体", "command": "files [PATH...]"})
    if info["in_progress"]:
        ask = True
        messages = ["進行中の操作（%s）があります．レビュー対象をユーザに確認"
                    "してください．現在の状態から考えられる候補は次のとおりです．"
                    % "，".join(info["in_progress"])]
    info.update({"ask_user": ask, "message": "".join(messages),
                 "recommendations": recs})
    return info


def cell(text):
    return text.replace("|", "\\|").replace("\n", " ")


def code(text):
    return "`%s`" % shown(text)


def category_summary(items):
    counts = {}
    for item in items:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    return "，".join("%s %d" % (name, counts[name])
                     for name in CATEGORY_ORDER if name in counts) or "なし"


def format_range(start, count):
    end = start + count - 1
    return str(start) if start == end else "%d-%d" % (start, end)


def format_hunks(item, max_ranges):
    hunks = item["hunks"]
    if item["binary"]:
        return "（バイナリ）"
    if item["category"] == "サブモジュール":
        return "（入れ子のリポジトリ）" if item["status"] == "?" else "（参照先の変更）"
    if item["status"] == "U":
        return "（未マージ）"
    if item["added"] is None:
        return "（未検査）"
    if not hunks:
        return "（内容の変更なし）"
    if item["category"] in OVERVIEW_CATEGORIES:
        return "%d 箇所" % len(hunks)
    ranges = []
    for hunk in hunks:
        if hunk["new_lines"] > 0:
            ranges.append(format_range(hunk["new_start"], hunk["new_lines"]))
        else:
            ranges.append("削除（変更前 %s）"
                          % format_range(hunk["old_start"], hunk["old_lines"]))
    if len(ranges) > max_ranges:
        ranges = ranges[:max_ranges] + ["ほか %d 箇所" % (len(ranges) - max_ranges)]
    return ", ".join(ranges)


def render_diff(repo, target, items, pathspecs, commits, max_ranges):
    added = sum(item["added"] or 0 for item in items)
    deleted = sum(item["deleted"] or 0 for item in items)
    lines = ["# レビュー対象一覧", "",
             "- 対象: " + target["title"],
             "- 比較: " + target["compare"],
             "- リポジトリ: " + code(repo.root)]
    if pathspecs:
        lines.append("- 絞り込み: " + "，".join(code(p) for p in pathspecs))
    lines.append("- ファイル数: %d（+%d / −%d）" % (len(items), added, deleted))
    lines.append("- 分類別: " + category_summary(items))
    commit_list, truncated = commits
    if commit_list:
        lines.append("- コミット（%s件）:" % (
            "%d " % len(commit_list) if not truncated
            else "%d 件以上のうち最新の %d " % (len(commit_list) + 1,
                                               len(commit_list))))
        lines.extend("  - `%s` %s" % (sha, shown(subject))
                     for sha, subject in commit_list)
    body = sum((item["added"] or 0) + (item["deleted"] or 0) for item in items
               if item["category"] not in OVERVIEW_CATEGORIES)
    if len(items) > LARGE_CHANGE_FILES or body > LARGE_CHANGE_LINES:
        lines.append("- 注意: 変更が大きいため，精読の進め方（ディレクトリ単位で"
                     "の分割など）をユーザに確認することを検討してください．")
    lines.append("")
    if not items:
        lines.append("対象となる変更はありません．")
        return lines
    lines += ["| # | 状態 | 分類 | 追加/削除 | パス | 変更行（変更後） | 注意 |",
              "|---|---|---|---|---|---|---|"]
    for number, item in enumerate(items, 1):
        status = item["status_label"]
        if item["similarity"] is not None:
            status += "（類似度 %d%%）" % item["similarity"]
        if item["added"] is None:
            counts = "（バイナリ）" if item["binary"] else "-"
        else:
            counts = "+%d / −%d" % (item["added"], item["deleted"] or 0)
        path = code(item["path"])
        if item["old_path"]:
            path = "%s → %s" % (code(item["old_path"]), path)
        lines.append("| %d | %s | %s | %s | %s | %s | %s |" % (
            number, status, item["category"], counts, cell(path),
            format_hunks(item, max_ranges), cell("，".join(item["notes"]))))
    lines += ["", POLICY]
    return lines


def render_files(repo, base, items, paths, skipped):
    total = sum(item["lines"] or 0 for item in items)
    lines = ["# レビュー対象一覧", "",
             "- 対象: ファイル全体（%s）" % (
                 "，".join(code(p) for p in paths) if paths
                 else ("リポジトリ全体" if repo.root else "カレントディレクトリ以下")),
             "- 基準ディレクトリ: %s（%s）" % (
                 code(base), "Git リポジトリ．追跡対象のファイルと，無視されて"
                 "いない未追跡のファイル" if repo.root
                 else "Git リポジトリではありません"),
             "- ファイル数: %d（計 %s 行）" % (len(items), "{:,}".format(total)),
             "- 分類別: " + category_summary(items)]
    if skipped:
        shown_skipped = "，".join(code(p) for p in skipped[:10])
        if len(skipped) > 10:
            shown_skipped += " ほか %d 件" % (len(skipped) - 10)
        lines.append("- %s: %s" % (
            "Git の無視対象として除外（必要ならパスを明示して指定する）"
            if repo.root else "除外したディレクトリ", shown_skipped))
    if len(items) > LARGE_TREE_FILES:
        lines.append("- 注意: ファイル数が多いため，精読の進め方（ディレクトリ単位"
                     "での分割など）をユーザに確認することを検討してください．")
    lines.append("")
    if not items:
        lines.append("対象となるファイルはありません．")
        return lines
    lines += ["| # | 分類 | 行数 | パス | 注意 |", "|---|---|---|---|---|"]
    for number, item in enumerate(items, 1):
        if item["binary"]:
            count = "（バイナリ）"
        elif item["lines"] is None:
            count = "-"
        else:
            count = str(item["lines"])
        lines.append("| %d | %s | %s | %s | %s |" % (
            number, item["category"], count, cell(code(item["path"])),
            cell("，".join(item["notes"]))))
    lines += ["", POLICY]
    return lines


def render_detect(info):
    lines = ["# リポジトリの状態", ""]
    if info["git"]:
        head = info["head"]
        if info["branch"] and head:
            branch = "%s（HEAD `%s`）" % (code(info["branch"]), short(head))
        elif info["branch"]:
            branch = "%s（コミットなし）" % code(info["branch"])
        else:
            branch = "なし（detached HEAD `%s`）" % short(head or "")
        if info["base"] and info["merge_base"]:
            base = "%s（merge-base `%s`，HEAD は %d コミット先行，%d コミット遅れ）" % (
                code(info["base"]), short(info["merge_base"]),
                info["ahead"] or 0, info["behind"] or 0)
        elif info["base"]:
            base = "%s（merge-base なし）" % code(info["base"])
        else:
            base = "検出できません"
        lines += [
            "- リポジトリ: " + code(info["root"]),
            "- 現在のブランチ: " + branch,
            "- アップストリーム: " + (code(info["upstream"])
                                     if info["upstream"] else "なし"),
            "- ベースの候補: " + base,
            "- 未コミットの変更: ステージ済み %d 件，未ステージ %d 件，未追跡 %d 件"
            % (info["staged"], info["unstaged"], info["untracked"]),
            "- 進行中の操作: " + ("，".join(info["in_progress"])
                                 if info["in_progress"] else "なし"),
            "- リモート origin: " + ("%s（%s）" % (code(info["origin"]),
                                                info["hosting"])
                                     if info["origin"] else "なし"),
            "",
        ]
    lines += ["## 推奨", "", info["message"], ""]
    lines += ["%d. %s: `list_review_targets.py %s`" % (n, rec["label"],
                                                       rec["command"])
              for n, rec in enumerate(info["recommendations"], 1)]
    lines += ["", "ユーザへの確認: " + (
        "必要（上の選択肢を示して質問してください）" if info["ask_user"]
        else "不要（1 番目を実行してください）")]
    return lines


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="JSON で出力する")
    common.add_argument(
        "--max-ranges", type=int, default=40, metavar="N",
        help="1 ファイルあたりに表示する変更行の範囲の最大数（既定: %(default)s）")
    parser = argparse.ArgumentParser(
        description="レビュー対象のファイルと変更箇所を一覧にする"
                    "（リポジトリは変更しない）．",
        epilog="差分を扱うサブコマンドでは，`--` の後にパスを並べて対象を"
               "絞り込める．")
    sub = parser.add_subparsers(dest="command", metavar="サブコマンド")
    sub.required = True
    sub.add_parser("detect", parents=[common],
                   help="リポジトリの状態を調べ，レビュー対象の候補を示す")
    sub.add_parser("worktree", parents=[common],
                   help="未コミットの変更（ステージ済み，未ステージ，未追跡）")
    sub.add_parser("staged", parents=[common], help="ステージ済みの変更")
    branch = sub.add_parser("branch", parents=[common],
                            help="BASE との merge-base から HEAD までの変更")
    branch.add_argument("base", nargs="?", metavar="BASE",
                        help="ベースのブランチ（省略時は自動で検出する）")
    branch.add_argument("--with-worktree", action="store_true",
                        help="未コミットの変更（未追跡のファイルを含む）も含める")
    ranged = sub.add_parser("range", parents=[common],
                            help="コミット範囲（A..B または A...B）の変更")
    ranged.add_argument("spec", metavar="A..B")
    commit = sub.add_parser("commit", parents=[common],
                            help="一つのコミットの変更")
    commit.add_argument("rev", metavar="REV")
    files = sub.add_parser("files", parents=[common],
                           help="ファイル全体（Git リポジトリの外でも使える）")
    files.add_argument("paths", nargs="*", metavar="PATH")
    return parser


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    argv = list(sys.argv[1:] if argv is None else argv)
    pathspecs = []
    if "--" in argv:
        index = argv.index("--")
        argv, pathspecs = argv[:index], argv[index + 1:]
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.max_ranges < 1:
        parser.error("--max-ranges には 1 以上を指定してください")
    try:
        repo = Repo(os.getcwd())
        if args.command == "detect":
            result = detect(repo)
            lines = render_detect(result)
        elif args.command == "files":
            paths = args.paths + pathspecs
            base, items, skipped = collect_files(repo, paths)
            result = {"mode": "files", "base": base, "paths": paths,
                      "excluded": skipped, "files": items}
            lines = render_files(repo, base, items, paths, skipped)
        else:
            repo.require()
            if args.command == "worktree":
                target = target_worktree(repo)
            elif args.command == "staged":
                target = target_staged(repo)
            elif args.command == "branch":
                target = target_branch(repo, args.base, args.with_worktree)
            elif args.command == "range":
                target = target_range(repo, args.spec)
            else:
                target = target_commit(repo, args.rev)
            items = collect_diff(repo, target, pathspecs)
            if "log" in target:
                commits = repo.commits(*target["log"])
            else:
                commits = (target.get("commit_list", []), False)
            result = {"mode": target["mode"], "title": target["title"],
                      "compare": target["compare"], "root": repo.root,
                      "pathspecs": pathspecs,
                      "commits": [{"sha": sha, "subject": subject}
                                  for sha, subject in commits[0]],
                      "commits_truncated": commits[1], "files": items}
            lines = render_diff(repo, target, items, pathspecs, commits,
                                args.max_ranges)
    except GitError as exc:
        sys.stderr.write("エラー: %s\n" % exc)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
