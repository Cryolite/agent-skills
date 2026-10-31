# Report Format

Write the report in the language the user writes in. Translate the headings
and labels; keep code, identifiers, paths, commands, and tool output
verbatim. Omit sections that do not apply.

## Template

```markdown
## Test report

### Summary

- Target and purpose: ...
- Result: <N> test cases added or changed; <all passed | failures below>
- Production code: not changed | changed with consent: ...

### Test cases

| Test | Behavior verified | Kind | Level | Runtime |
|---|---|---|---|---|
| `tests/test_parser.py::test_rejects_empty_header` | An empty header raises `ParseError` and writes no output | error | small | 0.01 s |

### Expected values

- `test_...`: derived from ... (non-obvious values only)

### Commands and results

- `python -m pytest tests/test_parser.py`: 12 collected, 12 passed

### Regression evidence

| Test | Pre-fix state | Pre-fix result | Post-fix state | Post-fix result |
|---|---|---|---|---|
| `test_...` | `HEAD` 3f2a1b0 production code, final tests | failed: `AssertionError: 3 != 2` (the off-by-one) | working tree | passed |

### Independence

- Ran alone, with `tests/test_parser.py`, in reverse order, and three
  times: identical results.

### Not tested

- ... (reason)

### Findings and assumptions

- ...

### Not verified

- ... (reason, and the uncertainty that remains)
```

- "Kind" is normal, boundary, or error. "Level" is a size from
  [Test weight](test-weight.md) or the project's own category.
- Use the exact commands and counts from the actual output. Do not round
  "11 passed, 1 skipped" up to "all passed".
- Every regression test has a row under "Regression evidence". Write "not
  run" with the reason instead of leaving a cell blank or guessing.
- Separate facts (observed output) from inferences (why you believe
  something).

## Handoff to a Parent Workflow

When another skill invoked this one, return the same information as a
compact record that the parent can store and cite:

```markdown
- Tests: <file::test ids>, registered in <test path or CTest name>
- Defect: <triggering condition>; expected <behavior> (source: ...)
- Pre-fix: <state>, `<command>`, <result and failure excerpt>
  | not run: <reason>; detection rationale: ...
- Post-fix: <state>, `<command>`, <result>
- Other checks: `<command>`: <result>
- Open items: <unverified checks, findings, assumptions>
```

Write the record in the language the parent requests (by default, the
user's language). The parent decides how to translate and publish it, for
example as English pull-request text.
