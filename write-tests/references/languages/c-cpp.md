# C and C++

## Tooling

- Drivers: CTest (`ctest --test-dir build -R <regex> --output-on-failure`,
  `-L <label>`, `--schedule-random`, `--repeat until-fail:<n>`, `-j`),
  Meson (`meson test -C build <name>`), Bazel (`bazel test //pkg:target`,
  `--runs_per_test`), or Make targets.
- Frameworks: GoogleTest and GoogleMock, Catch2, doctest, Boost.Test; for
  C, Unity with CMock, CMocka, Check, Criterion. Native code is also tested
  from Python through bindings, with the Python tests registered in CTest.
- Order and repetition: GoogleTest `--gtest_shuffle`,
  `--gtest_repeat=<n>`, `--gtest_filter`; Catch2 `--order rand`; doctest
  `--order-by=rand`.
- Run sanitizer configurations (ASan, UBSan, TSan) when the project
  provides them, especially for error paths and concurrency.

## Public API

- Public: declarations in public or installed headers and the public
  members of those classes; documented C functions with external linkage.
  For components of an application, the headers other components include.
- Implementation details: `private` members and undocumented `protected`
  ones, anonymous-namespace and `static` functions, `detail` and `impl`
  namespaces, internal headers, pimpl internals, and struct layouts the API
  does not promise.
- Not allowed: `#define private public`, `friend class FooTest` or
  `FRIEND_TEST` added for tests, including a `.cpp` or `.c` file into a
  test to reach `static` functions, `extern` redeclarations of internal
  symbols, `-fno-access-control`, and reading private fields through
  `reinterpret_cast`.

## Seams

- Constructor parameters, template parameters (policies, clocks), virtual
  interfaces the API already uses, and callbacks or function pointers in C
  APIs.
- Link-time substitution only for external dependencies (operating system,
  network, hardware), never for the unit's own translation units.
- Files: a unique directory under `std::filesystem::temp_directory_path()`
  (or from `mkdtemp`), removed in `TearDown`. Use GoogleMock mocks only for
  interfaces the unit receives.

## Isolation

- GoogleTest constructs a fixture per test (`SetUp`, `TearDown`);
  `SetUpTestSuite` and global environments are shared and must stay
  read-only.
- `gtest_discover_tests` registers each test case with CTest, which runs it
  in its own process. That isolates process-wide state but costs startup
  time.
- Restore `setenv`, `chdir`, `setlocale`, and signal handlers; `setenv` is
  not thread-safe.
- Death tests (`EXPECT_DEATH`) fork; with threads, use the `threadsafe`
  death-test style.

## Error Cases

- `EXPECT_THROW(statement, SpecificException)`, or Catch2
  `REQUIRE_THROWS_AS(expression, SpecificException)` and
  `REQUIRE_THROWS_MATCHES`; avoid `EXPECT_ANY_THROW` and untyped
  `REQUIRE_THROWS`.
- For error codes (`std::error_code`, `errno`, status enums), also check
  that outputs are unchanged after the failure.
- Test documented aborts with death tests that match the message; never
  test undefined behavior.

## Weight

- Add cases to an existing test executable when the project does, since
  each new executable adds build and link time.
- Use CTest `LABELS` (such as `slow` or `gpu`) and the per-test `TIMEOUT`
  property, and generate data in code instead of committing large binaries.

## Pre-Fix Runs

- Configure a fresh build directory for the tree (`cmake -S <tree> -B
  <tree>/build`) and never reuse the fixed checkout's build directory.
- Make the tree's headers and libraries win over installed copies: check
  include paths, `CMAKE_PREFIX_PATH`, and `LD_LIBRARY_PATH`. For Python
  bindings, point `PYTHONPATH` at the tree's build output and check the
  module's `__file__`.
