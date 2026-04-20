"""Adapter loader: three-tier precedence, CONTRACT_VERSION gate, HARNESS_ID first-match."""
from __future__ import annotations

import importlib.util
import sys
import types
from dataclasses import dataclass
from pathlib import Path

from vera.core import config

SUPPORTED_CONTRACT_VERSIONS = (1,)


@dataclass
class LoadedAdapter:
    harness_id: str
    contract_version: int
    source: Path
    source_group: str  # "project" | "user" | "package"
    module: types.ModuleType

    @property
    def detect(self) -> bool:
        try:
            return bool(self.module.detect())
        except Exception:
            return False


@dataclass
class AdapterLoadError:
    source: Path
    source_group: str
    reason: str


@dataclass
class AdapterGroups:
    project: list[LoadedAdapter]
    user: list[LoadedAdapter]
    package: list[LoadedAdapter]
    errors: list[AdapterLoadError]

    def flat(self) -> list[LoadedAdapter]:
        return list(self.project) + list(self.user) + list(self.package)

    def resolve(self, harness_id: str) -> LoadedAdapter | None:
        for a in self.flat():
            if a.harness_id == harness_id:
                return a
        return None


def _load_module_from_file(path: Path, unique_name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(unique_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load spec for {path}")
    module = importlib.util.module_from_spec(spec)
    # Register before exec so `@dataclass` with PEP 563 annotations can resolve
    # sys.modules[cls.__module__].
    sys.modules[unique_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(unique_name, None)
        raise
    return module


def _load_one(path: Path, group: str) -> LoadedAdapter | AdapterLoadError:
    unique = f"vera_adapter_{group}_{path.stem}"
    try:
        module = _load_module_from_file(path, unique)
    except Exception as exc:
        return AdapterLoadError(source=path, source_group=group, reason=f"import error: {exc}")

    for attr in ("HARNESS_ID", "CONTRACT_VERSION", "detect", "sessions_for_run", "session_turns"):
        if not hasattr(module, attr):
            return AdapterLoadError(
                source=path, source_group=group, reason=f"missing {attr}"
            )

    harness_id = module.HARNESS_ID
    contract_version = module.CONTRACT_VERSION
    if not isinstance(harness_id, str) or not harness_id:
        return AdapterLoadError(
            source=path, source_group=group, reason="HARNESS_ID must be a non-empty str"
        )
    if not isinstance(contract_version, int):
        return AdapterLoadError(
            source=path, source_group=group, reason="CONTRACT_VERSION must be an int"
        )
    if contract_version not in SUPPORTED_CONTRACT_VERSIONS:
        return AdapterLoadError(
            source=path,
            source_group=group,
            reason=(
                f"unsupported CONTRACT_VERSION={contract_version}; "
                f"supported: {SUPPORTED_CONTRACT_VERSIONS}. "
                f"upgrade vera to load this adapter."
            ),
        )

    return LoadedAdapter(
        harness_id=harness_id,
        contract_version=contract_version,
        source=path,
        source_group=group,
        module=module,
    )


def _scan_dir(directory: Path, group: str) -> tuple[list[LoadedAdapter], list[AdapterLoadError]]:
    adapters: list[LoadedAdapter] = []
    errors: list[AdapterLoadError] = []
    if not directory.exists() or not directory.is_dir():
        return adapters, errors
    for py in sorted(directory.glob("*.py")):
        if py.name.startswith("_"):
            continue
        result = _load_one(py, group)
        if isinstance(result, LoadedAdapter):
            adapters.append(result)
        else:
            errors.append(result)
    return adapters, errors


def _package_adapter_dir() -> Path:
    return Path(__file__).resolve().parent


def discover_all() -> AdapterGroups:
    """Scan all three tiers. Returns every loaded adapter including shadowed ones."""
    project, e1 = _scan_dir(config.project_adapters_dir(), "project")
    user, e2 = _scan_dir(config.user_adapters_dir(), "user")
    package_dir = _package_adapter_dir()
    package_files = [
        p
        for p in sorted(package_dir.glob("*.py"))
        if p.name not in ("__init__.py", "loader.py")
    ]
    package: list[LoadedAdapter] = []
    e3: list[AdapterLoadError] = []
    for p in package_files:
        if p.name.startswith("_"):
            continue
        res = _load_one(p, "package")
        if isinstance(res, LoadedAdapter):
            package.append(res)
        else:
            e3.append(res)

    return AdapterGroups(
        project=project,
        user=user,
        package=package,
        errors=[*e1, *e2, *e3],
    )


def get_adapter(harness_id: str) -> LoadedAdapter | None:
    """Resolve the winner for a HARNESS_ID via project > user > package precedence."""
    return discover_all().resolve(harness_id)


@dataclass
class AdapterProbe:
    adapter: LoadedAdapter
    since_seconds: int
    sessions: int
    turns: int
    models: dict[str, int]
    tool_kinds: dict[str, int]
    supported: bool  # false when the adapter doesn't implement recent_sessions


def probe_adapter(adapter: LoadedAdapter, since_seconds: int) -> AdapterProbe:
    """
    Diagnostic: summarize sessions the adapter has seen in the last N seconds.

    Pin verification uses path-scoped `sessions_for_run`; this function is purely
    for `vera adapters test` ("does my adapter parse anything?"). Adapters may
    opt in by exposing `recent_sessions(since_seconds)`. If they don't, we return
    supported=False.
    """
    if not hasattr(adapter.module, "recent_sessions"):
        return AdapterProbe(
            adapter=adapter,
            since_seconds=since_seconds,
            sessions=0,
            turns=0,
            models={},
            tool_kinds={},
            supported=False,
        )
    sessions = adapter.module.recent_sessions(since_seconds)
    turns: list[dict] = []
    for s in sessions:
        for t in adapter.module.session_turns(s):
            turns.append(t)
    models: dict[str, int] = {}
    tool_kinds: dict[str, int] = {}
    for t in turns:
        m = t.get("model")
        if m:
            models[m] = models.get(m, 0) + 1
        for call in t.get("tool_calls", []) or []:
            k = call.get("kind", "?")
            tool_kinds[k] = tool_kinds.get(k, 0) + 1
    return AdapterProbe(
        adapter=adapter,
        since_seconds=since_seconds,
        sessions=len(sessions),
        turns=len(turns),
        models=models,
        tool_kinds=tool_kinds,
        supported=True,
    )
