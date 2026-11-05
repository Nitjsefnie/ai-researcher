"""Behavioral tests for the independent GitHub most-starred capture."""
import contextlib
import email.message
import io
import json
import os
import pathlib
import sys
import tempfile
import unittest
import unittest.mock
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_github_stars  # noqa: E402  # pylint: disable=wrong-import-position

URL = ("https://api.github.com/search/repositories"
       "?q=stars:>1000&sort=stars&order=desc&per_page=30")
SEED = ROOT / "data" / "github-stars.json"
# Built at run time so no token-shaped literal is committed.
TOKEN = "-".join(("fixture", "credential", str(os.getpid())))


def names(*full_names: str) -> list[dict[str, str]]:
    return [{"full_name": full_name} for full_name in full_names]


def api_body(count: int = 30, **overrides: object) -> bytes:
    result = {"total_count": 60000, "incomplete_results": False,
              "items": [{"full_name": f"owner/repo-{number}",
                         "stargazers_count": 500000 - number}
                        for number in range(count)]}
    result.update(overrides)
    return json.dumps(result).encode("utf-8")


@contextlib.contextmanager
def token_env(token: str | None = TOKEN):
    """The token variable set to the fixture value, or absent; never ambient."""
    with unittest.mock.patch.dict(os.environ):
        os.environ.pop("AI_RESEARCHER_GITHUB_TOKEN", None)
        if token is not None:
            os.environ["AI_RESEARCHER_GITHUB_TOKEN"] = token
        yield


@contextlib.contextmanager
def crlf_default_writes():
    """Use real file writers with a CRLF default unless newline is explicit."""
    path_open = pathlib.Path.open

    def translated_open(path, *args, **kwargs):
        mode = args[0] if args else kwargs.get("mode", "r")
        if "w" in mode and kwargs.get("newline") is None:
            kwargs["newline"] = "\r\n"
        return path_open(path, *args, **kwargs)

    with unittest.mock.patch.object(pathlib.Path, "open", translated_open):
        yield


def expected_capture(full_names) -> bytes:
    entries = ",\n".join(f'    {{\n      "full_name": "{name}"\n    }}'
                         for name in full_names)
    return (f'{{\n  "source": "{URL}",\n  "models": [\n{entries}\n  ]\n}}\n'
            ).encode("utf-8")


class MessageTests(unittest.TestCase):
    def test_new_repositories_use_the_sibling_subject_and_body_spelling(self):
        self.assertEqual(
            fetch_github_stars.message([], names("o/a", "o/b")),
            "Most-starred: 2 new in the top 10: o/a, o/b\n\n"
            "NEW  rank 1 o/a\n"
            "NEW  rank 2 o/b\n")

    def test_rank_changes_use_the_new_order_and_exact_arrow_spacing(self):
        self.assertEqual(
            fetch_github_stars.message(names("o/a", "o/b", "o/c"),
                                       names("o/b", "o/a", "o/c")),
            "Most-starred: 2 rank change(s)\n\n"
            "MOVE o/b rank 2 -> 1\n"
            "MOVE o/a rank 1 -> 2\n")

    def test_no_changes_keep_the_order_updated_message(self):
        self.assertEqual(
            fetch_github_stars.message(names("o/a", "o/b"), names("o/a", "o/b")),
            "Most-starred: order updated\n")

    def test_departed_repositories_use_the_exact_out_line(self):
        self.assertEqual(
            fetch_github_stars.message(names("o/a", "o/b"), names("o/a")),
            "Most-starred: order updated\n\n"
            "OUT  o/b (was rank 2)\n")

    def test_new_departed_and_moved_lines_are_combined_in_sibling_order(self):
        text = fetch_github_stars.message(names("o/a", "o/b", "o/c"),
                                          names("o/d", "o/a", "o/c"))
        self.assertEqual(text,
                         "Most-starred: 1 new in the top 10: o/d\n\n"
                         "NEW  rank 1 o/d\n"
                         "OUT  o/b (was rank 2)\n"
                         "MOVE o/a rank 1 -> 2\n")
        # GitHub links every "#N" in a commit message to issue or PR N.
        self.assertNotRegex(text, r"#[0-9]")


