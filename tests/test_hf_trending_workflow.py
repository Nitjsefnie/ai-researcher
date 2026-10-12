"""Pin the trending workflow's privilege boundary and execute its shell steps."""
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _workflowrun  # noqa: E402  # pylint: disable=wrong-import-position

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/hf-trending.yml'
DATA = 'data/hf-trending.json'
MESSAGE = 'Trending: 1 new in the top 10: org/new\n\nNEW  #1 org/new\n'


def load():
    return yaml.safe_load(WORKFLOW.read_text(encoding='utf-8'))


def step(job, name):
    return _workflowrun.step_by_name(WORKFLOW, job, name)


class StructureTests(unittest.TestCase):
    """The key is accessible only to the push job, which executes no tree code."""

    def test_workflow_exists(self):
        self.assertTrue(WORKFLOW.is_file())

    def test_triggers_concurrency_and_main_only(self):
        workflow = load()
        self.assertEqual(workflow[True], {
            'schedule': [{'cron': '7 * * * *'}], 'workflow_dispatch': None})
        self.assertEqual(workflow['concurrency'], {
            'group': 'hf-trending', 'cancel-in-progress': False})
        refresh = yaml.safe_load(
            (ROOT / '.github/workflows/refresh.yml').read_text(encoding='utf-8'))
        self.assertNotEqual(workflow['concurrency']['group'],
                            refresh['concurrency']['group'])
        self.assertEqual(workflow['jobs']['fetch']['if'],
                         "github.ref == 'refs/heads/main'")

    def test_permissions_and_secret_scope(self):
        workflow = load()
        self.assertEqual(set(workflow['jobs']), {'fetch', 'push'})
        self.assertEqual(workflow['permissions'], {'contents': 'read'})
        self.assertNotIn('secrets.', str(workflow['jobs']['fetch']))
        for name, job in workflow['jobs'].items():
            with self.subTest(job=name):
                self.assertEqual(job['permissions'], {'contents': 'read'})
                self.assertEqual(job.get('environment'),
                                 'main-push' if name == 'push' else None)
                for entry in job['steps']:
                    if name == 'fetch':
                        self.assertNotIn('secrets.', str(entry))
        push = workflow['jobs']['push']
        self.assertEqual(push['needs'], 'fetch')
        self.assertEqual(push['if'], "needs.fetch.outputs.commits == 'true'")
        self.assertEqual(workflow['jobs']['fetch']['outputs'], {
            'commits': '${{ steps.commit.outputs.commits }}'})
        key_steps = [entry for entry in push['steps']
                     if 'secrets.' in str(entry)]
        self.assertEqual(key_steps, [step('push', 'Push the trending commit')])
        self.assertEqual(key_steps[0]['env']['MASTER_PUSH_DEPLOY_KEY'],
                         '${{ secrets.MASTER_PUSH_DEPLOY_KEY }}')
        self.assertEqual(key_steps[0]['if'],
                         "steps.replay.outputs.commits == 'true'")
        self.assertNotIn('env', workflow)
        self.assertNotIn('env', push)

    def test_only_fetch_checks_out_and_no_frontier_code_runs(self):
        workflow = load()
        checkout = [entry for entry in workflow['jobs']['fetch']['steps']
                    if entry.get('uses', '').startswith('actions/checkout@')]
        self.assertEqual(len(checkout), 1)
        self.assertEqual(checkout[0]['with']['persist-credentials'], False)
        self.assertEqual(checkout[0]['with']['fetch-depth'], 0)
        for name, job in workflow['jobs'].items():
            for entry in job['steps']:
                run = entry.get('run', '')
                self.assertNotRegex(run, r'build\.py|capture_gate\.py|fetch_aa\.py|publish_docs\.py|diff_aa\.py')
                if name == 'push':
                    self.assertFalse(entry.get('uses', '').startswith('actions/checkout@'))
                    self.assertNotRegex(run, r'\bpython3?\b|\bpip\b')
                    self.assertNotIn('github.token', str(entry))

    def test_artifact_is_this_runs_bundle_and_upload_is_success_gated(self):
        upload = step('fetch', 'Upload the push bundle')
        download = step('push', 'Download the push bundle')
        self.assertEqual(upload['if'], "success() && steps.commit.outputs.commits == 'true'")
        self.assertEqual(upload['with']['if-no-files-found'], 'error')
        self.assertEqual(upload['with']['name'], download['with']['name'])
        self.assertEqual(upload['with']['path'], download['with']['path'])
        self.assertNotIn('run-id', download['with'])
        self.assertNotIn('github-token', download['with'])
        self.assertEqual([entry.get('name') for entry in load()['jobs']['push']['steps']],
                         ['Download the push bundle', 'Replay onto fresh main',
                          'Push the trending commit'])

    def test_capture_message_and_exact_add_list(self):
        self.assertEqual(step('fetch', 'Fetch the top 10')['run'],
                         'python3 scripts/fetch_hf_trending.py --message "$RUNNER_TEMP/message"')
        run = step('fetch', 'Commit when changed')['run']
        adds = re.findall(r'^\s*git add (.+)$', run, re.MULTILINE)
        self.assertEqual(adds, [DATA])
        self.assertIn('git commit -q -F "$RUNNER_TEMP/message"', run)
        self.assertNotIn('git push', run)

    def test_action_pins_match_refresh_and_have_version_comments(self):
        text = WORKFLOW.read_text(encoding='utf-8')
        refresh = (ROOT / '.github/workflows/refresh.yml').read_text(encoding='utf-8')
        pattern = r'uses: (actions/[\w-]+@[0-9a-f]{40}) # (v[\d.]+)'
        pins = re.findall(pattern, text)
        self.assertEqual(len(pins), 3)
        self.assertTrue(set(pins).issubset(set(re.findall(pattern, refresh))))

    def test_key_lifecycle_matches_refresh_and_has_no_force_push(self):
        run = step('push', 'Push the trending commit')['run']
        self.assertIn('trap \'kill "$SSH_AGENT_PID" 2>/dev/null || true\' EXIT', run)
        self.assertIn('ssh-add <(printf \'%s\\n\' "$MASTER_PUSH_DEPLOY_KEY")', run)
        self.assertIn('StrictHostKeyChecking=yes', run)
        self.assertNotIn('--force', run)
        self.assertNotIn('--depth', run)

    def test_deploy_key_delivery_stays_in_lockstep_with_refresh(self):
        refresh_path = ROOT / '.github/workflows/refresh.yml'
        refresh = _workflowrun.step_by_name(
            refresh_path, 'push', 'Push the tested tree to main')['run'].splitlines()
        trending = step('push', 'Push the trending commit')['run'].splitlines()
        files = '.github/workflows/refresh.yml and .github/workflows/hf-trending.yml'
        # Only truthful diagnostics differ: the trending workflow runs no suite.
        differences = (
            # Trending's pre-push concession promises a fresh list, not a suite.
            ('  echo "::notice::main moved under the run (tested base $base, current tip $fetched); the next hourly run re-fetches, re-tests and lands it"',
             '  echo "::notice::main moved under the run (tested base $base, current tip $fetched); the next hourly run fetches and lands the trending list"', 1),
            # Trending's post-rejection concession likewise promises no suite.
            ('  echo "::notice::main moved before the push landed; the next hourly run re-fetches, re-tests and lands it"',
             '  echo "::notice::main moved before the push landed; the next hourly run fetches and lands the trending list"', 1),
            # Both summary branches describe fetching the list without a suite.
            ('    echo "The next hourly run re-fetches on the new tip, re-runs the suite"',
             '    echo "The next hourly run fetches the trending list on the new tip"', 2),
            # Both summary branches omit refresh's capture-job-specific wording.
            ('    echo "in the capture job, and lands the data there."',
             '    echo "and lands the data there."', 2),
        )
        canonical = {}
        for refresh_line, trending_line, count in differences:
            self.assertEqual(refresh.count(refresh_line), count, files)
            self.assertEqual(trending.count(trending_line), count, files)
            canonical[trending_line] = refresh_line
        # Whole-line canonicalization retains every line and its position: a
        # one-sided edit, insertion, deletion or reorder fails the comparison.
        self.assertEqual(refresh, [canonical.get(line, line) for line in trending],
                         f'Deploy-key delivery diverged between {files}')


