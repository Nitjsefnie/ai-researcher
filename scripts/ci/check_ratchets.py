#!/usr/bin/env python3
"""Refuse a change that relaxes a ratchet document.

    python3 scripts/ci/check_ratchets.py <base-rev> <head-rev>
        [--allow-declared-raises]

Both sides of each document are read as data with ``git show
<rev>:<path>`` at the merge base of the two revisions and at the head —
never from the working tree, and no head code is executed. The merge
base, not the base tip, is the reference: the automated raise lands on
main after a branch forks, and the branch did not loosen anything by
missing that raise.

Exit 0 when nothing is relaxed, 1 with one line per relaxation, 2 on a
usage error, an unknown revision, a shallow clone — refused up front,
because a shallow history can make ``git merge-base`` fail or return a
wrong base without erroring, and the fix is to fetch full history
(``git fetch --unshallow``) — a merge base that cannot be computed
(unrelated histories), or a document that is not valid JSON. A document
absent at the merge base cannot be relaxed; the sibling checks (thresholds
``--check``, the coverage gates, the perf budgets gate) judge its
content. A non-regular entry at the head is a finding (exit 1) — it is
the branch's own change; a non-regular entry at the merge base is a git
error (exit 2).

Three documents are guarded, each with its own direction rules:

- ``.github/ci-thresholds.json`` — every coverage value (``measured``
  and ``floor``, for both languages) may only rise, and
  ``schema_version`` may not change at all. The one value-direction
  subtlety is the raise itself: the ratchet rewrites the document so
  ``floor = measured - 1.5``, so a changed measurement must carry the
  floor it implies — a measured that rose while its floor stayed below
  ``measured - 1.5`` would lower the effective floor, and is a finding.
- ``.github/perf-budgets.json`` — every value is an integer MAXIMUM the
  gates hold a measurement under, so every numeric leaf except
  ``schema_version`` may only FALL: lowering a budget tightens, raising
  one relaxes. ``schema_version`` may not change at all.
- ``.github/instruction-budgets.json`` — the pipeline's instruction
  counts (issue #110), under the perf budgets' direction rules: every
  value is an integer MAXIMUM of a target's startup-subtracted callgrind
  total, so every leaf except ``schema_version`` may only fall.

  Key added and key removed are findings in every guarded document — a
  PR must not be able to mask a raise behind a reshuffle.

A deliberate budget raise has exactly one route onto main (issue #120,
widened by #133 to a pull request): the raise lands as its own commit —
on a fast-forward push of main, or as a pull request's commit — and the
raise commit's message carries one declaration line per raised leaf,

    Budget-Raise: <document> <key> <from> -> <to>

with the exact values the diff carries. The workflow invokes the guard
with --allow-declared-raises on both shapes: the push branch passes
--route push (the default), the pull-request branch --route pr. The
lines are collected from the window base..head — on a push that is
exactly the push's own commits because the base is an ancestor of the
head (enforced: without the ancestor relationship the route stays shut,
``declarations apply only on a fast-forward push of main``); on a pull
request the base is the merge commit's first parent, so base..head is
exactly the pull request's own commits by construction. On both routes
the lines count only from commits touching nothing outside the two
budget documents: the route is its own act, and a raise cannot ride
feature work onto main. Every raised budget leaf needs a declaration
naming it exactly: a raise with no declaration refuses, and so does a
declaration the diff does not carry exactly — a mismatched value, a
duplicate, a key that did not rise, a non-finite token, or one naming
the coverage document (whose raises are the ratchet's own automated act
and whose relaxations refuse everywhere; only the two budget documents'
raises are declarable). Merge shape matters on the PR route: a rebase
merge keeps the raise commit's lines, while a squash merge may replace
them with the pull request's title — GitHub's squash message can also
prefill the commit's own message, so the lines are not always lost —
but a squash that drops them makes the raise refuse on main's push.
A rebase merge is the deterministic route.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

DOCUMENT = '.github/ci-thresholds.json'
BUDGETS = '.github/perf-budgets.json'
INSTRUCTION_BUDGETS = '.github/instruction-budgets.json'
REGULAR_FILE = '100644 blob'
GAP = Decimal('1.5')
# The push route for a deliberate raise (issue #120): one line per
# raised leaf in the raise commit's message, naming the exact values the
# diff carries. Only these documents' raises may be declared.
DECLARABLE_DOCUMENTS = (BUDGETS, INSTRUCTION_BUDGETS)
_DECLARATION_PREFIX = 'Budget-Raise: '
_DECLARATION_LINE = re.compile(
    r'^(?P<document>\S+) +(?P<key>.+) +(?P<was>\S+) -> (?P<to>\S+)$')
# Direction each leaf may move: "up" means it may only rise, "down" means
# it may only fall, "fixed" means it may not change at all.
_DIRECTIONS = {
    'schema_version': 'fixed',
    'coverage.python.measured': 'up',
    'coverage.python.floor': 'up',
    'coverage.javascript.measured': 'up',
    'coverage.javascript.floor': 'up',
}
_LANGUAGES = ('python', 'javascript')


def _budget_direction(key):
    """The budgets document's direction for one leaf path.

    Every other value in the perf-budgets document is an integer maximum
    a gate holds a measurement under: lowering it tightens the ratchet,
    raising it relaxes. schema_version alone may not change at all.
    """
    if key == 'schema_version':
        return 'fixed'
    return 'down'


def _is_number(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, Decimal):
        return value.is_finite()
    if isinstance(value, int):
        return True
    # A float here is a JSON NaN/Infinity literal: the reader's
    # parse_constant hands those back as floats, past the parse_float
    # hook that would have made them Decimals. They must fail closed --
    # NaN and -Infinity never compare greater, so a poisoned budget
    # would pass the down-only walk silently, and +Infinity would
    # masquerade as a genuine raise instead of naming the non-finite
    # leaf.
    return isinstance(value, float) and math.isfinite(value)


def _decimal(value):
    """The value as a Decimal, so the gap arithmetic cannot mix types."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _show(value):
    if value is None:
        return 'absent'
    if isinstance(value, bool):
        return json.dumps(value)
    if isinstance(value, Decimal):
        return str(value)
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return repr(value)


