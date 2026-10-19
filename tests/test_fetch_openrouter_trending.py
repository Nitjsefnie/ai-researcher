"""Behavioral tests for the independent OpenRouter trending capture."""
import contextlib
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_openrouter_trending  # noqa: E402  # pylint: disable=wrong-import-position

URL = "https://openrouter.ai/api/frontend/v1/models/find?order=top-weekly"
SEED = ROOT / "data" / "openrouter-trending.json"


def slugs(*model_slugs: str) -> list[dict[str, str]]:
    return [{"slug": slug} for slug in model_slugs]


def api_models() -> dict[str, object]:
    return {"data": {"models": [
        {"slug": f"org/model-{number}", "weeklyTokens": 100 - number}
        for number in range(10)
    ]}}


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


class MessageTests(unittest.TestCase):
    def test_one_rank_change_uses_the_exact_subject_and_rank_spelling(self):
        self.assertEqual(
            fetch_openrouter_trending.message(
                slugs("org/a", "org/b", "org/x"), slugs("org/x")),
            "Top 10: 1 rank change(s)\n\n"
            "OUT  org/a (was rank 1)\n"
            "OUT  org/b (was rank 2)\n"
            "MOVE org/x rank 3 -> 1\n")

    def test_new_models_use_the_upstream_subject_and_body_spelling(self):
        self.assertEqual(
            fetch_openrouter_trending.message([], slugs("org/a", "org/b")),
            "Top 10: 2 new: org/a, org/b\n\n"
            "NEW  rank 1 org/a\n"
            "NEW  rank 2 org/b\n")

    def test_rank_changes_use_the_new_order_and_exact_arrow_spacing(self):
        self.assertEqual(
            fetch_openrouter_trending.message(
                slugs("org/a", "org/b", "org/c"),
                slugs("org/b", "org/a", "org/c")),
            "Top 10: 2 rank change(s)\n\n"
            "MOVE org/b rank 2 -> 1\n"
            "MOVE org/a rank 1 -> 2\n")

    def test_no_changes_keep_the_upstream_order_updated_message(self):
        self.assertEqual(
            fetch_openrouter_trending.message(
                slugs("org/a", "org/b"), slugs("org/a", "org/b")),
            "Top 10: order updated\n")

    def test_departed_models_use_the_exact_out_line(self):
        self.assertEqual(
            fetch_openrouter_trending.message(slugs("org/a", "org/b"), slugs("org/a")),
            "Top 10: order updated\n\n"
            "OUT  org/b (was rank 2)\n")

    def test_new_departed_and_moved_lines_are_combined_in_upstream_order(self):
        self.assertEqual(
            fetch_openrouter_trending.message(
                slugs("org/a", "org/old", "org/c"),
                slugs("org/new", "org/a", "org/c")),
            "Top 10: 1 new: org/new\n\n"
            "NEW  rank 1 org/new\n"
            "OUT  org/old (was rank 2)\n"
            "MOVE org/a rank 1 -> 2\n")

    def test_no_line_names_an_issue_reference(self):
        # GitHub links every "#N" in a commit message to issue or PR N.
        text = fetch_openrouter_trending.message(
            slugs("org/a", "org/b", "org/c"), slugs("org/d", "org/a", "org/c"))
        self.assertNotRegex(text, r"#[0-9]")


class FetchTests(unittest.TestCase):
    def test_request_uses_the_upstream_url_header_timeout_and_first_ten_slugs(self):
        api_response = [
            {"slug": f"org/model-{number}", "weeklyTokens": number}
            for number in range(12)
        ]
        calls = []

        def urlopen_stub(request, *, timeout):
            calls.append((request, timeout))
            return io.BytesIO(json.dumps({"data": {"models": api_response}}).encode("utf-8"))

        with unittest.mock.patch.object(urllib.request, "urlopen", urlopen_stub):
            result = fetch_openrouter_trending.fetch()

        self.assertEqual(len(calls), 1)
        request, timeout = calls[0]
        self.assertEqual(request.full_url, URL)
        self.assertEqual(request.get_header("User-agent"), "Mozilla/5.0 (openrouter-top)")
        self.assertEqual(request.get_header("Cache-control"), "no-cache")
        self.assertEqual(timeout, 60)
        self.assertEqual(result, slugs(*(f"org/model-{number}" for number in range(10))))


