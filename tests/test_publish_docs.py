import email.message
import http.client
import io
import json
import pathlib
import sys
import unittest
import urllib.error
import urllib.parse
from unittest import mock

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent / "scripts"
sys.path[:0] = [str(SCRIPTS), str(SCRIPTS / "ci")]

import download  # noqa: E402  # pylint: disable=wrong-import-position
import publish_docs  # noqa: E402  # pylint: disable=wrong-import-position

PAGE = b"<html>frontier</html>"

# The only host the credential may be sent to, derived from the production
# default the same way the client must derive it — never a second literal.
# `hostname` is typed Optional; the production default always carries a host.
HUB_HOST = urllib.parse.urlsplit(publish_docs.DEFAULT_URL).hostname
assert isinstance(HUB_HOST, str)


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
    # pylint: disable=too-many-public-methods
    # One behaviour, one test: each refusal row is a named test sharing the
    # same assert_refused contract, as in test_browser.py.
    def setUp(self):
        self.page = pathlib.Path(__file__).resolve().parent / "_page.html"
        self.page.write_bytes(PAGE)
        self.addCleanup(self.page.unlink)
        # The retry backoff runs on a clock only its own sleeps advance.
        self.sleeps = []
        for name, fake in (("sleep", self.sleeps.append),
                           ("monotonic", lambda: sum(self.sleeps))):
            patcher = mock.patch.object(download.time, name, fake)
            patcher.start()
            self.addCleanup(patcher.stop)

    def scripted(self, *answers):
        """A urlopen answering each call with the next answer, the last
        repeating: a status code, or an exception to raise."""
        calls = []

        def urlopen(req, timeout=None):
            calls.append(req.full_url)
            answer = answers[min(len(calls), len(answers)) - 1]
            if isinstance(answer, BaseException):
                raise answer
            if not 200 <= answer < 300:
                raise urllib.error.HTTPError(
                    req.full_url, answer, "refused", email.message.Message(),
                    io.BytesIO(b'{"error":"hub refusal"}'))
            return Response(answer, json.dumps({"ok": True}).encode())
        return urlopen, calls

    def publish(self, urlopen):
        with mock.patch.object(publish_docs.urllib.request, "urlopen", urlopen):
            return publish_docs.publish(str(self.page), {"slug": "a/b"},
                                        "secret-key", publish_docs.DEFAULT_URL)

    def publish_to(self, base, urlopen):
        with mock.patch.object(publish_docs.urllib.request, "urlopen", urlopen), \
                mock.patch.object(sys, "stderr", io.StringIO()) as err:
            return publish_docs.publish(str(self.page), {"slug": "a/b"},
                                        "secret-key", base), err.getvalue()

    def assert_refused(self, base):
        """The credential never leaves: no network call, exit 2, a one-line
        diagnostic naming the URL and requiring https on the pinned hub host."""
        urlopen = mock.MagicMock(return_value=Response(200, b"{}"))

        code, err = self.publish_to(base, urlopen)

        self.assertEqual(code, 2)
        self.assertIn(base, err)
        self.assertIn("https", err)
        self.assertIn(HUB_HOST, err)
        urlopen.assert_not_called()

    def test_http_base_url_is_refused_before_any_network_call(self):
        self.assert_refused("http://127.0.0.1:9999")

    def test_cleartext_to_the_hub_host_is_refused_before_any_network_call(self):
        # Cleartext to the RIGHT host: netloc is fine and the hostname pin
        # passes, so this row alone decides the scheme limb — without it,
        # every wrong-scheme row is also wrong-host and deleting the scheme
        # check stays green.
        self.assert_refused(f"http://{HUB_HOST}")

    def test_schemeless_base_url_is_refused_before_any_network_call(self):
        # No scheme: urlsplit finds neither a scheme nor a netloc to trust.
        self.assert_refused("127.0.0.1:9999")

    def test_https_scheme_with_no_netloc_is_refused_before_any_network_call(self):
        # The empty-netloc shape (`https:` parses with hostname=None) refuses
        # observably. The netloc limb deciding it is defense-in-depth — the
        # hostname pin co-refuses this input, so deleting the netloc limb
        # alone stays green — and is kept deliberately; this row pins the
        # refusal, not which limb produces it.
        self.assert_refused("https:")

    def test_wrong_host_is_refused_before_any_network_call(self):
        # A well-formed https URL at a different host is still a leak: the
        # credential would be handed to whoever controls that host.
        self.assert_refused("https://evil.com")

    def test_ftp_base_url_is_refused_before_any_network_call(self):
        self.assert_refused("ftp://host")

    def test_empty_base_url_is_refused_before_any_network_call(self):
        self.assert_refused("")

    def test_unparseable_base_url_is_refused_before_any_network_call(self):
        # A malformed URL (here: an unclosed IPv6 bracket) must take the
        # documented refusal, not propagate urlsplit's ValueError.
        self.assert_refused("http://[::1")

    def test_nonnumeric_port_is_refused_before_any_network_call(self):
        # urlsplit accepts a nonnumeric port and .hostname silently drops
        # it, so the pinned-host check passed and the request died in
        # urlopen as an http.client.InvalidURL traceback.
        self.assert_refused(f"https://{HUB_HOST}:notaport")

    def test_out_of_range_port_is_refused_before_any_network_call(self):
        self.assert_refused(f"https://{HUB_HOST}:99999")

    def test_uppercase_https_scheme_is_accepted(self):
        # urlsplit lowercases the scheme, so HTTPS:// is a healthy path.
        def urlopen(req, timeout=None):
            return Response(200, json.dumps({"ok": True, "version": 7}).encode())

        code, _ = self.publish_to("HTTPS://DOCS.NITJSEFNI.EU", urlopen)
        self.assertEqual(code, 0)

    def test_uppercase_host_is_accepted(self):
        # The pin compares parsed.hostname, which urlsplit lowercases — a
        # case-normalized spelling of the hub must not be refused.
        def urlopen(req, timeout=None):
            return Response(200, json.dumps({"ok": True, "version": 7}).encode())

        code, _ = self.publish_to("https://DOCS.NITJSEFNI.EU", urlopen)
        self.assertEqual(code, 0)

    def test_explicit_valid_port_is_accepted(self):
        # The port read must refuse only MALFORMED ports: an explicit valid
        # one is an ordinary https base, so a fix that refuses every port
        # cannot pass this row.
        def urlopen(req, timeout=None):
            return Response(200, json.dumps({"ok": True, "version": 7}).encode())

        code, _ = self.publish_to(f"https://{HUB_HOST}:443", urlopen)
        self.assertEqual(code, 0)

    def test_sends_the_key_as_a_header_and_reports_success(self):
        seen = {}

        def urlopen(req, timeout=None):
            seen["url"] = req.full_url
            seen["key"] = req.get_header("X-docs-key")
            seen["timeout"] = timeout
            return Response(200, json.dumps({"ok": True, "version": 7}).encode())

        self.assertEqual(self.publish(urlopen), 0)
        self.assertEqual(seen["url"], publish_docs.DEFAULT_URL + "/api/publish")
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

    def test_a_5xx_then_success_is_retried_once(self):
        urlopen, calls = self.scripted(503, 200)
        self.assertEqual(self.publish(urlopen), 0)
        self.assertEqual((len(calls), self.sleeps), (2, [5]))

    def test_a_429_is_retried(self):
        urlopen, calls = self.scripted(429, 200)
        self.assertEqual(self.publish(urlopen), 0)
        self.assertEqual((len(calls), self.sleeps), (2, [5]))

    def test_a_timeout_or_dropped_connection_is_retried(self):
        for fault in (urllib.error.URLError("connection refused"),
                      TimeoutError("timed out"),
                      ConnectionResetError("connection reset by peer"),
                      http.client.RemoteDisconnected("closed"),
                      http.client.IncompleteRead(b"")):
            with self.subTest(fault=fault):
                self.sleeps.clear()
                urlopen, calls = self.scripted(fault, 200)
                with mock.patch.object(sys, "stderr", io.StringIO()):
                    self.assertEqual(self.publish(urlopen), 0)
                self.assertEqual((len(calls), self.sleeps), (2, [5]))

    def test_another_4xx_fails_at_once_with_the_hubs_body(self):
        urlopen, calls = self.scripted(400)
        with mock.patch.object(sys, "stderr", io.StringIO()) as err:
            self.assertEqual(self.publish(urlopen), 1)
        self.assertEqual((len(calls), self.sleeps), (1, []))
        self.assertIn("publish failed: HTTP 400", err.getvalue())
        self.assertIn("hub refusal", err.getvalue())

    def test_a_2xx_error_field_fails_at_once(self):
        calls = []

        def urlopen(req, timeout=None):
            calls.append(req.full_url)
            return Response(200, json.dumps({"error": "slug rejected"}).encode())

        with mock.patch.object(sys, "stderr", io.StringIO()) as err, \
                mock.patch.object(sys, "stdout", io.StringIO()) as out:
            self.assertEqual(self.publish(urlopen), 1)
        self.assertEqual((len(calls), self.sleeps), (1, []))
        self.assertIn("publish failed: HTTP 200 with an error field", err.getvalue())
        self.assertIn("slug rejected", out.getvalue())

    def test_exhausting_the_window_fails_naming_the_attempts(self):
        urlopen, calls = self.scripted(503)
        with mock.patch.object(sys, "stderr", io.StringIO()) as err:
            self.assertEqual(self.publish(urlopen), 1)
        self.assertEqual((len(calls), self.sleeps), (8, [5, 10, 20, 40, 60, 60, 60]))
        self.assertIn("publish failed after 8 attempts in 255s: HTTP 503",
                      err.getvalue())
        self.assertIn("hub refusal", err.getvalue())

    def test_download_pys_window_governs_the_retry(self):
        # 5 + 10 fit a 15 s window and the next 20 s backoff does not, so
        # three attempts run: the window is download.py's, not a copy.
        urlopen, calls = self.scripted(503)
        with mock.patch.object(download, "WINDOW_SECONDS", 15), \
                mock.patch.object(sys, "stderr", io.StringIO()) as err:
            self.assertEqual(self.publish(urlopen), 1)
        self.assertEqual((len(calls), self.sleeps), (3, [5, 10]))
        self.assertIn("after 3 attempts in 15s", err.getvalue())