def _key_path(parts):
    if not parts:
        return '(document)'
    rendered = []
    for index, part in enumerate(parts):
        if part.replace('_', 'a').isalnum() and not part[0].isdigit():
            rendered.append(part if index == 0 else f'.{part}')
        else:
            rendered.append(f'[{json.dumps(part)}]')
    return ''.join(rendered)


def leaves(value, parts=None, out=None):
    """Leaf values keyed by their dotted path.

    A non-object or an empty object anywhere (including the document
    itself) is a leaf, so a subtree replaced by a scalar shows up as its
    leaves removed and one key added, and an added empty object is still
    an added key.
    """
    if parts is None:
        parts = []
    if out is None:
        out = {}
    if not isinstance(value, dict) or not value:
        out[_key_path(parts)] = value
        return out
    for key, child in value.items():
        leaves(child, [*parts, key], out)
    return out


def _finding(document, key, base, head, why):
    return (f'{document}: {key}: merge base {_show(base)}, '
            f'head {_show(head)} — {why}')


def _deleted(document):
    return _finding(document, '(document)', 'present', None,
                    'the document was deleted')


def _implied_floor_findings(before, after, document):
    """A changed measurement must carry the floor it implies.

    The ratchet writes ``floor = measured - 1.5`` on every raise, so a
    changed measurement whose floor no longer equals that difference is
    not a document the ratchet would have written: with the floor below
    the implied value the gate would pass runs the recorded measurement
    says are worse.
    """
    findings = []
    for language in _LANGUAGES:
        measured_key = f'coverage.{language}.measured'
        floor_key = f'coverage.{language}.floor'
        measured = after.get(measured_key)
        floor = after.get(floor_key)
        if before.get(measured_key) == measured:
            continue
        if not (_is_number(measured) and _is_number(floor)):
            continue
        if _decimal(floor) != _decimal(measured) - GAP:
            findings.append(_finding(
                document, floor_key, before.get(floor_key), floor,
                f'is not the floor implied by measured {measured}: a '
                f'changed measurement must carry floor = measured - '
                f'{GAP}'))
    return findings


