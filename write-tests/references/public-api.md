# Public API

Tests exercise a unit through its public API and check only observable
behavior. This reference explains how to find that API, what counts as an
implementation detail, which test doubles are allowed, and what to do when
the public API seems insufficient.

## Find the Unit and Its Consumers

"Public" is relative to a unit and to the code meant to use it.

| Unit | Intended consumers | Public API |
|---|---|---|
| Library or package | Code outside it | Exported and documented symbols; documented formats, commands, and configuration |
| Component of an application | Other components of the application | What other components are meant to call, such as Python names without a leading underscore, or module-internal declarations that other files of a Swift or C# application use |
| Command-line program | Users and scripts | Arguments, options, standard input and output, exit status, files read and written, documented environment variables |
| Service | Clients | Endpoints, messages, schemas, documented errors |

Choose the unit from the request, the project's structure, and how the
existing tests are organized. Anything only the unit itself uses is an
implementation detail, even when the language lets tests reach it.

Weigh the evidence in this order: documentation and export declarations
(`__all__`, public headers, `export`, `pub use`, `module-info.java`),
visibility keywords and naming conventions, use from outside the unit
(search for callers), and the project's conventions. When the evidence
conflicts, or the choice changes what you would test, ask; otherwise record
the decision in the report.

Module-internal visibility (Java package-private, Kotlin and C# `internal`,
Swift `internal` and `package`, Rust `pub(crate)`, TypeScript `@internal`)
is an implementation detail of a library whose consumers are outside the
module. In an application whose components use each other within one
module, the declarations other components use are those components' API.

## Implementation Details

- Private, file-private, or underscore-prefixed functions, methods, fields,
  and constants; anonymous-namespace and `static` functions in C and C++.
- Internal module layout: helper modules, which module imports what, file
  names.
- Internal state, caches, and intermediate data; the order and number of
  internal calls.
- Logs, metrics, and wording the contract does not promise.
- The choice of algorithm or data structure.

## Not Allowed in Tests

- Importing, calling, reading, or writing implementation details.
- Reaching them through escape hatches: reflection, `friend` or
  `FRIEND_TEST`, `#define private public`, `@testable import` or
  `InternalsVisibleTo` used for more than a component's API, name mangling,
  `send`, `instance_variable_get`, `Closure::bind`, `rewire`,
  `go:linkname`, `unsafe` field access.
- Replacing parts of the unit under test: monkeypatching its functions,
  mocking modules it imports for its own use, partial mocks of the unit,
  or overriding its unexported function variables.
- Asserting on internal calls, internal state, or intermediate values.
- Helpers, fixtures, or data builders that do any of this on a test's
  behalf.
- Copying such patterns from existing tests.

## Not Allowed in Production Code

Do not change production code for the sake of tests: wider visibility,
test-only parameters, flags, branches (`if TESTING`), hooks, accessors for
internal state, `@VisibleForTesting`-style annotations, `friend` or
`InternalsVisibleTo` declarations added for tests, `export_test.go`-style
re-exports, or test bindings that forward private members. This holds even
when the user asks: explain why and offer the alternatives below.

A design change that stands on its own merits, such as making a dependency
injectable because real callers also benefit, is a production change rather
than a test technique. Propose it, and make it only on the user's explicit
request.

## Interactions in the Contract

Assert on an interaction only when the interaction itself is promised and
happens through a public seam: "sends exactly one message to the injected
notifier", "closes the stream it was given", "invokes the callback with the
parsed record". Observe it through the double you injected, never through
the unit's internals.

## Test Doubles and Seams

In order of preference:

1. Real collaborators, when they are fast and deterministic: in-memory data,
   temporary files, local subprocesses.
2. Fakes, stubs, or mocks passed through public injection points:
   constructor or function parameters, configuration, documented
   environment variables, and plugin, callback, or factory interfaces.
3. Environment-level boundaries that do not depend on how the unit is
   built: a temporary directory or `HOME`, a local test server, a protocol
   fake listening on a real port, a test library's process-wide clock or
   randomness control, fake executables placed first on `PATH`, and file
   permissions.

Do not patch names inside the module under test (for example
`mymodule.time.time`, or the unit's own HTTP wrapper), even for time and
randomness: which function the unit calls is an implementation detail.

## When the Public API Is Not Enough

1. Test through a higher public entry point that exercises the behavior,
   checking the cost against [Test weight](test-weight.md).
2. Look for a lighter public unit that contains the logic, such as a
   lower-level public module the target uses.
3. Otherwise stop and report what cannot be verified, why, and design
   options with their trade-offs (extract the logic into its own public
   unit, inject the dependency, expose a supported configuration). Do not
   implement them without the user's explicit request.

## Native Code Tested from Another Language

When testing native code from another language needs a test-support binding
(for example, a C++ core tested from Python), the binding exposes only the
native component's public API. A binding that forwards private members is a
test-only window into implementation details.
