"""build.main() writes its output page and nothing else under its ROOT.

Its inputs are the committed data/ blobs, which no earlier test can have
rewritten; a write outside the patched paths is not seen.
"""
import contextlib
import io
import pathlib
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock

import build

GIT_TIMEOUT = 60  # seconds


def _files(root: pathlib.Path) -> dict:
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


class BuildWritesOnlyItsPageTests(unittest.TestCase):
    def test_a_build_leaves_every_input_it_reads_unchanged(self):
        archive = subprocess.run(
            ["git", "archive", "--format=tar", "HEAD", "data"],
            cwd=str(build.ROOT), capture_output=True, check=True,
            timeout=GIT_TIMEOUT).stdout
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
                tar.extractall(root, filter="data")
            data = root / "data"
            page = root / "out" / "frontier-models.html"
            before = _files(root)
            with mock.patch.object(build, "ROOT", root), \
                    mock.patch.object(build, "RAW", data / "aa-raw-models.json"), \
                    mock.patch.object(build, "AGENTS_RAW", data / "aa-raw-coding-agents.json"), \
                    mock.patch.object(build, "OUT", page), \
                    contextlib.redirect_stdout(io.StringIO()):
                build.main()
            after = _files(root)
        self.assertIn("data/aa-raw-models.json", before)
        self.assertIn("data/aa-raw-coding-agents.json", before)
        self.assertIn("out/frontier-models.html", after)
        del after["out/frontier-models.html"]
        changed = sorted(name for name in before.keys() | after.keys()
                         if before.get(name) != after.get(name))
        self.assertEqual(changed, [], "the build wrote besides its page")