def _relaxations(base, head, document, direction_of, cross_checks,
                 declarations=None):
    """Findings for a head document that relaxes the merge base's.

    ``document`` names the checked path in the finding lines;
    ``direction_of`` answers a leaf's dotted path with the one direction
    that leaf may move in (None: any change at all is a finding); each
    cross-check receives ``(before, after, document)`` and adds the
    document's own shape rules on top of the direction walk.

    ``declarations`` is the raise route's side of the deal (issue #120):
    the parsed Budget-Raise lines naming THIS document — a list when the
    route is open (possibly empty), None when it is closed. A raise a
    line names exactly is clean; a leftover line is a finding.
    """
    if base is None:
        return []
    if head is None:
        return [_deleted(document)]
    findings = []
    before = leaves(base)
    after = leaves(head)
    for key, was in before.items():
        if key not in after:
            findings.append(_finding(document, key, was, None, 'key removed'))
    for key, now in after.items():
        if key not in before:
            findings.append(_finding(document, key, None, now, 'key added'))
            continue
        was = before[key]
        if not _is_number(now):
            findings.append(
                _finding(document, key, was, now, 'not a finite number'))
            continue
        if was == now:
            continue
        direction = direction_of(key)
        if direction is None:
            findings.append(_finding(
                document, key, was, now,
                'changed, and has no tightening direction'))
        elif not _is_number(was):
            findings.append(_finding(
                document, key, was, now,
                'merge-base value is not a finite number'))
        elif direction == 'up' and now < was:
            findings.append(_finding(
                document, key, was, now, 'lowered; it may only rise'))
        elif direction == 'down' and now > was:
            if declarations is not None and _consume_declaration(
                    declarations, key, was, now):
                continue
            findings.append(_finding(
                document, key, was, now, 'raised; it may only fall'))
        elif direction == 'fixed':
            findings.append(_finding(
                document, key, was, now, 'schema_version changed'))
    for cross_check in cross_checks:
        findings.extend(cross_check(before, after, document))
    for _decl_document, key, was, to in declarations or ():
        findings.append(_declaration_mismatch(document, key, was, to))
    return findings


def coverage_relaxations(base, head, document=DOCUMENT):
    """Findings for a head thresholds document that relaxes the base's.

    ``document`` names the checked path in the finding lines; the default
    is the canonical ratchet document, and ``thresholds.py --check``
    passes the path it compared so a finding always names the file it is
    about.
    """
    return _relaxations(base, head, document, _DIRECTIONS.get,
                        (_implied_floor_findings,))


def budgets_relaxations(base, head, document=BUDGETS):
    """Findings for a head budgets document that relaxes the base's.

    Every budget is an integer maximum, so the relaxation is the RAISE:
    a budget that moved up lets worse measurements through the gates; a
    lowered budget is the ratchet tightening itself and is clean.
    """
    return _relaxations(base, head, document, _budget_direction, ())


def instruction_budgets_relaxations(base, head, document=INSTRUCTION_BUDGETS):
    """Findings for a head instruction-budgets document that relaxes the
    base's (issue #110).

    Same shape as the perf budgets -- integer maxima the gate holds a
    measured instruction count under -- so the same direction resolver
    applies: the relaxation is the RAISE.
    """
    return _relaxations(base, head, document, _budget_direction, ())


# The guarded documents, in the order the guard walks and reports them:
# each entry is (path, direction resolver, cross-checks).
DOCUMENTS = (
    (DOCUMENT, _DIRECTIONS.get, (_implied_floor_findings,)),
    (BUDGETS, _budget_direction, ()),
    (INSTRUCTION_BUDGETS, _budget_direction, ()),
)


def _declaration_mismatch(document, key, was, to):
    """The finding for a leftover declaration line.

    A leftover is a declaration the diff does not carry exactly: a
    mismatched value, a duplicate, or a key that did not rise. A line
    naming a non-declarable document never reaches a walk — check_ratchets
    reports that one itself.
    """
    return (f'{document}: {key}: declaration {was} -> {to} does not match '
            'a raise in this diff — a declaration must name the exact from '
            'and to the diff carries')


