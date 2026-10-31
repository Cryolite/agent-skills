# Regression Tests

A regression test is worth having only if it would fail when the bug comes
back. The direct evidence is two observations with the final test code: it
fails on the pre-fix production code because of the defect, and it passes
on the fixed code.

## 1. Define the Defect

Before writing the test, write down:

- the triggering condition (input, state, environment, sequence of calls);
- the wrong behavior that results, and the correct behavior with its source
  (specification, documentation, issue discussion);
- the public entry point where the condition can be produced.

Test the observable symptom, not the fix: the test must pass with any
correct fix, not only with the one written. Cover close neighbors when that
is cheap and meaningful (the other side of the boundary, another entry point
to the same root cause). Name or comment the test with the bug reference
and the triggering condition, following the project's conventions.

## 2. Choose the Pre-Fix and Post-Fix States

| Where the fix is | Pre-fix production code | Post-fix production code |
|---|---|---|
| Uncommitted changes | `HEAD`, or the base the user names | The working tree |
| Commit `C` | `C^` | `C`, or a later tree that contains it |
| Branch or pull request | The merge-base with the target branch | The branch head |
| Not written yet | The current code | Unverified until the fix exists |

Only production code differs between the two states; the test code is
always the final version, including new tests, their helpers and data, and
test registration. If candidate states give different results and the
context does not settle which is right, ask.

When the working tree mixes the fix with unrelated changes, the same script
can create a clean post-fix tree as well (`--rev C` for a committed fix).

## 3. Create the Pre-Fix Tree

Use the bundled script. `<skill-dir>` is the directory that contains this
skill's `SKILL.md`.

```sh
python3 <skill-dir>/scripts/pre_fix_tree.py create --rev HEAD \
  --copy tests/test_parser.py --copy tests/conftest.py
```

- `--rev` names the pre-fix revision.
- `--copy` names a test file or directory to take from the current working
  tree (relative to the current directory); repeat it as needed.
  Directories are mirrored, so files deleted in the working tree are absent
  from the copy too.
- The script creates a detached worktree in a new temporary directory
  outside the repository, with repository hooks disabled, and never changes
  the user's working tree, index, or branches. No confirmation is needed.
- It prints the tree location, the copied paths that differ from the
  revision (all of them must be test code), and the paths kept at the
  revision although the working tree differs. That second list should be
  exactly the fix. If it contains test files, copy them too; if it contains
  unrelated changes, judge whether they affect the result and say so in the
  report. If it is empty, the tree equals the final state and the test
  cannot fail there: recheck `--rev`.
- `--json` prints the same information as JSON.

Remove the tree when done, including after failures:

```sh
python3 <skill-dir>/scripts/pre_fix_tree.py remove <tree>
```

Without the script, do the same by hand: `git worktree add --detach
<new temporary directory>/tree <rev>`, copy the test files, and later `git
worktree remove --force <tree>`. Never reach the pre-fix state with
`stash`, `checkout`, `switch`, `restore`, or `reset` on the user's checkout.

**Tests sharing a file with production code** (Rust unit tests in
`mod tests`, doctests, a test module inside a production file): copying the
file would also copy the fix. Put the regression test in a separate test
file, or apply only the test hunk inside the tree (save the hunk as a patch
outside the repository and run `git apply` in the tree).

**Submodules** are not initialized in the tree. Initialize them there if the
build needs them; this may access the network.

## 4. Make Sure the Pre-Fix Code Runs

Typical traps: an editable install or `PYTHONPATH` that points at the
original checkout; an installed package shadowing the tree; build outputs,
caches, or a shared build directory from the fixed code; a workspace or
`replace` directive resolving to the original checkout. Build and run from
inside the tree with its own outputs, verify the imported module or the
binary path (see the language reference), and record how you verified it.

## 5. Run and Interpret

1. Run the test on the pre-fix tree. It must fail, and the failure must be
   the defect's symptom: a wrong value, a missing or wrong exception, wrong
   output, or a hang when the bug is a hang. Read the failure output.
2. These failures are not evidence: import or module-not-found errors,
   undefined names, signature or arity mismatches, syntax or compile errors
   in the test, fixture or setup errors, environment failures, and timeouts
   unrelated to the symptom.
3. Run the same test on the post-fix code. It must pass. Also run the
   related existing tests there.
4. If you change the test after the pre-fix run, run the pre-fix check
   again.

## 6. Special Situations

- **The fix changes the public API** (a new parameter or a renamed
  function), so the test cannot run on the pre-fix code: first try to
  reproduce the defect through API that both versions share. If that is
  impossible, demonstrate the defect on the pre-fix code another way (a
  throwaway script that uses the old API, kept outside the repository), and
  report both results and why the test itself could not run there.
- **The fix is not written yet**: confirm the failure reason and leave
  production code alone unless asked. If the user also asked for the fix,
  write the test first, watch it fail, fix the code, and watch it pass.
- **The pre-fix state cannot be built or run** (missing hardware or
  toolchain, impractical build time): report why, and why you believe the
  test detects the defect. Never claim a pre-fix failure you did not
  observe. The post-fix run is still required; if it cannot run either,
  report the test as unverified.
- **Nondeterministic defects** (races, timing): make the trigger
  deterministic through public means (an injected clock or scheduler,
  callbacks used as barriers). If that is impossible, report the pre-fix
  failure rate over N runs and the post-fix result over the same N runs.
- **Existing tests missed the bug**: when the reason is visible (the
  defective part was mocked, a boundary was missing), mention it.

## 7. Record

For each regression test, record its location (file and test id), the
triggering condition, the expected behavior and its source, the pre-fix and
post-fix states (commit or diff identity), the commands, the results, and
the key lines of the pre-fix failure. Mark anything not run, with the
reason.