@unittest.skipIf(os.name == 'nt', 'workflow shell runs on Ubuntu')
class ExecutedStepsTests(unittest.TestCase):
    """Run the actual YAML scripts against local git repos and a stubbed fetch."""

    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git(self.repo, 'init', '-q', '-b', 'main')
        self.configure(self.repo)
        (self.repo / 'data').mkdir()
        (self.repo / DATA).write_text('old\n', encoding='utf-8')
        (self.repo / 'README.md').write_text('base\n', encoding='utf-8')
        self.git(self.repo, 'add', DATA, 'README.md')
        self.git(self.repo, 'commit', '-qm', 'base')
        self.base = self.git(self.repo, 'rev-parse', 'HEAD').strip()
        self.origin = self.root / 'origin.git'
        self.git(self.root, 'clone', '-q', '--bare', str(self.repo), str(self.origin))
        self.git(self.repo, 'remote', 'add', 'origin', str(self.origin))
        self.runner = self.root / 'runner'
        self.runner.mkdir()
        (self.runner / 'message').write_text(MESSAGE, encoding='utf-8')
        home = self.root / 'home'
        home.mkdir()
        self.env = {**os.environ, 'RUNNER_TEMP': str(self.runner),
                    'GITHUB_OUTPUT': str(self.root / 'output'),
                    'GITHUB_STEP_SUMMARY': str(self.root / 'summary'),
                    'GITHUB_REPOSITORY': 'fixture/trending',
                    'REPO': 'fixture/trending',
                    'MASTER_PUSH_DEPLOY_KEY': '',
                    'HOME': str(home), 'PUSH_REMOTE': str(self.origin)}

    @staticmethod
    def git(repo, *args):
        return subprocess.run(['git', '-C', str(repo), *args], check=True,
                              capture_output=True, text=True, timeout=60).stdout

    def configure(self, repo):
        self.git(repo, 'config', 'user.name', 'fixture')
        self.git(repo, 'config', 'user.email', 'fixture@example.com')
        self.git(repo, 'config', 'commit.gpgsign', 'false')

    def run_step(self, job, name, expected=0):
        result = _workflowrun.run_step(self.repo, step(job, name), self.env)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def stage_change(self):
        (self.repo / DATA).write_text('new\n', encoding='utf-8')
        self.run_step('fetch', 'Commit when changed')

    def replay(self):
        # Redirect the production anonymous HTTPS fetch to the local bare remote.
        self.git(self.repo, 'config', '--file', str(self.root / 'gitconfig'),
                 f'url.{self.origin}.insteadOf', 'https://github.com/fixture/trending')
        self.env['GIT_CONFIG_GLOBAL'] = str(self.root / 'gitconfig')
        self.run_step('push', 'Replay onto fresh main')

    def advance_main(self, path='README.md', content='moved\n'):
        other = self.root / 'other'
        self.git(self.root, 'clone', '-q', str(self.origin), str(other))
        self.configure(other)
        (other / path).write_text(content, encoding='utf-8')
        self.git(other, 'add', path)
        self.git(other, 'commit', '-qm', 'main moved')
        self.git(other, 'push', '-q', 'origin', 'main')
        return self.git(other, 'rev-parse', 'HEAD').strip()

    def load_ephemeral_key(self):
        key = self.root / 'key'
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '',
                        '-f', str(key)], check=True, capture_output=True, timeout=60)
        self.env['MASTER_PUSH_DEPLOY_KEY'] = key.read_text(encoding='utf-8')

    def test_unchanged_capture_creates_no_commit_or_bundle(self):
        self.run_step('fetch', 'Commit when changed')
        self.assertEqual(self.git(self.repo, 'rev-parse', 'HEAD').strip(), self.base)
        self.assertEqual(pathlib.Path(self.env['GITHUB_OUTPUT']).read_text(encoding='utf-8'),
                         'commits=false\n')
        self.assertFalse((self.runner / 'push-data').exists())

    def test_changed_capture_commits_only_data_with_exact_message(self):
        (self.repo / 'README.md').write_text('do not commit\n', encoding='utf-8')
        self.stage_change()
        self.assertEqual(self.git(self.repo, 'diff-tree', '--no-commit-id',
                                  '--name-only', '-r', 'HEAD').splitlines(), [DATA])
        self.assertEqual(self.git(self.repo, 'log', '-1', '--format=%B').rstrip(),
                         MESSAGE.rstrip())
        self.assertEqual(self.git(self.repo, 'log', '-1', '--format=%an').strip(),
                         'github-actions[bot]')
        self.assertNotIn('Co-Authored-By:', self.git(self.repo, 'log', '-1', '--format=%B'))
        self.assertEqual(self.git(self.origin, 'rev-parse', 'main').strip(), self.base)
        self.assertTrue((self.runner / 'push-data/push.bundle').exists())
        self.assertEqual((self.runner / 'push-data/base.txt').read_text(encoding='utf-8').strip(),
                         self.base)

    @unittest.skipUnless(sys.platform == 'linux',
                         'requires Linux ssh-agent/ssh-add behaviour matching ubuntu-latest')
    def test_replay_preserves_fresh_main_and_message_then_pushes(self):
        self.stage_change()
        fresh = self.advance_main()
        self.replay()
        push_repo = self.runner / 'scratch'
        self.assertEqual(self.git(push_repo, 'rev-parse', 'HEAD^').strip(), fresh)
        self.assertEqual(self.git(push_repo, 'show', 'HEAD:README.md'), 'moved\n')
        self.assertEqual(self.git(push_repo, 'show', f'HEAD:{DATA}'), 'new\n')
        self.assertEqual(self.git(push_repo, 'log', '-1', '--format=%B').rstrip(), MESSAGE.rstrip())
        self.load_ephemeral_key()
        self.run_step('push', 'Push the trending commit')
        landed = self.git(self.origin, 'rev-parse', 'main').strip()
        self.assertEqual(landed, (self.runner / 'push-data/tip.txt').read_text(encoding='utf-8').strip())

    def test_replay_noops_when_main_already_has_capture(self):
        self.stage_change()
        fresh = self.advance_main(DATA, 'new\n')
        self.replay()
        self.assertTrue(pathlib.Path(self.env['GITHUB_OUTPUT']).read_text(encoding='utf-8').endswith('commits=false\n'))
        self.assertEqual(self.git(self.origin, 'rev-parse', 'main').strip(), fresh)

    def test_push_missing_key_fails_before_delivery(self):
        result = self.run_step('push', 'Push the trending commit', 1)
        self.assertIn('MASTER_PUSH_DEPLOY_KEY is empty', result.stderr)
        self.assertEqual(self.git(self.origin, 'rev-parse', 'main').strip(), self.base)

    @unittest.skipUnless(sys.platform == 'linux',
                         'requires Linux ssh-agent/ssh-add behaviour matching ubuntu-latest')
    def test_main_move_after_replay_concedes_without_force(self):
        self.stage_change()
        self.replay()
        fresh = self.advance_main()
        self.load_ephemeral_key()
        self.run_step('push', 'Push the trending commit')
        self.assertEqual(self.git(self.origin, 'rev-parse', 'main').strip(), fresh)
        self.assertIn('main moved under the run', pathlib.Path(self.env['GITHUB_STEP_SUMMARY']).read_text(encoding='utf-8'))

    @unittest.skipUnless(sys.platform == 'linux',
                         'requires Linux ssh-agent/ssh-add behaviour matching ubuntu-latest')
    def test_rejected_push_with_main_still_at_base_fails(self):
        self.stage_change()
        self.replay()
        hook = self.origin / 'hooks/pre-receive'
        hook.write_text('#!/bin/sh\nexit 1\n', encoding='utf-8')
        hook.chmod(0o755)
        self.load_ephemeral_key()
        result = self.run_step('push', 'Push the trending commit', 1)
        self.assertIn('the push was rejected while main stood still', result.stderr)

    @unittest.skipUnless(sys.platform == 'linux',
                         'requires Linux ssh-agent/ssh-add behaviour matching ubuntu-latest')
    def test_main_moving_during_push_concedes_after_rejection(self):
        self.stage_change()
        self.replay()
        writer = self.root / 'racer'
        self.git(self.root, 'clone', '-q', str(self.origin), str(writer))
        self.configure(writer)
        (writer / 'README.md').write_text('race\n', encoding='utf-8')
        self.git(writer, 'add', 'README.md')
        self.git(writer, 'commit', '-qm', 'raced')
        raced = self.git(writer, 'rev-parse', 'HEAD').strip()
        bin_dir = self.root / 'bin'
        bin_dir.mkdir()
        wrapper = bin_dir / 'git'
        wrapper.write_text(
            '#!/bin/sh\ncase "$*" in\n'
            '  *" push origin "*) "$REAL_GIT" -C "$RACE_REPO" push -q origin main ;;\n'
            'esac\nexec "$REAL_GIT" "$@"\n', encoding='utf-8')
        wrapper.chmod(0o755)
        real_git = shutil.which('git')
        assert real_git is not None, 'git is required to execute the workflow'
        self.env.update({'REAL_GIT': real_git, 'RACE_REPO': str(writer),
                         'PATH': str(bin_dir) + os.pathsep + os.environ['PATH']})
        self.load_ephemeral_key()
        self.run_step('push', 'Push the trending commit')
        self.assertEqual(self.git(self.origin, 'rev-parse', 'main').strip(), raced)
        self.assertIn('main moved before the push landed', pathlib.Path(self.env['GITHUB_STEP_SUMMARY']).read_text(encoding='utf-8'))

    def test_fetch_script_is_invoked_with_message_and_failure_propagates(self):
        scripts = self.repo / 'scripts'
        scripts.mkdir()
        target = scripts / 'fetch_hf_trending.py'
        shutil.copyfile(ROOT / 'scripts/fetch_hf_trending.py', target)
        # A sitecustomize stub answers the fetcher's network boundary only.
        stub = self.root / 'stub'
        stub.mkdir()
        (stub / 'sitecustomize.py').write_text(
            'import io, json, os, urllib.request\n'
            'urllib.request.urlopen = lambda *a, **k: io.BytesIO(json.dumps('
            ' [{"id": f"org/{n}"} for n in range(int(os.environ["COUNT"]))]'
            ').encode())\n', encoding='utf-8')
        (self.repo / DATA).write_text('{"models": []}\n', encoding='utf-8')
        self.env.update({'PYTHONPATH': str(stub), 'COUNT': '10'})
        self.run_step('fetch', 'Fetch the top 10')
        self.assertTrue((self.runner / 'message').read_text(encoding='utf-8').startswith('Trending: 10 new in the top 10:'))
        saved = (self.repo / DATA).read_bytes()
        self.env['COUNT'] = '9'
        result = self.run_step('fetch', 'Fetch the top 10', 1)
        self.assertIn('expected 10 models, got 9', result.stderr)
        self.assertEqual((self.repo / DATA).read_bytes(), saved)