def _consume_declaration(declarations, key, was, now):
    """Pop the one declaration naming this raise exactly; True when found.

    ``declarations`` is this walk's own pool, already filtered to the
    document under check; the pop is what makes a duplicate line a
    leftover.
    """
    for index, (_document, decl_key, decl_was, decl_to) in enumerate(
            declarations):
        if decl_key == key and decl_was == was and decl_to == now:
            del declarations[index]
            return True
    return False


def _declaration_parse_error(line):
    return (f'Budget-Raise declaration {line!r} does not parse — the '
            "format is 'Budget-Raise: <document> <key> <from> -> <to>'")


def _parse_declarations(lines):
    """Parse raw declaration lines to (document, key, was, to) tuples.

    Returns ``(declarations, errors)``: a malformed line is a finding,
    never a crash, and never a consumable.
    """
    declarations = []
    errors = []
    for line in lines:
        match = _DECLARATION_LINE.match(line[len(_DECLARATION_PREFIX):])
        if match is None:
            errors.append(_declaration_parse_error(line))
            continue
        try:
            was = Decimal(match.group('was'))
            to = Decimal(match.group('to'))
        except InvalidOperation:
            errors.append(_declaration_parse_error(line))
            continue
        # A non-finite token — quiet NaN, sNaN, an Infinity — is a
        # parse error: an sNaN here would raise InvalidOperation on the
        # very comparison the consumption makes, and a NaN would never
        # match anything. Neither is a value this format carries.
        if not (was.is_finite() and to.is_finite()):
            errors.append(_declaration_parse_error(line))
            continue
        declarations.append(
            (match.group('document'), match.group('key'), was, to))
    return declarations, errors


def _commits_with_declaration_lines(cwd, base, head):
    """(sha, raw declaration lines) for each window commit carrying any.

    The caller opens the window: this runs only when the route is
    allowed and base is an ancestor of head, so base..head is exactly
    the push's own commits. The whole message is scanned; only exact
    'Budget-Raise: '-prefixed lines count.
    """
    result = _git(cwd, ['log', '--format=%x00%H%n%B', f'{base}..{head}'])
    if result.returncode != 0:
        raise ValueError(
            f'cannot walk {base}..{head} for declarations: '
            f'{result.stderr.strip()}')
    found = []
    for record in result.stdout.split('\0'):
        if not record:
            continue
        sha, _newline, body = record.partition('\n')
        lines = [line.strip() for line in body.splitlines()
                 if line.strip().startswith(_DECLARATION_PREFIX)]
        if lines:
            found.append((sha, lines))
    return found


def _commit_paths(cwd, base, head):
    """The paths each window commit touches, as {sha: [paths]}.

    A commit that changed nothing lists no paths, and is pure by that
    answer.
    """
    result = _git(cwd, ['log', '--format=%x00%H%n', '--name-only',
                        f'{base}..{head}'])
    if result.returncode != 0:
        raise ValueError(
            f'cannot walk {base}..{head} for its paths: '
            f'{result.stderr.strip()}')
    paths_by_commit = {}
    for record in result.stdout.split('\0'):
        if not record:
            continue
        lines = [line for line in record.split('\n') if line]
        paths_by_commit[lines[0]] = lines[1:]
    return paths_by_commit


