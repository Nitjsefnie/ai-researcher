# Security policy

## Reporting a vulnerability

This repository has GitHub's private vulnerability reporting enabled. Use
it: open the repository's **Security** tab and choose **Report a
vulnerability**. A report filed there is visible only to the maintainer
until an advisory is published, so the flaw can be discussed and fixed
before any public disclosure.

Please do not open a public issue for a security report. The published
page executes JavaScript built from third-party captured data, so an
injection finding is exploitable in a visitor's browser and has no
responsible public channel.

There is no bounty and no response-time guarantee. This is a
single-maintainer project (see [GOVERNANCE.md](GOVERNANCE.md)); expect a
human reply rather than a triage pipeline.

When reporting, please include:

- what the vulnerability is and the impact you believe it has;
- how to reproduce it — the rendered markup, request, or input that
  triggers it. Input that survives the page's escaping and reaches the
  DOM is exactly the kind of report wanted here;
- what you were reading when you saw it — the captured-at stamp on the
  page, or the commit of `out/frontier-models.html`, since the page is
  rebuilt from a moving capture.

## Supported versions

Only the latest `main` is supported. The page is rebuilt from the latest
capture and republished on every data change; older published versions in
the docs-hub version history are not patched. Update by re-reading the
live page before reporting — the problem may already be fixed.

## What is not a security report

A benchmark number that looks wrong is a data question, not a
vulnerability: open a public issue of the form "AA's leaderboard says X,
the page says Y" (see [CONTRIBUTING.md](CONTRIBUTING.md) for what makes
that report useful).
