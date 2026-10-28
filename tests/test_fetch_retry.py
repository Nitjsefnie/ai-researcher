"""Retry behavior at the response boundary for the trending fetchers."""
import contextlib
import email.message
import http.client
import io
import json
import pathlib
import socket
import sys
import time
import unittest
import unittest.mock
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_aa  # noqa: E402  # pylint: disable=wrong-import-position
import fetch_http  # noqa: E402  # pylint: disable=wrong-import-position
import fetch_hf_trending  # noqa: E402  # pylint: disable=wrong-import-position
import fetch_openrouter_trending  # noqa: E402  # pylint: disable=wrong-import-position


class TimedOutResponse(io.BytesIO):
    """An open response whose body read times out."""

    def read(self, *args, **kwargs):
        raise TimeoutError("body read timed out")


class IncompleteResponse(io.BytesIO):
    """An open response whose body terminates early."""

    def read(self, *args, **kwargs):
        raise http.client.IncompleteRead(b"partial")


class SharedFetchTests(unittest.TestCase):
    def test_classifier_verdicts(self):
        for code, expected in ((429, True), (430, False), (499, False),
                               (500, True), (501, True), (502, True),
                               (503, True), (504, True), (599, True),
                               (400, False), (403, False), (404, False),
                               (409, False), (451, False)):
            with self.subTest(code=code):
                error = urllib.error.HTTPError("https://example.test/", code,
                                               "error", email.message.Message(), None)
                self.assertIs(fetch_http.retryable_transport_error(error), expected)

        errors = (urllib.error.URLError(socket.gaierror(-2, "DNS failure")),
                  urllib.error.URLError(ConnectionRefusedError("refused")),
                  socket.timeout("timed out"),
                  http.client.RemoteDisconnected("disconnected"),
                  http.client.IncompleteRead(b"partial"))
        for error in errors:
            with self.subTest(error=error):
                self.assertTrue(fetch_http.retryable_transport_error(error))
        self.assertFalse(fetch_http.retryable_transport_error(ValueError("invalid JSON")))

    def test_three_attempts_use_linear_backoff_and_keep_request_options(self):
        url = "https://example.test/models"
        outcomes = [
            urllib.error.HTTPError(url, 429, "rate limited", email.message.Message(), None),
            urllib.error.HTTPError(url, 503, "unavailable", email.message.Message(), None),
            io.BytesIO(b"response"),
        ]
        with unittest.mock.patch.object(urllib.request, "urlopen",
                                        side_effect=outcomes) as urlopen, \
                unittest.mock.patch.object(time, "sleep") as sleep, \
                contextlib.redirect_stderr(io.StringIO()):
            result = fetch_http.fetch_bytes(url, {"User-Agent": "test-agent"}, 37)

        self.assertEqual(result, b"response")
        self.assertEqual(urlopen.call_count, 3)
        for call in urlopen.call_args_list:
            request = call.args[0]
            self.assertEqual(request.full_url, url)
            self.assertEqual(request.get_header("User-agent"), "test-agent")
            self.assertEqual(call.kwargs["timeout"], 37)
        self.assertEqual(sleep.call_args_list, [unittest.mock.call(5), unittest.mock.call(10)])

    def test_a_dropped_body_is_closed_and_retried(self):
        failed = IncompleteResponse(b"partial")
        healthy = io.BytesIO(b"complete")
        with unittest.mock.patch.object(urllib.request, "urlopen",
                                        side_effect=[failed, healthy]) as urlopen, \
                unittest.mock.patch.object(time, "sleep") as sleep, \
                contextlib.redirect_stderr(io.StringIO()):
            result = fetch_http.fetch_bytes("https://example.test/", {}, 30)

        self.assertEqual(result, b"complete")
        self.assertEqual(urlopen.call_count, 2)
        self.assertTrue(failed.closed)
        self.assertTrue(healthy.closed)
        sleep.assert_called_once_with(5)

    def test_aa_refusal_and_retry_lines_keep_their_exact_wording(self):
        url = fetch_aa.URL
        error = urllib.error.HTTPError(url, 503, "unavailable", email.message.Message(), None)
        stderr = io.StringIO()
        with unittest.mock.patch.object(urllib.request, "urlopen", side_effect=error) as urlopen, \
                unittest.mock.patch.object(fetch_aa, "_sleep") as sleep, \
                contextlib.redirect_stderr(stderr), \
                self.assertRaises(SystemExit) as caught:
            fetch_aa.fetch_html(None, url)

        self.assertEqual(urlopen.call_count, 3)
        self.assertEqual(sleep.call_args_list, [unittest.mock.call(5), unittest.mock.call(10)])
        self.assertEqual(stderr.getvalue(),
                         f"{url}: attempt 1 of 3 failed ({error}); retrying in 5s\n"
                         f"{url}: attempt 2 of 3 failed ({error}); retrying in 10s\n")
        self.assertEqual(str(caught.exception),
                         f"{url}: fetch failed after 3 attempts: {error} -- nothing "
                         "was captured; check connectivity or the site, then re-run")

    def test_aa_non_retryable_refusal_keeps_its_exact_wording(self):
        url = fetch_aa.URL
        error = urllib.error.HTTPError(url, 404, "not found", email.message.Message(), None)
        stderr = io.StringIO()
        with unittest.mock.patch.object(urllib.request, "urlopen", side_effect=error) as urlopen, \
                unittest.mock.patch.object(fetch_aa, "_sleep") as sleep, \
                contextlib.redirect_stderr(stderr), \
                self.assertRaises(SystemExit) as caught:
            fetch_aa.fetch_html(None, url)

        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(str(caught.exception),
                         f"{url}: fetch failed: {error} -- nothing "
                         "was captured; check connectivity or the site, then re-run")


class TrendingRetryTests(unittest.TestCase):
    def assert_mid_body_retry(self, fetch, payload, expected, timeout):
        failed = TimedOutResponse(b"partial")
        healthy = io.BytesIO(json.dumps(payload).encode("utf-8"))
        with unittest.mock.patch.object(urllib.request, "urlopen",
                                        side_effect=[failed, healthy]) as urlopen, \
                unittest.mock.patch.object(time, "sleep") as sleep, \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(fetch(), expected)

        self.assertEqual(urlopen.call_count, 2)
        self.assertTrue(failed.closed)
        self.assertTrue(healthy.closed)
        self.assertEqual([call.kwargs["timeout"] for call in urlopen.call_args_list],
                         [timeout, timeout])
        sleep.assert_called_once_with(5)

    def test_hugging_face_retries_a_mid_body_timeout(self):
        self.assert_mid_body_retry(fetch_hf_trending.fetch,
                                   [{"id": "org/model"}],
                                   [{"id": "org/model"}], 30)

    def test_openrouter_retries_a_mid_body_timeout(self):
        self.assert_mid_body_retry(fetch_openrouter_trending.fetch,
                                   {"data": {"models": [{"slug": "org/model"}]}},
                                   [{"slug": "org/model"}], 60)

    def test_complete_invalid_json_is_not_retried(self):
        for fetch in (fetch_hf_trending.fetch, fetch_openrouter_trending.fetch):
            with self.subTest(fetch=fetch.__module__), \
                    unittest.mock.patch.object(urllib.request, "urlopen",
                                               return_value=io.BytesIO(b"{")) as urlopen, \
                    unittest.mock.patch.object(time, "sleep") as sleep:
                with self.assertRaises(json.JSONDecodeError):
                    fetch()
                self.assertEqual(urlopen.call_count, 1)
                sleep.assert_not_called()