def _collect_declarations(cwd, base, head):
    """The parsed declarations by document, plus the findings for the
    lines that can never be consumed: a line on a commit that touches
    anything outside the two budget documents (the route is its own
    act — this is what keeps a raise from riding feature work onto main
    through a squash merge), a malformed line, or one naming a document
    outside the declarable two.
    """
    paths_by_commit = _commit_paths(cwd, base, head)
    raw = []
    findings = []
    for sha, lines in _commits_with_declaration_lines(cwd, base, head):
        outside = sorted(path for path in paths_by_commit.get(sha, [])
                         if path not in DECLARABLE_DOCUMENTS)
        if outside:
            findings.append(
                'Budget-Raise: commit '
                f'{sha[:12]} carries declaration lines but also touches '
                f'{", ".join(outside)} — a declared raise lands as its own '
                'commit touching only the two budget documents')
            continue
        raw.extend(lines)
    parsed, errors = _parse_declarations(raw)
    findings.extend(errors)
    by_document = {
        document: [declaration for declaration in parsed
                   if declaration[0] == document]
        for document in DECLARABLE_DOCUMENTS
    }
    for document, key, was, to in parsed:
        if document not in DECLARABLE_DOCUMENTS:
            findings.append(
                f'{document}: {key}: declaration {was} -> {to} names a '
                "document whose values are not declarable — only the two "
                "budget documents' raises are")
    return by_document, findings


def _git(cwd, args):
    # The returncode is inspected by every caller, so check=False is the
    # deliberate shape here.
    return subprocess.run(  # pylint: disable=subprocess-run-check
        ['git', *args], cwd=str(cwd), capture_output=True, text=True)


def require_full_history(cwd):
    """A shallow history disqualifies the whole check.

    ``git merge-base`` can fail on one, or worse pick a wrong base without
    erroring, and either answer is one a relaxation could hide behind.
    """
    result = _git(cwd, ['rev-parse', '--is-shallow-repository'])
    if result.returncode != 0:
        raise ValueError(
            f'cannot tell whether the repository is shallow: '
            f'{result.stderr.strip()}')
    if result.stdout.strip() == 'true':
        raise ValueError(
            'the repository is shallow; a shallow history can make git '
            'merge-base return a wrong base without erroring, so the check '
            'refuses to run — fetch full history first (git fetch '
            '--unshallow)')


def resolve_commit(cwd, rev):
    result = _git(
        cwd, ['rev-parse', '--verify', '--quiet', '--end-of-options',
              f'{rev}^{{commit}}'])
    if result.returncode != 0:
        raise ValueError(f'unknown revision: {rev}')
    return result.stdout.strip()


def merge_base(cwd, base, head):
    result = _git(cwd, ['merge-base', base, head])
    sha = result.stdout.strip()
    if result.returncode != 0 or not sha:
        raise ValueError(
            f'no merge base between {base} and {head} (unrelated histories '
            'or a shallow clone)')
    return sha


def _is_ancestor(cwd, maybe_ancestor, descendant):
    """Whether ``maybe_ancestor`` is an ancestor of ``descendant``.

    The declaration route rides a fast-forward push: base..head must be
    exactly the push's own commits, and only an ancestor relationship
    gives that window a well-defined membership. --is-ancestor answers
    through its exit code (0 ancestor, 1 not); any other code is a git
    failure.
    """
    result = _git(cwd, ['merge-base', '--is-ancestor',
                        maybe_ancestor, descendant])
    if result.returncode not in (0, 1):
        raise ValueError(
            f'cannot tell whether {maybe_ancestor} is an ancestor of '
            f'{descendant}: {result.stderr.strip()}')
    return result.returncode == 0


def entry_kind(cwd, commit, path):
    """The ``<mode> <type>`` of the tree entry at ``path``, or None.

    ``git ls-tree`` reads its argument as a pattern — "dir/" lists the
    directory's children — so pathspec magic is off and only a record
    whose name equals ``path`` counts.
    """
    listing = _git(
        cwd, ['--literal-pathspecs', 'ls-tree', '-z', commit, '--', path])
    if listing.returncode != 0:
        raise ValueError(
            f'cannot list {path} at {commit}: {listing.stderr.strip()}')
    for record in listing.stdout.split('\0'):
        tab = record.find('\t')
        if tab == -1 or record[tab + 1:] != path:
            continue
        mode, kind, _object = record[:tab].split(' ', 2)
        return f'{mode} {kind}'
    return None


