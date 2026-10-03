#!/usr/bin/env python3
"""Refuse a commit subject whose scope names a workflow but whose type is not ci.

CONTRIBUTING.md's scope rule allows a workflow's `name:` as a scope only with
type `ci`, and states the distinction: `ci(refresh)` changes the workflow,
while `fix(refresh)` would be a change no reader can place — and this
repository has no script sharing a workflow's name, so the rule reaches every
workflow-name scope. Nothing checked it, and prose that no gate reads is a
convention, not a rule, so this check reads the same rule the prose states.

The workflow-name set is DERIVED at HEAD from the tracked files under
.github/workflows, not kept in a list here. A remembered list is only as
current as the last time somebody remembered to add to it, and a workflow
renamed out of the list would take its scope out of the rule in silence. The
value that joins the set is the top-level `name:` in the YAML — the thing
CONTRIBUTING tells a contributor to use — never the filename: zzz.yml naming
itself `scorecard` makes `scorecard` a workflow-name scope, and a job- or
step-level `name:` is indented and must not be collected.

Only the OUTGOING range origin/main..HEAD is examined, and the green line
says so. Already-merged history is what the check exists to stop repeating,
not what it re-tries: re-judging a merged commit would red every fetch of
main forever over commits nobody can amend.

WHAT IT CANNOT SEE, and says so rather than guessing:

  - A subject that does not parse — a merge commit, a non-conforming
    subject, anything without a lowercase type, a scope in parens and a
    colon. It is not a failure: it is counted and listed on stdout, so a
    green is never silent about what it skipped. Parsing it anyway would put
    a guessed scope under a gate it never agreed to.
  - A `name:` line this reader cannot read — quoted, anchored, a block
    scalar, a trailing comment, continued onto the next line, or missing
    entirely. Each is a refusal naming the file: an incomplete set is a
    green over a gate that was never checked, which is the same quiet
    narrowing a remembered list would drift into.
  - The type table's other half. A type outside CONTRIBUTING's convention is
    a defect under any scope, so no type is enumerated here: every type but
    `ci` violates when the scope names a workflow, and the scope rule is
    what fires.
  - A workflow whose `name:` can never be a scope. A name carrying a space —
    `coverage comment`, in this repository — can never equal a `[^()\\s]+`
    scope, so it sits outside the rule; the pr-gate repository's `pr gate`
    is the same case its own copy of this check names. A hyphenated
    repository name is not a workflow `name:` and stays outside the rule
    the same way.

Runs on the standard library alone, and reads blobs with
`git cat-file blob HEAD:<path>` for the same reason gate_base_freshness
reads its workflows that way: in CI the working tree and HEAD are the same
commit, and at review time the tree somebody is editing is not the tree any
gate has agreed to judge.

    scripts/ci/commit_scopes.py [--root DIR]

--root points the check at a repository other than the one containing
scripts/ci/, which is how the suite rehearses it against real fixtures.
"""

import re
import subprocess
import sys
from pathlib import Path

# The branch a pull request's head is compared against. Not configurable: a
# second branch here would be a second base, and this question has one.
BASE_BRANCH = "main"

WORKFLOW_DIR = ".github/workflows"


class GateError(Exception):
    """This run could not establish the answer, and says so instead."""


def git(root, *arguments, what):
    """Run one git command in `root` and return its stdout.

    Every call goes through here because a guard that reads its own error as a
    clean tree is the false green this exists to prevent: a non-zero status is
    a refusal naming what was being attempted, never an empty answer.
    """
    command = ("git", "-C", str(root)) + arguments
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        detail = done.stderr.strip() or "no output"
        raise GateError(
            f"cannot {what}: `{' '.join(command)}` exited {done.returncode}: {detail}")
    return done.stdout


# --- reading the workflow names ---------------------------------------------
#
# The subset of YAML these workflows use for the one key this check reads: a
# plain block mapping entry at column 0. Every other shape is refused rather
# than guessed at, because a guessed name is either a scope the rule should
# have caught or a refusal nobody asked for — and only the first of those is
# silent.

MAPPING = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_.-]*):(?:[ \t]+(?P<value>.*))?$")

# The first characters that say a scalar is NOT plain: a quoted, anchored,
# aliased, tagged, block or flow value. A plain scalar starts with none of
# them, and reading one as if it were plain is how `name: "tests"` would
# enter the set carrying its quotes.
NOT_PLAIN = re.compile(r"""["'|>&*![\]{}]""")

# In a plain scalar a space before `#` starts a comment, so the value would
# end there — a fact this reader refuses to model rather than half-models by
# stripping, because a stripped comment and a name containing a space-hash
# are indistinguishable at this line's granularity.
TRAILING_COMMENT = re.compile(r"\s#")


