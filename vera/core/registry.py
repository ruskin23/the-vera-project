"""Challenge registry: clone/extract/symlink/validate/install."""

from __future__ import annotations

import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

import requests

from vera.core import config
from vera.core.validate import (
    ChallengeError,
    ChallengeMeta,
    find_challenge_dirs,
    validate_challenge,
)


class RegistryError(RuntimeError):
    pass


VERSION_FILENAME = ".vera_version"


@dataclass
class AddedChallenge:
    meta: ChallengeMeta
    source_label: str  # e.g. "github.com/.../vera.git → challenges/foo"
    registry_path: Path
    version: str | None = None


@dataclass
class ListedChallenge:
    meta: ChallengeMeta
    is_symlink: bool
    version: str | None = None


def read_version(challenge_dir: Path) -> str | None:
    """Read the .vera_version file from a registered challenge dir, if present."""
    vf = challenge_dir / VERSION_FILENAME
    if not vf.exists():
        return None
    try:
        value = vf.read_text().strip()
    except OSError:
        return None
    return value or None


def _write_version(challenge_dir: Path, version: str | None) -> None:
    if version is None:
        return
    (challenge_dir / VERSION_FILENAME).write_text(version.strip() + "\n")


def _is_git_url(source: str) -> bool:
    return source.startswith(
        ("http://", "https://", "git@", "ssh://", "git+", "git://")
    ) or source.endswith(".git")


def _is_tarball_url(source: str) -> bool:
    if not source.startswith(("http://", "https://")):
        return False
    lower = source.lower().split("?", 1)[0]
    return lower.endswith((".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".tar"))


def _parse_fragment(source: str) -> tuple[str, str | None]:
    if "#" in source:
        url, frag = source.split("#", 1)
        return url, frag or None
    return source, None


def _clean_adapters_dir(root: Path) -> None:
    """Adapters are a separate trust decision — strip any .vera/adapters in the challenge tree."""
    target = root / ".vera" / "adapters"
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)


def _install_copy(src: Path, dst: Path) -> None:
    if dst.exists():
        if dst.is_symlink() or dst.is_file():
            dst.unlink()
        else:
            shutil.rmtree(dst)
    shutil.copytree(src, dst, symlinks=False)
    _clean_adapters_dir(dst)


def _install_symlink(src: Path, dst: Path) -> None:
    if dst.exists() or dst.is_symlink():
        if dst.is_symlink() or dst.is_file():
            dst.unlink()
        else:
            shutil.rmtree(dst)
    dst.symlink_to(src.resolve(), target_is_directory=True)


def _git_clone(url: str, into: Path, tag: str | None = None) -> None:
    args = ["git", "clone", "--depth", "1"]
    if tag:
        args.extend(["--branch", tag])
    args.extend([url, str(into)])
    result = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if tag:
            raise RegistryError(f"git clone failed for tag {tag!r}: {stderr}")
        raise RegistryError(f"git clone failed: {stderr}")


def _download_tar(url: str, into: Path) -> Path:
    into.mkdir(parents=True, exist_ok=True)
    tarball = into / "source.tar"
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        with tarball.open("wb") as f:
            for chunk in response.iter_content(chunk_size=1 << 16):
                if chunk:
                    f.write(chunk)
    extract_root = into / "extracted"
    extract_root.mkdir(exist_ok=True)
    try:
        with tarfile.open(tarball) as tf:
            tf.extractall(extract_root, filter="data")
    except TypeError:
        with tarfile.open(tarball) as tf:
            tf.extractall(extract_root)
    # If the tarball has a single top-level directory, descend into it.
    children = list(extract_root.iterdir())
    if len(children) == 1 and children[0].is_dir():
        return children[0]
    return extract_root


def _select_challenge_dirs(root: Path, subpath: str | None) -> list[Path]:
    if subpath:
        candidate = (root / subpath).resolve()
        if not candidate.exists() or not candidate.is_dir():
            raise RegistryError(f"subpath not found: {subpath}")
        return [candidate]
    return find_challenge_dirs(root)


def _source_label(source: str, subpath: str | None) -> str:
    base = source
    if subpath:
        return f"{base} → {subpath}"
    return base


def add(
    source: str,
    subpath: str | None = None,
    version: str | None = None,
) -> list[AddedChallenge]:
    """Register challenge(s) from a git URL, local path, or tarball URL.

    `version` — optional git tag to clone at, for tagged git URL installs.
    Ignored for local paths (they're symlinks; the challenge author owns
    versioning on disk) and tarballs (tarballs are the version).
    """
    config.ensure_registry()

    url, fragment = _parse_fragment(source)
    sub = subpath or fragment

    is_local = not (_is_git_url(url) or _is_tarball_url(url))
    added: list[AddedChallenge] = []

    if is_local:
        src_root = Path(url).expanduser().resolve()
        if not src_root.exists() or not src_root.is_dir():
            raise RegistryError(f"local path not found: {src_root}")
        candidates = _select_challenge_dirs(src_root, sub)
        if not candidates:
            raise RegistryError(f"no vera.yaml found under {src_root}")
        for challenge_dir in candidates:
            try:
                meta = validate_challenge(challenge_dir)
            except ChallengeError as exc:
                raise RegistryError(f"{challenge_dir}: {exc}") from exc
            dst = config.registry_path() / meta.slug
            _install_symlink(challenge_dir, dst)
            # Symlinks can't carry a .vera_version side-file (would write through
            # to the author's source tree). Local installs are versionless by
            # design — the author's working copy is the truth.
            meta_canonical = validate_challenge(dst)
            added.append(
                AddedChallenge(
                    meta=meta_canonical,
                    source_label=_source_label(str(src_root), sub),
                    registry_path=dst,
                    version=None,
                )
            )
        return added

    with tempfile.TemporaryDirectory(prefix="vera-add-") as tmp:
        tmp_path = Path(tmp)
        if _is_git_url(url):
            clone_into = tmp_path / "clone"
            _git_clone(url, clone_into, tag=version)
            src_root = clone_into
        else:
            src_root = _download_tar(url, tmp_path)

        candidates = _select_challenge_dirs(src_root, sub)
        if not candidates:
            raise RegistryError(f"no vera.yaml found under {url}")

        for challenge_dir in candidates:
            try:
                meta = validate_challenge(challenge_dir)
            except ChallengeError as exc:
                raise RegistryError(f"{challenge_dir}: {exc}") from exc
            dst = config.registry_path() / meta.slug
            _install_copy(challenge_dir, dst)
            _write_version(dst, version)
            meta_canonical = validate_challenge(dst)
            added.append(
                AddedChallenge(
                    meta=meta_canonical,
                    source_label=_source_label(url, sub),
                    registry_path=dst,
                    version=version,
                )
            )

    return added


def list_challenges(tags: list[str] | None = None) -> list[ListedChallenge]:
    root = config.registry_path()
    if not root.exists():
        return []
    out: list[ListedChallenge] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() and not child.is_symlink():
            continue
        try:
            meta = validate_challenge(child)
        except ChallengeError:
            continue
        if tags and not any(t in meta.tags for t in tags):
            continue
        out.append(
            ListedChallenge(
                meta=meta,
                is_symlink=child.is_symlink(),
                version=read_version(child),
            )
        )
    return out


def resolve(slug: str) -> ChallengeMeta:
    root = config.registry_path()
    path = root / slug
    if not path.exists():
        raise RegistryError(f"no such registered challenge: {slug}")
    try:
        return validate_challenge(path)
    except ChallengeError as exc:
        raise RegistryError(f"registered challenge {slug} is invalid: {exc}") from exc
