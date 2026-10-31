# Rust

## Tooling

- `cargo test` runs unit tests (`#[cfg(test)] mod tests`), integration
  tests (`tests/*.rs`), and doctests. Use `cargo nextest run` when the
  project uses nextest, which runs each test in its own process; do not
  enable its retries to hide flakiness.
- Select with a name filter (`cargo test parser::empty`), `-- --exact`, and
  `--test <name>`; `-- --test-threads=1` serializes, and `-- --ignored` or
  `-- --include-ignored` runs ignored tests. libtest's `--shuffle` requires
  nightly (`-Z unstable-options`).
- Crates the project may use: `rstest`, `proptest`, `mockall`, `tempfile`,
  `assert_cmd` with `predicates`, `insta`, `pretty_assertions`.

## Public API

- `pub` items reachable from the crate root, including `pub use`
  re-exports, form a library's API. `pub(crate)`, `pub(super)`, and private
  items are internal to the crate; in a binary crate, the items other
  modules use are those modules' API.
- Prefer integration tests in `tests/`, which compile as separate crates
  and see only the public API. Unit tests in `mod tests` with
  `use super::*` can reach private items; if the project keeps tests there,
  still call only items that other modules are meant to use.
- Not allowed: making items `pub` or `pub(crate)` for tests,
  `#[cfg(test)]` accessors, constructors, or branches in production code,
  and reading private fields with `unsafe` or `transmute`.

## Seams

- Traits and generics the API accepts (a clock trait, `R: Rng`,
  `impl Read`), and constructor parameters.
- Time in tokio code: `#[tokio::test(start_paused = true)]` with
  `tokio::time::advance` controls the runtime's clock.
- Randomness: pass `StdRng::seed_from_u64(...)` when the API accepts an
  RNG.
- Files: `tempfile::tempdir()`, removed on drop. Environment variables are
  process-wide (`std::env::set_var` is `unsafe` in edition 2024), so pass
  configuration explicitly where possible.
- Command-line programs: `assert_cmd::Command::cargo_bin("name")` runs the
  real binary (medium weight).

## Isolation

- libtest runs tests on parallel threads of one process, so environment
  variables, the working directory, and statics leak between tests. Avoid
  them, restore them, or serialize the affected tests the project's way
  (`serial_test`, nextest); ask before adding a crate.
- Drop guards clean up during unwinding, but not when the test profile sets
  `panic = "abort"`.

## Error Cases

- Match the variant: `assert!(matches!(result, Err(Error::InvalidHeader {
  .. })))` or `assert_matches!`, and compare `io::ErrorKind`. `is_err()`
  alone is too weak when a specific error is promised.
- Use `#[should_panic(expected = "...")]` only when panicking is the
  documented contract.

## Weight

- Mark expensive tests `#[ignore = "reason"]` and run them in the project's
  slow job; gate optional integrations behind features.
- Each file in `tests/` is a separate crate with its own compile and link
  cost; add to an existing file when the project groups tests.

## Pre-Fix Runs

- Build with a target directory of the tree's own; if `CARGO_TARGET_DIR` is
  set globally, override it with a temporary directory.
- Check `[patch]` sections and `.cargo/config.toml` overrides that may point
  outside the tree.
- Inline unit tests share files with production code, so copying the test
  file would also copy the fix: place the regression test in `tests/`, or
  apply only the test hunk inside the tree (see
  [Regression tests](../regression.md)).
