#!/usr/bin/env python3
"""Patch coverage: what the diff added, and which of it the suites reached.

The number this reports is only useful if it is honest in both directions, so
these pin the two ways it could lie. Counting a blank line or a comment as
missed would make the percentage depend on formatting; counting a file the
report never measured would make it depend on which extras a runner resolved.
"""
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))
import diff_coverage  # noqa: E402  # pylint: disable=wrong-import-position

_SCRIPT = REPO_ROOT / "scripts" / "ci" / "diff_coverage.py"


def _run_cli(args, **kwargs):
    """Run the reporter as a child, measured when the job asks for it.

    With COVERAGE_MEASURE_CHILDREN_RC set (the coverage job sets it), the
    child runs under its own `coverage run`: the reporter constructs a
    second Coverage object of its own — the statement analyzer with
    `data_file=None` — and a second construction is fatal to the .pth
    auto-started collector's save, so subprocess measurement cannot be the
    implicit hook. It must be the explicit command, which saves itself.
    """
    rc = os.environ.get("COVERAGE_MEASURE_CHILDREN_RC")
    if rc:
        assert args[0] == sys.executable, args
        args = [sys.executable, "-m", "coverage", "run",
                "--parallel-mode", "--rcfile", rc, *args[1:]]
    env = {key: value for key, value in os.environ.items()
           if key != "COVERAGE_PROCESS_START"}
    kwargs.setdefault("env", env)
    return subprocess.run(args, check=kwargs.pop("check", False), **kwargs)


_SCOPE_NOTE = (
    "Only Python statements are measured. The page's JavaScript ships "
    "inside the built page, not as a source file a coverage report names, "
    "so it has no patch number — the browser suite is what exercises it.")

_COVERAGE_XML = """<?xml version="1.0" ?>
<coverage>
  <packages>
    <package name="pkg">
      <classes>
        <class filename="pkg/mod.py">
          <lines>
            <line number="1" hits="1"/>
            <line number="2" hits="0"/>
            <line number="3" hits="0"/>
            <line number="7" hits="1"/>
          </lines>
        </class>
      </classes>
    </package>
  </packages>
</coverage>
"""

_TWO_FILE_COVERAGE_XML = """<?xml version="1.0" ?>
<coverage><packages><package><classes>
  <class filename="a.py"><lines>
    <line number="1" hits="1"/>
  </lines></class>
  <class filename="b.py"><lines>
    <line number="1" hits="0"/>
  </lines></class>
</classes></package></packages></coverage>
"""

_HALF_COVERED_OUTPUT = f"""### Coverage of this change

**50.0%** of added lines covered (1/2).

| File | Covered | Added | Missed lines |
| --- | ---: | ---: | --- |
| `a.py` | 1 | 1 | — |
| `b.py` | 0 | 1 | 1 |

{_SCOPE_NOTE}
"""

_UPPERCASE_UNMEASURED_OUTPUT = f"""### Coverage of this change

**100.0%** of measured added lines covered (1/1).

| File | Covered | Added | Missed lines |
| --- | ---: | ---: | --- |
| `present.py` | 1 | 1 | — |

The coverage reports did not measure these changed source files:
- `silent.PY`

Every measured added line was reached; the files above were not measured.

{_SCOPE_NOTE}
"""


