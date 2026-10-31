# Ruby

## Tooling

- RSpec (`spec/`, `.rspec`): `bundle exec rspec path/to_spec.rb:42`,
  `--order random`, `--seed <n>`, `--profile`. Minitest (`test/`):
  `bundle exec rake test`, or `bundle exec ruby -Itest path/to_test.rb -n
  /name/`; Minitest randomizes the order by default and prints the seed.
  Rails: `bin/rails test`.
- Always run through `bundle exec` so that the project's gems are used.

## Public API

- Public methods of documented classes and modules are the API. `private`
  and `protected` methods, `private_constant` constants, and methods
  documented as `@api private` are implementation details.
- Not allowed: `send(:private_method)`, `__send__`, `instance_variable_get`
  or `instance_variable_set`, `instance_eval` or `class_eval` to reach
  internals, reopening classes in tests to add accessors, stubbing the
  unit's own methods (`allow(subject).to receive(:helper)`), and
  `expect_any_instance_of`.

## Seams

- Constructor and keyword-argument injection. RSpec `instance_double` and
  `class_double` verify doubles against the real interface of injected
  collaborators.
- Time: `ActiveSupport::Testing::TimeHelpers#travel_to` or Timecop control
  the process-wide clock; restore it (`travel_back`, `Timecop.return`).
- HTTP: a local server when the base URL is configurable. WebMock and VCR
  intercept at the HTTP-library level and are acceptable when the project
  already uses them.
- Files: `Dir.mktmpdir` with a block. Environment: ClimateControl, or save
  and restore the `ENV` entries a test changes.

## Isolation

- `let` values are memoized per example; `before(:all)` and
  `before(:context)` state is shared and must stay read-only.
- Rails transactional tests roll back database changes per test, but code
  that uses other threads or connections can escape the transaction.
- Restore global state such as `Rails.cache`, class-level instance
  variables, and `ENV`.

## Error Cases

- `expect { action }.to raise_error(SpecificError, /message/)`, never a
  bare `raise_error`; Minitest `assert_raises(SpecificError) { ... }`,
  which returns the exception for further checks.
- Check validation failures through the model's public `errors` API.

## Weight

- Browser-driven system and feature tests are heavy; use model, request, or
  unit tests when the behavior does not need a browser. Tag slow examples
  and filter them (`--tag ~slow`).

## Pre-Fix Runs

- Run `bundle install` in the tree when its lockfile differs. `path:` gems
  in the Gemfile may point at the original checkout; check
  `Gem.loaded_specs["name"].full_gem_path` under `bundle exec`.
