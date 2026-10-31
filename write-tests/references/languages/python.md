# Python

## Tooling

- Runners: pytest (`conftest.py`, `[tool.pytest.ini_options]` in
  `pyproject.toml`, `pytest.ini`, `setup.cfg`, `tox.ini`) or `unittest`.
  Use the project's entry point (`python -m pytest`, `tox -e`, `nox -s`,
  `hatch run`, `uv run`, `make test`) in its environment.
- Select with node ids (`path/test_x.py::TestY::test_z`), `-k`, or `-m`.
  `--collect-only -q` shows what is collected, `-rA` lists every outcome
  with skip reasons, and `--durations=0` reports timings.
- Passing node ids in a different order usually reorders a run without
  plugins; confirm the order in `-v` output. Use `pytest-randomly`,
  `pytest-repeat`, or `pytest-xdist` only when the project already has them.
- Check tests with the project's ruff, flake8, mypy, or pyright settings.

## Public API

- Public: names without a leading underscore that a module or package
  exposes, narrowed by `__all__` where it exists and by re-exports in
  `__init__.py`; documented classes, functions, and attributes; console
  scripts and `python -m` entry points.
- Implementation details: `_name` and `__name` members, `_private` modules,
  module-level caches, and the names a module imports for its own use
  (`mymodule.os`, `mymodule.requests`).
- Not allowed: `from pkg.mod import _helper`, `obj._state`,
  `obj._Class__secret`, `monkeypatch.setattr("pkg.mod._helper", ...)`,
  `mock.patch("pkg.mod.requests.get")`, `patch.object(unit, "_method")`,
  assertions on mocks of internals, and `importlib.reload` to reset module
  internals.
- A non-underscore name that is missing from `__all__` and used only inside
  its module is a gray zone: decide from documentation and callers, and
  record the decision.

## Seams

- Parameters and constructor arguments first. Use `monkeypatch.setenv` and
  `delenv` for documented environment variables, `tmp_path` and
  `monkeypatch.chdir` for files, and `monkeypatch.setenv("HOME",
  str(tmp_path))` for user configuration.
- Time: inject a clock when the API accepts one. `time-machine` and
  `freezegun` patch the standard library for the whole process rather than
  the unit's names; use them when the project already depends on them, and
  ask otherwise.
- Randomness: pass `random.Random(seed)` or `numpy.random.default_rng(seed)`
  when the API accepts it. When code uses global generators, seed them in a
  fixture and restore the saved state afterwards (`random.getstate` and
  `setstate`, `numpy.random.get_state` and `set_state`,
  `torch.get_rng_state` and `set_rng_state`).
- HTTP: a local server (`http.server` in a thread, `pytest-httpserver`) or
  an injected transport such as `httpx.MockTransport`. Library-wide
  interceptors (`responses`, `requests-mock`) assume which HTTP library the
  unit uses; use them only when the project already does.
- Command-line programs: run the console script or `[sys.executable, "-m",
  "pkg", ...]`, or call a documented `main(argv)`.

## Isolation

- Use fixtures with `yield` for teardown, and the self-restoring
  `monkeypatch`, `tmp_path`, `capsys`, and `capfd`. Use `caplog` only for
  logs the contract promises.
- Use module- or session-scoped fixtures only for read-only resources.
- When global state has no public reset, isolate the test in a subprocess
  and accept the extra weight rather than poking at the module.

## Error Cases

- `with pytest.raises(SpecificError, match=r"...")`: add `match` only for
  promised content, and check the attributes of `excinfo.value` that the
  contract defines.
- For command-line programs, check `SystemExit.code` or the `returncode`,
  and the standard error.
- Use `pytest.warns(SpecificWarning)` when a warning is part of the
  contract.

## Weight

- Register custom markers (`slow`, `gpu`) the way the project does and
  select with `-m`. Skip missing resources with `pytest.mark.skipif(...,
  reason=...)` or `pytest.importorskip`.
- Time limits: `pytest-timeout` if present; otherwise timeouts on
  `subprocess.run`, `Future.result`, `Thread.join`, and queue reads.
- For PyTorch, prefer the CPU and tiny tensors unless the behavior is
  specific to a device.

## Pre-Fix Runs

- Editable installs (`pip install -e`, `.pth` files) and a `PYTHONPATH` set
  for the original checkout make the pre-fix tree import the fixed code.
  Run with `PYTHONPATH` pointing into the tree (its `src/` when the project
  uses that layout), or install the tree into a fresh virtual environment.
  Confirm with `python -c "import pkg; print(pkg.__file__)"` in the same
  environment and working directory.
- Rebuild compiled extensions (C, Cython, pybind11, nanobind) from the tree
  and make sure the tree's build output is the one imported.
- Run pytest from inside the tree, keep the project's `--import-mode`, and
  add `-p no:cacheprovider` to avoid writing caches.