class MainTests(unittest.TestCase):
    def setUp(self):
        self.page = pathlib.Path(__file__).resolve().parent / "_page.html"
        self.page.write_bytes(PAGE)
        self.addCleanup(self.page.unlink)

    def argv(self):
        return ["publish_docs.py", str(self.page), "--slug", "a/b",
                "--title", "T", "--from", "ai-researcher"]

    def test_missing_key_exits_2_without_touching_the_network(self):
        argv = ["publish_docs.py", "page.html", "--slug", "a/b",
                "--title", "T", "--from", "ai-researcher"]
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.dict(publish_docs.os.environ, {"DOCS_HUB_API_KEY": ""}), \
                mock.patch.object(sys, "stderr", io.StringIO()) as err:
            self.assertEqual(publish_docs.main(), 2)

        self.assertIn("DOCS_HUB_API_KEY", err.getvalue())

    def test_default_url_is_the_https_one_and_reaches_the_network(self):
        seen = {}

        def urlopen(req, timeout=None):
            seen["url"] = req.full_url
            return Response(200, json.dumps({"ok": True, "version": 7}).encode())

        with mock.patch.object(sys, "argv", self.argv()), \
                mock.patch.dict(publish_docs.os.environ,
                                {"DOCS_HUB_API_KEY": "secret-key"}), \
                mock.patch.object(publish_docs.urllib.request, "urlopen", urlopen):
            # Absent from the environment, not merely blank: the override is
            # the attack surface, so the default must survive its absence.
            publish_docs.os.environ.pop("DOCS_HUB_URL", None)
            code = publish_docs.main()

        self.assertEqual(code, 0)
        self.assertEqual(seen["url"], publish_docs.DEFAULT_URL + "/api/publish")

    def test_http_url_override_is_refused_before_the_network(self):
        urlopen = mock.MagicMock(return_value=Response(200, b"{}"))

        with mock.patch.object(sys, "argv", self.argv()), \
                mock.patch.dict(publish_docs.os.environ,
                                {"DOCS_HUB_API_KEY": "secret-key",
                                 "DOCS_HUB_URL": "http://127.0.0.1:9999"}), \
                mock.patch.object(publish_docs.urllib.request, "urlopen", urlopen), \
                mock.patch.object(sys, "stderr", io.StringIO()) as err:
            code = publish_docs.main()

        self.assertEqual(code, 2)
        self.assertIn("http://127.0.0.1:9999", err.getvalue())
        urlopen.assert_not_called()

    def test_wrong_host_url_override_is_refused_before_the_network(self):
        urlopen = mock.MagicMock(return_value=Response(200, b"{}"))

        with mock.patch.object(sys, "argv", self.argv()), \
                mock.patch.dict(publish_docs.os.environ,
                                {"DOCS_HUB_API_KEY": "secret-key",
                                 "DOCS_HUB_URL": "https://evil.com"}), \
                mock.patch.object(publish_docs.urllib.request, "urlopen", urlopen), \
                mock.patch.object(sys, "stderr", io.StringIO()) as err:
            code = publish_docs.main()

        self.assertEqual(code, 2)
        self.assertIn("https://evil.com", err.getvalue())
        self.assertIn(HUB_HOST, err.getvalue())
        urlopen.assert_not_called()

    def test_unparseable_url_override_is_refused_before_the_network(self):
        # The same input the repro hits through the environment: today the
        # ValueError escapes main() as a traceback with exit 1.
        urlopen = mock.MagicMock(return_value=Response(200, b"{}"))

        with mock.patch.object(sys, "argv", self.argv()), \
                mock.patch.dict(publish_docs.os.environ,
                                {"DOCS_HUB_API_KEY": "secret-key",
                                 "DOCS_HUB_URL": "http://[::1"}), \
                mock.patch.object(publish_docs.urllib.request, "urlopen", urlopen), \
                mock.patch.object(sys, "stderr", io.StringIO()) as err:
            code = publish_docs.main()

        self.assertEqual(code, 2)
        self.assertIn("http://[::1", err.getvalue())
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
