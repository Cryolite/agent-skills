---
name: write-tests
description: 'Write, run, and verify automated tests for a program through its public API: unit, integration, and end-to-end tests for new or changed behavior; missing normal, boundary, and error cases; regression tests for bug fixes, proven to fail on the pre-fix code and pass after the fix; test-first specifications; characterization tests before refactoring; and, on request, rewrites of flaky or implementation-coupled tests. Covers all major languages (Python, JavaScript/TypeScript, Java/Kotlin, C#, C/C++, Go, Rust, Ruby, PHP, Swift, shell). Use it whenever the user asks to write, add, extend, or improve tests, even casually (「テストを書いて」「回帰テストを追加して」「異常系のテストを足して」, "add unit tests", "write a regression test for this fix"), and when another skill needs regression tests for a fix. Not for only running tests, investigating failures, or reviewing test code. Changes test code only; production code, commits, and pushes need an explicit request.'
---

# Write Tests

Write automated tests for a program, run them, and report what they prove.
Every step below serves five properties:

1. **Public API.** Tests drive the code the way its consumers do and check
   only what those consumers can observe, so they survive refactoring and
   verify behavior someone relies on.
2. **Proven regression tests.** A regression test fails on the pre-fix code
   because of the defect and passes on the fixed code. Without both
   observations there is no evidence that it would catch the bug again.
3. **Independence.** Every test case gives the same result alone, in any
   order, repeated, and in parallel, so a failure points at a defect rather
   than at test ordering.
4. **Normal and error cases.** Tests cover boundaries and failure modes, not
   just the happy path, because that is where defects concentrate.
5. **Right weight.** Each test is the lightest one that still reaches the
   code path it is meant to check: heavy enough to detect the defect, light
   enough for the project's normal test loop.

## Ground Rules

- **Never touch implementation details for the sake of a test.** Do not
  import, call, read, write, or patch what only the unit itself uses, even
  when the language makes it reachable (underscore names, `friend`,
  reflection, same-package access, monkeypatching the unit's own
  functions). Do not change production code to make it testable (wider
  visibility, test-only parameters, flags, branches, hooks, or accessors).
  Such tests break on every refactoring and certify behavior no consumer
  sees. If the public API cannot reach a behavior, test it from a higher
  public entry point, or report the gap and propose a design change; do not
  bend this rule even when asked. Details:
  [Public API](references/public-api.md).
- **Expected values come from the contract**, never from running the code
  under test or copying its formula; otherwise a wrong implementation
  confirms itself.
- **Report only what you observed.** A skipped, deselected, uncollected, or
  unexecuted test has not passed. Say what could not be run and why.