class FetchTests(unittest.TestCase):
    def test_request_is_authenticated_and_keeps_the_first_ten_in_order(self):
        calls = []

        def urlopen_stub(request, *, timeout):
            calls.append((request, timeout))
            return io.BytesIO(api_body())

        with token_env(), \
                unittest.mock.patch.object(urllib.request, "urlopen", urlopen_stub):
            result = fetch_github_stars.fetch()

        self.assertEqual(len(calls), 1)
        request, timeout = calls[0]
        self.assertEqual(request.full_url, URL)
        self.assertEqual(request.get_header("Authorization"), f"Bearer {TOKEN}")
        self.assertEqual(request.get_header("Accept"), "application/vnd.github+json")
        self.assertEqual(request.get_header("User-agent"), "ai-researcher-github-stars")
        self.assertEqual(timeout, 30)
        self.assertEqual(result, names(*(f"owner/repo-{n}" for n in range(10))))

    def test_missing_or_empty_token_refuses_before_any_request(self):
        for token in (None, ""):
            with self.subTest(token=token), token_env(token), \
                    unittest.mock.patch.object(urllib.request, "urlopen") as urlopen:
                with self.assertRaises(SystemExit) as caught:
                    fetch_github_stars.fetch()
                self.assertIn("AI_RESEARCHER_GITHUB_TOKEN is not set", str(caught.exception))
                urlopen.assert_not_called()

    def test_every_unexpected_response_shape_refuses(self):
        good = json.loads(api_body())
        missing_name = json.loads(api_body())
        del missing_name["items"][3]["full_name"]
        null_name = json.loads(api_body())
        null_name["items"][0]["full_name"] = None
        no_flag = json.loads(api_body())
        del no_flag["incomplete_results"]
        bodies = {
            "invalid json": b"{",
            "a list, not an object": json.dumps(good["items"]).encode("utf-8"),
            "no items": json.dumps({"incomplete_results": False}).encode("utf-8"),
            "items not a list": api_body(items={"full_name": "o/a"}),
            "item not an object": api_body(items=["o/a"] * 10),
            "item without full_name": json.dumps(missing_name).encode("utf-8"),
            "null full_name": json.dumps(null_name).encode("utf-8"),
            "empty full_name": api_body(items=[{"full_name": ""}] * 10),
            "numeric full_name": api_body(items=[{"full_name": 123}] * 10),
            "incomplete results": api_body(incomplete_results=True),
            "no incomplete_results": json.dumps(no_flag).encode("utf-8"),
        }
        for label, body in bodies.items():
            with self.subTest(shape=label), token_env(), \
                    unittest.mock.patch.object(urllib.request, "urlopen",
                                               return_value=io.BytesIO(body)):
                with self.assertRaises(SystemExit) as caught:
                    fetch_github_stars.fetch()
                self.assertIn(f"{URL}: unexpected response:", str(caught.exception))


