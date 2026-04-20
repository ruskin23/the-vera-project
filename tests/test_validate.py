from __future__ import annotations

from pathlib import Path

import pytest

from vera.core.validate import ChallengeError, find_challenge_dirs, validate_challenge


class TestValidateChallenge:
    def test_valid_fixture(self, simple_challenge: Path) -> None:
        meta = validate_challenge(simple_challenge)
        assert meta.slug == "challenge-simple"
        assert meta.container is False
        assert any(v["name"] == "baseline" for v in meta.variants)

    def test_missing_brief(self, simple_challenge: Path) -> None:
        (simple_challenge / "brief.md").unlink()
        with pytest.raises(ChallengeError, match="brief"):
            validate_challenge(simple_challenge)

    def test_slug_mismatch(self, simple_challenge: Path) -> None:
        renamed = simple_challenge.parent / "other-name"
        simple_challenge.rename(renamed)
        with pytest.raises(ChallengeError, match="match folder name"):
            validate_challenge(renamed)

    def test_grade_sh_not_executable(self, simple_challenge: Path) -> None:
        (simple_challenge / "grader" / "grade.sh").chmod(0o644)
        with pytest.raises(ChallengeError, match="not executable"):
            validate_challenge(simple_challenge)

    def test_container_without_compose(self, simple_challenge: Path) -> None:
        yaml = simple_challenge / "vera.yaml"
        yaml.write_text(yaml.read_text().replace("container: false", "container: true"))
        with pytest.raises(ChallengeError, match="compose.yaml"):
            validate_challenge(simple_challenge)


class TestFindChallengeDirs:
    def test_single_challenge(self, simple_challenge: Path) -> None:
        dirs = find_challenge_dirs(simple_challenge)
        assert dirs == [simple_challenge]

    def test_monorepo_scan(self, tmp_path: Path, simple_challenge: Path) -> None:
        # Build a fake monorepo with a challenges/ subdir containing our fixture.
        mono = tmp_path / "mono"
        mono.mkdir()
        import shutil

        shutil.copytree(simple_challenge, mono / "challenges" / "challenge-simple")
        shutil.copytree(simple_challenge, mono / "tools" / "not-a-challenge")
        (mono / "tools" / "not-a-challenge" / "vera.yaml").unlink()

        # Scan at top level — neither /challenges nor /tools have vera.yaml directly
        top_dirs = find_challenge_dirs(mono)
        assert top_dirs == []

        # Scan one level down into challenges/
        chal_dirs = find_challenge_dirs(mono / "challenges")
        assert len(chal_dirs) == 1 and chal_dirs[0].name == "challenge-simple"
