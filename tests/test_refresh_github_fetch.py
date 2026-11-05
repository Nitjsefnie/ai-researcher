"""The refresh workflow's GitHub most-starred producer, pinned and executed.

github-fetch mirrors hf-fetch and or-fetch, so their structure and executed
stage tests run again here for it; the rest pins what only this producer
has: the job token its search call reads, and its payload's place in the
joined commit and the rankings build.
"""
import json
import os
import pathlib
import shutil
import sys
import tempfile
import unittest

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _workflowrun  # noqa: E402  # pylint: disable=wrong-import-position
import test_refresh_workflow as refresh  # noqa: E402  # pylint: disable=wrong-import-position

TOKEN_ENV = 'AI_RESEARCHER_GITHUB_TOKEN'
# Built at run time so no token-shaped literal is committed.
TOKEN = '-'.join(('fixture', 'credential', str(os.getpid())))
MESSAGE = 'Most-starred: 1 new in the top 10: org/new\n\nNEW  rank 1 org/new\n'


class GitHubTrackerStructureTests(refresh.HFTrackerStructureTests):
    tracker = 'github'
    script = 'fetch_github_stars.py'

    def test_the_job_token_reaches_only_the_search_call_through_env(self):
        workflow = refresh.load()
        fetch = self.tracker_step('fetch', 'Fetch the top 10')
        self.assertEqual(fetch['env'], {TOKEN_ENV: '${{ github.token }}'})
        self.assertNotIn('${{', fetch['run'])
        holders = [(name, entry.get('name')) for name, job in workflow['jobs'].items()
                   for entry in job['steps']
                   if 'github.token' in str(entry) or 'secrets.GITHUB_TOKEN' in str(entry)]
        self.assertEqual(holders, [('github-fetch', 'Fetch the top 10')])
        self.assertNotIn('github.token', str({key: value for key, value in
                                              workflow['jobs']['github-fetch'].items()
                                              if key != 'steps'}))


class GitHubTrackerExecutedStepsTests(refresh.HFTrackerExecutedStepsTests):
    tracker = 'github'
    data = 'data/github-stars.json'
    message = MESSAGE

    def setUp(self):
        super().setUp()
        self.env[TOKEN_ENV] = TOKEN

    def test_fetch_script_is_invoked_with_message_and_failure_propagates(self):
        scripts = self.repo / 'scripts'
        scripts.mkdir()
        for script in ('fetch_github_stars.py', 'fetch_http.py', 'trending_message.py'):
            shutil.copyfile(refresh.ROOT / 'scripts' / script, scripts / script)
        # A sitecustomize stub answers the network boundary and records the
        # credential the request carried.
        stub = self.root / 'stub'
        stub.mkdir()
        (stub / 'sitecustomize.py').write_text(
            'import io, json, os, urllib.request\n'
            'def urlopen(request, **_):\n'
            '    with open(os.environ["SEEN"], "w", encoding="utf-8") as seen:\n'
            '        seen.write(request.get_header("Authorization"))\n'
            '    items = [{"full_name": f"org/{n}"} for n in range(int(os.environ["COUNT"]))]\n'
            '    return io.BytesIO(json.dumps({"incomplete_results": False,'
            ' "items": items}).encode())\n'
            'urllib.request.urlopen = urlopen\n', encoding='utf-8')
        (self.repo / self.data).write_text('{"models": []}\n', encoding='utf-8')
        seen = self.root / 'seen'
        self.env.update({'PYTHONPATH': str(stub), 'COUNT': '10', 'SEEN': str(seen)})
        self.run_step('fetch', 'Fetch the top 10')
        self.assertEqual(seen.read_text(encoding='utf-8'), f'Bearer {TOKEN}')
        self.assertTrue((self.runner / 'message').read_text(encoding='utf-8').startswith(
            'Most-starred: 10 new in the top 10:'))
        saved = (self.repo / self.data).read_bytes()
        self.env['COUNT'] = '9'
        result = self.run_step('fetch', 'Fetch the top 10', 1)
        self.assertIn('expected 10 repositories, got 9', result.stderr)
        self.assertEqual((self.repo / self.data).read_bytes(), saved)
        seen.unlink()
        self.env.update({TOKEN_ENV: '', 'COUNT': '10'})
        result = self.run_step('fetch', 'Fetch the top 10', 1)
        self.assertIn(f'{TOKEN_ENV} is not set', result.stderr)
        self.assertFalse(seen.exists())
        self.assertEqual((self.repo / self.data).read_bytes(), saved)


