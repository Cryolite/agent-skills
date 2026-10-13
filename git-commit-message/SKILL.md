---
name: git-commit-message
description: 'Draft or polish an English commit message for the currently staged changes (git diff --cached) following the Conventional Commits 1.0.0 specification. Use when asked to write, suggest, review, proofread, or improve a commit message, to check whether a message conforms to Conventional Commits (feat, fix, BREAKING CHANGE, ...), or to turn rough or non-English notes into an English commit message (e.g., 「コミットメッセージを考えて」「コミットメッセージを推敲して」, or mentions of issue/PR/MR numbers like #123, !456). Only proposes the message; never runs git commit.'
---

# Git Commit Message

Draft a commit message for the **staged** changes, or polish a draft supplied
by the user, so that it follows
[Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)
and reads as clear, natural English.

## Ground Rules

- **Propose only.** Never run `git commit` or anything else that changes the
  index, working tree, refs, or history (`git add`, `git restore`,
  `git reset`, `git stash`, `git commit --amend`, ...). Use read-only commands
  only. The user commits the message themselves.
- **Staged changes only.** The message describes `git diff --cached`. Do not
  describe unstaged or untracked changes; mention them only when they look
  like they belong to this commit (for example, a staged call to a function
  that is defined only in an unstaged file).
- **English message, user's language for discussion.** The commit message is
  always in English. Write explanations, rationale, and questions in the
  language the user writes in.
- **No fabrication.** Base every statement on the staged diff, the user's
  input, retrieved issue/PR/discussion/MR context, or other explicit context.
  Never invent motivations, issue or PR numbers, URLs, measurements, or people
  (`Reviewed-by`, `Co-authored-by`, ...). If the reason for a change matters
  and cannot be determined, ask, or write a neutral body and point out the gap.
- **Repository conventions first.** Follow the repository's commit rules
  (commitlint or commitizen configuration, `CONTRIBUTING.md`, commit template)
  and the style of its history wherever they are compatible with Conventional
  Commits. If an explicit rule conflicts with Conventional Commits, tell the
  user and ask which one to follow.

## Procedure

### 1. Inspect the Staged Changes and Conventions

Run these read-only commands, with paging disabled (`git --no-pager` or
`GIT_PAGER=cat`):

```sh
git status --short --branch
git diff --cached --stat --summary
git diff --cached
git diff --cached --check
git log -n 30 --format='%s'
git log -n 5 --format='%B%n----'
git ls-files | grep -Ei '(^|/)(\.?commitlint|\.czrc|\.cz\.|contributing|\.gitmessage|\.husky/commit-msg|\.pre-commit-config|lefthook)'
git config --get commit.template
cat "$(git rev-parse --git-path MERGE_MSG)" "$(git rev-parse --git-path SQUASH_MSG)" 2>/dev/null
git remote get-url origin 2>/dev/null
```

The commands for `commit.template`, merge/squash messages, and `origin` exit
with a non-zero status when there is nothing configured or found; that is
expected.

- If nothing is staged, stop and say so; do not stage anything. If the user
  only wants their draft polished, polish it, but state that it could not be
  checked against a diff.
- Inspect `origin` remote: `git remote get-url origin 2>/dev/null` identifies
  the hosting platform and repository path:
  - **GitHub**: Host is `github.com` or custom GitHub Enterprise domain (e.g.,
    `git@github.com:owner/repo.git` or `https://github.com/owner/repo.git`).
    Target is `owner/repo`.
  - **GitLab**: Host is `gitlab.com` or self-hosted GitLab domain (e.g.,
    `git@gitlab.com:group/project.git` or `https://gitlab.com/group/project.git`).
    Target is `group/project`.
  - **Neither**: The repository is local or hosted on another service.
- For a large diff, start from the `--stat` output and read files one at a
  time with `git diff --cached -- <path>`. Skim lock files, generated or
  vendored files, and binaries instead of reading them in full.
- `git diff --cached -w --stat` reveals whitespace-only changes, and
  `git diff --cached --submodule=log` summarizes submodule updates.
- From the history, note whether Conventional Commits is already in use,
  which types and scopes appear, and style details: capitalization of the
  description, backticks around identifiers, one or two spaces after a
  sentence-ending period, wrap width, and footers. Skip this if the
  repository has no commits yet.
