import email.message
import io
import json
import pathlib
import sys
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import publish_docs  # noqa: E402  # pylint: disable=wrong-import-position

PAGE = b"<html>frontier</html>"


class Response:
    """Context-manager stand-in for urlopen's return value."""

    def __init__(self, status: int, body: bytes):
        self.status = status
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._body


class MultipartTests(unittest.TestCase):
    def test_encodes_fields_and_the_file_under_the_name_the_hub_reads(self):
        body, content_type = publish_docs.multipart(
            {"slug": "a/b", "from": "ai-researcher"}, "page.html", PAGE)

        boundary = content_type.split("boundary=")[1]
        self.assertIn(f"--{boundary}".encode(), body)
        self.assertIn(b'name="slug"', body)
        self.assertIn(b"a/b", body)
        # The hub takes the document from a part named exactly `file`.
        self.assertIn(b'name="file"; filename="page.html"', body)
        self.assertIn(PAGE, body)
        self.assertTrue(body.endswith(f"--{boundary}--\r\n".encode()))


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.page = pathlib.Path(__file__).resolve().parent / "_page.html"
        self.page.write_bytes(PAGE)
        self.addCleanup(self.page.unlink)

    def publish(self, urlopen):
        with mock.patch.object(publish_docs.urllib.request, "urlopen", urlopen):
            return publish_docs.publish(str(self.page), {"slug": "a/b"},
                                        "secret-key", "https://hub.example")

    def test_sends_the_key_as_a_header_and_reports_success(self):
        seen = {}

        def urlopen(req, timeout=None):
            seen["url"] = req.full_url
            seen["key"] = req.get_header("X-docs-key")
            seen["timeout"] = timeout
            return Response(200, json.dumps({"ok": True, "version": 7}).encode())

        self.assertEqual(self.publish(urlopen), 0)
        self.assertEqual(seen["url"], "https://hub.example/api/publish")
        # Never a query parameter or an argument: headers stay out of logs.
        self.assertEqual(seen["key"], "secret-key")
        self.assertIsNotNone(seen["timeout"])

    def test_http_error_is_a_failure_not_a_traceback(self):
        def urlopen(req, timeout=None):
            # HTTPError's `hdrs` is typed as an email.message.Message; a bare
            # dict works at runtime but is not what the signature promises.
            raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized",
                                         email.message.Message(),
                                         io.BytesIO(b'{"error":"bad key"}'))

        with mock.patch.object(sys, "stderr", io.StringIO()) as err:
            self.assertEqual(self.publish(urlopen), 1)
        self.assertIn("HTTP 401", err.getvalue())

    def test_unreachable_hub_is_a_failure_not_a_traceback(self):
        def urlopen(req, timeout=None):
            raise urllib.error.URLError("connection refused")

        with mock.patch.object(sys, "stderr", io.StringIO()) as err:
            self.assertEqual(self.publish(urlopen), 1)
        self.assertIn("cannot reach", err.getvalue())

    def test_non_json_body_is_a_failure(self):
        # A Cloudflare error page answers 200 with HTML often enough to matter.
        def urlopen(req, timeout=None):
            return Response(200, b"<html>502</html>")

        with mock.patch.object(sys, "stderr", io.StringIO()) as err:
            self.assertEqual(self.publish(urlopen), 1)
        self.assertIn("non-JSON", err.getvalue())

    def test_json_error_field_fails_even_on_a_2xx(self):
        def urlopen(req, timeout=None):
            return Response(200, json.dumps({"error": "slug rejected"}).encode())

        self.assertEqual(self.publish(urlopen), 1)


class MainTests(unittest.TestCase):
    def test_missing_key_exits_2_without_touching_the_network(self):
        argv = ["publish_docs.py", "page.html", "--slug", "a/b",
                "--title", "T", "--from", "ai-researcher"]
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.dict(publish_docs.os.environ, {"DOCS_HUB_API_KEY": ""}), \
                mock.patch.object(sys, "stderr", io.StringIO()) as err:
            self.assertEqual(publish_docs.main(), 2)

        self.assertIn("DOCS_HUB_API_KEY", err.getvalue())


if __name__ == "__main__":
    unittest.main()
