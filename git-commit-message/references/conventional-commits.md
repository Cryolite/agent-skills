# Conventional Commits Reference

A condensed, paraphrased working reference for
[Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).
Where this summary and the official specification differ, the specification
prevails.

## Contents

- [Rules](#rules)
- [Choosing the Type](#choosing-the-type)
- [Choosing the Scope](#choosing-the-scope)
- [Breaking Changes](#breaking-changes)
- [Footers](#footers)
- [Special Cases](#special-cases)

## Rules

```text
<type>[optional scope][optional !]: <description>

[optional body]

[optional footer(s)]
```

1. The header consists of a type (a noun such as `feat` or `fix`), an
   optional scope in parentheses, an optional `!`, a colon and a space, and
   the description: `feat(parser)!: ...`.
2. `feat` must be used for a commit that adds a feature, and `fix` must be
   used for a commit that fixes a bug. Other types are allowed.
3. A scope is a noun describing a section of the codebase, in parentheses:
   `fix(parser):`.
4. The description immediately follows `: ` and briefly summarizes the
   change.
5. The optional body begins one blank line after the header. It is
   free-form and may consist of several paragraphs.
6. Optional footers begin one blank line after the body. A footer is a
   token, then `: ` or ` #`, then a value, as in git trailers:
   `Reviewed-by: Z`, `Refs: #123`, `Closes #123`.
7. Footer tokens use `-` instead of spaces (`Acked-by`). The only exception
   is `BREAKING CHANGE`.
8. A footer value may contain spaces and newlines; it ends where the next
   `token: ` or `token #` begins.
9. A breaking change is marked with `!` immediately before the `:` of the
   header, with a `BREAKING CHANGE: <description>` footer, or with both. When
   only `!` is used, the description must describe the breaking change.
10. `BREAKING CHANGE` must be uppercase, and `BREAKING-CHANGE` is a synonym.
    Tools treat everything else case-insensitively, but use one casing
    consistently; lowercase types are the norm.

Versioning: `fix` corresponds to a PATCH release, `feat` to a MINOR release,
and a breaking change of any type to a MAJOR release. Other types do not
affect the version unless they are breaking.

## Choosing the Type

Go through these questions in order and take the first match.

1. Does it revert an earlier commit? Use `revert` (see [Reverts](#reverts)).
2. Is the change confined to a supporting area? Use that area's type even if
   the change "fixes" or "adds" something there:
   - documentation only (README, docs, code comments, docstrings): `docs`
   - tests only (test code, fixtures, fixes for flaky tests): `test`
   - CI configuration only (e.g., `.github/workflows/`): `ci`
   - build scripts, packaging, or dependency manifests only: `build`
3. Does it change what users of the software (or configuration) experience?
   - It corrects wrong behavior: `fix`.
   - It adds a capability, such as a command, option, setting, or API:
     `feat`.
   - It removes a capability or changes it incompatibly: the type that
     matches the intent (often `feat`, as in the specification's example
     `feat!: drop support for Node 6`), marked as breaking.
4. Does it keep the observable behavior the same?
   - It makes things faster or lighter: `perf`.
   - It restructures code: `refactor`.
   - It changes formatting only: `style`.
5. Anything else (repository housekeeping, `.gitignore`, editor or linter
   settings, release bookkeeping): `chore`.

Notes:

- A bug fix that needs some refactoring is still `fix`, and a feature that
  comes with documentation and tests is still `feat`.
- If two types apply equally because the commit mixes unrelated changes,
  recommend splitting it.
- `style` means code formatting, not CSS or visual design; a visible change
  to a user interface is `feat` or `fix`.
- In configuration-only repositories (dotfiles, infrastructure as code),
  treat the configuration as the product: a new alias, key binding, or
  setting is `feat`, correcting broken behavior is `fix`, and reorganizing
  without changing the effect is `refactor`.
- Dependency updates: `build(deps): bump foo from 1.2.0 to 1.3.0`, or
  `chore(deps): ...` if that is the repository's practice. When an update is
  made specifically to fix a user-visible bug, `fix(deps): ...` is also
  common.
- Removing dead code is `refactor`; deleting obsolete non-code files is
  `chore`.
- Release bookkeeping (version bumps, changelog updates):
  `chore(release): 1.4.0`, or the repository's own convention.

## Choosing the Scope

- The scope is optional. Add one when it makes the header clearer.
- Use a noun that names a component, module, package, command, or subsystem:
  `api`, `parser`, `cli`, `auth`, `deps`.
- Reuse the scopes already in the history, spelled the same way. To list
  them:

  ```sh
  git log -n 300 --format=%s | sed -nE 's/^[A-Za-z]+\(([^)]+)\)!?: .*/\1/p' | sort | uniq -c | sort -rn
  ```

- Write it in lowercase, with hyphens between words (`user-settings`).
- Omit the scope when the change spans many areas instead of inventing a
  vague one (`misc`, `general`, `all`).
- Do not use file paths or file extensions (`fix(src/utils/date.ts):`).
- Use a single scope unless the repository allows several (e.g.,
  `feat(api,cli):`).

## Breaking Changes

Typical breaking changes:

- Removing or renaming public functions, classes, endpoints, fields,
  commands, options, configuration keys, or environment variables.
- Changing signatures, return values, error behavior, defaults, output
  formats, file locations, or protocols that others rely on.
- Dropping support for a platform, runtime, or dependency version.
- Requiring a data, schema, or configuration migration.

Usually not breaking: additions, internal refactoring, changes to private or
internal interfaces, and fixes that make the code behave as documented. Ask
the user when unsure, especially when it is unclear whether the affected
behavior is public.

How to mark a breaking change:

- Put `!` immediately before the colon: `feat(api)!: ...`.
- Add a `BREAKING CHANGE:` footer that says what breaks and what users must
  do. Keep it on one line when possible:

  ```text
  feat(config)!: read settings from config.toml instead of config.json

  TOML allows comments, which users have requested repeatedly.

  BREAKING CHANGE: config.json is ignored; convert it to config.toml.
  ```

## Footers

- Footers form the last paragraph of the message: one blank line after the
  body, with no blank lines between footers. A footer separated from the
  others by a blank line is read as part of the body.
- Format: `Token: value` or `Token #value`. Common tokens are `Refs`,
  `Closes` and `Fixes` (GitHub and GitLab close the referenced issue when the
  commit reaches the default branch), `Reviewed-by`, `Acked-by`,
  `Co-authored-by`, `Signed-off-by`, and `BREAKING CHANGE`.
- Examples: `Refs: #123`, `Refs: #123, #456`, `Closes #123`,
  `Refs: !123`, `Closes: !123`, `Co-authored-by: Jane Doe <jane@example.com>`.
- For GitLab merge requests (`!123`), always use `: ` as the separator (e.g.,
  `Refs: !123`, `Closes: !123`), because Conventional Commits requires either
  `:<space>` or `<space>#`; `<space>!` is not a standard footer separator.
- Include issue references, people, and sign-offs only when the user
  provided them or they are explicit in the context, such as an issue number
  stated in the conversation. Never guess them. `Signed-off-by` is normally
  added by the user with `git commit -s`.
- Keep each footer on one line when practical. A long `BREAKING CHANGE:`
  value may continue on the following lines.

## Special Cases

### Reverts

Use the `revert` type, repeat the description of the reverted commit, and
reference the reverted commit(s):

```text
revert: add ability to parse arrays

This reverts commit 676104e because array parsing broke the handling of
quoted strings.

Refs: 676104e
```

During `git revert --no-commit`, git writes the reverted commit's ID to
`REVERT_HEAD` and prepares a message in `MERGE_MSG` that consists of
`Revert "<header>"` and `This reverts commit <sha>.`. Convert it into the
form above, keeping the full commit ID if the user prefers it. Ask the user
for the reason for the revert if it is not known.

### Merges

Conventional Commits targets ordinary commits, and tools such as commitlint
ignore merge commits by default. If a merge is in progress, keep the message
that git prepared in `MERGE_MSG` (e.g., `Merge branch 'topic'`) unless the
user asks for something else. You may suggest a short body that explains how
conflicts were resolved.

### Squash Merges

`git merge --squash` prepares a `SQUASH_MSG` that lists the squashed
commits. Write a single Conventional Commits message that summarizes the
combined change; the list of original commits may be kept in the body if the
user wants it.

### Cherry-Picks

`git cherry-pick --no-commit` prepares the original message in `MERGE_MSG`
(`CHERRY_PICK_HEAD` exists only while a conflict is being resolved). Reuse
the original message, and adjust it only if the picked change was modified.

### Autosquash Commits

Messages that start with `fixup!`, `squash!`, or `amend!` are meant to be
folded into another commit by `git rebase --autosquash`. Leave them in the
form that git generates (`git commit --fixup=<commit>`).

### Initial Commits

For the first commit of a repository, `chore: initial commit` is common. If
the commit already contains substantial functionality, a `feat:` header that
describes it is more informative.

### Submodules, Lock Files, Generated and Binary Files

- Submodule updates: run `git diff --cached --submodule=log` to see the
  included commits, then write a header such as
  `build(deps): update libfoo submodule to v2.1.0`.
- Lock files and generated files belong to the change that produced them
  (e.g., `package-lock.json` in a dependency update). Do not describe their
  contents line by line.
- Binary files: describe them by name and purpose, since their contents
  cannot be inspected in the diff.
