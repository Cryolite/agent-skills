# Acceptance Evaluation

Read this only when creating, changing, or evaluating this skill.
Evaluating the skill does not authorize changes to real projects.

## Method

- Build small fixture repositories in a temporary directory; never evaluate
  on a real project checkout. Provide fixtures for every language reference
  (Python, JavaScript/TypeScript, Java/Kotlin, C#, C/C++, Go, Rust, Ruby,
  PHP, Swift, shell), covering at least the cases marked "each language".
- Give an independent agent only the skill, a realistic request, and the
  fixture. Do not reveal the expected answer (the defect location or the
  intended tests).
- Judge the actual artifacts: the generated tests, the commands run and
  their output, the final state of the fixture's working tree and index, and
  the report. Check both the expected work and the absence of forbidden side
  effects: production-code changes, access to implementation details,
  changes to the user's checkout, and leftovers in the repository or in
  temporary worktrees.
- Do not count instruction text or a plausible plan as evidence that
  something ran.
- After changing `scripts/pre_fix_tree.py`, run
  `python3 scripts/test_pre_fix_tree.py`.
- After changing the skill, re-run the affected cases. Evaluate the
  description's triggering with should-trigger requests and near-miss
  should-not-trigger requests, in Japanese and in English.

## Cases

| ID | Fixture or condition | Pass criteria |
|---|---|---|
| W01 | A Python module with public functions and underscore-prefixed helpers. | Tests call only the public functions; no helper is imported, called, or patched; the helpers' branches are covered through public inputs. |
| W02 | Behavior visible only through an internal cache. | Verified through observable behavior, or the gap is reported with design options; no visibility change or test-only hook. |
| W03 | The user asks for a direct test of a private function. | The rule and its reason are explained with alternatives; no test touches the private function. |
| W04 | A class calling an HTTP API with an injectable client. | A fake goes through the injection point; no internal method is patched; nothing reaches the external network. |
| W05 | A C++ core tested from Python. | Any test binding exposes only the core's public API. |
| W06 | An uncommitted fix in the working tree. | The final test fails on the `HEAD` production code because of the defect and passes on the fix, both observed. The pre-fix worktree is created without asking and removed afterwards; the user's working tree, index, and untracked files are unchanged. |
| W07 | A fix commit is named. | The final test fails on the parent commit's production code and passes on the fix commit. |
| W08 | The fix adds a parameter, so a naive test fails on the old code with `TypeError`. | The `TypeError` is not accepted as evidence; reproduction through shared API is attempted, or alternative evidence and the reason are reported. |
| W09 | An editable install points at the original checkout. | The pre-fix run is shown to load the pre-fix code; a pass of the fixed code is not mistaken for pre-fix evidence. |
| W10 | A bug report without a fix. | The test fails because of the defect; production code is untouched; the post-fix pass is reported as unverified. |
| W11 | The pre-fix build needs unavailable hardware, such as a GPU. | The reason and the detection rationale are reported; no pre-fix failure is claimed. |
| W12 | Code that reads and writes environment variables, the working directory, and global random state. | Each test sets and restores the state; results are identical alone, together, reordered, and repeated. |
| W13 | A suite with a mutable shared fixture. | New tests do not mutate shared state. |
| W14 | An API with documented exceptions and exit codes. | Normal and boundary cases plus every documented failure mode, with narrowed exception checks and checks of the state after failure. |
| W15 | Behavior for invalid input is unspecified. | Today's accidental behavior is not frozen; the agent asks or reports the assumption. |
| W16 | Writing tests reveals a production bug. | The expectation is not bent to the implementation; the bug is reported with a reproduction; no `xfail` without consent. |
| W17 | An off-by-one error in a pure function. | A small unit test without integration setup. |
| W18 | A command-line parsing bug that a direct call to an internal function would bypass. | The minimal test goes through the public entry point. |
| W19 | A training loop or multi-process behavior. | Minimal configuration, a heavy-test marker, a time limit, and the runtime reported. |
| W20 | Behavior that depends on time or randomness. | Determinism through seams or seeds; no fixed sleeps. |
| W21 | Numerical code whose expected value tempts copying the formula. | An independent oracle with its source and the tolerance rationale stated. |
| W22 | Behavior to pin down before refactoring. | Characterization tests labeled as such, through the public API; suspicious behavior reported. |
| W23 | Tests first for an unimplemented feature. | The tests fail for the expected reason; the post-implementation pass is reported as unverified; nothing is implemented without a request. |
| W24 | Python tests that are also registered with CTest. | New tests are registered the project's way and observed running under both pytest and CTest. |
| W25 | A project without test infrastructure. | A minimal setup is proposed and consent requested before any framework or dependency is added. |
| W26 | Pre-existing failures unrelated to the task. | They are classified and reported separately; existing tests are neither weakened nor removed. |
| W27 | "Write tests for the whole repository." | A risk-ranked plan and scope agreement come before mass test writing. |
| W28 | The user asks for the tests to be committed. | Only this skill's files are staged; the message comes from `git-commit-message`; nothing is pushed. |
| W29 | A request in Japanese, and separately the same request in English. | Each report is in the request's language; code, commands, and output are quoted verbatim. |
| W30 | Invoked by an issue-repair skill with a repair worktree and the fix location. | Works in that worktree; creates no commits; returns the handoff record with pre-fix and post-fix evidence; the parent's scope and language rules are respected. |
| W31 | Each language: existing tests use a test-only access pattern (Go `export_test.go`, Java reflection, C# `InternalsVisibleTo`, C++ `FRIEND_TEST`, Ruby `send`, PHP reflection, Rust `#[cfg(test)] pub`, JavaScript `rewire`). | New tests neither use nor extend the pattern; it is reported. |
| W32 | Each language: a regression fixture. | The language reference is read; tests use the project's framework and commands; the pre-fix run uses the tree's own build and environment. |
| W33 | A Swift application target without public API. | `@testable import` reaches only declarations that other parts of the app use. |
| W34 | Rust unit tests share a file with the fixed production code. | The regression test is placed or applied so that the pre-fix tree keeps the pre-fix production code. |
| W35 | The request only discusses, edits, or evaluates this skill. | The test-writing workflow does not start. |
| W36 | Inspect the finished package. | Valid name, description of at most 1024 characters, `SKILL.md` under 500 lines, resolvable links, English instructions with reporting in the user's language, no personal absolute paths, and passing script tests. |
