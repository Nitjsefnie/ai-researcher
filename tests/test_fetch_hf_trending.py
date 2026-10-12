"""Behavioral tests for the independent Hugging Face trending capture."""
import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest
import unittest.mock
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_hf_trending  # noqa: E402  # pylint: disable=wrong-import-position

URL = "https://huggingface.co/api/models?sort=trendingScore&limit=10"
SEED = ROOT / "data" / "hf-trending.json"


def ids(*model_ids: str) -> list[dict[str, str]]:
    return [{"id": model_id} for model_id in model_ids]


def api_models() -> list[dict[str, object]]:
    return [
        {"id": f"org/model-{number}", "trendingScore": 100 - number}
        for number in range(10)
    ]


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
    def test_new_models_use_the_upstream_subject_and_body_spelling(self):
        self.assertEqual(
            fetch_hf_trending.message([], ids("org/a", "org/b")),
            "Trending: 2 new in the top 10: org/a, org/b\n\n"
            "NEW  #1 org/a\n"
            "NEW  #2 org/b\n")

    def test_rank_changes_use_the_new_order_and_exact_arrow_spacing(self):
        self.assertEqual(
            fetch_hf_trending.message(
                ids("org/a", "org/b", "org/c"),
                ids("org/b", "org/a", "org/c")),
            "Trending: 2 rank change(s)\n\n"
            "MOVE org/b #2 -> #1\n"
            "MOVE org/a #1 -> #2\n")

    def test_no_changes_keep_the_upstream_order_updated_message(self):
        self.assertEqual(
            fetch_hf_trending.message(ids("org/a", "org/b"),
                                      ids("org/a", "org/b")),
            "Trending: order updated\n")

    def test_departed_models_use_the_exact_out_line(self):
        self.assertEqual(
            fetch_hf_trending.message(ids("org/a", "org/b"), ids("org/a")),
            "Trending: order updated\n\n"
            "OUT  org/b (was #2)\n")

    def test_new_departed_and_moved_lines_are_combined_in_upstream_order(self):
        self.assertEqual(
            fetch_hf_trending.message(
                ids("org/a", "org/b", "org/c"),
                ids("org/d", "org/a", "org/c")),
            "Trending: 1 new in the top 10: org/d\n\n"
            "NEW  #1 org/d\n"
            "OUT  org/b (was #2)\n"
            "MOVE org/a #1 -> #2\n")


class FetchTests(unittest.TestCase):
    def test_request_uses_the_upstream_url_header_timeout_and_first_ten_ids(self):
        api_response = [
            {"id": f"org/model-{number}", "trendingScore": number}
            for number in range(12)
        ]
        calls = []

        def urlopen_stub(request, *, timeout):
            calls.append((request, timeout))
            return io.BytesIO(json.dumps(api_response).encode("utf-8"))

        with unittest.mock.patch.object(urllib.request, "urlopen", urlopen_stub):
            result = fetch_hf_trending.fetch()

        self.assertEqual(len(calls), 1)
        request, timeout = calls[0]
        self.assertEqual(request.full_url, URL)
        self.assertEqual(request.get_header("User-agent"), "hf-trending")
        self.assertEqual(timeout, 30)
        self.assertEqual(result, ids(*(f"org/model-{number}" for number in range(10))))


