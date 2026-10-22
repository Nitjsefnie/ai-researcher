"""Temporary-file isolation for executed workflow steps."""
import os
import pathlib
import subprocess
import sys
from unittest import mock

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _workflowrun  # noqa: E402  # pylint: disable=wrong-import-position


@pytest.mark.parametrize('status', [0, 7])
def test_run_step_removes_leaked_temp_files(tmp_path, status):
    """Each step isolates and removes scratch files even on a nonzero exit."""
    probe = tmp_path / 'probe'
    probe.mkdir()
    workdir = tmp_path / 'work'
    workdir.mkdir()
    entry = {'run': 'mktemp > /dev/null\n'
             '"$TEST_PYTHON" -c \'import os; from pathlib import Path; '
             'p = Path(os.environ["TMPDIR"]); assert any(p.iterdir()); print(p)\'\n'
             f'exit {status}\n'}
    previous = os.environ.get('TMPDIR')
    try:
        os.environ['TMPDIR'] = str(probe)
        done = _workflowrun.run_step(
            workdir, entry, {**os.environ, 'TEST_PYTHON': sys.executable})
    finally:
        if previous is None:
            os.environ.pop('TMPDIR', None)
        else:
            os.environ['TMPDIR'] = previous
    assert done.returncode == status, done.stderr
    created = pathlib.Path(done.stdout.strip())
    assert not created.exists()
    assert created.parent == workdir
    assert not list(probe.iterdir())
    assert list(workdir.iterdir()) == [workdir / 'workflow-step.sh']


def test_run_step_removes_temp_files_after_timeout(tmp_path):
    """A timed-out child leaves no scratch files or per-step directory."""
    probe = tmp_path / 'probe'
    probe.mkdir()
    workdir = tmp_path / 'work'
    workdir.mkdir()
    entry = {'run': 'mktemp\nexec "$TEST_PYTHON" -c "import time; time.sleep(30)"\n'}
    env = {**os.environ, 'TMPDIR': str(probe), 'TEST_PYTHON': sys.executable}
    real_run = subprocess.run

    def short_run(*args, check=False, **kwargs):
        kwargs['timeout'] = 0.5
        return real_run(*args, check=check, **kwargs)

    with mock.patch.object(_workflowrun.subprocess, 'run', side_effect=short_run):
        with pytest.raises(subprocess.TimeoutExpired) as caught:
            _workflowrun.run_step(workdir, entry, env)
    assert caught.value.stdout
    assert not list(probe.iterdir())
    assert list(workdir.iterdir()) == [workdir / 'workflow-step.sh']
