# Swift

## Tooling

- SwiftPM: `swift test --filter 'Module.Suite/test'`, `--parallel`. Xcode:
  `xcodebuild test -scheme <scheme> -destination '<destination>'
  -only-testing:<Target>/<Class>/<method>`.
- Frameworks: XCTest and Swift Testing (`import Testing`, `@Test`,
  `#expect`, `#require`, `@Suite`, and traits such as `.tags`,
  `.timeLimit`, and `.serialized`). Swift Testing runs tests in parallel by
  default. Xcode test plans can randomize the execution order.

## Public API

- For a package or framework: `public` and `open` declarations. `package`,
  `internal` (the default), `fileprivate`, and `private` declarations are
  implementation details to its consumers.
- `@testable import` exposes `internal` declarations to tests. Use a plain
  `import` for packages and frameworks. For an application target, which has
  no public API by design, `@testable import` is the normal way to reach its
  components; call only declarations that other parts of the app use.
- Not allowed: widening `private` or `fileprivate` for tests, `#if DEBUG`
  hooks for tests, `Mirror` to read private state, and adding `@_spi`
  groups for tests.

## Seams

- Protocol-typed dependencies injected through initializers, and closures
  or a `Clock` the API accepts for time.
- A `URLSession` built from a `URLSessionConfiguration` the API accepts,
  with a custom `URLProtocol` subclass serving canned responses.
- Files: a unique directory under `FileManager.default.temporaryDirectory`,
  removed in teardown. Use a dedicated `UserDefaults(suiteName:)` when the
  API accepts one.

## Isolation

- XCTest creates an instance per test method (`setUp`, `tearDown`,
  `addTeardownBlock`); class-level setup is shared.
- Swift Testing creates a suite instance per test (`init`, `deinit`) and
  runs tests in parallel, so shared mutable state is unsafe; process-wide
  state needs `.serialized` and restoration.

## Error Cases

- XCTest `XCTAssertThrowsError(try f()) { error in ... }`, with a check of
  the error inside the closure; Swift Testing
  `#expect(throws: MyError.invalidHeader) { try f() }` or
  `#expect(throws: MyError.self) { try f() }`.
- `precondition` and `fatalError` failures cannot be caught in-process. Use
  Swift Testing exit tests where the toolchain supports them, or test the
  validation that precedes them.

## Weight

- UI tests (XCUITest) are heavy; test view models and logic directly unless
  the behavior is in the UI. Bound time with `.timeLimit` or XCTest
  execution time allowances.

## Pre-Fix Runs

- SwiftPM builds into the tree's `.build/`. For Xcode, pass
  `-derivedDataPath` with a temporary directory. Local package dependencies
  referenced by relative paths outside the tree may resolve to fixed code;
  check them.