class MainTests(unittest.TestCase):
    def test_capture_write_keeps_lf_with_crlf_default(self):
        with crlf_default_writes():
            self.test_capture_write_has_exact_json_bytes()

    def test_message_write_keeps_lf_with_crlf_default(self):
        with crlf_default_writes():
            self.test_message_option_writes_the_same_exact_bytes_it_prints()

    def test_missing_capture_uses_an_empty_previous_list(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = pathlib.Path(directory) / "hf-trending.json"
            output = io.StringIO()
            response = io.BytesIO(json.dumps(api_models()).encode("utf-8"))

            with unittest.mock.patch.object(fetch_hf_trending, "DATA", capture), \
                    unittest.mock.patch.object(urllib.request, "urlopen",
                                               return_value=response), \
                    contextlib.redirect_stdout(output):
                fetch_hf_trending.main([])

            self.assertIn("Trending: 10 new in the top 10:", output.getvalue())
            self.assertTrue(capture.is_file())

    def test_capture_write_has_exact_json_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = pathlib.Path(directory) / "hf-trending.json"
            response = io.BytesIO(json.dumps(api_models()).encode("utf-8"))
            expected = (
                b'{\n'
                b'  "source": "https://huggingface.co/api/models?sort=trendingScore&limit=10",\n'
                b'  "models": [\n'
                b'    {\n      "id": "org/model-0"\n    },\n'
                b'    {\n      "id": "org/model-1"\n    },\n'
                b'    {\n      "id": "org/model-2"\n    },\n'
                b'    {\n      "id": "org/model-3"\n    },\n'
                b'    {\n      "id": "org/model-4"\n    },\n'
                b'    {\n      "id": "org/model-5"\n    },\n'
                b'    {\n      "id": "org/model-6"\n    },\n'
                b'    {\n      "id": "org/model-7"\n    },\n'
                b'    {\n      "id": "org/model-8"\n    },\n'
                b'    {\n      "id": "org/model-9"\n    }\n'
                b'  ]\n'
                b'}\n')

            with unittest.mock.patch.object(fetch_hf_trending, "DATA", capture), \
                    unittest.mock.patch.object(urllib.request, "urlopen",
                                               return_value=response), \
                    contextlib.redirect_stdout(io.StringIO()):
                fetch_hf_trending.main([])

            self.assertEqual(capture.read_bytes(), expected)

    def test_short_api_result_refuses_without_changing_the_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = pathlib.Path(directory) / "hf-trending.json"
            old_bytes = (
                b'{"source":"old","models":[{"id":"org/old"}]}\n')
            capture.write_bytes(old_bytes)
            response = io.BytesIO(json.dumps(api_models()[:9]).encode("utf-8"))
            output = io.StringIO()

            with unittest.mock.patch.object(fetch_hf_trending, "DATA", capture), \
                    unittest.mock.patch.object(urllib.request, "urlopen",
                                               return_value=response), \
                    contextlib.redirect_stdout(output):
                with self.assertRaises(SystemExit) as caught:
                    fetch_hf_trending.main([])

            self.assertEqual(str(caught.exception), "expected 10 models, got 9")
            self.assertEqual(capture.read_bytes(), old_bytes)
            self.assertEqual(output.getvalue(), "")

    def test_message_option_writes_the_same_exact_bytes_it_prints(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = pathlib.Path(directory) / "hf-trending.json"
            message_file = pathlib.Path(directory) / "message.txt"
            old_ids = [f"org/model-{number}" for number in range(10)]
            capture.write_text(json.dumps({"models": ids(*old_ids)}),
                               encoding="utf-8")
            new_ids = [old_ids[1], old_ids[0], *old_ids[2:]]
            response = io.BytesIO(json.dumps(
                [{"id": model_id} for model_id in new_ids]
            ).encode("utf-8"))
            output = io.StringIO()
            expected = (
                "Trending: 2 rank change(s)\n\n"
                "MOVE org/model-1 #2 -> #1\n"
                "MOVE org/model-0 #1 -> #2\n")

            with unittest.mock.patch.object(fetch_hf_trending, "DATA", capture), \
                    unittest.mock.patch.object(urllib.request, "urlopen",
                                               return_value=response), \
                    contextlib.redirect_stdout(output):
                fetch_hf_trending.main(["--message", str(message_file)])

            self.assertEqual(message_file.read_bytes(), expected.encode("utf-8"))
            self.assertEqual(output.getvalue(), expected)

    def test_committed_seed_has_ten_model_ids(self):
        seed = json.loads(SEED.read_text(encoding="utf-8"))

        self.assertEqual(seed["source"], URL)
        self.assertEqual(len(seed["models"]), 10)
        self.assertTrue(all(isinstance(model["id"], str)
                            for model in seed["models"]))