def _written(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_added_lines_follow_the_new_file_numbering():
    """Context advances the counter, a removed line does not."""
    diff = (
        '--- a/pkg/mod.py\n'
        '+++ b/pkg/mod.py\n'
        '@@ -1,3 +1,4 @@\n'
        ' keep\n'
        '-gone\n'
        '+added_two\n'
        '+added_three\n'
        ' tail\n')
    assert diff_coverage.added_lines(diff) == {'pkg/mod.py': {2, 3}}


def test_added_lines_reads_every_hunk_of_every_file():
    """A second hunk restarts the counter from its own header."""
    diff = (
        'diff --git a/one.py b/one.py\n'
        '--- a/one.py\n'
        '+++ b/one.py\n'
        '@@ -1 +1,2 @@\n'
        ' a\n'
        '+b\n'
        '@@ -10,2 +11,3 @@\n'
        ' c\n'
        '+d\n'
        ' e\n'
        'diff --git a/two.py b/two.py\n'
        '--- a/two.py\n'
        '+++ b/two.py\n'
        '@@ -0,0 +1 @@\n'
        '+only\n')
    assert diff_coverage.added_lines(diff) == {
        'one.py': {2, 12}, 'two.py': {1}}


def test_added_triple_plus_content_stays_in_the_current_file():
    """A source line beginning `+++ ` is not a later file header."""
    diff = (
        'diff --git a/x.py b/x.py\n'
        '--- a/x.py\n'
        '+++ b/x.py\n'
        '@@ -1,0 +2,2 @@\n'
        '+++ value\n'
        '+print(value)\n')
    assert diff_coverage.added_lines(diff) == {'x.py': {2, 3}}


def test_added_lines_decode_git_quoted_paths():
    """Git C-quoted UTF-8 paths join the coverage report spelling."""
    diff = (
        '--- "a/caf\\303\\251.py"\n'
        '+++ "b/caf\\303\\251.py"\n'
        '@@ -1 +1,2 @@\n'
        ' old\n'
        '+new\n')
    assert diff_coverage.added_lines(diff) == {'café.py': {2}}


def test_a_deleted_file_adds_nothing():
    """A deletion adds nothing, and the next file is still measured.

    The deletion is followed by a real addition, because a deletion hunk on
    its own carries no `+` record and would hold however it was parsed.
    """
    diff = (
        'diff --git a/gone.py b/gone.py\n'
        '--- a/gone.py\n'
        '+++ /dev/null\n'
        '@@ -1,2 +0,0 @@\n'
        '-a\n'
        '-b\n'
        'diff --git a/kept.py b/kept.py\n'
        '--- a/kept.py\n'
        '+++ b/kept.py\n'
        '@@ -1,0 +2 @@\n'
        '+added\n')
    assert diff_coverage.added_lines(diff) == {'kept.py': {2}}


def _git(repo, *args):
    """Run one git command inside a fixture repository."""
    return subprocess.run(('git', '-C', str(repo)) + args, check=True,
                          capture_output=True, text=True)


def _git_input(repo, value, *args):
    """Run one git command with exact UTF-8 bytes on standard input."""
    done = subprocess.run(
        ('git', '-C', str(repo)) + args,
        input=value.encode('utf-8'), check=True, capture_output=True)
    return done.stdout.decode('utf-8')


def _source_tree(repo, source, attributes=None):
    """Build a tree containing the real diff coverage module as a blob."""
    source_blob = _git_input(
        repo, source, 'hash-object', '-w', '--stdin').strip()
    ci_tree = _git_input(
        repo,
        f'100644 blob {source_blob}\tdiff_coverage.py\n',
        'mktree').strip()
    scripts_tree = _git_input(
        repo, f'040000 tree {ci_tree}\tci\n', 'mktree').strip()
    entries = f'040000 tree {scripts_tree}\tscripts\n'
    if attributes is not None:
        attributes_blob = _git_input(
            repo, attributes,
            'hash-object', '-w', '--stdin').strip()
        entries += f'100644 blob {attributes_blob}\t.gitattributes\n'
    return _git_input(repo, entries, 'mktree').strip()


def test_real_workflow_diffs_binary_attributed_python_as_text(tmp_path):
    """The producer command overrides a pull-request binary attribute."""
    workflow = (
        REPO_ROOT / '.github' / 'workflows' / 'tests.yml').read_text(
            encoding='utf-8')
    marker = '      - name: Measure the coverage of this change\n'
    _before, found, after = workflow.partition(marker)
    assert found, 'real workflow has no diff coverage measurement step'
    _before, found, after = after.partition('        run: |\n')
    assert found, 'real measurement step has no shell block'
    run_lines = [line[10:] for line in after.splitlines()
                 if line.startswith('          ')]
    start = next(index for index, line in enumerate(run_lines)
                 if line.startswith('git diff '))
    command_lines = [run_lines[start]]
    while command_lines[-1].endswith('\\'):
        command_lines.append(run_lines[start + len(command_lines)])
    command = [
        word for line in command_lines
        for word in line.removesuffix('\\').split()
    ]
    assert command[:2] == ['git', 'diff'], command
    assert command[-2:] == ['>', 'patch.diff'], command
    # The pull request controls .gitattributes on its own tree; --text is
    # the flag that keeps a binary verdict from costing the whole report,
    # and the fixture below is the proof it works.
    assert '--text' in command, command

    repo = tmp_path / 'binary-attribute'
    repo.mkdir()
    _git(repo, 'init', '-q')
    _git(repo, 'config', 'user.email', 'tests@example.invalid')
    _git(repo, 'config', 'user.name', 'Tests')
    module = _SCRIPT.read_text(encoding='utf-8')
    added = 'BINARY_ATTRIBUTE_PROBE = 1\n'
    attributes = 'scripts/ci/diff_coverage.py binary\n'
    base_tree = _source_tree(repo, module)
    base = _git_input(repo, 'base\n', 'commit-tree', base_tree).strip()
    head_tree = _source_tree(repo, module + added, attributes)
    head = _git_input(
        repo, 'head\n', 'commit-tree', head_tree, '-p', base).strip()
    _git(repo, 'update-ref', 'HEAD', head)
    (repo / '.gitattributes').write_text(attributes, encoding='utf-8')

    done = subprocess.run(
        command[:-2], cwd=repo, check=False, capture_output=True, text=True)
    assert done.returncode == 0, (done.stdout, done.stderr)
    patch = done.stdout
    assert 'Binary files ' not in patch, patch
    assert f'+{added}' in patch, patch
    line = len(module.splitlines()) + 1
    parsed = diff_coverage.added_lines(patch)
    assert parsed.get('scripts/ci/diff_coverage.py') == {line}, parsed


def test_a_binary_diff_record_is_refused():
    """A binary record cannot silently erase a changed source path."""
    diff = (
        'diff --git a/pkg/mod.py b/pkg/mod.py\n'
        'Binary files a/pkg/mod.py and b/pkg/mod.py differ\n')
    try:
        diff_coverage.added_lines(diff)
    except ValueError as error:
        assert 'binary diff record' in str(error), str(error)
    else:
        raise AssertionError('binary diff record was silently ignored')


def test_a_removed_line_of_dashes_keeps_the_rest_of_the_file(tmp_path):
    """Git renders a removed `-- ...` line as `--- ...`, not as a header.

    Built from a real `git diff` rather than a written-out string: a
    hand-written fixture is exactly what let this through, because it only
    ever contains the shapes its author already thought of.
    """
    repo = tmp_path / 'dashes'
    repo.mkdir()
    _git(repo, 'init', '-q')
    _git(repo, 'config', 'user.email', 'tests@example.invalid')
    _git(repo, 'config', 'user.name', 'Tests')
    source = repo / 'mod.py'
    source.write_text('a = 1\n-- legacy note\nb = 2\nc = 3\n',
                      encoding='utf-8')
    _git(repo, 'add', '-f', 'mod.py')
    _git(repo, 'commit', '-qm', 'base')
    source.write_text('a = 1\nb = 2\nc = 3\nd = 4\ne = 5\n',
                      encoding='utf-8')
    _git(repo, 'add', '-f', 'mod.py')
    _git(repo, 'commit', '-qm', 'drop the note and append')
    diff = _git(repo, 'diff', '--unified=0', 'HEAD~1', 'HEAD').stdout
    # The record this is about, as git really spells it.
    assert '\n--- legacy note\n' in diff, diff
    assert diff_coverage.added_lines(diff) == {'mod.py': {4, 5}}, diff


def test_executable_lines_keeps_the_best_hit_count(tmp_path):
    """One file split across classes keeps the hit count in either order."""
    for index, lines in enumerate(((0, 4), (4, 0))):
        xml = _written(
            tmp_path, f'split-{index}.xml', f"""<?xml version="1.0" ?>
<coverage><packages><package name="p"><classes>
  <class filename="pkg/mod.py"><lines>
    <line number="1" hits="{lines[0]}"/>
  </lines></class>
  <class filename="pkg/mod.py"><lines>
    <line number="1" hits="{lines[1]}"/>
  </lines></class>
</classes></package></packages></coverage>
""")
        assert diff_coverage.executable_lines(xml) == {
            'pkg/mod.py': {1: 4}}


def test_executable_lines_refuses_incomplete_or_malformed_records(tmp_path):
    """Every line record must carry an integer number and hit count."""
    cases = (
        ('missing-number', '<line hits="0"/>'),
        ('missing-hits', '<line number="2"/>'),
        ('malformed-number', '<line number="second" hits="0"/>'),
    )
    for label, record in cases:
        xml = _written(
            tmp_path, f'{label}.xml',
            '<coverage><class filename="pkg/mod.py"><lines>'
            f'<line number="1" hits="1"/>{record}'
            '</lines></class></coverage>\n')
        try:
            diff_coverage.executable_lines(xml)
        except ValueError:
            pass
        else:
            raise AssertionError(f'{label} line record was accepted')


def test_only_measured_statements_count():
    """Added lines absent from the report are excluded, not counted missed."""
    measured = {'pkg/mod.py': {1: 1, 2: 0, 3: 0, 7: 1}}
    # 4, 5 and 6 are blank/comment lines the report never mentions.
    added = {'pkg/mod.py': {1, 2, 4, 5, 6, 7}}
    rows, covered, total = diff_coverage.measure(measured, added)
    assert (covered, total) == (2, 3), rows
    assert rows == [('pkg/mod.py', 2, 3, [2])], rows


def test_a_file_the_report_never_measured_is_skipped():
    """A workflow or Markdown file must not drag the percentage down."""
    measured = {'pkg/mod.py': {1: 1}}
    added = {'pkg/mod.py': {1}, '.github/workflows/tests.yml': {4, 5, 6}}
    rows, covered, total = diff_coverage.measure(measured, added)
    assert (covered, total) == (1, 1), rows
    assert [row[0] for row in rows] == ['pkg/mod.py'], rows


def test_nothing_measurable_added_is_said_plainly():
    """Zero added statements must not render as 0%, which reads as failure."""
    body = diff_coverage.render([], 0, 0)
    assert 'no patch coverage to report' in body, body
    # It must name the reason: tests/* is omitted, so a test-only change
    # lands here and a bare "nothing added" would read as a broken tool.
    assert 'tests/*' in body, body
    assert '0.0%' not in body, body


def test_a_report_naming_no_changed_path_says_so():
    """A path-spelling mismatch must not read like a test-only change."""
    measured = {'src/pkg/mod.py': {1: 1}}
    added = {'pkg/mod.py': {1, 2}}
    rows, covered, total = diff_coverage.measure(measured, added)
    body = diff_coverage.render(rows, covered, total,
                                diff_coverage.unmeasured_sources(measured,
                                                                 added))
    assert 'names none of the changed paths' in body, body
    assert 'no patch coverage to report' not in body, body


def test_a_change_confined_to_tests_still_reads_as_benign():
    """The mismatch warning must not fire on the case it looks like."""
    measured = {'pkg/mod.py': {1: 1}}
    added = {'tests/test_mod.py': {1}}
    rows, covered, total = diff_coverage.measure(measured, added)
    body = diff_coverage.render(rows, covered, total,
                                diff_coverage.unmeasured_sources(measured,
                                                                 added))
    assert 'no patch coverage to report' in body, body


def test_a_measured_file_cannot_hide_an_unmeasured_source():
    """A partial path mismatch is named and cannot claim perfect coverage."""
    measured = {'pkg/a.py': {1: 1}}
    added = {'pkg/a.py': {1}, 'pkg/b.py': {1}}
    rows, covered, total = diff_coverage.measure(measured, added)
    missing = diff_coverage.unmeasured_sources(measured, added)
    body = diff_coverage.render(rows, covered, total, missing)
    assert missing == {'pkg/b.py'}, missing
    assert '`pkg/b.py`' in body, body
    assert '**100.0%** of added lines covered' not in body, body
    assert 'of measured added lines' in body, body
    assert 'Every measured added line was reached' in body, body


def test_missed_lines_are_collapsed_into_spans():
    """A reviewer reads `12-15`, not four separate numbers."""
    body = diff_coverage.render([('pkg/mod.py', 1, 6, [12, 13, 14, 15, 20])],
                                1, 6)
    assert '12-15, 20' in body, body
    assert '16.7%' in body, body


def test_the_cli_reports_the_percentage_and_the_misses(tmp_path):
    """End to end: the script reads both inputs and prints the table."""
    package = tmp_path / 'pkg'
    package.mkdir()
    _written(package, 'mod.py',
             'one = 1\ntwo = 2\nthree = 3\n\n\n\nseven = 7\n')
    coverage_xml = _written(tmp_path, 'coverage.xml', _COVERAGE_XML)
    diff = _written(tmp_path, 'patch.diff',
                    '--- a/pkg/mod.py\n'
                    '+++ b/pkg/mod.py\n'
                    '@@ -1,0 +1,3 @@\n'
                    '+one\n'
                    '+two\n'
                    '+three\n')
    done = _run_cli(
        [sys.executable, str(_SCRIPT), '--coverage', str(coverage_xml),
         '--diff', str(diff)],
        cwd=tmp_path, capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, (done.returncode, done.stdout, done.stderr)
    assert '**33.3%** of added lines covered (1/3).' in done.stdout, (
        done.stdout)
    assert '2-3' in done.stdout, done.stdout


def test_the_cli_reports_wholly_uncovered_numeric_lines(tmp_path):
    """Numeric zero hits are usable and render a wholly uncovered patch."""
    _written(tmp_path, 'zero.py', 'first = 1\nsecond = 2\n')
    coverage_xml = _written(
        tmp_path, 'zero.xml',
        '<coverage><class filename="zero.py"><lines>'
        '<line number="1" hits="0"/>'
        '<line number="2" hits="0"/>'
        '</lines></class></coverage>\n')
    diff = _written(
        tmp_path, 'zero.diff',
        'diff --git a/zero.py b/zero.py\n'
        '--- /dev/null\n'
        '+++ b/zero.py\n'
        '@@ -0,0 +1,2 @@\n'
        '+first = 1\n'
        '+second = 2\n')
    try:
        measured = diff_coverage.executable_lines(coverage_xml)
    except ValueError as error:
        raise AssertionError(
            f'numeric zero-hit lines were rejected: {error}') from error
    assert measured == {'zero.py': {1: 0, 2: 0}}
    done = _run_cli(
        [sys.executable, str(_SCRIPT), '--coverage', str(coverage_xml),
         '--diff', str(diff)],
        cwd=tmp_path, capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, (
        done.returncode, done.stdout, done.stderr)
    assert done.stderr == '', done.stderr
    assert '**0.0%** of added lines covered (0/2).' in done.stdout, (
        done.stdout)
    assert '| `zero.py` | 0 | 2 | 1-2 |' in done.stdout, done.stdout


def test_the_cli_reads_every_file_in_a_plain_unified_diff(tmp_path):
    """Hunk counts end one file before the next plain file header."""
    _written(tmp_path, 'a.py', 'covered_a = 1\n')
    _written(tmp_path, 'b.py', 'untested_b = 1\n')
    coverage_xml = _written(tmp_path, 'coverage.xml', _TWO_FILE_COVERAGE_XML)
    diff = _written(
        tmp_path, 'plain.diff',
        '--- a/a.py\n'
        '+++ b/a.py\n'
        '@@ -0,0 +1 @@\n'
        '+covered_a = 1\n'
        '--- a/b.py\n'
        '+++ b/b.py\n'
        '@@ -0,0 +1 @@\n'
        '+untested_b = 1\n')
    done = _run_cli(
        [sys.executable, str(_SCRIPT), '--coverage', str(coverage_xml),
         '--diff', str(diff)],
        cwd=tmp_path, capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, (done.returncode, done.stdout, done.stderr)
    assert done.stderr == '', done.stderr
    assert done.stdout == _HALF_COVERED_OUTPUT, done.stdout


def test_the_cli_removes_timestamps_from_unified_diff_paths(tmp_path):
    """A tab-delimited header timestamp is metadata, not the path."""
    _written(tmp_path, 'a.py', 'covered_a = 1\n')
    _written(tmp_path, 'b.py', 'untested_b = 1\n')
    coverage_xml = _written(tmp_path, 'coverage.xml', _TWO_FILE_COVERAGE_XML)
    diff = _written(
        tmp_path, 'timestamp.diff',
        'diff --git a/a.py b/a.py\n'
        '--- a/a.py\n'
        '+++ b/a.py\n'
        '@@ -0,0 +1 @@\n'
        '+covered_a = 1\n'
        'diff --git a/b.py b/b.py\n'
        '--- a/b.py\t2026-08-25 10:00:00.000000000 +0000\n'
        '+++ b/b.py\t2026-08-25 10:00:00.000000000 +0000\n'
        '@@ -0,0 +1 @@\n'
        '+untested_b = 1\n')
    done = _run_cli(
        [sys.executable, str(_SCRIPT), '--coverage', str(coverage_xml),
         '--diff', str(diff)],
        cwd=tmp_path, capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, (done.returncode, done.stdout, done.stderr)
    assert done.stderr == '', done.stderr
    assert done.stdout == _HALF_COVERED_OUTPUT, done.stdout


def test_the_cli_names_an_unmeasured_uppercase_python_file(tmp_path):
    """Python source suffix matching is case-insensitive."""
    _written(tmp_path, 'present.py', 'reached = 1\n')
    coverage_xml = _written(
        tmp_path, 'coverage.xml',
        '<coverage><class filename="present.py"><lines>'
        '<line number="1" hits="1"/>'
        '</lines></class></coverage>\n')
    diff = _written(
        tmp_path, 'uppercase.diff',
        'diff --git a/present.py b/present.py\n'
        '--- /dev/null\n'
        '+++ b/present.py\n'
        '@@ -0,0 +1 @@\n'
        '+reached = 1\n'
        'diff --git a/silent.PY b/silent.PY\n'
        '--- /dev/null\n'
        '+++ b/silent.PY\n'
        '@@ -0,0 +1 @@\n'
        '+never_reached = 2\n')
    done = _run_cli(
        [sys.executable, str(_SCRIPT), '--coverage', str(coverage_xml),
         '--diff', str(diff)],
        cwd=tmp_path, capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, (done.returncode, done.stdout, done.stderr)
    assert done.stderr == '', done.stderr
    assert done.stdout == _UPPERCASE_UNMEASURED_OUTPUT, done.stdout


def test_the_cli_refuses_missing_or_nonpositive_statement_coordinates(tmp_path):
    """Every added source statement needs one positive XML coordinate."""
    _written(tmp_path, 'sample.py', 'covered = 1\nuncovered = 2\n')
    diff = _written(
        tmp_path, 'sample.diff',
        'diff --git a/sample.py b/sample.py\n'
        '--- /dev/null\n'
        '+++ b/sample.py\n'
        '@@ -0,0 +1,2 @@\n'
        '+covered = 1\n'
        '+uncovered = 2\n')
    records = {
        'omitted': (
            '<line number="1" hits="1"/>',
            'coverage report invalid: missing executable statement records '
            'for sample.py: 2\n'),
        'zero': ((
            '<line number="1" hits="1"/>'
            '<line number="0" hits="0"/>'
        ), "coverage report invalid: invalid line number for sample.py: '0' "
            '(must be positive)\n'),
    }
    for label, (lines, expected) in records.items():
        coverage_xml = _written(
            tmp_path, f'{label}.xml',
            '<coverage><class filename="sample.py"><lines>'
            f'{lines}</lines></class></coverage>\n')
        done = _run_cli(
            [sys.executable, str(_SCRIPT), '--coverage', str(coverage_xml),
             '--diff', str(diff)], cwd=tmp_path,
            capture_output=True, text=True, timeout=60, check=False)
        assert done.returncode == 1, (
            label, done.returncode, done.stdout, done.stderr)
        assert done.stdout == '', (label, done.stdout)
        assert done.stderr == expected, (label, done.stderr)


def test_the_cli_fails_loudly_without_the_statement_analyzer(tmp_path):
    """An unavailable coverage.py cannot look like validation passed."""
    del tmp_path
    done = subprocess.run(
        [sys.executable, '-S', str(_SCRIPT), '--help'],
        capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode != 0, (
        'diff coverage silently ran without coverage.py')
    assert "No module named 'coverage'" in done.stderr, done.stderr


def test_the_cli_refuses_a_non_integer_coverage_hit_count(tmp_path):
    """A malformed hit count cannot remove an uncovered line."""
    coverage_xml = _written(
        tmp_path, 'coverage.xml',
        '<coverage><class filename="malformed.py"><lines>'
        '<line number="1" hits="1"/>'
        '<line number="2" hits="not-an-integer"/>'
        '</lines></class></coverage>\n')
    diff = _written(
        tmp_path, 'malformed.diff',
        'diff --git a/malformed.py b/malformed.py\n'
        '--- /dev/null\n'
        '+++ b/malformed.py\n'
        '@@ -0,0 +1,2 @@\n'
        '+reached = 1\n'
        '+never_reached = 2\n')
    done = _run_cli(
        [sys.executable, str(_SCRIPT), '--coverage', str(coverage_xml),
         '--diff', str(diff)],
        capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 1, (done.returncode, done.stdout, done.stderr)
    assert done.stdout == '', done.stdout
    assert done.stderr == (
        "coverage report invalid: invalid hits for malformed.py:2: "
        "'not-an-integer'\n"), done.stderr


def test_the_cli_does_not_round_a_miss_up_to_perfect():
    """A non-perfect result must never headline as 100.0 percent."""
    body = diff_coverage.render(
        [('pkg/mod.py', 1999, 2000, [2000])], 1999, 2000)
    assert '**100.0%**' not in body, body


def test_non_cobertura_xml_is_an_error_not_clean_coverage(tmp_path):
    """A well-formed XML document with the wrong root must fail."""
    coverage_xml = _written(
        tmp_path, 'wrong-root.xml',
        '<html><class filename="evil.py"><line number="9" hits="12"/>'
        '</class></html>\n')
    done = _run_cli(
        [sys.executable, str(_SCRIPT), '--coverage', str(coverage_xml),
         '--diff', '-'],
        input=('+++ b/evil.py\n@@ -0,0 +9 @@\n+evil\n'),
        capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 1, (done.returncode, done.stdout, done.stderr)
    assert 'root is not <coverage>' in done.stderr, done.stderr


def test_coverage_without_usable_lines_is_an_error(tmp_path):
    """A named file without numeric line data must fail the measurement."""
    coverage_xml = _written(
        tmp_path, 'unusable.xml',
        '<coverage><class filename="x.py"><lines/></class></coverage>\n')
    done = _run_cli(
        [sys.executable, str(_SCRIPT), '--coverage', str(coverage_xml),
         '--diff', '-'],
        input='', capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 1, (done.returncode, done.stdout, done.stderr)
    assert 'no usable line entries' in done.stderr, done.stderr


def test_an_empty_report_is_an_error_not_a_clean_result(tmp_path):
    """A measurement that did not happen must not read as nothing to cover."""
    coverage_xml = _written(tmp_path, 'empty.xml',
                            '<?xml version="1.0" ?><coverage/>\n')
    done = _run_cli(
        [sys.executable, str(_SCRIPT), '--coverage', str(coverage_xml),
         '--diff', '-'],
        input='', capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 1, (done.returncode, done.stdout, done.stderr)
    assert 'no usable line entries' in done.stderr, done.stderr


def test_an_undecodable_path_is_reported_not_a_traceback(tmp_path):
    """A git-quoted path that is not UTF-8 gets the clean error treatment."""
    coverage_xml = _written(tmp_path, 'coverage.xml', _COVERAGE_XML)
    done = _run_cli(
        [sys.executable, str(_SCRIPT), '--coverage', str(coverage_xml),
         '--diff', '-'],
        input='+++ "b/\\377.py"\n@@ -0,0 +1 @@\n+x\n',
        capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 1, (done.returncode, done.stdout, done.stderr)
    assert 'Traceback' not in done.stderr, done.stderr
    assert 'coverage report invalid' in done.stderr, done.stderr


def test_the_cli_reports_python_alongside_a_binary_asset(tmp_path):
    """A binary asset must not cost the whole patch report.

    Built from the workflow's own git invocation on a real repository: a
    change adds covered and uncovered Python statements AND a PNG whose
    bytes are not valid UTF-8, and the reporter must render the Python
    report the way it would without the asset.
    """
    repo = tmp_path / 'with-binary'
    repo.mkdir()
    _git(repo, 'init', '-q')
    _git(repo, 'config', 'user.email', 'tests@example.invalid')
    _git(repo, 'config', 'user.name', 'Tests')
    (repo / 'mod.py').write_bytes(b'one = 1\ntwo = 2\nthree = 3\n')
    (repo / 'logo.png').write_bytes(
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\xff\xfe\x80')
    _git(repo, 'add', '-f', 'mod.py', 'logo.png')
    _git(repo, 'commit', '-qm', 'base')
    (repo / 'mod.py').write_bytes(
        b'one = 1\ntwo = 2\nthree = 3\nfour = 4\n')
    (repo / 'logo.png').write_bytes(
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\xff\xfe\x80\x00\x01\x02')
    _git(repo, 'add', '-f', 'mod.py', 'logo.png')
    _git(repo, 'commit', '-qm', 'extend mod and grow the png')
    # Bytes, not text: the diff carries the PNG's non-UTF-8 bytes through,
    # and the text-level helper would die on exactly that.
    raw_diff = subprocess.run(
        ('git', '-C', str(repo), 'diff', '--text', '--no-ext-diff',
         '--no-textconv', '--unified=0', 'HEAD^1', 'HEAD'),
        check=True, capture_output=True).stdout
    patch = repo / 'patch.diff'
    patch.write_bytes(raw_diff)
    # The producer's flags really did carry the binary through as text,
    # with bytes no UTF-8 decoder accepts.
    assert b'\xff\xfe' in raw_diff
    _written(repo, 'mod.py', 'one = 1\ntwo = 2\nthree = 3\nfour = 4\n')
    coverage_xml = _written(
        repo, 'coverage.xml',
        '<coverage><class filename="mod.py"><lines>'
        '<line number="1" hits="1"/>'
        '<line number="4" hits="0"/>'
        '</lines></class></coverage>\n')
    done = _run_cli(
        [sys.executable, str(_SCRIPT), '--coverage', str(coverage_xml),
         '--diff', str(patch)],
        cwd=repo, capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, (done.returncode, done.stderr)
    # The asset sits beside exactly one added statement, missed.
    assert '**0.0%** of added lines covered (0/1).' in done.stdout, (
        done.stdout)
    assert '| `mod.py` | 0 | 1 | 4 |' in done.stdout, done.stdout
    assert 'logo.png' not in done.stdout, done.stdout
