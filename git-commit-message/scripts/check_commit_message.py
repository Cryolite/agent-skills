#!/usr/bin/env python3
"""Check a commit message against Conventional Commits 1.0.0 and git conventions.

The message is read from FILE, or from standard input when FILE is omitted or
is "-".  Each problem is reported as an "error" (a violation of the
specification or of a hard limit) or a "warning" (probably worth fixing, but
possibly acceptable).  A summary line shows how the message was parsed.

Exit status: 0 if there are no errors, 1 if there are errors, 2 on usage
errors.
"""

import argparse
import re
import sys

DEFAULT_TYPES = ("build", "chore", "ci", "docs", "feat", "fix", "perf",
                 "refactor", "revert", "style", "test")

HEADER_RE = re.compile(r"^(?P<type>[A-Za-z]+)(?:\((?P<scope>[^()]*)\))?"
                       r"(?P<bang>!)?: (?P<description>.*)$")
HEADER_PREFIX = r"^[A-Za-z]+(?:\([^()]*\))?!?"
FOOTER_RE = re.compile(r"^(?P<token>BREAKING CHANGE|[A-Za-z][A-Za-z0-9-]*)"
                       r"(?:: | #)")
BREAKING_LIKE_RE = re.compile(r"^breaking[ -]change\s*:", re.IGNORECASE)
BREAKING_RE = re.compile(r"^BREAKING[ -]CHANGE: \S")
MR_REF_NO_COLON_RE = re.compile(r"^(?P<token>[A-Za-z][A-Za-z0-9-]*)\s+!\d+")
SPACED_TOKEN_RE = re.compile(r"^[A-Z][a-z]*(?: [a-z]+){1,2}: \S")
WIDE_CHAR_RE = re.compile("[\u3000-\u303f\u3040-\u30ff\u3400-\u4dbf"
                          "\u4e00-\u9fff\uac00-\ud7af\uff00-\uffef]")
URL_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://")
FIRST_WORD_RE = re.compile(r"[A-Za-z]+")

# Footer tokens without a hyphen that are still recognizable as footers when
# they appear in a paragraph other than the last one.
KNOWN_FOOTER_TOKENS = {"breaking change", "breaking-change", "bug", "cc",
                       "close", "closed", "closes", "fix", "fixed", "fixes",
                       "ref", "refs", "resolve", "resolved", "resolves",
                       "see"}

THIRD_PERSON_VERBS = {
    "adds", "adjusts", "allows", "avoids", "bumps", "changes", "cleans",
    "converts", "corrects", "creates", "deletes", "deprecates", "disables",
    "drops", "enables", "ensures", "extracts", "fixes", "handles", "hides",
    "implements", "improves", "increases", "introduces", "lets", "makes",
    "migrates", "modifies", "moves", "optimizes", "prevents", "reduces",
    "refactors", "removes", "renames", "replaces", "restores", "reverts",
    "sets", "shows", "simplifies", "supports", "updates", "upgrades", "uses",
}
# Words that end in "-ed" or "-ing" but are neither past tense nor gerunds.
NOT_PAST_OR_GERUND = {
    "bleed", "breed", "embed", "exceed", "proceed", "shred", "speed",
    "succeed", "bring", "cling", "fling", "sling", "spring", "sting",
    "string", "swing", "thing", "wring",
}

HEADER_HINTS = (
    (r"^(?:fixup|squash|amend)! ",
     "this is an autosquash message for 'git rebase --autosquash', not a "
     "final commit message"),
    (r"^Merge ",
     "this looks like a git-generated merge message; Conventional Commits "
     "does not apply to merge commits"),
    (r'^Revert "',
     "write a revert as 'revert: <description>' with a 'Refs: <commit>' "
     "footer"),
    (HEADER_PREFIX + "\uff1a", "replace the full-width colon with ':'"),
    (HEADER_PREFIX + r":\s*$", "add a description after ': '"),
    (HEADER_PREFIX + r":(?! )", "add a space after ':'"),
    (HEADER_PREFIX + r"\s+:", "remove the whitespace before ':'"),
    (r"^[A-Za-z]+\s+\(", "remove the whitespace between the type and '('"),
    (r"^[A-Za-z]+!\(", "put '!' after the scope, as in 'feat(api)!: '"),
    (r"^[A-Za-z]+\([^()]*$", "close the scope with ')'"),
    (r"^\[", "write the type as 'type(scope): ', not in brackets"),
)


class Report(object):
    def __init__(self):
        self.items = []

    def error(self, line, message):
        self.items.append((line or 0, 0, "error", message))

    def warning(self, line, message):
        self.items.append((line or 0, 1, "warning", message))

    def count(self, severity):
        return sum(1 for item in self.items if item[2] == severity)

    def render(self):
        lines = []
        for line, _, severity, message in sorted(self.items):
            where = "line %d: " % line if line else ""
            lines.append("%s: %s%s" % (severity, where, message))
        return lines


