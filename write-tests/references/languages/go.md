# Go

## Tooling

- `go test ./...`, selected with `-run 'TestName/Subtest'`. Use `-count=1`
  to bypass cached results, `-shuffle=on` to randomize order (Go 1.17 and
  later), `-count=<n>` to repeat, `-race` for the race detector, `-short`
  for the quick subset, `-timeout`, and `-v` or `-json` for timings.
- Libraries the project may use: testify, go-cmp, gomock or mockery,
  Ginkgo and Gomega.

## Public API

- Exported (capitalized) identifiers are a package's API. Packages under
  `internal/` are implementation details to code outside the parent tree;
  inside the module, their exported identifiers are their API.
- Prefer black-box tests in the external test package (`package foo_test`),
  which can use only exported identifiers. In-package tests (`package foo`)
  can reach unexported identifiers; if the project uses them, still call
  only exported ones.
- Not allowed: `export_test.go` files that re-export unexported identifiers
  (a common idiom, and exactly a test-only window into internals),
  `reflect` or `unsafe` access to unexported fields, `go:linkname`, and
  overriding unexported package-level variables such as
  `var now = time.Now`.

## Seams

- Interfaces and function parameters the API accepts (`io.Reader`,
  `http.RoundTripper`, `*http.Client`, a clock function), and options
  structs.
- HTTP: `httptest.NewServer` with the server URL passed through
  configuration, or `httptest.NewRecorder` for handlers.
- Files and environment: `t.TempDir()`; `t.Setenv`, which restores the
  variable and cannot be used in parallel tests; `t.Chdir` (Go 1.24 and
  later).
- Time: an injected clock, or `testing/synctest` (Go 1.25 and later), which
  runs code in a bubble with a fake clock.

## Isolation

- Register teardown with `t.Cleanup`; it runs even when the test fails.
- Use `t.Parallel()` only for tests without shared mutable state.
- Package-level state persists across the tests of a package; keep
  `TestMain` setup read-only.

## Error Cases

- Check documented errors with `errors.Is` and `errors.As` (or testify
  `require.ErrorIs` and `require.ErrorAs`) instead of comparing strings;
  `err != nil` alone is too weak when a specific error is promised.
- Test panics only when they are part of the contract
  (`assert.PanicsWithValue`, or a deferred `recover`).

## Weight

- Long tests check `testing.Short()`; integration suites may use build
  tags (`//go:build integration`) when the project does. Benchmarks are not
  tests; add them only on request.
- Bound waits inside tests with `context.WithTimeout`.

## Pre-Fix Runs

- Run `go test -count=1` inside the tree.
- `go.work` files and `replace` directives can point at modules in the
  original checkout; check `go env GOWORK` and `go list -m all` in the tree.
