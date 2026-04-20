"""Output formatting. Matches cli.html example output closely.

Uses click.echo + click.style for cross-platform color. Rich is only pulled in for
the handful of places where structured tables help.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

import click

from vera.core import config, timebudget


def _home_shorten(path: Path) -> str:
    """Render a path with ~ prefix when inside $HOME. Does not follow symlinks."""
    try:
        abs_path = path.absolute()
        rel = abs_path.relative_to(Path.home())
        return f"~/{rel}"
    except ValueError:
        return str(path)


def _cwd_shorten(path: Path) -> str:
    try:
        abs_path = path.absolute()
        rel = abs_path.relative_to(Path.cwd())
        return str(rel)
    except ValueError:
        return _home_shorten(path)


def _format_signal_value(key: str, value: Any, signals: dict[str, Any]) -> str | None:
    """Render a single grader signal.

    Suppress 'X_total' counterparts when 'X_passed' handles them.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    # tests_passed / tests_total -> "38 / 42"; skip printing tests_total on its own.
    if key == "tests_total" and "tests_passed" in signals:
        return None
    if key == "tests_passed" and "tests_total" in signals:
        return f"{value} / {signals['tests_total']}"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not value.is_integer():
            return f"{value}"
        return str(int(value))
    if value is None:
        return ""
    return str(value)


def _variant_label(variant: dict[str, Any]) -> str:
    budget = variant.get("time_budget")
    if budget in (None, "unbounded"):
        return f"{variant['name']} unbounded"
    return f"{variant['name']} {budget}"


# ------------------------------------------------------------------ list


def render_list(entries: Iterable, catalog_versions: dict[str, str] | None = None) -> None:
    rows: list[tuple[str, str, str, str, str]] = []
    # (slug, version_col, tag_col, variants, update_marker)
    catalog_versions = catalog_versions or {}
    for entry in entries:
        meta = entry.meta
        tag_col = meta.tags[0] if meta.tags else ""
        variants = "   ".join(_variant_label(v) for v in meta.variants)
        local_v = getattr(entry, "version", None)
        version_col = f"@{local_v}" if local_v else ""
        catalog_v = catalog_versions.get(meta.slug)
        if catalog_v and local_v and catalog_v != local_v:
            update_marker = click.style(f"[update to {catalog_v} available]", fg="yellow")
        else:
            update_marker = ""
        rows.append((meta.slug, version_col, tag_col, variants, update_marker))

    if not rows:
        click.echo("(no challenges registered — use `vera add` to register one)")
        return

    slug_w = max(len(r[0]) for r in rows)
    version_w = max((len(r[1]) for r in rows), default=0)
    tag_w = max(len(r[2]) for r in rows) if any(r[2] for r in rows) else 0

    for slug, version, tag, variants, marker in rows:
        parts = [slug.ljust(slug_w)]
        if version_w:
            parts.append(version.ljust(version_w))
        if tag_w:
            parts.append(tag.ljust(tag_w))
        parts.append(variants)
        line = "   ".join(parts)
        if marker:
            line = f"{line}   {marker}"
        click.echo(line)


# ------------------------------------------------------------------ add


def render_add(results: list) -> None:
    for r in results:
        reg = _home_shorten(r.registry_path)
        if r.registry_path.is_symlink():
            click.echo(f"linked   {reg}")
        else:
            click.echo(f"cloned into {reg}")
        if "→" in r.source_label:
            click.echo(f"source    {r.source_label}")
        click.echo(f"slug      {r.meta.slug}")
        click.echo(f"variants  {'  '.join(v['name'] for v in r.meta.variants)}")
        click.echo(click.style("registered", fg="green"))


# ------------------------------------------------------------------ start


def _fmt_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n / 1024 / 1024:.1f} MB"


def render_start(info: Any) -> None:
    rel_run = _cwd_shorten(info.run_dir) + "/"
    click.echo(f"→ created  {rel_run}")
    click.echo(f"→ copied   workspace/ ({info.file_count} files, {_fmt_bytes(info.bytes_copied)})")
    if info.container:
        ports = "  ".join(info.compose_ports) if info.compose_ports else "up"
        click.echo(f"→ compose  up  ({ports})" if info.compose_ports else "→ compose  up")
    click.echo(f"→ pin      {info.pin['harness']} + {info.pin['model']}")
    budget = info.pin.get("time_budget")
    if budget in (None, "unbounded"):
        click.echo("→ budget   unbounded (reported, not enforced)")
    else:
        click.echo(f"→ budget   {budget} (reported, not enforced)")
    brief_rel = _cwd_shorten(info.brief_path)
    click.echo(click.style(f"brief    {brief_rel}", fg="yellow"))