def header_hint(header):
    for pattern, hint in HEADER_HINTS:
        if re.search(pattern, header):
            return hint
    return "expected something like 'feat(parser): add array support'"


def is_non_imperative(word):
    if word in THIRD_PERSON_VERBS:
        return True
    if word in NOT_PAST_OR_GERUND:
        return False
    return bool(re.match(r"^[a-z]{3,}ed$", word)
                or re.match(r"^[a-z]{2,}ing$", word))


def is_known_footer(line):
    match = FOOTER_RE.match(line)
    if not match:
        return False
    token = match.group("token")
    return "-" in token or token.lower() in KNOWN_FOOTER_TOKENS


def split_paragraphs(numbered_lines):
    paragraphs = []
    current = []
    for number, line in numbered_lines:
        if line:
            current.append((number, line))
        elif current:
            paragraphs.append(current)
            current = []
    if current:
        paragraphs.append(current)
    return paragraphs


def check_header(report, number, header, types, types_explicit,
                 max_header_length):
    """Check the header and return its match object (or None)."""
    if len(header) > max_header_length:
        report.error(number, "the header is %d characters long (limit %d)"
                     % (len(header), max_header_length))

    match = HEADER_RE.match(header)
    if not match:
        report.error(number, "the header must have the form "
                     "'type(scope)!: description'; " + header_hint(header))
        return None

    type_ = match.group("type")
    if type_ != type_.lower():
        report.warning(number, "write the type in lowercase: '%s'"
                       % type_.lower())
    if type_.lower() not in types:
        message = "unknown type '%s'; expected one of: %s" % (
            type_, ", ".join(types))
        if types_explicit:
            report.error(number, message)
        else:
            report.warning(number, message)

    scope = match.group("scope")
    if scope is not None:
        if not scope.strip():
            report.error(number, "the scope is empty; name it or remove the "
                         "parentheses")
        else:
            if re.search(r"\s", scope):
                report.warning(number, "the scope contains whitespace; use "
                               "a single noun such as 'parser' or "
                               "'user-settings'")
            if "/" in scope or re.search(r"\.[A-Za-z0-9]{1,4}$", scope):
                report.warning(number, "the scope looks like a file path; "
                               "name the affected component instead")
            if scope != scope.lower():
                report.warning(number, "scopes are usually lowercase: '%s'"
                               % scope.lower())

    description = match.group("description")
    if not description.strip():
        report.error(number, "the description is empty")
        return match
    if description[0].isspace():
        report.error(number, "the description must immediately follow ': '; "
                     "remove the extra whitespace")
        return match
    if description.endswith(".") and not description.endswith(".."):
        report.warning(number, "remove the trailing period from the "
                       "description")

    word_match = FIRST_WORD_RE.match(description)
    if word_match:
        word = word_match.group(0)
        if word[0].isupper() and sum(1 for c in word if c.isupper()) == 1:
            report.warning(number, "start the description with a lowercase "
                           "letter, unless '%s' is a proper noun or the "
                           "repository capitalizes descriptions" % word)
        if is_non_imperative(word.lower()):
            report.warning(number, "use the imperative mood ('add', not "
                           "'added', 'adds', or 'adding'): '%s'" % word)
        if word.lower() == type_.lower():
            report.warning(number, "the description repeats the type '%s'; "
                           "describe the change more specifically" % type_)
    return match


