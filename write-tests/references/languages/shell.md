# Shell (sh, Bash)

## Tooling

- Bats (bats-core, with bats-support, bats-assert, and bats-file): `bats
  test/`, `--filter <regex>`, `--filter-tags`, `--jobs <n>` (needs GNU
  parallel), `--timing`. Also shUnit2, ShellSpec, or plain test scripts run
  by `make test`.
- Run ShellCheck on scripts and tests when the project does.

## Public API

- The command-line interface: arguments, options, standard input, exit
  status, the promised standard output and error, files created or changed,
  and documented environment variables. For a library meant to be sourced,
  the functions it documents.
- Implementation details: internal functions of a script, temporary file
  names, intermediate output, and the order of internal commands.
- Not allowed: sourcing an executable script to call its internal
  functions, adding `TESTING` branches or source guards only for tests, and
  redefining the script's own functions to stub them.

## Seams

- Fake executables for external commands (`curl`, `git`, `date`) in a
  temporary directory placed first on `PATH`; each fake should model the
  real command's contract (arguments, output, exit status).
- `HOME`, `TMPDIR`, and `XDG_*` pointing at temporary directories, plus the
  documented environment variables.
- A temporary working directory; never real user files.

## Isolation

- Bats runs each test in its own process. `setup` and `teardown` run per
  test; `setup_file` is shared and must stay read-only. Use
  `$BATS_TEST_TMPDIR` for per-test files.
- Do not write fixed names under `/tmp`. Set `LC_ALL=C` when output depends
  on the locale.

## Error Cases

- Check the exit status and standard error: `run --separate-stderr script
  args`, then `[ "$status" -eq 2 ]` or `assert_failure 2`, and assertions on
  `$stderr`. Also check that no partial files remain.
- Cover missing or invalid arguments, unreadable inputs, failing external
  commands (fakes that exit non-zero), and interrupts when the script traps
  signals.

## Weight

- Prefer fake external commands to real network or system operations. Wrap
  commands that could hang in `timeout`, and tag slow tests
  (`# bats test_tags=slow`) for filtering.

## Pre-Fix Runs

- Invoke the script by its path inside the tree, not through `PATH`, which
  may find an installed or fixed copy; print the resolved path in the
  test's output when in doubt.