# ------------------------------------------------------------------ status


def render_status(active: Any) -> None:
    run = active.run_json
    run_dir_str = _cwd_shorten(active.run_dir) + "/"
    started = datetime.utcfromtimestamp(active.start_epoch).strftime("%Y-%m-%d %H:%M:%S")
    elapsed = int(datetime.utcnow().timestamp() - active.start_epoch)
    budget = run["pin"].get("time_budget")
    budget_str = f"   (budget {budget})" if budget not in (None, "unbounded") else ""

    click.echo(f"slug         {run['slug']}")
    click.echo(f"variant      {run['variant']}")
    click.echo(f"pin          {run['pin']['harness']} + {run['pin']['model']}")
    click.echo(f"started      {started}")
    click.echo(f"elapsed      {timebudget.format_elapsed(elapsed)}{budget_str}")
    click.echo(f"run dir      {run_dir_str}")


# ------------------------------------------------------------------ grade


def render_grade(outcome: Any) -> None:
    grader_s = f"{outcome.grader_seconds:.1f}s"
    click.echo(f"running grader/grade.sh ... done ({grader_s})")
    if outcome.pin_honored not in ("skipped", "unimplemented"):
        harness_id = outcome.adapter_used.harness_id if outcome.adapter_used else "harness"
        click.echo(f"reading {harness_id} session logs ... done")
    elif outcome.pin_honored == "unimplemented":
        harness_id = outcome.adapter_used.harness_id if outcome.adapter_used else "harness"
        click.echo(f"reading {harness_id} session logs ... skipped (adapter pending)")
    if outcome.compose_down:
        click.echo("tearing down compose ... done")

    click.echo("")

    if outcome.result["pass"]:
        click.echo(click.style("✓ pass", fg="green"))
    else:
        click.echo(click.style("✗ fail", fg="red"))

    if "score" in outcome.result:
        score = outcome.result["score"]
        click.echo(f"score              {int(score) if float(score).is_integer() else score} / 100")
    budget = outcome.budget_seconds
    budget_str = f"   (budget {timebudget.format_elapsed(budget)})" if budget else ""
    elapsed_str = timebudget.format_elapsed(outcome.elapsed_seconds)
    click.echo(f"elapsed            {elapsed_str}{budget_str}")
    pin_suffix = (
        "   (this harness adapter doesn't verify pin yet)"
        if outcome.pin_honored == "unimplemented"
        else ""
    )
    click.echo(f"pin honored        {outcome.pin_honored}{pin_suffix}")

    signals = outcome.result.get("signals") or {}
    if signals:
        click.echo("signals")
        key_width = max((len(k) for k in signals), default=0)
        for k, v in signals.items():
            val_str = _format_signal_value(k, v, signals)
            if val_str is None:
                continue
            click.echo(f"  {k.ljust(max(key_width + 2, 18))}{val_str}")

    click.echo("")
    rel = _cwd_shorten(outcome.run_dir / "result.json")
    click.echo(f"result written: {rel}")


# ------------------------------------------------------------------ submit


def render_submit(info: Any) -> None:
    click.echo(f"appended to {_home_shorten(info.journal_path)}")
    click.echo(click.style("done", fg="green"))


# ------------------------------------------------------------------ new


def render_new(slug: str, created: list[str]) -> None:
    click.echo(f"created {slug}/")
    for line in created:
        click.echo(f"  {click.style('✓', fg='green')} {line}")
    click.echo("")
    click.echo(
        click.style(
            "next: fill in workspace/ and grader/grade.sh, then run vera test.",
            fg="yellow",
        )
    )


# ------------------------------------------------------------------ test


def render_test(report: Any) -> None:
    for line in report.lines:
        prefix = click.style("✓", fg="green") if line.ok else click.style("✗", fg="red")
        click.echo(f"{prefix} {line.text}")
        for detail in line.details:
            click.echo(click.style(f"  → {detail}", fg="red"))
    click.echo("")
    if report.ok:
        click.echo(click.style("ok — ready to publish", fg="green"))
    else:
        click.echo(click.style("test failed — fix and re-run.", fg="red"))


# ------------------------------------------------------------------ info


