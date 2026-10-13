# English Style Guide for Commit Messages

How to write and polish the English of a commit message, with emphasis on
mistakes that are common in non-native writing, especially literal
translations from Japanese.

## Contents

- [Header](#header)
- [Body](#body)
- [Word Choice](#word-choice)
- [Grammar and Punctuation](#grammar-and-punctuation)
- [Before and After](#before-and-after)

## Header

- Write an imperative verb phrase that completes the sentence "If applied,
  this commit will ...": `add`, `fix`, `remove`, `rename`, `replace`,
  `allow`, `prevent`, `handle`, `support`, `simplify`, `document`.
- Headline style is fine: articles may be dropped when the meaning stays
  clear (`fix(cli): handle missing config file`).
- Name the outcome rather than the activity:
  `fix(io): retry writes interrupted by signals`, not
  `fix(io): fix write problem`.
- Use the vocabulary of the codebase: identifiers, option names, and terms
  spelled exactly as they appear in the code.

## Body

- Write complete, grammatical sentences.
- A reliable structure:
  1. Context or problem: what is wrong or missing, in the present tense
     ("`load()` raises `KeyError` when the cache is empty.").
  2. Change: what the commit does about it, in the imperative mood ("Fall
     back to the default value ...") or in the voice used in the history.
  3. Consequences (optional): side effects, limitations, alternatives that
     were considered, and follow-up work.
- Do not narrate your work ("I changed ...", "First I tried ...") or the
  diff ("Modify foo.c and bar.c.").
- Be concrete: quote error messages, and name the conditions, versions, and
  numbers that the diff or the user provides.
- Do not open the body by repeating the header.

## Word Choice

| Instead of | Write |
|------------|-------|
| `fix bug`, `fix issue`, `fix problem` | the problem itself: `fix crash on empty input` |
| `update X`, `change X`, `modify X` | how it changed: `rename X to Y`, `replace X with Y`, `raise the timeout to 30 seconds` |
| `improve X`, `enhance X` | in what way: `speed up X`, `simplify X`, `clarify X` |
| `correspond to X`, `deal with X` (対応する) | the precise meaning: `support X`, `handle X`, `follow X` |
| `enable to do X` (できるようにする) | `allow users to do X`, `make X configurable`, `enable X` |
| `in case of X` (の場合) | `when X`, `if X` |
| `for doing X` (するため) | `to do X`, `so that ...` |
| `consider X` (考慮する) | `take X into account`, `account for X`, `handle X` |
| `does not work well` (うまく動かない) | the symptom: `hangs`, `crashes`, `returns the wrong value` |
| `and so on`, `etc.` | the items themselves, or `such as` |
| `some`, `various`, `a lot of` | the actual items, or a number |

## Grammar and Punctuation

- **Verb forms**: `does not exist` (not `is not exist` or `not exists`),
  `fails to start` (not `fails starting`), `allow users to configure X` or
  `make X configurable` (not `enable to configure X`).
- **Uncountable nouns** take no plural and no `a`/`an`: code, information,
  documentation, software, hardware, feedback, advice. Write `code` and
  `pieces of information`, never `codes` or `informations`.
- **Articles** in the body: a singular countable noun needs `a`/`an` or
  `the` ("a missing file", "the cache"); generic plurals and uncountable
  nouns usually take none ("files", "memory").
- **Agreement**: "the list of files is sorted", "each entry has", "neither
  option works".
- **Tense**: the present for current behavior, the imperative for the
  change, and the past only for history ("Commit 1a2b3c4 introduced ...").
- **Punctuation**: ASCII only (`,` `.` `:` `(` `)` `'` `"` and ordinary
  spaces). Never use `、` `。` `，` `．` `：` `（` `）` or full-width spaces.
- **Capitalization**: do not capitalize common nouns in the middle of a
  sentence (`config file`, not `Config File`). Spell names the way their
  owners do: `GitHub`, `JavaScript`, `macOS`, `Node.js`, `PostgreSQL`,
  `YAML`.
- **Sentence spacing**: use one or two spaces after a period, as the
  history does, and be consistent within the message.
- **Sentence length**: split sentences longer than about 25 words, and avoid
  long chains of `and`.
- **Pronouns**: replace an ambiguous `it` or `this` with the noun it refers
  to.
- **Abbreviations**: `e.g.` means "for example" and `i.e.` means "that is";
  do not mix them up. Write `cannot` as one word.

## Before and After

Headers:

| Before | After |
|--------|-------|
| `fix: Fixed the bug that program crashes when config file is not exist.` | `fix(config): do not crash when the config file is missing` |
| `feat: enable to specify the timeout` | `feat(client): make the request timeout configurable` |
| `fix: correspond to the case that the list is empty` | `fix: handle empty lists` |
| `refactor: modify some codes for readability` | `refactor(parser): split parse() into smaller functions` |
| `docs: update README.md` | `docs(readme): document installation on macOS` (state what the update is) |
| `feat: add the function that user can export data as CSV` | `feat(export): allow exporting reports as CSV` |

Body, before:

```text
In this commit, I modified foo.c and bar.c. I changed the function baz
to return error when write is failed because there was a problem.
```

Body, after:

```text
baz() ignores write errors, so callers cannot tell that data has not
been saved, e.g., when the disk is full.

Return -EIO from baz() when a write fails, and propagate the error to
its callers.
```
