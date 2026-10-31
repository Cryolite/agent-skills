# Java and Kotlin

## Tooling

- Maven: `mvn -q test`, `-Dtest=ClassName#method`; Surefire runs unit
  tests (`*Test`) and Failsafe runs integration tests (`*IT`) in `verify`.
  Gradle: `./gradlew test --tests 'pkg.ClassName.method'`; add
  `--rerun-tasks` or run `cleanTest` first, because Gradle skips test tasks
  it considers up to date.
- Frameworks: JUnit 5 (Jupiter), JUnit 4, TestNG, Kotest; assertions with
  AssertJ, Hamcrest, Truth, or `kotlin.test`; doubles with Mockito or MockK.
- Results and timings: `target/surefire-reports`, `build/test-results`,
  `build/reports/tests`.
- JUnit 5 can randomize method order through the
  `junit.jupiter.testmethod.order.default` configuration parameter; set it
  temporarily rather than committing it.

## Public API

- Java: `public` types and members of exported packages (see the `exports`
  of `module-info.java`), plus `protected` members documented as extension
  points. Package-private and `private` members, and packages named
  `internal` or `impl` in a library, are implementation details.
- Kotlin: declarations are `public` by default; `internal` is visible
  across one compilation module and `private` within a file or class.
  `@PublishedApi internal` exists for inline functions and is not API.
- Tests usually share the package of the code under test, which makes
  package-private members reachable; call only the public API anyway.
- Not allowed: reflection with `setAccessible(true)`, PowerMock or
  Whitebox, widening visibility with `@VisibleForTesting`, Mockito `spy` to
  stub the unit's own methods, `mockStatic` of the unit's internal static
  helpers, and making members `open` or non-`final` only so they can be
  mocked.

## Seams

- Constructor injection of interfaces; `java.time.Clock` (`Clock.fixed`,
  `Clock.offset`); an injected `Random` or `RandomGenerator`; coroutine
  dispatchers or scopes the API accepts, driven by
  `kotlinx-coroutines-test` (`runTest`, `StandardTestDispatcher`) for
  virtual time.
- HTTP: OkHttp `MockWebServer` or WireMock, with the base URL passed
  through configuration.
- Databases: Testcontainers gives fidelity at medium or large weight and
  needs Docker; an in-memory database such as H2 is lighter but can behave
  differently from the production engine. Choose by what the test must
  detect.

## Isolation

- JUnit 5 creates a new instance per test method by default; avoid
  `@TestInstance(PER_CLASS)` with mutable fields, and avoid mutable statics.
- Use `@TempDir`, and restore `System.setProperty`, `Locale.setDefault`,
  and `TimeZone.setDefault` changes in `@AfterEach`.
- With parallel execution enabled (`junit.jupiter.execution.parallel.*`,
  Gradle `maxParallelForks`), tests that touch process-wide state need
  `@Isolated` or `@ResourceLock`.

## Error Cases

- `assertThrows(SpecificException.class, () -> ...)` returns the exception
  for further checks; AssertJ `assertThatThrownBy(...).isInstanceOf(...)`;
  Kotlin `assertFailsWith<SpecificException> { ... }` or Kotest
  `shouldThrow<SpecificException> { ... }`.
- Avoid JUnit 4 `@Test(expected = ...)`: it also passes when setup code
  throws.

## Weight

- Tag heavy tests (`@Tag("slow")`) and filter them the project's way, or
  follow its Surefire and Failsafe split.
- In Spring, prefer plain construction or slice tests (`@WebMvcTest`,
  `@DataJpaTest`) to `@SpringBootTest` unless the full context is the
  subject.
- Time limits: `@Timeout`, or `assertTimeoutPreemptively`, which runs the
  code in another thread (mind thread-local state).

## Pre-Fix Runs

- Build the tree from its root so that sibling modules come from the tree
  (`mvn -pl <module> -am test`), not from snapshots of the fixed code in
  `~/.m2` or from a shared build cache (Gradle `--no-build-cache`).
- Force the tests to run (`--rerun-tasks` or `cleanTest`) and confirm the
  executed classes in the reports.