def _format_variant_row(v: dict[str, Any]) -> tuple[str, str, str]:
    """Return (name, pin, budget_str) tuple for a variant."""
    name = v["name"]
    pin = f"{v['harness']} + {v['model']}"
    budget = v.get("time_budget")
    budget_str = f"budget {budget}" if budget not in (None, "unbounded") else "budget unbounded"
    return name, pin, budget_str


def render_info(listed: Any, catalog_version: str | None = None) -> None:
    meta = listed.meta
    local_v = listed.version
    header_version = f"@{local_v}" if local_v else ""
    click.echo(f"{click.style(meta.slug, fg='yellow')}   {header_version}".rstrip())
    if catalog_version and local_v and catalog_version != local_v:
        click.echo(
            click.style(
                f"  [update to {catalog_version} available — run `vera update {meta.slug}`]",
                fg="yellow",
            )
        )
    if meta.description:
        click.echo(meta.description)
    click.echo("")

    if meta.title and meta.title != meta.slug:
        click.echo(f"title        {meta.title}")
    if meta.tags:
        click.echo(f"tags         {' · '.join(meta.tags)}")

    # Registered path is the registry entry; meta.root is the resolved target.
    reg_entry = config.registry_path() / meta.slug
    reg_short = _home_shorten(reg_entry)
    if listed.is_symlink:
        target_short = _home_shorten(meta.root)
        click.echo(f"registered   {reg_short}/   (symlink → {target_short})")
    else:
        click.echo(f"registered   {reg_short}/")
    click.echo(f"container    {'yes' if meta.container else 'no'}")
    click.echo("")

    click.echo("variants")
    rows = [_format_variant_row(v) for v in meta.variants]
    name_w = max(len(r[0]) for r in rows) if rows else 0
    pin_w = max(len(r[1]) for r in rows) if rows else 0
    for v, (name, pin, budget_str) in zip(meta.variants, rows, strict=True):
        click.echo(f"  {name.ljust(name_w)}   {pin.ljust(pin_w)}   {budget_str}")
        notes = v.get("notes")
        if notes:
            indent = " " * (2 + name_w + 3)
            click.echo(click.style(f"{indent}{notes}", fg="bright_black"))


def render_discover_detail(entry: Any, local_version: str | None = None) -> None:
    """Detail view for a catalog entry — reachable via `vera discover <slug>`."""
    header_bits = [click.style(entry.slug, fg="yellow"), f"@{entry.version}"]
    if local_version:
        if local_version == "untagged":
            header_bits.append(click.style("(installed, untagged)", fg="green"))
        else:
            header_bits.append(click.style(f"(installed @{local_version})", fg="green"))
    else:
        header_bits.append(click.style("(not installed)", fg="bright_black"))
    click.echo("   ".join(header_bits))
    if entry.description:
        click.echo(entry.description)
    click.echo("")

    click.echo(f"source       {entry.url}")
    if entry.path:
        click.echo(f"path         {entry.path}")
    if entry.tags:
        click.echo(f"tags         {' · '.join(entry.tags)}")
    if entry.author:
        click.echo(f"author       @{entry.author}")
    if entry.difficulty:
        click.echo(f"difficulty   {entry.difficulty}")
    click.echo("")

    if not local_version:
        click.echo(
            click.style(
                f"install with: vera add {entry.slug}",
                fg="bright_black",
            )
        )
        click.echo(
            click.style(
                "(full variant pins — harness + model + budget — are visible via "
                "`vera info` after installing)",
                fg="bright_black",
            )
        )
    else:
        click.echo(
            click.style(
                f"full variant detail: vera info {entry.slug}",
                fg="bright_black",
            )
        )


def render_discover_pack(pack: Any) -> None:
    """Detail view for a pack slug — reachable via `vera discover <pack-slug>`."""
    click.echo(f"{click.style(pack.title, fg='yellow')}   @{pack.version}   ({pack.slug})")
    if pack.description:
        click.echo(pack.description)
    click.echo("")

    click.echo(f"source       {pack.url}")
    if pack.tags:
        click.echo(f"tags         {' · '.join(pack.tags)}")
    if pack.author:
        click.echo(f"author       @{pack.author}")
    click.echo("")

    click.echo(f"challenges in this pack ({len(pack.children)}):")
    slug_w = max(len(c.slug) for c in pack.children) if pack.children else 0
    for c in pack.children:
        tags = " · ".join(c.tags) if c.tags else ""
        diff = f"[{c.difficulty}]" if c.difficulty else ""
        click.echo(f"  {c.slug.ljust(slug_w)}   {tags}   {diff}")
    click.echo("")
    click.echo(click.style(f"install the whole pack: vera add {pack.slug}", fg="bright_black"))
    click.echo(
        click.style(
            "install a single child: vera add <child-slug>",
            fg="bright_black",
        )
    )