def check(text, types, types_explicit, max_header_length, max_line_length):
    """Check a commit message and return (report, summary)."""
    report = Report()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]

    # Like git, ignore leading and trailing blank lines.
    start = 0
    while start < len(lines) and not lines[start]:
        start += 1
    end = len(lines)
    while end > start and not lines[end - 1]:
        end -= 1
    if start == end:
        report.error(None, "the message is empty")
        return report, "nothing to parse"

    numbered = [(index + 1, lines[index]) for index in range(start, end)]
    header_number, header = numbered[0]
    rest = numbered[1:]

    match = check_header(report, header_number, header, types,
                         types_explicit, max_header_length)

    if rest and rest[0][1]:
        report.error(rest[0][0], "separate the header from the body with a "
                     "blank line")

    for number, line in numbered:
        wide = WIDE_CHAR_RE.search(line)
        if wide:
            report.warning(number, "the line contains a CJK or full-width "
                           "character ('%s'); write the message in English "
                           "with ASCII punctuation" % wide.group(0))

    for number, line in rest:
        if line.startswith("#"):
            report.warning(number, "the line starts with '#', which git "
                           "removes as a comment when the message is edited "
                           "in an editor")
        if (len(line) > max_line_length and not URL_RE.search(line)
                and re.search(r"\s", line.strip())):
            report.warning(number, "the line is %d characters long (limit "
                           "%d); wrap it" % (len(line), max_line_length))
        if BREAKING_LIKE_RE.match(line) and not BREAKING_RE.match(line):
            report.error(number, "write a breaking change as 'BREAKING "
                         "CHANGE: <description>' (uppercase, then ': ' and "
                         "a description)")
        mr_no_colon = MR_REF_NO_COLON_RE.match(line)
        if (mr_no_colon and mr_no_colon.group("token").lower()
                in KNOWN_FOOTER_TOKENS):
            report.warning(number, "use ': ' separator for merge request "
                           "references (e.g., '%s: !...'): Conventional "
                           "Commits requires ': ' before '!'"
                           % mr_no_colon.group("token"))

    paragraphs = split_paragraphs(rest)
    body_paragraphs = paragraphs
    footer_block = []
    if paragraphs and FOOTER_RE.match(paragraphs[-1][0][1]):
        body_paragraphs = paragraphs[:-1]
        footer_block = paragraphs[-1]

    for paragraph in body_paragraphs:
        for number, line in paragraph:
            if BREAKING_RE.match(line):
                report.error(number, "move this BREAKING CHANGE footer into "
                             "the last paragraph, together with the other "
                             "footers")
        if all(is_known_footer(line) for _, line in paragraph):
            report.warning(paragraph[0][0], "this paragraph looks like "
                           "footers, but only the last paragraph is read as "
                           "footers; remove blank lines between footers")

    footers = []
    has_breaking_footer = False
    for number, line in footer_block:
        footer = FOOTER_RE.match(line)
        if footer:
            footers.append(footer.group("token"))
            if BREAKING_RE.match(line):
                has_breaking_footer = True

    if paragraphs and (footer_block
                       or SPACED_TOKEN_RE.match(paragraphs[-1][0][1])):
        for number, line in paragraphs[-1]:
            if SPACED_TOKEN_RE.match(line) and not BREAKING_LIKE_RE.match(line):
                report.warning(number, "footer tokens use '-' instead of "
                               "spaces (e.g., 'Reviewed-by')")

    if not match:
        return report, "header not parsed"

    bang = bool(match.group("bang"))
    if bang and not has_breaking_footer:
        report.warning(header_number, "the header has '!' but there is no "
                       "'BREAKING CHANGE:' footer; add one that explains the "
                       "impact and migration unless the description already "
                       "does")
    if has_breaking_footer and not bang:
        report.warning(header_number, "there is a 'BREAKING CHANGE:' footer; "
                       "consider adding '!' before ':' in the header")

    summary = "type=%s, scope=%s, breaking=%s, body paragraphs=%d, footers=%s" % (
        match.group("type"),
        match.group("scope") if match.group("scope") is not None else "(none)",
        "yes" if bang or has_breaking_footer else "no",
        len(body_paragraphs),
        ", ".join(footers) if footers else "(none)")
    return report, summary


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Check a commit message against Conventional Commits "
        "1.0.0 and common git conventions.")
    parser.add_argument(
        "file", nargs="?", default="-",
        help="file containing the message ('-' or omitted: standard input)")
    parser.add_argument(
        "--types", metavar="LIST",
        help="comma-separated list of allowed types; unknown types become "
        "errors (default: %s, where unknown types are only warnings)"
        % ",".join(DEFAULT_TYPES))
    parser.add_argument(
        "--max-header-length", metavar="N", type=int, default=72,
        help="maximum header length (default: %(default)s)")
    parser.add_argument(
        "--max-line-length", metavar="N", type=int, default=72,
        help="maximum length of body and footer lines (default: "
        "%(default)s)")
    args = parser.parse_args(argv)
    if args.file == "-" and sys.stdin.isatty():
        parser.error("no input: pass a file or pipe the message to standard "
                     "input")
    return args


def main(argv=None):
    args = parse_args(argv)
    if args.types is None:
        types, types_explicit = DEFAULT_TYPES, False
    else:
        types = tuple(t.strip().lower() for t in args.types.split(",")
                      if t.strip())
        types_explicit = True

    if args.file == "-":
        data = sys.stdin.buffer.read()
    else:
        try:
            with open(args.file, "rb") as stream:
                data = stream.read()
        except (IOError, OSError) as exc:
            sys.stderr.write("error: cannot read %s: %s\n" % (args.file, exc))
            return 2
    text = data.decode("utf-8", "replace")

    report, summary = check(text, types, types_explicit,
                            args.max_header_length, args.max_line_length)
    for line in report.render():
        print(line)
    print("summary: " + summary)
    errors, warnings = report.count("error"), report.count("warning")
    if errors or warnings:
        print("result: %d error(s), %d warning(s)" % (errors, warnings))
    else:
        print("result: OK")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