def indent_of(line):
    return len(line) - len(line.lstrip(" "))


def skippable(line):
    """A blank line or a whole-line comment, which carries no node."""
    stripped = line.strip()
    return not stripped or stripped.startswith("#")


def tracked_files(root):
    return tuple(f for f in
                 git(root, "ls-tree", "-r", "--name-only", "--full-tree", "HEAD",
                     what="list the tracked tree").split("\n") if f)


def workflow_files(files):
    return sorted(f for f in files
                  if f.startswith(WORKFLOW_DIR + "/")
                  and (f.endswith(".yml") or f.endswith(".yaml")))


def refuse_name(workflow, reason):
    raise GateError(
        f"{workflow}: {reason} The workflow-name set would be incomplete, and "
        f"an incomplete set is a green over a gate that was never checked: "
        f"spell the name as a plain top-level `name:` line, or teach this "
        f"check the shape.")


def top_level_keys(lines, key):
    """[(line index, match)] for column-0 block entries whose key is `key`.

    One `MAPPING.match` per line, narrowed once: calling the match twice —
    once as a guard, once for its groups — reads to the type checker as two
    unrelated optionals.
    """
    found = []
    for index, line in enumerate(lines):
        if skippable(line) or indent_of(line) != 0:
            continue
        match = MAPPING.match(line)
        if match is not None and match["key"] == key:
            found.append((index, match))
    return found


def workflow_name(workflow, text):
    """The single top-level `name:` value of one workflow.

    Only column 0 is read: a job's or a step's `name:` is indented and is
    not a workflow name, and collecting it would put e.g. `check` from a
    job's display name under the ci-type rule where CONTRIBUTING never put
    it.
    """
    lines = text.splitlines()
    matches = top_level_keys(lines, "name")
    tops = [index for index, match in matches]
    if len(tops) == 0:
        refuse_name(
            workflow,
            "has no top-level `name:` this reader can read, so the workflow "
            "it defines is unnamed")
    if len(tops) != 1:
        raise GateError(
            f"{workflow} has {len(tops)} top-level `name:` mappings this "
            f"reader can read, and which one names the workflow cannot be "
            f"established")
    at, matched = matches[0]
    value = (matched["value"] or "").strip()
    if not value:
        refuse_name(workflow, f"the top-level `name:` at line {at + 1} carries no value")
    if NOT_PLAIN.match(value[0]):
        refuse_name(
            workflow,
            f"the top-level `name:` at line {at + 1} is {value!r}, which is "
            f"not a plain scalar")
    if TRAILING_COMMENT.search(value):
        refuse_name(
            workflow,
            f"the top-level `name:` at line {at + 1} carries a trailing "
            f"comment, and where the name ends cannot be read at this line's "
            f"granularity")
    for line in lines[at + 1:]:
        if skippable(line):
            continue
        if indent_of(line) > 0:
            refuse_name(
                workflow,
                f"the top-level `name:` at line {at + 1} continues onto an "
                f"indented line")
        break
    return value


def workflow_name_set(root):
    """Every workflow name, derived from HEAD's workflows and nothing else."""
    files = tracked_files(root)
    if not files:
        raise GateError("HEAD tracks no files, so there are no workflows to read")
    names = set()
    for workflow in workflow_files(files):
        names.add(workflow_name(
            workflow,
            git(root, "cat-file", "blob", f"HEAD:{workflow}",
                what=f"read {workflow}")))
    if not names:
        raise GateError(
            f"no workflow under {WORKFLOW_DIR}/ carries a readable `name:`, "
            f"so the workflow-name set is empty and no subject can be judged")
    return names


# --- the subjects -----------------------------------------------------------


def fetch_base(root):
    """Bring main in as it is NOW, not as the checkout left it.

    actions/checkout fetches one commit of one ref by default, so a main that
    moved after that run left nothing here to compare against. Anonymous on
    purpose: every checkout in this repository sets persist-credentials:
    false and the repository is public.

    --unshallow deepens the ref actually being compared. Without it the
    grafted boundary hides the head's own ancestry, and a range against a
    base git cannot see into reports commits the head already carries.
    """
    arguments = ["fetch", "--no-tags", "--quiet"]
    if git(root, "rev-parse", "--is-shallow-repository",
           what="ask whether the checkout is shallow").strip() == "true":
        arguments.append("--unshallow")
    arguments += ["origin", f"+refs/heads/{BASE_BRANCH}:refs/remotes/origin/{BASE_BRANCH}"]
    git(root, *arguments, what=f"fetch origin/{BASE_BRANCH}")


