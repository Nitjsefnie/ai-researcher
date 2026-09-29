# Governance

ai-researcher is deliberately single-maintainer. One person —
[Nitjsefnie](https://github.com/Nitjsefnie) — is the repository's only
collaborator and its sole administrator, and every merge, publish and
credential rotation runs through that account. This note records that
concentration as a known, accepted risk rather than leaving it to be
inferred from the collaborator list.

## Who can do what

- **Merge** — the owner only. There is no second collaborator, so no
  CODEOWNERS entry could name an independent reviewer.
- **Publish** — the live page is republished by the `refresh` workflow
  (or a maintainer-driven build) to a self-hosted docs hub outside
  GitHub. Publishing is therefore a single-account capability too.
- **Rotate credentials** — the pipeline holds exactly two credentials:
  the workflow's own `GITHUB_TOKEN` (issued per run, scoped to
  `contents: write`, and unusable beyond that run) and the
  `DOCS_HUB_API_KEY` repository secret. Both are rotated by the owner
  in the repository's settings.

## If the account is lost

- The repository is public, so the code and the captured data survive
  on every clone and fork. Recovery is GitHub's standard account
  recovery, followed by re-established admin access for whoever takes
  the repository over.
- `DOCS_HUB_API_KEY` is re-issued by the operator of the docs hub and
  re-set as a repository secret.
- The hourly dispatcher that keeps the page current (see
  [CONTRIBUTING.md](CONTRIBUTING.md) for what it is and how it fires)
  is infrastructure on the maintainer's side of the repository
  boundary. Without it the refresh cadence degrades to the workflow's
  own schedule trigger, and the page stops updating until someone
  triggers the workflow by hand.