class MainTests(unittest.TestCase):
    def test_seed_checkout_keeps_lf_with_autocrlf(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = pathlib.Path(directory)
            subprocess.run(["git", "init", "-q", str(repo)], check=True,
                           capture_output=True, timeout=60)
            (repo / ".gitattributes").write_bytes((ROOT / ".gitattributes").read_bytes())
            seed = repo / "data" / "openrouter-trending.json"
            seed.parent.mkdir()
            seed_bytes = b'{"models": []}\n'
            seed.write_bytes(seed_bytes)
            subprocess.run(
                ["git", "-C", str(repo), "-c", "core.autocrlf=false", "add", "--",
                 ".gitattributes", "data/openrouter-trending.json"],
                check=True, capture_output=True, timeout=60)
            output = repo / "checkout"
            subprocess.run(
                ["git", "-C", str(repo), "-c", "core.autocrlf=true", "checkout-index",
                 f"--prefix={output.as_posix()}/", "--", "data/openrouter-trending.json"],
                check=True, capture_output=True, timeout=60)
            checked_out = (output / "data" / "openrouter-trending.json").read_bytes()

            self.assertNotIn(b"\r", checked_out)
            self.assertEqual(checked_out, seed_bytes)

    def test_capture_write_keeps_lf_with_crlf_default(self):
        with crlf_default_writes():
            self.test_capture_write_has_exact_json_bytes()

    def test_message_write_keeps_lf_with_crlf_default(self):
        with crlf_default_writes():
            self.test_message_option_writes_the_same_exact_bytes_it_prints()

    def test_missing_capture_uses_an_empty_previous_list(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = pathlib.Path(directory) / "openrouter-trending.json"
            output = io.StringIO()
            response = io.BytesIO(json.dumps(api_models()).encode("utf-8"))

            with unittest.mock.patch.object(fetch_openrouter_trending, "DATA", capture), \
                    unittest.mock.patch.object(urllib.request, "urlopen",
                                               return_value=response), \
                    contextlib.redirect_stdout(output):
                fetch_openrouter_trending.main([])

            self.assertIn("Top 10: 10 new:", output.getvalue())
            self.assertTrue(capture.is_file())

    def test_capture_write_has_exact_json_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = pathlib.Path(directory) / "openrouter-trending.json"
            response = io.BytesIO(json.dumps(api_models()).encode("utf-8"))
            expected = (
                b'{\n'
                b'  "source": "https://openrouter.ai/api/frontend/v1/models/find?order=top-weekly",\n'
                b'  "models": [\n'
                b'    {\n      "slug": "org/model-0"\n    },\n'
                b'    {\n      "slug": "org/model-1"\n    },\n'
                b'    {\n      "slug": "org/model-2"\n    },\n'
                b'    {\n      "slug": "org/model-3"\n    },\n'
                b'    {\n      "slug": "org/model-4"\n    },\n'
                b'    {\n      "slug": "org/model-5"\n    },\n'
                b'    {\n      "slug": "org/model-6"\n    },\n'
                b'    {\n      "slug": "org/model-7"\n    },\n'
                b'    {\n      "slug": "org/model-8"\n    },\n'
                b'    {\n      "slug": "org/model-9"\n    }\n'
                b'  ]\n'
                b'}\n')

            with unittest.mock.patch.object(fetch_openrouter_trending, "DATA", capture), \
                    unittest.mock.patch.object(urllib.request, "urlopen",
                                               return_value=response), \
                    contextlib.redirect_stdout(io.StringIO()):
                fetch_openrouter_trending.main([])

            self.assertEqual(capture.read_bytes(), expected)
            self.assertNotIn(b"\r", capture.read_bytes())

    def test_short_api_result_refuses_without_changing_the_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = pathlib.Path(directory) / "openrouter-trending.json"
            old_bytes = (
                b'{"source":"old","models":[{"slug":"org/old"}]}\n')
            capture.write_bytes(old_bytes)
            response = io.BytesIO(json.dumps({"data": {"models": [
                {"slug": f"org/model-{n}"} for n in range(9)]}}).encode("utf-8"))
            output = io.StringIO()

            with unittest.mock.patch.object(fetch_openrouter_trending, "DATA", capture), \
                    unittest.mock.patch.object(urllib.request, "urlopen",
                                               return_value=response), \
                    contextlib.redirect_stdout(output):
                with self.assertRaises(SystemExit) as caught:
                    fetch_openrouter_trending.main([])

            self.assertEqual(str(caught.exception), "expected 10 models, got 9")
            self.assertEqual(capture.read_bytes(), old_bytes)
            self.assertEqual(output.getvalue(), "")

    def test_message_option_writes_the_same_exact_bytes_it_prints(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = pathlib.Path(directory) / "openrouter-trending.json"
            message_file = pathlib.Path(directory) / "message.txt"
            old_slugs = [f"org/model-{number}" for number in range(10)]
            capture.write_text(json.dumps({"models": slugs(*old_slugs)}),
                               encoding="utf-8")
            new_slugs = [old_slugs[1], old_slugs[0], *old_slugs[2:]]
            response = io.BytesIO(json.dumps(
                {"data": {"models": [{"slug": slug} for slug in new_slugs]}}
            ).encode("utf-8"))
            output = io.StringIO()
            expected = (
                "Top 10: 2 rank change(s)\n\n"
                "MOVE org/model-1 rank 2 -> 1\n"
                "MOVE org/model-0 rank 1 -> 2\n")

            with unittest.mock.patch.object(fetch_openrouter_trending, "DATA", capture), \
                    unittest.mock.patch.object(urllib.request, "urlopen",
                                               return_value=response), \
                    contextlib.redirect_stdout(output):
                fetch_openrouter_trending.main(["--message", str(message_file)])

            self.assertEqual(message_file.read_bytes(), expected.encode("utf-8"))
            self.assertNotIn(b"\r", message_file.read_bytes())
            self.assertEqual(output.getvalue(), expected)

    def test_unchanged_seed_remains_byte_identical_and_announces_no_models(self):
        seed_bytes = SEED.read_bytes()
        seed = json.loads(seed_bytes)
        with tempfile.TemporaryDirectory() as directory:
            capture = pathlib.Path(directory) / "openrouter-trending.json"
            capture.write_bytes(seed_bytes)
            response = io.BytesIO(json.dumps(
                {"data": {"models": seed["models"]}}).encode("utf-8"))
            output = io.StringIO()
            with unittest.mock.patch.object(fetch_openrouter_trending, "DATA", capture), \
                    unittest.mock.patch.object(urllib.request, "urlopen",
                                               return_value=response), \
                    unittest.mock.patch.object(sys, "argv", ["fetch_openrouter_trending.py"]), \
                    contextlib.redirect_stdout(output):
                fetch_openrouter_trending.main()

            self.assertEqual(capture.read_bytes(), seed_bytes)
            self.assertEqual(output.getvalue(), "Top 10: order updated\n")

    def test_committed_seed_has_ten_model_slugs(self):
        seed = json.loads(SEED.read_text(encoding="utf-8"))

        self.assertEqual(seed["source"], URL)
        self.assertEqual(len(seed["models"]), 10)
        self.assertTrue(all(isinstance(model["slug"], str)
                            for model in seed["models"]))