# ------------------------------------------------------------------ discover


def render_discover(packs: list, singles: list) -> None:
    if not packs and not singles:
        click.echo("(catalog is empty — nothing to show)")
        return

    if packs:
        for pack, children in packs:
            header = click.style(f"{pack.title} @{pack.version}", fg="yellow")
            click.echo(f"{header}  ({pack.slug})")
            if pack.description:
                click.echo(click.style(f"  {pack.description}", fg="bright_black"))
            if children:
                slug_w = max(len(c.slug) for c in children)
                for c in children:
                    tags = " · ".join(c.tags) if c.tags else ""
                    diff = f"[{c.difficulty}]" if c.difficulty else ""
                    click.echo(f"  {c.slug.ljust(slug_w)}   {tags}   {diff}")
            click.echo("")

    if singles:
        click.echo(click.style("community", fg="yellow"))
        slug_w = max(len(s.slug) for s in singles)
        for s in singles:
            version = f"@{s.version}"
            tags = " · ".join(s.tags) if s.tags else ""
            author = f"@{s.author}" if s.author else ""
            click.echo(f"  {s.slug.ljust(slug_w)}   {version}   {tags}   {author}")


# ------------------------------------------------------------------ update


def render_update(updates: list) -> None:
    """updates: list of (slug, old_version, new_version, error|None)."""
    if not updates:
        click.echo("nothing to update")
        return
    any_changed = False
    any_error = False
    slug_w = max(len(u[0]) for u in updates)
    for slug, old, new, error in updates:
        if error:
            click.echo(f"{click.style('✗', fg='red')} {slug.ljust(slug_w)}   {error}")
            any_error = True
            continue
        if old == new:
            click.echo(f"  {slug.ljust(slug_w)}   @{old or '?'}   (up to date)")
            continue
        any_changed = True
        click.echo(f"{click.style('↑', fg='green')} {slug.ljust(slug_w)}   {old or '?'} → {new}")
    if any_changed and not any_error:
        click.echo("")
        click.echo(click.style("done", fg="green"))


# ------------------------------------------------------------------ adapters


def render_adapters_list(groups: Any) -> None:
    def _print_group(title: str, location: Path, adapters: list) -> None:
        click.echo(f"{title}   {_home_shorten(location)}/")
        if not adapters:
            click.echo("  (none)")
            return
        width = max((len(a.harness_id) for a in adapters), default=0)
        for a in adapters:
            detect = "yes" if a.detect else "no"
            click.echo(
                f"  {a.harness_id.ljust(max(width, 16))}  v{a.contract_version}   "
                f"detect={detect}   {a.source.name}"
            )

    _print_group("project ", config.project_adapters_dir(), groups.project)
    click.echo("")
    _print_group("user    ", config.user_adapters_dir(), groups.user)
    click.echo("")
    _print_group("package ", Path(__file__).resolve().parent.parent / "adapters", groups.package)

    if groups.errors:
        click.echo("")
        click.echo(click.style("adapter load errors:", fg="red"))
        for err in groups.errors:
            click.echo(f"  {err.source_group} {err.source.name}: {err.reason}")


def render_adapters_test(probe: Any) -> None:
    click.echo(
        f"adapter       {probe.adapter.harness_id}  v{probe.adapter.contract_version}   "
        f"{_home_shorten(probe.adapter.source)}"
    )
    if not probe.supported:
        click.echo(
            click.style(
                "note          this adapter does not implement recent_sessions() "
                "— no diagnostic available.",
                fg="yellow",
            )
        )
        return

    click.echo(f"since         last {timebudget.format_elapsed(probe.since_seconds)}")
    click.echo(f"sessions      {probe.sessions}")
    click.echo(f"turns         {probe.turns}")
    if probe.models:
        models_str = "   ".join(f"{k} ({v})" for k, v in probe.models.items())
        click.echo(f"models        {models_str}")
    else:
        click.echo("models        (none)")
    if probe.tool_kinds:
        kinds_str = "   ".join(f"{k} ({v})" for k, v in probe.tool_kinds.items())
        click.echo(f"tool kinds    {kinds_str}")
    else:
        click.echo("tool kinds    (none)")