- If the merge/squash check prints anything, git has already prepared a
  message for an in-progress merge, revert, cherry-pick, or squash; see
  [Special Cases](./references/conventional-commits.md#special-cases).

### 2. Identify and Fetch Referenced Issues, PRs, and MRs

When the user's prompt or notes mention numbers prefixed with `#` or `!`,
determine if they reference remote tracker items:

#### Recognition Rules

1. **`#` prefix (`#1`, `#2`, ...)**:
   - **GitHub origin**: Recognize `#<number>` as a GitHub **issue**,
     **pull request**, or **discussion**.
   - **GitLab origin**: Recognize `#<number>` as a GitLab **issue**.
   - **Neither (or no origin)**: Do not assume `#<number>` is a GitHub or
     GitLab tracker item; treat it as plain text.
2. **`!` prefix (`!1`, `!2`, ...)**:
   - **GitLab origin**: Recognize `!<number>` as a GitLab **merge request**.
   - **Not GitLab (including GitHub or no origin)**: Do not treat `!<number>`
     as a merge request.

#### Retrieving Information

When an item is recognized, retrieve its details (title, description/body,
and comments/discussions) using available MCP tools (or CLI / API fallbacks)
before composing the commit message:

- **GitHub items (`#<number>`)**:
  - **Issue / Pull Request**: Use GitHub MCP server tools (e.g.,
    `github-mcp-server-issue_read` with `method: "get"` and `method: "get_comments"`,
    or `github-mcp-server-pull_request_read` with `method: "get"`,
    `method: "get_comments"`, and `method: "get_review_comments"`).
    *Note*: On GitHub, issues and PRs share the same number namespace. If it
    is not specified whether `#<number>` is an issue or a PR, check as an
    issue first; if it indicates a pull request or is not found, check as a
    pull request.
  - **Discussion**: If specified or identified as a discussion, fetch
    discussion title, body, and comments via GitHub MCP / GraphQL or GitHub
    CLI (`gh api repos/{owner}/{repo}/discussions/{number}`).
  - **Fallback**: If MCP tools are unavailable, use GitHub CLI (`gh issue view <number> --comments`,
    `gh pr view <number> --comments`) or GitHub REST API (`curl`).
- **GitLab items (`#<number>` for issues, `!<number>` for merge requests)**:
  - **Issue (`#<number>`)**: Use GitLab MCP server tools if available.
    Fallback: GitLab CLI (`glab issue view <number> --comments`) or GitLab
    REST API (`GET /api/v4/projects/<id_or_path>/issues/<number>` and `/notes`).
  - **Merge Request (`!<number>`)**: Use GitLab MCP server tools if available.
    Fallback: GitLab CLI (`glab mr view <number> --comments`) or GitLab
    REST API (`GET /api/v4/projects/<id_or_path>/merge_requests/<number>` and `/notes`).

#### Utilizing Retrieved Information

Use the retrieved title, description, and comments as authoritative reference
context:

- **Why it changed**: Extract the underlying problem, bug report, or feature
  request to explain the motivation clearly in the commit body rather than
  guessing.
- **Decisions and nuances**: Inspect comments and review discussions to learn
  what decisions were agreed upon, edge cases to handle, and user expectations.
- **Verification against diff**: Verify that the staged changes
  (`git diff --cached`) actually address the discussed requirements. Flag any
  discrepancy or partial fix.
- **Terminology**: Align terminology and naming in the commit message with the
  issue, PR, or MR.
- **Footers**: Link the referenced item in the footers (e.g., `Closes: #123`,
  `Fixes: #123`, `Refs: #123`, `Refs: !123`).

### 3. Understand the Change

Work out the following before writing anything:

- **What** changed, in terms of behavior or purpose, not as a line-by-line
  replay of the diff.
- **Why** it changed: the problem, motivation, or requirement. Use the
  user's notes, retrieved issue/PR/discussion/MR context, and the code
  comments, tests, and documentation in the diff; do not guess.
- **Impact**: who or what is affected, and whether anything breaks for users
  or dependents.
- **Cohesion**: whether the staged changes form one logical change. If they
  mix unrelated concerns (e.g., a bug fix and an unrelated refactoring),
  recommend splitting them: list which files or hunks belong together and
  give a message for each. If the user still wants a single commit, use the
  type of the most significant change and mention the rest in the body.
- **Anomalies** to flag before the user commits: debug output, commented-out
  code, conflict markers, credentials or other secrets, unexpectedly large or
  binary files, and edits that seem unrelated to the purpose of the change
  (such as deleted lines that look accidental).

### 4. Compose the Message

If the user supplied a draft or notes, start from them: keep the intended
meaning and any facts that the diff cannot show (motivation, issue numbers),
verify everything else against the staged diff, and rewrite non-English text
as natural English rather than translating it word for word.

```text
<type>[(<scope>)][!]: <description>

[body]

[footer(s)]
```

**Type**: choose it by the main intent of the change.

| Type | Use when the commit ... |
|------|-------------------------|
| `feat` | adds a feature or capability (SemVer MINOR) |
| `fix` | fixes a bug, i.e., wrong behavior (SemVer PATCH) |
| `docs` | changes documentation only |
| `style` | changes code formatting only, without changing meaning |
| `refactor` | restructures code without changing behavior |
| `perf` | improves performance |
| `test` | adds or corrects tests only |
| `build` | changes the build system, packaging, or dependencies |
| `ci` | changes CI configuration or scripts |
| `chore` | does other maintenance that touches neither product code nor tests (e.g., `.gitignore`, tool settings) |
| `revert` | reverts an earlier commit |

`feat` and `fix` are mandatory for features and bug fixes. Use the
repository's own list of types if it defines one. For borderline cases
(typo fixes in docs, dependency updates, removals, configuration-only
repositories, ...), read the
[type decision guide](./references/conventional-commits.md#choosing-the-type).

**Scope** (optional): a short lowercase noun in parentheses that names the
affected area, such as a module, package, component, or command:
`fix(parser):`. Reuse scopes from the history when they exist. Omit the
scope when the change is cross-cutting or no meaningful name exists. Do not
use file paths or file extensions.

**Breaking change**: if users or dependents must change something (a
removed or renamed API, command, option, configuration key, or environment
variable; a changed default or output format; dropped platform support; a
required migration), put `!` right before the colon and add a
`BREAKING CHANGE:` footer that states what breaks and how to migrate. Do not
mark a change as breaking without evidence; ask when unsure.

**Description**: the summary after `: `.

- Use the imperative mood: `add`, `fix`, `remove`, not `added`, `adds`, or
  `adding`.
- Start with a lowercase letter unless the description begins with a proper
  noun or an identifier, or the repository's existing Conventional Commits
  messages consistently capitalize it.
- Do not end it with a period.
- Say specifically what the change achieves:
  `fix(auth): reject expired refresh tokens`, not `fix: fix bug`. Avoid vague
  verbs on their own (`update`, `change`, `modify`, `improve`, `tweak`), and
  do not repeat the type (`fix: fix ...`).
- Keep the whole header within 72 characters (shorter is better) unless the
  repository sets another limit.

**Body**: recommended unless the header alone says everything (typo fixes,
trivial renames, routine version bumps).

- Separate it from the header with one blank line.
- Explain why the change is needed and what it does at a higher level than
  the diff: the problem or previous behavior, the approach taken, and notable
  consequences, limitations, or alternatives. Do not list the changed files
  or narrate the diff.
- Describe the problem in the present tense and the change in the imperative
  mood ("Return an error instead of ..."), or match the voice used in the
  history (e.g., "This commit ...").
- Wrap lines at 72 columns; URLs, code, and long identifiers may exceed this.
  Separate paragraphs with blank lines; simple `-` bullet lists are fine.
  Write plain text: no Markdown headings, bold text, or tables.
- Do not start a line with `#`: git drops such lines as comments when the
  message is edited in an editor.

**Footers** (optional): after one blank line following the body, as a single
block with no blank lines between footers.

- Use `Token: value` or `Token #value`. Tokens use `-` instead of spaces
  (`Reviewed-by`, `Refs`), except `BREAKING CHANGE`, which must be uppercase
  (`BREAKING-CHANGE` is a synonym).
- Add issue references such as `Refs: #123`, `Closes: #123`, or `Closes #123`,
  or merge request references such as `Refs: !123` or `Closes: !123`, only
  when the user provided them, they are explicit in the context, or they were
  resolved from referenced items.
- For GitLab merge requests (`!123`), write `Refs: !123` or `Closes: !123`
  (always use `: ` as the separator, as Conventional Commits requires `: `
  before `!`).

### 5. Polish and Verify

Critique the draft and revise it until all of the following hold:

1. **Accuracy**: every statement is backed by the staged diff, the user's
   input, or retrieved issue/PR/MR context, nothing significant in the staged
   diff is missing, and nothing from unstaged changes is included.
2. **Classification**: the type, scope, and breaking-change markers follow
   the rules above.
3. **English**: grammatical, idiomatic, and concise, with correct articles
   and plurals, consistent tense, natural wording rather than literal
   translation, identifiers spelled exactly as in the code, and ASCII
   punctuation only. Read the
   [English style guide](./references/english-style.md) when polishing a
   user's draft or non-native phrasing.
4. **Format**: run the bundled checker on the final text. Fix every error,
   and either fix each warning or knowingly accept it (e.g., an unbreakable
   URL):

   ```sh
   python3 ~/.agents/skills/git-commit-message/scripts/check_commit_message.py <<'COMMIT_MSG'
   feat(cli): add --dry-run option

   Allow users to preview the files that would be deleted.
   COMMIT_MSG
   ```

   Since this skill is intended to reside under `~/.agents/skills/git-commit-message`,
   run the checker with
   `python3 ~/.agents/skills/git-commit-message/scripts/check_commit_message.py`
   (or `<skill-dir>/scripts/check_commit_message.py` if installed in a
   different directory). Quote the here-document delimiter (`'COMMIT_MSG'`) so
   that backticks and `$` in the message are not expanded. In shells without
   here-documents, write the message to a temporary file and pass its path
   instead. Pass `--types`, `--max-header-length`, or `--max-line-length` when
   the repository uses other types or limits (see `--help`). Check the summary
   line to confirm that the type, scope, breaking flag, and footers were
   parsed as intended. If Python 3 is unavailable, check the format by hand.

### 6. Present the Result

1. The final message in one `text` code block, exactly as it should be
   committed: no surrounding quotes, extra indentation, or commentary inside
   the block.
2. A brief rationale in the user's language: why this type and scope,
   whether the change is breaking, and any assumptions made.
3. Open questions and warnings: unknown motivation, suspicious staged edits,
   or a recommendation to split the commit.
4. When polishing a user's draft: the main corrections (accuracy,
   Conventional Commits, English), briefly.
5. Optionally, one or two alternative headers when the type or scope is
   genuinely debatable.

Do not commit. When the user gives feedback, revise the message, re-run the
checks, and present the full message again.

## Examples

A bug fix whose issue number was given by the user:

```text
fix(parser): handle consecutive spaces inside quoted strings

Arguments are split on single spaces, which produces empty tokens when a
quoted string contains consecutive spaces, so valid input is rejected.

Split on runs of whitespace outside quotes and keep the contents of
quoted strings verbatim.

Closes #142
```

A breaking change:

```text
feat(cli)!: rename --out option to --output

Use the same option name as the other subcommands.

BREAKING CHANGE: --out has been removed; use --output instead.
```

A change that needs no body:

```text
docs: correct installation command for macOS
```

A change referencing a GitLab merge request:

```text
feat(api): export project archives asynchronously

Allow clients to trigger background export of project repositories.
Details and parameter naming follow discussion in merge request !58.

Refs: !58
```

| Avoid | Prefer |
|-------|--------|
| `Fixed bug.` | `fix(auth): reject expired refresh tokens` |
| `feat: Added a dry run option.` | `feat(cli): add --dry-run option` |
| `fix: correct typo in README` | `docs: correct typo in README` |
| `chore: update deps` | `build(deps): bump requests from 2.31.0 to 2.32.3` |
| `refactor: modify some codes` | `refactor(parser): extract tokenizer into its own module` |

## Resources

- [Conventional Commits reference](./references/conventional-commits.md):
  condensed rules, the type decision guide, scopes, breaking changes,
  footers, and special cases (reverts, merges, initial commits, ...).
- [English style guide](./references/english-style.md): wording, grammar,
  and common non-native mistakes, with before-and-after examples.
- [Format checker](./scripts/check_commit_message.py): validates the header,
  blank lines, footers, and line lengths.
