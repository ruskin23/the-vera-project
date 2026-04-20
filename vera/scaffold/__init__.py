from __future__ import annotations


class ScaffoldError(RuntimeError):
    pass


def create(slug: str, container: bool = False) -> list[str]:
    from vera.scaffold._create import create as _create
    return _create(slug=slug, container=container)