class GitHubJoinedCommitTests(refresh._SeededOrigin, unittest.TestCase):  # pylint: disable=protected-access
    """The GitHub payload joins the one bot commit beside the other two."""

    LISTS = (('hf', 'data/hf-trending.json', 'Trending: fresh HF'),
             ('or', 'data/openrouter-trending.json', 'Top 10: fresh OR'),
             ('github', 'data/github-stars.json', 'Most-starred: fresh GH'))

    def test_github_list_commits_in_fixed_order_with_only_its_path(self):
        step = _workflowrun.step_by_name(refresh.WORKFLOW, 'publish', 'Commit the refresh')
        for sources in (('github',), ('hf', 'github'), ('or', 'github'), ('hf', 'or', 'github')):
            with self.subTest(sources=sources), tempfile.TemporaryDirectory() as raw:
                tmp = pathlib.Path(raw)
                files = {**refresh.ExecutedCommitMessageTests.BASE_FILES,
                         **{path: 'old list\n' for _, path, _ in self.LISTS}}
                config, base, _, _, _ = self._seed_origin(tmp, files)
                blocks, changed = [], []
                for tracker, path, subject in self.LISTS:
                    if tracker in sources:
                        payload = tmp / f'{tracker}-payload'
                        (payload / 'data').mkdir(parents=True)
                        (payload / path).write_text('fresh list\n', encoding='utf-8')
                        (payload / 'message.txt').write_text(
                            subject + '\n\nNEW  rank 1 o/new\n', encoding='utf-8', newline='\n')
                        blocks.append(subject + '\n\nNEW  rank 1 o/new')
                        changed.append(path)
                result = _workflowrun.run_step(tmp, step, self._env(tmp, config, base))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                scratch = tmp / 'scratch'
                message = self._git('log', '-1', '--format=%B', cwd=scratch).stdout.strip()
                self.assertEqual(message, '\n\n'.join(
                    blocks + ['Captured by .github/workflows/refresh.yml.']))
                self.assertEqual(self._git('rev-list', '--count', base + '..HEAD',
                                           cwd=scratch).stdout.strip(), '1')
                self.assertEqual(self._git('diff-tree', '--no-commit-id', '--name-only', '-r',
                                           'HEAD', cwd=scratch).stdout.splitlines(),
                                 sorted(changed))


@pytest.mark.skipif(os.name == 'nt', reason='workflow shell runs on Ubuntu')
@pytest.mark.parametrize('fresh', [('github',), ('hf', 'or', 'github')])
def test_rankings_build_passes_the_fresh_github_list(tmp_path, fresh):
    """The real build block hands a fresh GitHub list its own timestamp."""
    runner = tmp_path / 'runner'
    runner.mkdir()
    args = []
    for tracker, filename, timestamp in (
            ('hf', 'hf-trending.json', '2026-10-20T09:41:00Z'),
            ('or', 'openrouter-trending.json', '2026-10-20T09:42:00Z'),
            ('github', 'github-stars.json', '2026-10-20T09:43:00Z')):
        if tracker in fresh:
            data = runner / f'{tracker}-payload/data/{filename}'
            data.parent.mkdir(parents=True)
            data.write_text('{"models": []}', encoding='utf-8')
            (runner / f'{tracker}-payload/fetched-at.txt').write_text(
                timestamp + '\n', encoding='utf-8')
            args.extend([f'--fresh-{tracker}', str(data),
                         f'--fresh-{tracker}-timestamp', timestamp])
    (tmp_path / 'scripts').mkdir()
    (tmp_path / 'scripts/build_rankings.py').write_text(
        'import json, sys\nfrom pathlib import Path\n'
        'Path("args.json").write_text(json.dumps(sys.argv[1:]))\n', encoding='utf-8')
    env = {**os.environ, 'RUNNER_TEMP': str(runner), 'GITHUB_RUN_ID': '12345'}
    build = refresh.step_in(refresh.load(), 'rankings', 'Build the rankings page')
    done = _workflowrun.run_step(tmp_path, build, env)
    assert done.returncode == 0, done.stdout + done.stderr
    assert json.loads((tmp_path / 'args.json').read_text(encoding='utf-8')) == \
        args + ['--fresh-label', 'run 12345']
