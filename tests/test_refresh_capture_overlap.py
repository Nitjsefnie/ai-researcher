"""Exercise the refresh capture across its two workflow steps."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _workflowrun  # noqa: E402  # pylint: disable=wrong-import-position

WORKFLOW = Path(__file__).resolve().parent.parent / '.github/workflows/refresh.yml'
pytestmark = pytest.mark.skipif(os.name == 'nt', reason='workflow shell runs on Ubuntu')


def _wait_for(path, future=None):
    deadline = time.monotonic() + 10
    while not path.exists() or not path.stat().st_size:
        if future is not None and future.done():
            pytest.fail(f'collection ended before {path.name}: {future.result()}')
        if time.monotonic() >= deadline:
            pytest.fail(f'{path.name} was not created')
        time.sleep(0.01)


def _run(repo, name, env):
    entry = _workflowrun.step_by_name(WORKFLOW, 'refresh', name)
    real_run = subprocess.run
    env = {'AI_RESEARCHER_CAPTURE_PID': '', **env}

    def bounded_run(*args, **kwargs):
        kwargs['timeout'] = 10
        kwargs['encoding'] = 'utf-8'
        kwargs.pop('check', None)
        return real_run(*args, check=False, **kwargs)

    with mock.patch.object(_workflowrun.subprocess, 'run', side_effect=bounded_run):
        return _workflowrun.run_step(repo, entry, env)


def _pid_exists(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _pid_running(pid):
    result = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)], check=False,
                            capture_output=True, text=True, encoding='utf-8', timeout=10)
    assert result.returncode in (0, 1), result.stderr
    state = result.stdout.strip()
    return bool(state) and not state.startswith('Z')


def _release_capture(repo, child):
    (repo / 'release').touch()
    deadline = time.monotonic() + 10
    while _pid_running(child):
        if time.monotonic() >= deadline:
            pytest.fail(f'capture process {child} did not exit after release')
        time.sleep(0.01)


def _start(tmp_path, status):
    repo = tmp_path / 'repo'
    runner = tmp_path / 'runner'
    scripts = repo / 'scripts'
    scripts.mkdir(parents=True)
    runner.mkdir()
    (scripts / 'fetch_aa.py').write_text(
        'import os, sys, time\nfrom pathlib import Path\n'
        'assert sys.argv[1:] == ["--cross-run-lookback"]\n'
        'assert sys.stdin.read() == ""\n'
        'Path("child.pid").write_text(str(os.getpid()), encoding="utf-8")\n'
        'Path("started").write_text("ready", encoding="utf-8")\n'
        'deadline = time.monotonic() + 30\n'
        'while not Path("release").exists():\n'
        '    if time.monotonic() >= deadline: sys.exit(90)\n'
        '    time.sleep(0.01)\n'
        'print("capture stdout")\n'
        'print("capture diagnostic", file=sys.stderr)\n'
        'sys.exit(int(os.environ["AI_RESEARCHER_STUB_STATUS"]))\n', encoding='utf-8')
    env = {'PATH': os.environ['PATH'], 'RUNNER_TEMP': str(runner),
           'GITHUB_OUTPUT': str(tmp_path / 'start-output'),
           'AI_RESEARCHER_STUB_STATUS': str(status)}
    started = _run(repo, 'Start the leaderboard capture', env)
    assert started.returncode == 0, started.stderr
    assert started.stdout == started.stderr == ''
    _wait_for(repo / 'started')
    start_output = tmp_path / 'start-output'
    output = start_output.read_text(encoding='utf-8') if start_output.exists() else ''
    env['AI_RESEARCHER_CAPTURE_PID'] = output.removeprefix('pid=').strip()
    env['GITHUB_OUTPUT'] = str(tmp_path / 'output')
    return repo, runner, env


@pytest.mark.parametrize('failed_write', ['pid', 'output'])
def test_failed_start_write_stops_and_reaps_the_capture(tmp_path, failed_write):
    repo, runner = tmp_path / 'repo', tmp_path / 'runner'
    scripts = repo / 'scripts'
    scripts.mkdir(parents=True)
    runner.mkdir()
    descendant = (
        'import os, time\nfrom pathlib import Path\n'
        'Path("descendant.pid").write_text(str(os.getpid()), encoding="utf-8")\n'
        'deadline = time.monotonic() + 30\n'
        'while not Path("release").exists() and time.monotonic() < deadline:\n'
        '    time.sleep(0.01)\n')
    (scripts / 'fetch_aa.py').write_text(
        'import os, signal, subprocess, sys, time\nfrom pathlib import Path\n'
        f'worker = subprocess.Popen([sys.executable, "-c", {descendant!r}])\n'
        'def stop(_signum, _frame):\n'
        '    signal.signal(signal.SIGTERM, signal.SIG_IGN)\n'
        '    worker.wait()\n'
        '    raise SystemExit(143)\n'
        'signal.signal(signal.SIGTERM, stop)\n'
        'Path("child.pid").write_text(str(os.getpid()), encoding="utf-8")\n'
        'deadline = time.monotonic() + 30\n'
        'while not Path("release").exists() and time.monotonic() < deadline:\n'
        '    time.sleep(0.01)\n'
        'worker.wait()\n'
        'Path("finished").touch()\n', encoding='utf-8')
    full_device = Path('/dev/full')
    has_full_device = failed_write == 'pid' and full_device.is_char_device()
    if has_full_device:
        (runner / 'aa-capture.pid').symlink_to(full_device)
    setup = ('  capture_pid="$1"\n' if failed_write == 'pid' else
             '  case "$1" in pid=*) capture_pid="${1#pid=}" ;;\n'
             '    *) builtin echo "$@"; return ;; esac\n')
    write = ('  builtin echo "$@"\n' if has_full_device else
             '  builtin printf "injected start write failure\\n" >&2\n  return 37\n')
    shell_env = tmp_path / 'fail-pid-write.sh'
    shell_env.write_text(
        'echo() {\n'
        + setup +
        '  while [ ! -s "$AI_RESEARCHER_CHILD_PID" ] || [ ! -s "$AI_RESEARCHER_DESCENDANT_PID" ]; do\n'
        '    if ! kill -0 "$capture_pid" 2>/dev/null; then return 98; fi\n'
        '    sleep 0.01\n'
        '  done\n'
        '  builtin printf "%s\\n" "$capture_pid" > "$AI_RESEARCHER_WRAPPER_PID"\n'
        + write +
        '}\n', encoding='utf-8')
    env = {'PATH': os.environ['PATH'], 'RUNNER_TEMP': str(runner),
           'GITHUB_OUTPUT': str(tmp_path / 'output'), 'BASH_ENV': str(shell_env),
           'AI_RESEARCHER_CHILD_PID': str(repo / 'child.pid'),
           'AI_RESEARCHER_DESCENDANT_PID': str(repo / 'descendant.pid'),
           'AI_RESEARCHER_WRAPPER_PID': str(repo / 'wrapper.pid')}
    try:
        done = _run(repo, 'Start the leaderboard capture', env)
        wrapper = int((repo / 'wrapper.pid').read_text(encoding='utf-8'))
        child = int((repo / 'child.pid').read_text(encoding='utf-8'))
        grandchild = int((repo / 'descendant.pid').read_text(encoding='utf-8'))
        assert done.returncode == (1 if has_full_device else 37), done.stderr
        assert done.stderr
        # Observe the whole fixture before releasing it.
        assert not _pid_exists(wrapper), f'capture wrapper {wrapper} still exists'
        assert not _pid_exists(child), f'capture process {child} still exists'
        assert not _pid_exists(grandchild), f'capture descendant {grandchild} still exists'
        collect_env = dict(env)
        del collect_env['BASH_ENV']
        collected = _run(repo, 'Capture the leaderboard', collect_env)
        assert collected.returncode == 1
        diagnostic = ('Capture start did not record a PID' if failed_write == 'pid'
                      else 'without an exit status')
        assert diagnostic in collected.stderr
        output = tmp_path / 'output'
        if failed_write == 'pid':
            assert not output.exists()
        else:
            assert output.read_text(encoding='utf-8') == ''
    finally:
        child_file = repo / 'child.pid'
        if child_file.exists() and _pid_exists(int(child_file.read_text(encoding='utf-8'))):
            (repo / 'release').touch()
            deadline = time.monotonic() + 10
            while _pid_exists(int(child_file.read_text(encoding='utf-8'))):
                if time.monotonic() >= deadline:
                    pytest.fail('capture fixture did not exit after release')
                time.sleep(0.01)


def test_capture_success_reports_stdout_and_cleans_files(tmp_path):
    repo, runner, env = _start(tmp_path, 0)
    (repo / 'release').touch()
    done = _run(repo, 'Capture the leaderboard', env)
    assert done.returncode == 0, done.stderr
    assert done.stdout == 'capture stdout\n'
    assert done.stderr == ''
    assert (tmp_path / 'output').exists(), 'capture success did not publish its verdict'
    assert (tmp_path / 'output').read_text(encoding='utf-8') == 'captured=true\n'
    assert not list(runner.iterdir())


def test_capture_failure_keeps_status_and_shows_both_streams(tmp_path):
    repo, runner, env = _start(tmp_path, 7)
    (repo / 'release').touch()
    done = _run(repo, 'Capture the leaderboard', env)
    assert done.returncode == 7
    assert done.stdout == 'capture stdout\n'
    assert done.stderr == 'capture diagnostic\n'
    assert not (tmp_path / 'output').exists()
    assert not list(runner.iterdir())


def test_collection_waits_for_the_live_capture(tmp_path):
    repo, runner, env = _start(tmp_path, 0)
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    sleeper = bin_dir / 'sleep'
    sleeper.write_text('#!/bin/sh\nprintf waiting > "$RUNNER_TEMP/waiting"\n'
                       'exec /bin/sleep 1\n', encoding='utf-8')
    sleeper.chmod(0o755)
    env['PATH'] = str(bin_dir) + os.pathsep + env['PATH']
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_run, repo, 'Capture the leaderboard', env)
            try:
                _wait_for(runner / 'waiting', future)
            finally:
                (repo / 'release').touch()
            done = future.result(timeout=15)
    finally:
        (repo / 'release').touch()
    assert done.returncode == 0, done.stderr
    assert done.stdout == 'capture stdout\n'


def test_dead_capture_without_status_fails_without_hanging(tmp_path):
    repo, runner, env = _start(tmp_path, 0)
    pid = int((runner / 'aa-capture.pid').read_text(encoding='utf-8'))
    child = int((repo / 'child.pid').read_text(encoding='utf-8'))
    assert _pid_running(child)
    os.kill(pid, signal.SIGKILL)
    try:
        done = _run(repo, 'Capture the leaderboard', env)
        # Observe the child before releasing the fixture.
        assert not _pid_running(child), f'capture child {child} still running'
    finally:
        _release_capture(repo, child)
    assert done.returncode != 0
    assert 'without an exit status' in done.stderr
    assert not (tmp_path / 'output').exists()


def test_missing_pid_after_start_stops_capture(tmp_path):
    repo, runner, env = _start(tmp_path, 0)
    pid = (runner / 'aa-capture.pid').read_text(encoding='utf-8').strip()
    child = int((repo / 'child.pid').read_text(encoding='utf-8'))
    assert _pid_running(child)
    (runner / 'aa-capture.pid').unlink()
    try:
        done = _run(repo, 'Capture the leaderboard', env)
        # The fallback handle must stop the child before fixture teardown.
        assert not _pid_running(child), f'capture child {child} still running'
    finally:
        _release_capture(repo, child)
    assert env['AI_RESEARCHER_CAPTURE_PID'] == pid
    assert done.returncode != 0
    assert 'Capture start did not record a PID' in done.stderr
    assert not (tmp_path / 'output').exists()


def test_missing_pid_after_completion_does_not_signal_group(tmp_path):
    repo, runner, env = _start(tmp_path, 0)
    (repo / 'release').touch()
    _wait_for(runner / 'aa-capture.status')
    (runner / 'aa-capture.pid').unlink()
    shell_env = tmp_path / 'record-signal.sh'
    shell_env.write_text('kill() { printf called > "$RUNNER_TEMP/signalled"; return 1; }\n',
                         encoding='utf-8')
    env['BASH_ENV'] = str(shell_env)
    done = _run(repo, 'Capture the leaderboard', env)
    assert done.returncode != 0
    assert 'Capture start did not record a PID' in done.stderr
    assert not (runner / 'signalled').exists()
    assert not (tmp_path / 'output').exists()


def test_status_arrives_during_liveness_check(tmp_path):
    runner = tmp_path / 'runner'
    runner.mkdir()
    (runner / 'aa-capture.pid').write_text('99999999\n', encoding='utf-8')
    (runner / 'aa-capture.stdout').write_text('capture stdout\n', encoding='utf-8')
    (runner / 'aa-capture.stderr').write_text('capture diagnostic\n', encoding='utf-8')
    shell_env = tmp_path / 'race-env.sh'
    shell_env.write_text(
        'kill() { printf "7\\n" > "$RUNNER_TEMP/aa-capture.status"; return 1; }\n',
        encoding='utf-8')
    env = {'PATH': os.environ['PATH'], 'RUNNER_TEMP': str(runner),
           'GITHUB_OUTPUT': str(tmp_path / 'output'), 'BASH_ENV': str(shell_env)}
    done = _run(tmp_path, 'Capture the leaderboard', env)
    assert done.returncode == 7, (done.returncode, done.stderr)
    assert done.stdout == 'capture stdout\n'
    assert done.stderr == 'capture diagnostic\n'
    assert not (tmp_path / 'output').exists()


def test_status_arrives_during_failed_group_cleanup(tmp_path):
    runner = tmp_path / 'runner'
    runner.mkdir()
    (runner / 'aa-capture.pid').write_text('99999999\n', encoding='utf-8')
    (runner / 'aa-capture.stdout').write_text('capture stdout\n', encoding='utf-8')
    (runner / 'aa-capture.stderr').write_text('capture diagnostic\n', encoding='utf-8')
    shell_env = tmp_path / 'cleanup-race-env.sh'
    shell_env.write_text(
        'kill() {\n'
        '  if [ "$1" = "-KILL" ]; then\n'
        '    printf "7\\n" > "$RUNNER_TEMP/aa-capture.status"\n'
        '  fi\n'
        '  return 1\n'
        '}\n', encoding='utf-8')
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    ps = bin_dir / 'ps'
    ps.write_text('#!/bin/sh\nexit 2\n', encoding='utf-8')
    ps.chmod(0o755)
    env = {'PATH': str(bin_dir) + os.pathsep + os.environ['PATH'],
           'RUNNER_TEMP': str(runner), 'GITHUB_OUTPUT': str(tmp_path / 'output'),
           'BASH_ENV': str(shell_env)}
    done = _run(tmp_path, 'Capture the leaderboard', env)
    assert done.returncode == 7, (done.returncode, done.stderr)
    assert done.stdout == 'capture stdout\n'
    assert 'capture diagnostic\n' in done.stderr
    assert 'Could not stop capture process group' in done.stderr
    assert (runner / 'aa-capture.pid').exists()
    assert not (tmp_path / 'output').exists()


@pytest.mark.parametrize('status', [0, 7])
def test_collection_runs_after_failed_install(tmp_path, status):
    repo, _runner, env = _start(tmp_path, status)
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    python = bin_dir / 'python3'
    python.write_text('#!/bin/sh\nexit 17\n', encoding='utf-8')
    python.chmod(0o755)
    env['PATH'] = str(bin_dir) + os.pathsep + env['PATH']
    try:
        install = _run(repo, 'Install the test toolchain', env)
        assert install.returncode == 17
        install_step = _workflowrun.step_by_name(WORKFLOW, 'refresh', 'Install the test toolchain')
        assert not install_step.get('continue-on-error', False)
    finally:
        (repo / 'release').touch()
    done = _run(repo, 'Capture the leaderboard', env)
    assert done.returncode == status, done.stderr
    assert done.stdout == 'capture stdout\n'
    if status:
        assert done.stderr == 'capture diagnostic\n'
        assert not (tmp_path / 'output').exists()
    else:
        assert done.stderr == ''
        assert (tmp_path / 'output').read_text(encoding='utf-8') == 'captured=true\n'
    collection = _workflowrun.step_by_name(WORKFLOW, 'refresh', 'Capture the leaderboard')
    assert collection.get('if') == '${{ !cancelled() }}'
    assert not collection.get('continue-on-error', False)
    upload = _workflowrun.step_by_name(WORKFLOW, 'refresh', 'Upload the capture on failure')
    assert upload['if'] == "failure() && steps.fetch.outputs.captured == 'true'"


@pytest.mark.parametrize('pid_record', [None, ''])
def test_collection_fails_loudly_without_start_record(tmp_path, pid_record):
    runner = tmp_path / 'runner'
    runner.mkdir()
    if pid_record is not None:
        (runner / 'aa-capture.pid').write_text(pid_record, encoding='utf-8')
    env = {'PATH': os.environ['PATH'], 'RUNNER_TEMP': str(runner),
           'GITHUB_OUTPUT': str(tmp_path / 'output')}
    done = _run(tmp_path, 'Capture the leaderboard', env)
    assert done.returncode != 0
    assert 'Capture start did not record a PID' in done.stderr
    assert not (tmp_path / 'output').exists()
    collection = _workflowrun.step_by_name(WORKFLOW, 'refresh', 'Capture the leaderboard')
    assert collection.get('if') == '${{ !cancelled() }}'


def test_toolchain_install_passes_pure_python_setting_to_child(tmp_path):
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    python = bin_dir / 'python3'
    python.write_text('#!/bin/sh\nprintf "%s\\n" "$PYYAML_FORCE_LIBYAML" "$@"\n',
                      encoding='utf-8')
    python.chmod(0o755)
    env = {'PATH': str(bin_dir) + os.pathsep + os.environ['PATH']}
    done = _run(tmp_path, 'Install the test toolchain', env)
    assert done.returncode == 0, done.stderr
    assert done.stdout.splitlines() == ['0', '-m', 'pip', 'install', '-r',
                                        'requirements-test.txt']
