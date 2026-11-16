"""A `python3` shim running a script with only docs-hub faked (issue #402).

urlopen answers POST /api/publish from AI_RESEARCHER_UPLOAD_CODE (statuses or `transport`,
comma-separated, the last repeating) and AI_RESEARCHER_UPLOAD_BODY; backoff sleeps are
instant. Each upload is one JSON line in the record; other requests fail. A live-page
GET (download.py URL DEST, issue #426) answers AI_RESEARCHER_LIVE_CODE the same way,
serving the file AI_RESEARCHER_LIVE_PAGE names; each such run's argv is a line in fetches.
"""
import email.message
import email.parser
import email.policy
import errno
import importlib
import io
import json
import os
import runpy
import sys
import types
import urllib.error
import urllib.request
from pathlib import Path

PUBLISH_URL = "https://docs.nitjsefni.eu/api/publish"


def install(directory):
    record = Path(directory) / "uploads.jsonl"
    shim = Path(directory) / "python3"
    shim.write_text(f"#!/bin/bash\nexec '{sys.executable}' '{__file__}' "
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


def fetches(record):
    path = Path(record).with_name("fetches.jsonl")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def _fault(answer, url, body):
    if answer == "transport":
        raise ConnectionResetError(errno.ECONNRESET, "Connection reset by peer")
    if not 200 <= int(answer) < 300:
        raise urllib.error.HTTPError(url, int(answer), "fixture", email.message.Message(), io.BytesIO(body))


def _urlopen(record, request, timeout=None):
    if isinstance(request, str):  # download.py's GET: a bare URL
        assert request.startswith("https://docs.nitjsefni.eu/d/ai-researcher/"), request
        answers = os.environ.get("AI_RESEARCHER_LIVE_CODE", "200").split(",")
        _LIVE.append(request)
        _fault(answers[min(len(_LIVE), len(answers)) - 1], request, b"")
        return _Response(200, Path(os.environ["AI_RESEARCHER_LIVE_PAGE"]).read_bytes())
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
    answers = os.environ["AI_RESEARCHER_UPLOAD_CODE" if "AI_RESEARCHER_UPLOAD_CODE" in os.environ else "UPLOAD_CODE"].split(",")
    answer = answers[min(done, len(answers) - 1)]
    body = os.environ["AI_RESEARCHER_UPLOAD_BODY" if "AI_RESEARCHER_UPLOAD_BODY" in os.environ else "UPLOAD_BODY"].encode()
    _fault(answer, PUBLISH_URL, body)
    return _Response(int(answer), body)


_LIVE = []


def _run(record, script, *args):
    if Path(script).name == "download.py" and args[:1] != ("--run",):
        with Path(record).with_name("fetches.jsonl").open("a", encoding="utf-8") as out:
            out.write(json.dumps(args) + "\n")
    urllib.request.urlopen = lambda request, timeout=None: _urlopen(
        record, request, timeout)
    sys.argv = [script, *args]
    # Only download.py's own clock is faked: a process-wide one would also time subprocess's waits.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "ci"))
    download, sleeps = importlib.import_module("download"), []
    setattr(download, "time", types.SimpleNamespace(sleep=sleeps.append, monotonic=lambda: 1000.0 + sum(sleeps)))
    if Path(script).name == "download.py":
        sys.exit(download.main(list(args)))
    runpy.run_path(script, run_name="__main__")


if __name__ == "__main__":
    _run(*sys.argv[1:])
