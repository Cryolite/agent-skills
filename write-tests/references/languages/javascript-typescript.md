# JavaScript and TypeScript

## Tooling

- Runners: Jest, Vitest, Mocha (with Chai and Sinon), `node:test`,
  Jasmine, AVA; Playwright or Cypress for browser and end-to-end tests.
  Detect them from `package.json` (`scripts.test`, `devDependencies`) and
  config files (`jest.config.*`, `vitest.config.*`, `.mocharc.*`,
  `playwright.config.*`).
- Run through the project's package manager (`npm test --`, `pnpm test`,
  `yarn test`, `bun test`). Select by file and by name (`-t` in Jest and
  Vitest, `--grep` in Mocha). List tests with `jest --listTests` or
  `vitest list`.
- Order: Jest `--randomize` (with `--seed`), Vitest `--sequence.shuffle`.
  Jest runs files in parallel workers; `--runInBand` runs them serially.
- TypeScript: Vitest and many Jest setups strip types without checking
  them, so also run the project's type check (`tsc --noEmit` or its
  script).

## Public API

- Public: what the package exports through `package.json` (`exports`,
  `main`, `module`, `types`) and its documented `bin` commands. For an
  application's modules, the exports that other modules use.
- Implementation details: non-exported functions and variables, `#private`
  fields, TypeScript `private` members and undocumented `protected` ones,
  declarations marked `@internal`, deep imports into a package's internal
  files, and module-level state.
- Not allowed: exporting a function only for tests (`export const
  _forTesting`), `rewire` or `babel-plugin-rewire`, casting to `any` to
  reach `private` members, `jest.mock` or `vi.mock` of modules the unit
  imports for its own use, and `vi.spyOn(module, "internalFunction")`.

## Seams

- Inject dependencies through parameters, constructors, or options (a
  `fetch` implementation, a clock, a random source).
- Time: `jest.useFakeTimers()`, `vi.useFakeTimers()`, and Sinon fake timers
  replace global timers and `Date` for the whole process; restore real
  timers in `afterEach`.
- Network: a local `http.createServer` listening on port 0, or
  network-level interception with MSW or `nock`. Do not mock the unit's own
  HTTP wrapper.
- Files: `fs.mkdtemp(path.join(os.tmpdir(), "..."))`, removed in
  `afterEach`. Save and restore the `process.env` entries and the working
  directory a test changes.

## Isolation

- Jest and Vitest isolate module registries per test file, not per test, so
  module-level state survives between the tests of a file. Create fresh
  instances through public factories in `beforeEach` instead of resetting
  module internals.
- Restore spies and mocks (`restoreMocks` in the configuration, or
  `vi.restoreAllMocks()` in `afterEach`).
- Await every promise. A forgotten `await` lets a test finish before its
  assertion runs; use `expect.assertions(n)` when assertions sit in
  callbacks. Jest `--detectOpenHandles` finds leaked handles.

## Error Cases

- `expect(() => f()).toThrow(SpecificError)`,
  `await expect(promise).rejects.toThrow(SpecificError)`, or `node:test`
  `assert.throws` and `assert.rejects` with the error class; check
  `error.code` when it is promised.
- For command-line programs, check the exit code and the standard error of
  the spawned process.

## Weight

- Keep browser tests (Playwright, Cypress) for behavior that needs a
  browser; test modules directly otherwise.
- Use per-test timeouts (`test(name, fn, 10_000)`, Playwright
  `test.setTimeout`) and the project's tags, projects, or workspaces to
  separate slow suites.

## Pre-Fix Runs

- Install dependencies inside the tree (`npm ci`, `pnpm install
  --frozen-lockfile`) instead of linking the original `node_modules`;
  workspace packages could otherwise resolve to the fixed checkout. Check
  with `node -p "require.resolve('pkg')"` (or the ESM equivalent) from the
  tree.
- Rebuild compiled output (`dist/`) when tests import it, and bypass runner
  caches (`jest --no-cache`) if results look stale.
