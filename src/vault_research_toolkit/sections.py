"""解析 / 替换 Markdown 里的 section 块。

Section 格式（在 Markdown 正文中）：

    <!--section
    id: daily_basic
    machine: true
    source: research-stock/scripts/fetch_daily_basic.py
    freq: daily
    last_updated: null
    -->

    任意 Markdown 正文……

    <!--/section-->

元字段（YAML）：
    id            str   必填；section 唯一标识
    machine       bool  是否由 Agent 自动维护（默认 false）
    source        str   可选；section 产出方标识。path-style
                        `<skillId>/scripts/<file>.py`（相对 `<vault>/.skills/`），
                        文件须暴露 `fetch(info) + render(data)`
    freq          str   可选；always / daily / weekly / monthly / quarterly / on-demand
    last_updated  date  可选；上次刷新日期（ISO 字符串或 null）
    alert         dict  可选；告警阈值
    其余字段保留在 extra 字典中，写回时保留。

与 fin-studio 的 `shared/markdown/sections.ts` + `section-meta.ts` 一一对应。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterator

import yaml

_SECTION_RE = re.compile(
    r"<!--section\n(?P<meta>.*?)\n-->(?P<body>.*?)<!--/section-->",
    re.DOTALL,
)

_META_ORDER = ("id", "machine", "source", "freq", "last_updated", "alert")


@dataclass
class Section:
    id: str
    machine: bool = False
    source: str | None = None
    freq: str | None = None
    last_updated: str | None = None
    alert: dict[str, Any] | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    span: tuple[int, int] = (0, 0)  # 原文中整个 section 块的 [start, end)


def iter_sections(content: str) -> Iterator[Section]:
    """按出现顺序遍历 content 中的所有 section。"""
    for match in _SECTION_RE.finditer(content):
        meta_raw = match.group("meta")
        body = match.group("body")
        meta = yaml.safe_load(meta_raw) or {}
        if not isinstance(meta, dict):
            meta = {}
        sec = _section_from_meta(meta, body=body.strip("\n"))
        sec.span = (match.start(), match.end())
        yield sec


def _section_from_meta(meta: dict[str, Any], *, body: str) -> Section:
    known = {k: meta.get(k) for k in _META_ORDER if k in meta}
    extra = {k: v for k, v in meta.items() if k not in _META_ORDER}
    sec_id = known.get("id") or extra.pop("id", None)
    if not sec_id:
        raise ValueError(f"section 缺少 id: {meta!r}")
    machine_val = known.get("machine", False)
    if isinstance(machine_val, str):
        machine_val = machine_val.strip().lower() == "true"
    last = known.get("last_updated")
    return Section(
        id=str(sec_id),
        machine=bool(machine_val),
        source=known.get("source"),
        freq=known.get("freq"),
        last_updated=str(last) if last not in (None, "") else None,
        alert=known.get("alert"),
        extra=extra,
        body=body,
    )


def replace_section(
    content: str,
    section_id: str,
    *,
    new_body: str | None = None,
    **meta_updates: Any,
) -> str:
    """替换指定 section 的 body 和/或元字段，返回新 content。

    未命中抛 `KeyError`。
    """
    for match in _SECTION_RE.finditer(content):
        meta_raw = match.group("meta")
        meta = yaml.safe_load(meta_raw) or {}
        if not isinstance(meta, dict):
            continue
        if str(meta.get("id")) != section_id:
            continue
        if meta_updates:
            meta = {**meta, **meta_updates}
        body_text = match.group("body").strip("\n") if new_body is None else new_body
        rebuilt = _render_block(meta, body_text)
        start, end = match.start(), match.end()
        return content[:start] + rebuilt + content[end:]
    raise KeyError(f"未找到 section id={section_id}")


def _render_block(meta: dict[str, Any], body: str) -> str:
    meta_text = _dump_meta(meta)
    body = body.strip("\n")
    return f"<!--section\n{meta_text}\n-->\n\n{body}\n\n<!--/section-->"


def _dump_meta(meta: dict[str, Any]) -> str:
    ordered: dict[str, Any] = {}
    for key in _META_ORDER:
        if key in meta:
            ordered[key] = meta[key]
    for key, val in meta.items():
        if key not in ordered:
            ordered[key] = val
    return yaml.safe_dump(
        ordered,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).rstrip("\n")
