# C#

## Tooling

- `dotnet test` on the solution or a test project. Frameworks: xUnit,
  NUnit, MSTest; assertions with FluentAssertions or Shouldly; doubles with
  Moq, NSubstitute, or FakeItEasy.
- Select with `--filter` (`FullyQualifiedName~Namespace.Class.Method`,
  `Category=Slow`, xUnit `[Trait]` values), list with `--list-tests`, and
  get timings from a `trx` logger or detailed console verbosity.

## Public API

- Public: `public` types and members of the assembly, plus `protected`
  members documented as extension points. `internal` is an implementation
  detail of a library; in an application, internal types that other
  components use are those components' API.
- `InternalsVisibleTo` exists to let tests see internals. Do not add it for
  tests. Where it already exists, use it only for internal types that other
  components consume, never for members that only their own type uses.
- Not allowed: reflection with `BindingFlags.NonPublic`, `PrivateObject`
  and `PrivateType`, partial classes or methods added for tests, and making
  members `virtual` only so that a mocking library can override them.

## Seams

- Inject `TimeProvider` (.NET 8 and later) or a clock interface, and drive
  it with `FakeTimeProvider` from `Microsoft.Extensions.TimeProvider.Testing`
  when the API accepts one.
- `HttpClient` with a stub `HttpMessageHandler`, passed through the
  constructor or `IHttpClientFactory`. For ASP.NET Core,
  `WebApplicationFactory<TEntryPoint>` runs in-process integration tests
  (medium weight).
- Files: a unique directory under `Path.GetTempPath()`, deleted in
  `Dispose`.

## Isolation

- xUnit creates a new class instance per test (setup in the constructor,
  teardown in `Dispose` or `IAsyncLifetime`); class and collection fixtures
  are shared and must stay read-only.
- xUnit runs test collections in parallel by default. Put tests that touch
  environment variables, the current directory, or culture into a
  collection whose `[CollectionDefinition]` sets
  `DisableParallelization = true`, and restore the state.
- NUnit reuses one fixture instance for all tests of a class unless
  `[FixtureLifeCycle(LifeCycle.InstancePerTestCase)]` is set; reset fields
  in `[SetUp]`.
- Set and restore `CultureInfo.CurrentCulture` when formatted output
  matters.

## Error Cases

- xUnit `Assert.Throws<T>` (exact type) or `Assert.ThrowsAsync<T>`; NUnit
  `Assert.That(() => ..., Throws.TypeOf<T>())`; MSTest
  `Assert.ThrowsException<T>` or `Assert.ThrowsExactly<T>`, depending on
  the version; FluentAssertions `act.Should().Throw<T>()`.
- Check the `ParamName` of an `ArgumentException` and error codes when they
  are documented.

## Weight

- Keep heavy tests in separate integration test projects or categories.
- Bound run time with the framework's timeout support for the target
  runtime, or with a `CancellationToken` that has a deadline, passed to the
  API.

## Pre-Fix Runs

- Build the tree on its own; its `bin/` and `obj/` directories live inside
  it. Watch for package references to locally packed builds of the fixed
  code in a local NuGet feed.