# A Conventional-Commits-shaped subject: a lowercase type, an optional
# breaking marker after the type and/or after the scope's closing paren, a
# scope of non-parenthesis non-whitespace inside parens, and the colon
# CONTRIBUTING requires. A type outside CONTRIBUTING's convention is not this
# regex's problem — the rule below flags any non-ci type on a workflow-name
# scope, and a bad type is a defect under any scope.
SUBJECT = re.compile(
    r"^(?P<type>[a-z]+)!?\((?P<scope>[^()\s]+)\)!?:\s?(?P<summary>\S.*)?$")


def outgoing_commits(root, base):
    """[(sha, subject)] for exactly the commits this head is asking main to take."""
    listing = git(root, "log", "--format=%H%x09%s", f"{base}..HEAD",
                  what="list the outgoing commits")
    commits = []
    for line in listing.split("\n"):
        if not line.strip():
            continue
        sha, _, subject = line.partition("\t")
        commits.append((sha.strip(), subject.strip()))
    return commits


def check(root):
    # Resolved for its refusal, not its value: a checkout with no commit must
    # fail here, before anything compares it.
    git(root, "rev-parse", "--verify", "HEAD^{commit}",
        what="resolve the checked-out head")
    fetch_base(root)
    base = git(root, "rev-parse", "--verify",
               f"refs/remotes/origin/{BASE_BRANCH}^{{commit}}",
               what=f"resolve origin/{BASE_BRANCH}").strip()
    names = workflow_name_set(root)
    commits = outgoing_commits(root, base)

    examined = 0
    unexamined = []
    violations = []
    for sha, subject in commits:
        match = SUBJECT.match(subject)
        if match is None:
            # Not a failure — a merge commit or a non-conforming subject has
            # no scope to read, and inventing one would gate a contributor on
            # a parse they never wrote. Counted and listed, so a green never
            # rides silently over what it skipped.
            unexamined.append((sha, subject))
            continue
        examined += 1
        scope, commit_type = match["scope"], match["type"]
        # CONTRIBUTING: a workflow's `name:` is a scope only with the `ci`
        # type. This repository has no script sharing a workflow's name, so
        # unlike claim's own check there is no exempt scope: the rule reaches
        # every scope a derived `name:` equals exactly.
        if scope in names and commit_type != "ci":
            violations.append((sha, subject, scope, commit_type))

    if violations:
        plural = "s" if len(violations) != 1 else ""
        verb = "pair" if len(violations) != 1 else "pairs"
        print(f"{len(violations)} commit{plural} in origin/main..HEAD {verb} a "
              f"workflow-name scope with a type other than `ci`:")
        for sha, subject, scope, commit_type in violations:
            print(f"  {sha} {subject}")
            print(f"    scope `{scope}` is the name of a workflow under "
                  f"{WORKFLOW_DIR}/; type `{commit_type}` is not `ci`.")
        print("A workflow's `name:` is a scope only with the `ci` type: use "
              "the `ci` type on that scope, or take a scope that names what "
              "the commit is actually about.")
        return 1

    plural = "s" if examined != 1 else ""
    print(f"Examined {examined} commit subject{plural} in origin/main..HEAD; "
          f"{len(unexamined)} not examined.")
    # The green line states its own reach. Only the outgoing range is judged:
    # already-merged history is never re-judged, and a subject without a
    # readable scope is listed rather than failed. A green line that claimed
    # more than this would be the same over-claim as a report over its
    # evidence.
    print("  Only the OUTGOING range is examined: history already merged into")
    print("  main is never re-judged, and a subject that does not parse (a")
    print("  merge commit, a non-conforming subject) is listed below and is")
    print("  never a failure:")
    for sha, subject in unexamined:
        print(f"    {sha} {subject}")
    print("No commit pairs a workflow-name scope with a type other than `ci`.")
    return 0


def main(argv):
    # The repository ROOT (three parents from scripts/ci/), like
    # gate_base_freshness's; no command here is cwd-sensitive the way a
    # pathspec list is, but the two gates keep one spelling.
    root = Path(__file__).resolve().parent.parent.parent
    rest = list(argv[1:])
    while rest:
        argument = rest.pop(0)
        if argument == "--root":
            if not rest:
                print("usage: commit_scopes.py [--root DIR]", file=sys.stderr)
                return 2
            root = Path(rest.pop(0))
        else:
            print("usage: commit_scopes.py [--root DIR]", file=sys.stderr)
            return 2
    try:
        return check(root)
    except GateError as refusal:
        print(f"commit scopes: {refusal}", file=sys.stderr)
        return 1
    except OSError as failure:
        # git could not be run at all — absent from the runner image, or an
        # argument list past what the kernel will exec. Named rather than
        # traced: the exit status is the same either way, and a refusal is
        # what this run owes the reader.
        print(f"commit scopes: cannot run git: {failure}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
