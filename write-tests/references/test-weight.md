# Test Weight

The weight of a test is what it costs to run and maintain: wall time; CPU,
GPU, memory, and disk; processes and network; the number of real components
involved; setup complexity; and the risk of flakiness. Choose the lightest
test that still detects what it is for.

## Sizes

Use the project's categories when it has them. Otherwise think in sizes:

| Size | Scope | Typical constraints |
|---|---|---|
| Small | One unit in one process | No network, no sleeps, temporary files only; milliseconds to well under a second |
| Medium | Several components, or real local resources | One machine; subprocesses, local servers, real file formats, a local database; seconds |
| Large | The whole system or several machines | Deployments, GPUs, distributed runs, large data sets; minutes |

## Choose by Purpose

1. State what the test must detect.
2. Identify the code path where that behavior or defect lives.
3. Keep that path real; shrink or substitute everything else through public
   seams.
4. Pick the smallest size that keeps the path real.

| Behavior | Lightest sufficient test |
|---|---|
| Pure computation, value parsing, boundary logic | A small test of the public function |
| Argument parsing, entry-point wiring, process setup | The public entry point (`main(argv)` or the command) with minimal arguments |
| Serialization between components, file formats | A round trip through the real format with tiny data |
| Configuration loading and validation | A minimal real configuration through the public loader |
| Concurrency, inter-process communication, distributed coordination | The smallest thread or process count that triggers it, with time limits |
| GPU or hardware-specific code | Tiny problems on the device, skipped without it |
| Behavior at a native boundary | The actual binding with minimal data |

Too light is a failure too. Mocking out the defective component, or calling
an internal function that bypasses the faulty wiring, gives a fast test that
cannot detect the bug.

## Minimize

- Use the smallest inputs, models, iteration counts, epochs, and process
  counts that exercise the behavior.
- Generate data in the test rather than shipping large fixtures.
- Avoid real sleeps: poll for a condition with a deadline, or use a
  controllable clock.
- Prefer a few representative parameter combinations to full cross
  products.

## Fit the Project's Budget

- Put tests where the project's default command expects them, and mark heavy
  ones with its markers, labels, tags, or directories (for example
  `@pytest.mark.slow`, CTest `LABELS`, Go `testing.Short()`, JUnit
  `@Tag`) so that the default loop stays fast.
- Respect CI time limits, and give tests that could hang their own timeout.
- Skip resource-dependent tests where the resource is missing, using the
  project's mechanism and a clear reason.
- Measure the runtime of each new test with the runner's timing output and
  compare it with similar existing tests; report it.

## Maintenance Weight

Large golden files, deep fixture hierarchies, and many mocks make tests
expensive to understand and update. Prefer small, explicit setup. When a
golden file is the right tool, keep it small and review its content as an
expectation, not as whatever the code happened to produce.
