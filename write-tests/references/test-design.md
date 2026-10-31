# Test Design

## Contents

- [Deriving Cases](#deriving-cases)
- [Error Cases](#error-cases)
- [Oracles](#oracles)
- [Assertions](#assertions)
- [Detection Power](#detection-power)
- [Independence](#independence)
- [Determinism](#determinism)
- [Readability](#readability)

## Deriving Cases

Start from the contract, not the code. For each behavior:

- **Equivalence partitioning**: group inputs the contract treats alike; one
  representative per class is usually enough.
- **Boundary values**: at, just below, and just above each boundary:
  empty, one, and many; zero and negative; minimum and maximum; length
  limits; off-by-one in ranges and indexes; date, time-zone, and encoding
  boundaries.
- **State transitions**: valid transitions, invalid ones, and repeated
  operations (idempotence, double close).
- **Condition combinations**: a decision table when several conditions
  interact; pairwise combinations when the full product is too large.
- **Properties**: invariants and round trips (`decode(encode(x)) == x`,
  sortedness, conservation) checked over many generated inputs, with
  property-based testing when the project has it (Hypothesis, fast-check,
  jqwik, proptest, and others). Ask before adding the dependency.

Rank by risk: impact, likelihood, complexity, recent change, bug history.
Drop cases that only repeat a covered class. Coverage tools can reveal
untested branches, but never add tests that execute code without checking
its behavior just to raise the number.

## Error Cases

Consider, as far as the contract defines them:

- invalid input: wrong type, out of range, malformed, empty, missing,
  duplicate, oversized, wrong encoding;
- precondition violations: use before initialization or after close,
  invalid state transitions, reentrancy;
- dependency failures: missing file, permission denied, full disk, network
  error, timeout, malformed response;
- resource exhaustion and limits;
- concurrency: concurrent modification, cancellation, interruption.

For each, check what the contract promises: the error type, the error code
or exit status, the essential message content when it is promised, and the
state afterwards (nothing partially written, resources released, the object
still usable or unusable as documented). When the contract is silent, do not
lock in today's accidental behavior: ask, or state the assumption. When no
error case applies (a pure function defined for every input), say so in the
report instead of inventing one.

## Oracles

Derive expected values independently of the code under test:

- the specification or documentation and their examples;
- hand calculation, with the derivation in a comment when it is not obvious;
- known values, published test vectors, reference outputs from the
  literature;
- inverse operations and round trips;
- invariants and metamorphic relations (scaling the input scales the
  output; permuting the input leaves a sum unchanged);
- an independent reference implementation (a slow but obviously correct
  version, another library).

Do not compute expected values by calling the unit, copy its formula into
the test, or paste its current output. Characterization tests are the
exception: they deliberately freeze current outputs. Label them as such,
keep them on the public API, and report behavior that looks wrong.

For floating point, use a tolerance justified by the computation (magnitude,
number of operations, precision), relative or absolute as appropriate, and
state the reason. Never make it so loose that the bug would pass.

## Assertions

- Check the whole result when the contract defines it; do not spot-check one
  field and miss the rest.
- Do not depend on what the contract leaves open: set or dictionary order,
  unspecified formatting, wording outside the contract.
- Narrow exception checks to the specific type; check message content only
  when it is promised.
- "Does not raise" is a valid assertion only when it is the contract; then
  make it explicit.
- Make failure messages diagnostic by including the input and the compared
  values.

## Detection Power

A test that cannot fail proves nothing. Avoid:

- tests without assertions, or with assertions that always hold (`assert
  result is not None` for a function that never returns `None`);
- catching exceptions broadly and passing;
- asserting only on a value that a test double returned;
- conditional assertions that skip themselves;
- expected values computed by the code under test.

Sanity-check important tests by breaking the behavior in a disposable copy
outside the repository (invert a comparison, drop a branch, return a
constant) and confirming that the test fails. The bundled
`scripts/pre_fix_tree.py create --rev HEAD --copy <tests>` gives such a copy
with the current tests; edit the production code in it, run the tests, and
remove it.

## Independence

Each test case must pass alone, in any order, repeated, and in parallel if
the project runs tests in parallel.

- Create preconditions in the test or in a per-test fixture; never rely on
  another test's side effects.
- Share fixtures across tests only when they are read-only and no test
  mutates them.
- Restore global state with facilities that also run on failure (fixtures,
  teardown, cleanup callbacks, `defer`): environment variables, working
  directory, module-level state and caches, singletons, global random
  generators, logging and signal handlers, locale and time zone, import
  paths, registries.
- Write files only under per-test temporary directories, never into the
  repository, the home directory, or fixed shared paths.
- Allocate ports and other contended resources dynamically.
- Terminate processes, threads, and servers, and close files, even when the
  test fails.

Verify by running the new tests alone, then with their neighbors, then in
reverse or random order if the project already supports it, and repeatedly.

## Determinism

- Control time and randomness through seams or fixed seeds; do not let the
  wall clock drive the logic under test.
- Do not depend on unspecified ordering: hash iteration, directory listing,
  the completion order of concurrent work.
- Do not use the network or external services, and do not rely on
  machine-specific state (home configuration, caches, absolute paths,
  locale, time zone, CPU count, GPU presence without a skip).
- Wait for conditions with a deadline instead of sleeping.
- Do not hide flakiness with retries or reruns; find and remove its cause.

## Readability

- Name tests after the condition and the expected result, in the project's
  style.
- One behavior per test, with visible arrange, act, and assert steps.
- Parametrize or use tables for multiple inputs, with readable case ids.
- Factor out repetition only while each test still reads on its own.
- Keep test data small and synthetic: no secrets, personal data, or data
  with unclear licenses, and no large downloads.
