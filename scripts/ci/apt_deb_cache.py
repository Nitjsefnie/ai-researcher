"""Shared best-effort apt archive cache mechanics for CI installers."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

APT_ARCHIVES = Path("/var/cache/apt/archives")


def matching_debs(directory: Path, packages: set[str]) -> list[Path]:
    """Archives belonging to the requested package names, in stable order."""
    return sorted(path for path in directory.glob("*.deb")
                  if path.name.split("_", 1)[0] in packages)


def cached_debs(cache: Path, packages: set[str], key: str) -> list[Path]:
    """A hit requires the resolved identity and coverage of every package."""
    cached = matching_debs(cache, packages)
    marker = cache / "cache-key"
    if marker.is_file() and marker.read_text(encoding="utf-8") == key \
            and packages <= {path.name.split("_", 1)[0] for path in cached}:
        return cached
    return []


def restore_install(debs: list[Path], resolved: list[str]) -> bool:
    """Pre-warm apt's archives, then install without contacting a mirror."""
    result = subprocess.run(
        ["sudo", "cp", "--", *[str(path.resolve()) for path in debs],
         str(APT_ARCHIVES)], check=False)
    if result.returncode == 0:
        result = subprocess.run(
            ["sudo", "apt-get", "install", "-y", "--no-install-recommends",
             "--no-download", *resolved], check=False)
    return result.returncode == 0


def backfill(cache: Path, packages: set[str], key: str) -> bool:
    """Copy a complete archive set before marking its resolved identity."""
    debs = matching_debs(APT_ARCHIVES, packages)
    if not packages <= {path.name.split("_", 1)[0] for path in debs}:
        return False
    for path in debs:
        shutil.copyfile(path, cache / path.name)
    (cache / "cache-key").write_text(key, encoding="utf-8")
    return True


def emit_output(name: str, value: str) -> None:
    """Append an Actions output when running inside a workflow step."""
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def configure_apt_acquire(
        fragment_dir: Path = Path("/etc/apt/apt.conf.d"),
        sudo: tuple[str, ...] = ("sudo", "-n")) -> None:
    """Best-effort system fragment, loaded by apt.conf(5) through sudo."""
    # apt.conf(5): Retries; apt-transport-http(1), apt-transport-https(1): Timeout.
    settings = ('Acquire::http::Timeout "20";\n'
                'Acquire::https::Timeout "20";\n'
                'Acquire::Retries "2";\n')
    target = fragment_dir / "99ai-researcher-playwright-acquire"
    # apt.conf(5) ignores .disabled fragments until the atomic rename succeeds.
    staged = target.with_suffix(".disabled")
    try:
        with tempfile.TemporaryDirectory(prefix="playwright-apt-acquire-") as scratch:
            source = Path(scratch) / "apt.conf"
            source.write_text(settings, encoding="utf-8")
            for command in (
                    [*sudo, "install", "-T", "-m", "0644", str(source), str(staged)],
                    [*sudo, "mv", "-T", "--", str(staged), str(target)]):
                result = subprocess.run(command, capture_output=True,
                                        encoding="utf-8", check=False)
                if result.returncode != 0:
                    raise OSError(f"{command[len(sudo)]} exited {result.returncode}: "
                                  f"{result.stderr.strip()}")
    except OSError as error:
        print(f"WARNING: could not configure apt acquire limits ({error}); "
              "continuing with apt's existing settings", file=sys.stderr, flush=True)