class MainTests(unittest.TestCase):
    def run_main(self, capture, body, argv=(), output=None):
        output = output or io.StringIO()
        with token_env(), \
                unittest.mock.patch.object(fetch_github_stars, "DATA", capture), \
                unittest.mock.patch.object(urllib.request, "urlopen",
                                           return_value=io.BytesIO(body)), \
                contextlib.redirect_stdout(output):
            fetch_github_stars.main(list(argv))
        return output.getvalue()

    def assert_refusal_keeps_the_capture(self, body, expected_error):
        with tempfile.TemporaryDirectory() as directory:
            capture = pathlib.Path(directory) / "github-stars.json"
            old_bytes = b'{"source":"old","models":[{"full_name":"o/old"}]}\n'
            capture.write_bytes(old_bytes)
            output = io.StringIO()
            with self.assertRaises(SystemExit) as caught:
                self.run_main(capture, body, output=output)
            self.assertIn(expected_error, str(caught.exception))
            self.assertEqual(capture.read_bytes(), old_bytes)
            self.assertEqual(output.getvalue(), "")

    def test_capture_write_has_exact_json_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = pathlib.Path(directory) / "github-stars.json"
            self.run_main(capture, api_body())
            self.assertEqual(capture.read_bytes(), expected_capture(
                f"owner/repo-{n}" for n in range(10)))

    def test_capture_write_keeps_lf_with_crlf_default(self):
        with crlf_default_writes():
            self.test_capture_write_has_exact_json_bytes()

    def test_message_write_keeps_lf_with_crlf_default(self):
        with crlf_default_writes():
            self.test_message_option_writes_the_same_exact_bytes_it_prints()

    def test_an_unchanged_top_ten_leaves_the_capture_byte_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = pathlib.Path(directory) / "github-stars.json"
            before = expected_capture(f"owner/repo-{n}" for n in range(10))
            capture.write_bytes(before)
            printed = self.run_main(capture, api_body())
            self.assertEqual(capture.read_bytes(), before)
            self.assertEqual(printed, "Most-starred: order updated\n")

    def test_missing_capture_uses_an_empty_previous_list(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = pathlib.Path(directory) / "github-stars.json"
            printed = self.run_main(capture, api_body())
            self.assertIn("Most-starred: 10 new in the top 10:", printed)
            self.assertTrue(capture.is_file())

    def test_message_option_writes_the_same_exact_bytes_it_prints(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = pathlib.Path(directory) / "github-stars.json"
            message_file = pathlib.Path(directory) / "message.txt"
            old = [f"owner/repo-{n}" for n in range(10)]
            capture.write_text(json.dumps({"models": names(*old)}), encoding="utf-8")
            swapped = [{"full_name": name} for name in [old[1], old[0], *old[2:]]]
            printed = self.run_main(capture, api_body(items=swapped),
                                    ["--message", str(message_file)])
            expected = ("Most-starred: 2 rank change(s)\n\n"
                        "MOVE owner/repo-1 rank 2 -> 1\n"
                        "MOVE owner/repo-0 rank 1 -> 2\n")
            self.assertEqual(message_file.read_bytes(), expected.encode("utf-8"))
            self.assertEqual(printed, expected)

    def test_short_result_refuses_without_changing_the_capture(self):
        self.assert_refusal_keeps_the_capture(api_body(count=9),
                                              "expected 10 repositories, got 9")

    def test_bad_shape_refuses_without_changing_the_capture(self):
        self.assert_refusal_keeps_the_capture(api_body(incomplete_results=True),
                                              "unexpected response")

    def test_http_failure_refuses_without_changing_the_capture(self):
        refused = urllib.error.HTTPError(URL, 401, "Bad credentials",
                                         email.message.Message(), None)
        with tempfile.TemporaryDirectory() as directory:
            capture = pathlib.Path(directory) / "github-stars.json"
            old_bytes = b'{"source":"old","models":[{"full_name":"o/old"}]}\n'
            capture.write_bytes(old_bytes)
            with token_env(), \
                    unittest.mock.patch.object(fetch_github_stars, "DATA", capture), \
                    unittest.mock.patch.object(urllib.request, "urlopen",
                                               side_effect=refused) as urlopen, \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(SystemExit) as caught:
                    fetch_github_stars.main([])
            self.assertIn(f"{URL}: fetch failed: HTTP Error 401", str(caught.exception))
            self.assertEqual(urlopen.call_count, 1)
            self.assertEqual(capture.read_bytes(), old_bytes)
            self.assertEqual(output.getvalue(), "")

    def test_missing_token_refuses_without_changing_the_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = pathlib.Path(directory) / "github-stars.json"
            old_bytes = b'{"source":"old","models":[{"full_name":"o/old"}]}\n'
            capture.write_bytes(old_bytes)
            with token_env(None), \
                    unittest.mock.patch.object(fetch_github_stars, "DATA", capture), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(SystemExit) as caught:
                    fetch_github_stars.main([])
            self.assertIn("AI_RESEARCHER_GITHUB_TOKEN is not set", str(caught.exception))
            self.assertEqual(capture.read_bytes(), old_bytes)
            self.assertEqual(output.getvalue(), "")

    def test_committed_seed_has_the_source_url_and_ten_repository_names(self):
        seed = json.loads(SEED.read_text(encoding="utf-8"))

        self.assertEqual(seed["source"], URL)
        self.assertEqual(len(seed["models"]), 10)
        self.assertTrue(all(isinstance(repo["full_name"], str)
                            for repo in seed["models"]))