def read_document(cwd, commit, path):
    """The parsed document at ``commit``, or None when absent there."""
    kind = entry_kind(cwd, commit, path)
    if kind is None:
        return None
    if kind != REGULAR_FILE:
        raise ValueError(f'{path} at {commit} is {kind}, not a regular file')
    blob = _git(cwd, ['show', f'{commit}:{path}'])
    if blob.returncode != 0:
        raise ValueError(
            f'cannot read {path} at {commit}: {blob.stderr.strip()}')
    try:
        return json.loads(blob.stdout, parse_float=Decimal, parse_int=Decimal)
    except json.JSONDecodeError as error:
        raise ValueError(
            f'{path} at {commit} is not valid JSON: {error}') from None


def check_ratchets(cwd, base_rev, head_rev, allow_declared_raises=False,
                   route='push'):
    require_full_history(cwd)
    base = resolve_commit(cwd, base_rev)
    head = resolve_commit(cwd, head_rev)
    fork = merge_base(cwd, base, head)
    findings = []
    by_document = None
    # The push route rides a fast-forward (base an ancestor of head), so
    # base..head is exactly the push's own commits. The PR route needs no
    # ancestor check: its base is the merge commit's first parent, and
    # base..head is the pull request's own commits by construction.
    route_open = allow_declared_raises and (
        route == 'pr' or _is_ancestor(cwd, base, head))
    if route_open:
        by_document, declaration_findings = _collect_declarations(
            cwd, base, head)
        findings.extend(declaration_findings)
    for document, direction_of, cross_checks in DOCUMENTS:
        kind = entry_kind(cwd, head, document)
        if kind is not None and kind != REGULAR_FILE:
            findings.append(_finding(
                document, '(document)', REGULAR_FILE, kind,
                'not a regular file'))
        else:
            base_document = read_document(cwd, fork, document)
            head_document = read_document(cwd, head, document)
            declarations = None
            if by_document is not None and document in by_document:
                declarations = by_document[document]
            findings.extend(_relaxations(
                base_document, head_document, document, direction_of,
                cross_checks, declarations))
    return fork, findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base_rev', help='the base revision (e.g. HEAD^1)')
    parser.add_argument('head_rev', help='the head revision (e.g. HEAD^2)')
    parser.add_argument(
        '--allow-declared-raises', action='store_true',
        help='let a budget raise pass when a Budget-Raise line in '
             'base..head names it exactly')
    parser.add_argument(
        '--route', choices=('push', 'pr'), default='push',
        help='which shape the comparison is: push requires base to be an '
             'ancestor of head (a fast-forward push of main); pr reads '
             'the window as the merge commit\'s own commits (base is '
             'HEAD^1, head HEAD^2)')
    args = parser.parse_args(argv)
    try:
        fork, findings = check_ratchets(
            Path.cwd(), args.base_rev, args.head_rev,
            allow_declared_raises=args.allow_declared_raises,
            route=args.route)
    except ValueError as error:
        print(f'ratchet check: {error}', file=sys.stderr)
        return 2
    if not findings:
        for document, _direction_of, _cross_checks in DOCUMENTS:
            print(f'ratchet check: {document} not relaxed against merge '
                  f'base {fork} — ok')
        return 0
    for line in findings:
        print(line)
    print(f'ratchet check: {len(findings)} relaxation(s) against merge '
          f'base {fork}; the ratchet document may only tighten')
    saw_raise = any('raised; it may only fall' in line for line in findings)
    route_open = (args.allow_declared_raises
                  and (args.route == 'pr'
                       or _is_ancestor(Path.cwd(), args.base_rev,
                                       args.head_rev)))
    if saw_raise and route_open:
        print("ratchet check: a deliberate raise lands as its own commit "
              "touching only the two budget documents, with one line per "
              "raised leaf — "
              "'Budget-Raise: <document> <key> <from> -> <to>' "
              '(CONTRIBUTING.md)')
    elif saw_raise and args.allow_declared_raises:
        print('ratchet check: Budget-Raise declarations apply only on a '
              'fast-forward push of main — this comparison is not one')
    elif saw_raise:
        print("ratchet check: a budget raise needs one Budget-Raise line "
              "per raised leaf, on a commit touching only the two budget "
              'documents — pass --allow-declared-raises (CONTRIBUTING.md)')
    return 1


if __name__ == '__main__':
    sys.exit(main())
