"""Publish one built page to docs-hub.

WHY THIS EXISTS RATHER THAN THE CANONICAL CLI. Publishing is normally
`~/.agent-bundle/scripts/docs_hub.py publish`, and on a workstation that stays
the way to do it. A GitHub runner cannot: that script lives in a private
bundle repository and imports `_settings.py` from beside it, so reaching it
from CI would mean shipping a second credential just to read the publisher.
This is the minimum client for the single endpoint the refresh workflow needs
— POST /api/publish — and deliberately implements nothing else. Anything
beyond publishing belongs in the canonical CLI, not here.

The key is read from the environment only (DOCS_HUB_API_KEY); it is never a
command-line argument, because arguments are visible in the process list and
land in CI logs when a step echoes its own command.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import uuid

DEFAULT_URL = "https://docs.nitjsefni.eu"


def multipart(fields: dict[str, str], filename: str,
              blob: bytes) -> tuple[bytes, str]:
    """Encode `fields` plus one HTML file part. Mirrors the canonical CLI's
    wire format: the hub reads the file from a part named `file`."""
    boundary = uuid.uuid4().hex
    body = b""
    for key, value in fields.items():
        body += (f"--{boundary}\r\n"
                 f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
                 f"{value}\r\n").encode()
    body += (f"--{boundary}\r\n"
             f'Content-Disposition: form-data; name="file"; '
             f'filename="{filename}"\r\n'
             f"Content-Type: text/html\r\n\r\n").encode()
    body += blob + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def publish(path: str, fields: dict[str, str], key: str, base: str) -> int:
    with open(path, "rb") as handle:
        blob = handle.read()
    body, content_type = multipart(fields, os.path.basename(path), blob)

    req = urllib.request.Request(base.rstrip("/") + "/api/publish",
                                 data=body, method="POST")
    req.add_header("x-docs-key", key)
    req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:
        # The hub answers with JSON on refusal; a Cloudflare error page is
        # HTML. Print whichever came back rather than a traceback.
        print(f"publish failed: HTTP {exc.code}\n{exc.read()[:400]!r}",
              file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"publish failed: cannot reach {base}: {exc.reason}",
              file=sys.stderr)
        return 1

    try:
        payload = json.loads(raw)
    except ValueError:
        print(f"publish returned HTTP {status} with a non-JSON body:\n"
              f"{raw[:400]!r}", file=sys.stderr)
        return 1

    print(json.dumps(payload, indent=1))
    # A 2xx with an error field is still a failure; the hub uses both.
    return 0 if 200 <= status < 300 and not payload.get("error") else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Publish one built page to docs-hub.")
    ap.add_argument("file", help="the built HTML page")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--from", dest="from_agent", required=True,
                    help="the authoring agent")
    ap.add_argument("--tags", default="", help="comma-separated")
    ap.add_argument("--project", default="")
    args = ap.parse_args()

    key = os.environ.get("DOCS_HUB_API_KEY", "")
    if not key:
        print("DOCS_HUB_API_KEY is not set in the environment", file=sys.stderr)
        return 2

    return publish(args.file, {
        "slug": args.slug,
        "title": args.title,
        "tags": args.tags,
        "project": args.project,
        "from": args.from_agent,
    }, key, os.environ.get("DOCS_HUB_URL", DEFAULT_URL))


if __name__ == "__main__":
    sys.exit(main())