- **Never weaken tests to get a pass.** Do not delete or loosen assertions,
  add skips or expected-failure marks, or widen tolerances to hide a
  failure. When the production code looks wrong, report it (see
  [When the Code or the Specification Looks Wrong](#when-the-code-or-the-specification-looks-wrong)).
- **Change test code only**: tests, test helpers and data, and the test
  registration they need. Production code, CI configuration, and
  dependencies change only on the user's explicit request, and even then
  the first rule holds. Keep the user's uncommitted work intact.
- **Follow the project.** Use its framework, layout, naming, fixtures,
  markers, commands, and execution environment. Add a framework, plugin, or
  dependency only with the user's consent.
- **Use the user's language.** Write reports, questions, and explanations in
  the language the user writes in. Names and comments in test code follow
  the project's conventions.

## Scope

| Purpose | Typical request |
|---|---|
| New or changed behavior | "Write tests for this function", "test my change" |
| Missing coverage | "The error cases are untested", "cover this module" |
| Regression test for a bug fix | "Add a regression test for this bug / issue #12" |
| Test-first specification | "Write the tests before I implement it" |
| Characterization before refactoring | "Pin down the current behavior first" |
| Improving existing tests (explicit request only) | "Fix this flaky test", "stop these tests poking at internals" |

Out of scope unless the user explicitly asks: fixing or refactoring
production code, benchmarks, load tests, fuzzing infrastructure, new test
infrastructure or CI configuration, commits, pushes, and posting to pull
requests or issues. Requests that only run tests, investigate failures, or
review tests do not need this skill. Requests to create, edit, explain, or
evaluate this skill do not start the workflow.

### When Another Skill Invokes This One

A parent workflow, such as an issue-repair skill, may apply this skill to
create the regression tests for its fix.

- The parent supplies the target, the defect and its triggering condition,
  where the fix is (or that it is not written yet), the work location, and
  its constraints. Ask only for what it could not supply.
- This skill owns test design, test code, and the pre-fix and post-fix
  evidence. The parent owns the fix, staging, commits, pushes, and pull
  requests. The restrictions here on production code and Git apply to this
  stage; they neither revoke the parent's authorized steps nor extend this
  skill beyond the parent's scope.
- Work in the work location the parent chose.
- Return the result as a
  [handoff record](references/report-format.md#handoff-to-a-parent-workflow).
  The parent's language rules govern anything it publishes.

## Procedure

### 1. Pin Down the Request

Determine the **target** (files, modules, functions or classes, a diff, a
commit, an issue), the **purpose** (a row of [Scope](#scope)), and, for a
regression test, **where the fix is**: uncommitted changes, a commit, a
branch or pull request, or not written yet. The last one decides what
"before the fix" means.

Infer what is not stated from context (`git status`, recent commits, the
linked issue); ask only when the inference would change the work. For a
broad request such as "test the whole repository", propose a risk-ranked
plan and agree on the scope before writing many tests.

### 2. Learn the Contract and the Project

- **Contract**: documentation, docstrings, type annotations, README, the
  issue or pull request discussion, how callers use the target, and
  existing tests. Read the implementation to understand the contract and
  locate the public surface, not to derive expected values.
- **Public surface**: decide the unit, its consumers, and its public API as
  described in [Public API](references/public-api.md). Record the evidence
  when it is not obvious; ask when the choice changes what you would test.
- **Project conventions**: `README`, `CONTRIBUTING`, `AGENTS.md`,
  `CLAUDE.md`, test documentation, build and test configuration, CI
  definitions, and neighboring tests. Find the test command, how tests are
  registered and selected, the markers or labels for heavy tests, and the
  intended execution environment (virtual environment, devcontainer, CI
  image).
- **Language**: read the reference for each language involved (see
  [Languages](#languages)) for its public-API rules, seams, isolation
  idioms, and pitfalls.

### 3. Plan the Cases, Oracles, and Weight

For each behavior, before writing code:

- **Cases**: derive normal, boundary, and error cases from the contract
  with equivalence partitioning, boundary-value analysis, state
  transitions, and condition combinations. Error cases include invalid
  input, precondition violations, dependency failures, resource limits, and
  concurrency, as far as the contract defines them. Rank by risk and drop
  cases that repeat an equivalence class.
- **Oracle**: the independent source of each expected value
  (specification, hand calculation, published examples, inverse operations,
  invariants, a reference implementation).
- **Weight**: what the test must detect, where that code path lives, and
  the lightest level that keeps that path real. See
  [Test weight](references/test-weight.md).

[Test design](references/test-design.md) details the techniques. Show the
plan to the user when it is large or a judgment call could go either way.
When the contract leaves a behavior undefined (error handling often is), do
not freeze today's behavior as the expectation: ask, or state the
assumption.

### 4. Write the Tests

- Place, name, and structure tests the way the project does: one behavior
  per test case, a name that states the condition and the expected result,
  a visible arrange/act/assert flow, and parametrization instead of loops
  or conditionals that compute expectations.
- Assert precisely: exact values when deterministic; for failures, the
  specific error type, the promised code or exit status, the promised
  message content, and the state afterwards (no partial writes, resources
  released, object still usable). Never accept an exception without naming
  its type, and do not assert details the contract leaves open (set order,
  wording outside the contract).
- Replace dependencies only through public seams: constructor or function
  parameters, configuration, documented environment variables, plugin or
  callback interfaces, or environment-level boundaries such as temporary
  directories, a local test server, or process-wide clock control. Prefer
  real collaborators when they are fast and deterministic.
- Isolate every test case: its own state and temporary directory, ports
  allocated dynamically, global state restored even on failure
  (environment variables, working directory, module-level caches,
  singletons, random state, logging and signal handlers, locale and time
  zone, import paths, registries), and processes, threads, and files
  cleaned up. Share expensive fixtures only when they are read-only.
- Keep results deterministic: control time and randomness through seams or
  fixed seeds; do not depend on unspecified ordering, external services, or
  machine-specific state; wait for conditions with a deadline instead of
  fixed sleeps; time-limit anything that could hang.
- Keep inputs, models, iterations, and processes minimal. Mark heavy tests
  the project's way, and make tests that need a GPU, a specific OS, or an
  optional dependency skip with a reason where it is missing.
- Explain non-obvious expected values in a comment. In a regression test,
  reference the bug (issue number or summary) and its triggering condition.
- Register new tests where the project requires it so that its standard
  command and CI run them, and pass the formatter, linter, and type checker
  the project applies to tests (format only the files you touched).

### 5. Run and Verify

Run tests in the project's intended environment and read the output, not
just the exit status.

1. **New tests**: confirm they were collected, executed, and passed.
2. **Independence**: run the new tests alone and together with the related
   existing tests; where practical, also in a different order (reverse, or
   the project's own random-order option) and repeatedly. Do not add an
   ordering plugin without consent.
3. **Detection power**: for the key tests, break the behavior under test in
   a disposable copy outside the repository (flip a comparison, skip a
   branch) and confirm that the test fails.
4. **Regression tests**, following [Regression tests](references/regression.md):
   - Build the pre-fix state, the production code without the fix plus the
     final test code, in a detached temporary worktree outside the
     repository made with `scripts/pre_fix_tree.py` (relative to this
     skill's directory). Creating and removing it needs no confirmation.
     Never `stash`, `checkout`, or `reset` the user's checkout instead.
   - Confirm that the pre-fix run loaded the pre-fix code; editable
     installs, installed packages, stale builds, and caches can point back
     to the fixed code.
   - Confirm that the pre-fix failure is the defect's symptom, not an
     import error, a missing name, a signature mismatch, or a broken test.
     Then confirm the pass on the fixed code. Repeat the pre-fix run after
     any change to the test.
   - Without a fix yet, confirm the failure reason and report the post-fix
     pass as unverified.
5. **Test-first requests**: confirm each test fails for the expected reason
   and report the post-implementation pass as unverified.
6. **Shared test code**: when you changed helpers, fixtures, or test
   registration, also run the existing tests that use them.
7. **Failures**: classify each as caused by this work, pre-existing
   (checked on the unchanged state when feasible), or environmental. Fix
   your own; report the rest.
8. **Runtime**: measure the new tests and compare them with similar tests
   and the CI limits.

Before a long, GPU, memory-heavy, or network-dependent run, weigh whether it
is needed and ask if it would strain shared resources. Remove temporary
worktrees, copies, and processes before finishing.

### 6. Review the Tests

Check every new test against this list before reporting:

- Uses only the public API; no production change made for testing.
- Fails when the behavior breaks: no assertion-free or always-true checks,
  swallowed exceptions, or assertions that only echo a test double.
- Has an independent oracle; non-obvious values are explained.
- Is isolated, deterministic, and cleans up after itself.
- Together with its siblings, covers normal, boundary, and error cases, or
  the report says why not.
- Is not redundant, is no heavier than its purpose, and is marked if heavy.
- Follows the project's conventions and runs in its standard test path.

### 7. Report

Report in the user's language using
[Report format](references/report-format.md): target and purpose; each test
case with the behavior it verifies, its kind (normal, boundary, error),
level, and runtime; commands and results; for regression tests, the pre-fix
and post-fix states, their results, and the pre-fix failure reason; how
independence was checked; what was deliberately not tested and why; bugs,
specification gaps, and assumptions; checks not run and the uncertainty
left; and whether production code changed. Separate facts from inferences.

## When the Code or the Specification Looks Wrong

- **A likely production bug**: do not adjust the expectation to the
  implementation. Report the reproduction, the expected behavior and its
  source, and the actual behavior, then ask whether to fix it, record it as
  a known failure, or leave it.
- **Expected-failure marks** (`xfail` and the like): only with the user's
  consent, with the reason and a bug reference, and strict, so that an
  unexpected pass is noticed.
- **An ambiguous specification**: ask; if you continue without an answer,
  state the assumption in the report.
- **Problems in existing tests** (implementation coupling, flakiness, wrong
  expectations): report them, change them only on explicit request, and do
  not copy their patterns.

## Git and Workspace Safety

- Unless the user asks for a commit (below), do not change the user's index,
  branches, or history: no `add`, `commit`, `stash`, `checkout`, `switch`,
  `restore`, `reset`, `rebase`, `merge`, `pull`, or `push`. The temporary
  pre-fix worktree is the only other exception.
- Keep uncommitted changes intact, including in files you edit.
- Keep scratch files, reproductions, and deliberately broken copies in a
  temporary directory outside the repository, and delete them at the end.
- Commit only when the user asks: stage only the files this skill created or
  changed, and write the message with the `git-commit-message` skill. Push
  or post to pull requests and issues only on explicit request.
- Never use production systems, real credentials, or paid resources in tests
  or test runs.

## References

| Reference | Read when |
|---|---|
| [Public API](references/public-api.md) | Deciding the unit, its public surface, and allowed test doubles; something seems untestable without internals |
| [Regression tests](references/regression.md) | Writing any regression test, before preparing the pre-fix state |
| [Test design](references/test-design.md) | Choosing cases, oracles, and assertions; securing independence and determinism |
| [Test weight](references/test-weight.md) | Choosing the test level, sizing inputs, marking heavy tests |
| [Report format](references/report-format.md) | Writing the final report or a handoff record |
| [Acceptance evaluation](references/acceptance.md) | Only when developing or evaluating this skill |

### Languages

Read the reference for every language the target and its tests use.

| Languages | Reference |
|---|---|
| Python | [python.md](references/languages/python.md) |
| JavaScript, TypeScript | [javascript-typescript.md](references/languages/javascript-typescript.md) |
| Java, Kotlin | [java-kotlin.md](references/languages/java-kotlin.md) |
| C# | [csharp.md](references/languages/csharp.md) |
| C, C++ | [c-cpp.md](references/languages/c-cpp.md) |
| Go | [go.md](references/languages/go.md) |
| Rust | [rust.md](references/languages/rust.md) |
| Ruby | [ruby.md](references/languages/ruby.md) |
| PHP | [php.md](references/languages/php.md) |
| Swift | [swift.md](references/languages/swift.md) |
| Shell (sh, Bash) | [shell.md](references/languages/shell.md) |

For another language, apply the general rules, use the closest reference as
a guide, and follow the project's conventions.
