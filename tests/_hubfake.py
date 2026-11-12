"""A `python3` shim running a script with only docs-hub faked (issue #402).

urlopen answers POST /api/publish from UPLOAD_CODE (statuses or `transport`,
comma-separated, the last repeating) and UPLOAD_BODY; backoff sleeps are
instant. Each upload is one JSON line in the record; other requests fail.
"""
import email.message
import email.parser
import email.policy
import errno
import io
import json
import os
import runpy
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PUBLISH_URL = "https://docs.nitjsefni.eu/api/publish"


def install(directory):
    record = Path(directory) / "uploads.jsonl"
    shim = Path(directory) / "python3"
    shim.write_text(f"#!/bin/sh\nexec '{sys.executable}' '{__file__}' "
                    f"'{record}' \"$@\"\n", encoding="utf-8")
    shim.chmod(0o755)
    return record


def uploads(record):
    if not Path(record).exists():
        return []
    return [json.loads(line) for line in
            Path(record).read_text(encoding="utf-8").splitlines()]


class _Response(io.BytesIO):
    def __init__(self, status, body):
        super().__init__(body)
        self.status = status


def _text(part):
    payload = part.get_payload(decode=True)
    assert isinstance(payload, bytes), payload
    return payload.decode("utf-8")


def _urlopen(record, request, timeout=None):
    assert (request.full_url, request.get_method()) == (PUBLISH_URL, "POST"), (
        request.full_url, request.get_method())
    head = f"Content-Type: {request.get_header('Content-type')}\r\n\r\n"
    message = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
        head.encode() + request.data)
    parts = {part.get_param("name", header="content-disposition"): part
             for part in message.iter_parts()}
    page = parts.pop("file")
    upload = {"key": request.get_header("X-docs-key"), "timeout": timeout,
              "fields": {name: _text(part) for name, part in parts.items()},
              "filename": page.get_filename(),
              "type": page.get_content_type(),
              "page": _text(page)}
    done = len(uploads(record))
    with Path(record).open("a", encoding="utf-8") as out:
        out.write(json.dumps(upload) + "\n")
    answers = os.environ["UPLOAD_CODE"].split(",")
    answer = answers[min(done, len(answers) - 1)]
    body = os.environ["UPLOAD_BODY"].encode()
    if answer == "transport":
        raise ConnectionResetError(errno.ECONNRESET, "Connection reset by peer")
    if not 200 <= int(answer) < 300:
        raise urllib.error.HTTPError(PUBLISH_URL, int(answer), "fixture",
                                     email.message.Message(), io.BytesIO(body))
    return _Response(int(answer), body)


def _run(record, script, *args):
    sleeps = []
    time.sleep = sleeps.append
    time.monotonic = lambda: 1000.0 + sum(sleeps)
    urllib.request.urlopen = lambda request, timeout=None: _urlopen(
        record, request, timeout)
    sys.argv = [script, *args]
    runpy.run_path(script, run_name="__main__")


if __name__ == "__main__":
    _run(*sys.argv[1:])
