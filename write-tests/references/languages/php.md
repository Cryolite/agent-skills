# PHP

## Tooling

- PHPUnit (`phpunit.xml` or `phpunit.xml.dist`): `vendor/bin/phpunit
  --filter <name>`, `--testsuite`, `--group` and `--exclude-group`,
  `--order-by=random` with `--random-order-seed`. Pest: `vendor/bin/pest
  --filter`, `--group`, `--parallel`. Laravel: `php artisan test`.
- Run PHPStan or Psalm on tests when the project does.

## Public API

- Public methods and properties of documented classes, plus `protected`
  members documented as extension points. `private` members and elements
  marked `@internal` are implementation details.
- Not allowed: `ReflectionMethod` or `ReflectionProperty` with
  `setAccessible(true)`, `Closure::bind` or `Closure::call` into an object's
  scope, partial mocks that stub the unit's own methods, and widening
  `private` to `protected` or `public` for tests.

## Seams

- Constructor injection of interfaces, especially PSR interfaces (the
  PSR-18 HTTP client, the PSR-20 `ClockInterface`), doubled with
  `createStub` or `createMock`.
- Time: an injected PSR-20 clock or Symfony `MockClock`. Carbon
  `Carbon::setTestNow()` is process-wide and must be reset in `tearDown`.
- HTTP: Guzzle `MockHandler` or Symfony `MockHttpClient`, passed into a
  client the API accepts.
- Files: a unique directory under `sys_get_temp_dir()`, or vfsStream.

## Isolation

- PHPUnit creates a test-case object per test method, but static properties
  and globals persist; avoid them or restore them in `tearDown`. Use
  `#[RunInSeparateProcess]` only when process-wide state cannot be
  restored, and accept the extra weight.
- Laravel's `RefreshDatabase` and `DatabaseTransactions` traits isolate
  database changes.

## Error Cases

- `$this->expectException(SpecificException::class)` before the call, with
  `expectExceptionMessage` or `expectExceptionCode` when promised. Code
  after the throwing call does not run, so check the state after failure in
  another test, or with `try`/`catch` and `fail()`.
- Assert PHP warnings and deprecations with the facilities of the PHPUnit
  version in use.

## Weight

- PHPUnit size attributes (`#[Small]`, `#[Medium]`, `#[Large]`) enforce
  time limits when `enforceTimeLimit` is enabled and `phpunit/php-invoker`
  is installed. Use `#[Group('slow')]` for the project's slow suite.
- Prefer unit tests to Laravel HTTP feature tests, and those to browser
  tests (Dusk), unless the behavior needs the heavier level.

## Pre-Fix Runs

- Run `composer install` in the tree, which gets its own `vendor/`. Path
  repositories may symlink to the original checkout. Clear framework caches
  in the tree (`bootstrap/cache`, `var/cache`).
