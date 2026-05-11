"""Research-类 skill 的通用调度。

把"建档 + 按 section.freq + last_updated 懒刷"的骨架抽出来，
让每个 `research-{asset}` skill 只声明差异点（解析器、页面路径、frontmatter 等）。

接入方式（在 skill 的 `scripts/refresh.py`）：

    from pathlib import Path
    from vault_research_toolkit.research import ResearchSkillSpec, main

    _SKILL_DIR = Path(__file__).resolve().parents[1]            # vault/.skills/<id>/
    _VAULT_ROOT = _SKILL_DIR.parents[1]                         # vault/

    SPEC = ResearchSkillSpec(
        skill_name="research-stock",
        vault_root=_VAULT_ROOT,
        template_path=_SKILL_DIR / "templates" / "entity-stock.md",
        resolve=resolve.resolve_stock,
        page_path=lambda info: _VAULT_ROOT / "1-Wiki" / f"{info['name']}.md",
        build_frontmatter=_build_frontmatter,
    )

    if __name__ == "__main__":
        raise SystemExit(main(SPEC))

`section.source` 协议：path-style `<skillId>/scripts/<file>.py`，相对
`<vault_root>/.skills/`。文件须暴露 `fetch(info) + render(data)`。调度器用
`importlib.util.spec_from_file_location` 按文件路径加载，不依赖 `sys.path`。
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import frontmatter, sections

_FREQ_DAYS = {"daily": 1, "weekly": 7, "monthly": 30, "quarterly": 90}
_FREQ_KNOWN = set(_FREQ_DAYS) | {"always", "on-demand"}


@dataclass(frozen=True)
class ResearchSkillSpec:
    """Research-类 skill 的差异声明。"""

    skill_name: str
    """skill 名（如 `research-stock`），用于 CLI 描述与错误信息。"""

    vault_root: Path
    """该 skill 服务的 vault 根目录。`<vault_root>/.skills/` 用于 path-style
    `section.source` 解析。"""

    template_path: Path
    """该 skill 的模板文件，模板正文里用 `<!--section ... -->` 声明可刷新段。"""

    resolve: Callable[[str], dict]
    """把 CLI 里的 `keyword` 字符串解析成 `info` dict；未命中应抛 LookupError，多义应抛 LookupError 并列候选。"""

    page_path: Callable[[dict], Path]
    """info → wiki 页面绝对路径。父目录由调度自动创建。文件名 stem 同时用作
    `[[wikilink]]` 名（fin-studio 反链 / 全文检索都按 stem 走）。"""

    build_frontmatter: Callable[[dict, str], dict]
    """(info, today) → frontmatter dict。created/updated 都填 today。"""

    body_prefix: Callable[[dict], str] | None = None
    """可选：建档时插在模板正文前的额外内容（如分类导航行）。**仅创建骨架时注入**；
    已存在的页面不会自动更新这段，因此应放结构稳定、几乎不变的内容。"""


def _ensure_skeleton(spec: ResearchSkillSpec, info: dict, today: str) -> bool:
    """页面不存在时按模板建骨架；返回是否新建。"""
    page = spec.page_path(info)
    if page.exists():
        return False
    page.parent.mkdir(parents=True, exist_ok=True)
    body = spec.template_path.read_text(encoding="utf-8")
    if spec.body_prefix is not None:
        body = spec.body_prefix(info) + "\n\n" + body
    frontmatter.write(page, spec.build_frontmatter(info, today), body)
    return True


def _ensure_template_sections(spec: ResearchSkillSpec, body: str) -> tuple[str, list[str]]:
    """把模板里有、当前 body 里没有的 section 追加到 body 末尾（含其上方 H2 标题与空行）。"""
    template_text = spec.template_path.read_text(encoding="utf-8")
    existing_ids = {s.id for s in sections.iter_sections(body)}
    added: list[str] = []
    prev_end = 0
    for sec in sections.iter_sections(template_text):
        _, end = sec.span
        if sec.id not in existing_ids:
            piece = template_text[prev_end:end].lstrip("\n")
            body = body.rstrip("\n") + "\n\n" + piece
            added.append(sec.id)
        prev_end = end
    return body, added


def _needs_refresh(sec: sections.Section, today: str, force: bool) -> bool:
    if not sec.machine:
        return False
    if force:
        return True
    freq = (sec.freq or "always").lower()
    if freq == "always":
        return True
    if freq == "on-demand":
        return False
    if not sec.last_updated:
        return True
    if freq not in _FREQ_KNOWN:
        print(
            f"[warn] 未知 freq={sec.freq!r}（section id={sec.id}），按 always 处理",
            file=sys.stderr,
        )
        return True
    days = _FREQ_DAYS[freq]
    try:
        last = dt.date.fromisoformat(str(sec.last_updated))
        today_d = dt.date.fromisoformat(today)
    except ValueError:
        return True
    return (today_d - last).days >= days


def _call_source(spec: ResearchSkillSpec, source: str, info: dict) -> str:
    """按 path-style `source` 加载 fetch + render 函数并执行。

    `source` 形如 `<skillId>/scripts/<file>.py`，相对 `<vault_root>/.skills/`。
    用 `importlib.util.spec_from_file_location` 按文件路径加载，不依赖 `sys.path`。
    模块必须暴露 `fetch(info)` 与 `render(data)`。
    """
    if not (source.endswith(".py") and "/" in source):
        raise ValueError(
            f"section.source 必须是 path-style `<skillId>/scripts/<file>.py`，得到: {source!r}"
        )
    skills_root = spec.vault_root / ".skills"
    file_path = skills_root / source
    if not file_path.is_file():
        raise FileNotFoundError(
            f"section.source 文件不存在: {file_path}（vault_root={spec.vault_root}）"
        )
    module_name = "_vrt_source_" + source.replace("/", "__").replace(".", "_")
    spec_obj = importlib.util.spec_from_file_location(module_name, file_path)
    if spec_obj is None or spec_obj.loader is None:
        raise ImportError(f"无法为 {file_path} 构造 module spec")
    mod = importlib.util.module_from_spec(spec_obj)
    sys.modules[module_name] = mod
    spec_obj.loader.exec_module(mod)

    if not hasattr(mod, "fetch") or not hasattr(mod, "render"):
        raise AttributeError(
            f"模块 {source} 必须提供 fetch(info) 和 render(data) 函数"
        )
    return str(mod.render(mod.fetch(info))).rstrip("\n")


def run_refresh(
    spec: ResearchSkillSpec,
    keyword: str,
    *,
    force: bool = False,
    section_id: str | None = None,
) -> None:
    """skill 调度主流程。资产无关。

    - `section_id=None`：整页流程，按 freq + last_updated + force 判断哪些段过期。
    - `section_id` 非空：段级精刷流程，只刷该 id（**强制，无视 freq / last_updated**）；
      找不到 / 非 machine / 缺 source 时抛错。供 fin-studio "刷新本段" 通路调用。
    """
    today = dt.date.today().isoformat()
    info = spec.resolve(keyword)
    page = spec.page_path(info)

    created = _ensure_skeleton(spec, info, today)
    meta, body = frontmatter.read(page)
    body, added_ids = _ensure_template_sections(spec, body)

    refreshed_ids: list[str] = []
    if section_id is not None:
        body, refreshed_ids = _refresh_single_section(spec, body, section_id, info, today)
    else:
        for sec in list(sections.iter_sections(body)):
            if not _needs_refresh(sec, today, force):
                continue
            if not sec.source:
                continue
            new_body = _call_source(spec, sec.source, info)
            body = sections.replace_section(
                body, sec.id, new_body=new_body, last_updated=today
            )
            refreshed_ids.append(sec.id)

    if refreshed_ids:
        meta["updated"] = today
    frontmatter.write(page, meta, body)

    try:
        rel = page.relative_to(spec.vault_root.parent)
    except ValueError:
        rel = page
    status = "created" if created else "updated"
    print(f"[{status}] {rel}")
    if added_ids:
        print(f"  sections added: {', '.join(added_ids)}")
    if refreshed_ids:
        print(f"  sections refreshed: {', '.join(refreshed_ids)}")
    elif not added_ids:
        print("  no sections needed refresh")


def _refresh_single_section(
    spec: ResearchSkillSpec,
    body: str,
    section_id: str,
    info: dict,
    today: str,
) -> tuple[str, list[str]]:
    """段级精刷：只处理 section_id 这一段，强制刷新；返回新 body 与已刷 id 列表。

    校验：
      - 该 id 必须存在
      - 必须 machine=true
      - 必须有 source 字段
    """
    target = next(
        (s for s in sections.iter_sections(body) if s.id == section_id), None
    )
    if target is None:
        raise LookupError(f"页面中没有 section id={section_id!r}")
    if not target.machine:
        raise ValueError(
            f"section id={section_id!r} 是人写区（machine=false），不可机器刷新"
        )
    if not target.source:
        raise ValueError(
            f"section id={section_id!r} 没有 source 字段，不知道由谁产出"
        )
    new_body = _call_source(spec, target.source, info)
    body = sections.replace_section(
        body, section_id, new_body=new_body, last_updated=today
    )
    return body, [section_id]


def main(spec: ResearchSkillSpec, argv: list[str] | None = None) -> int:
    """标准 CLI 入口：keyword + `--force` / `--section` 开关 + 友好错误。

    `--force` 与 `--section` 互斥——段级精刷本身就是强制（无视 freq）。
    """
    parser = argparse.ArgumentParser(
        description=f"{spec.skill_name}：建档 + 按 section.freq 懒刷"
    )
    parser.add_argument(
        "keyword",
        help="解析为目标实体的关键词（具体语义见对应 skill 的 SKILL.md）",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--force",
        action="store_true",
        help="忽略 freq / last_updated，强制刷新所有 machine=true 段",
    )
    group.add_argument(
        "--section",
        metavar="ID",
        default=None,
        help="只刷指定 section id（machine=true 段，强制无视 freq）；fin-studio 段级刷新通路使用",
    )
    args = parser.parse_args(argv)
    try:
        run_refresh(
            spec, args.keyword, force=args.force, section_id=args.section
        )
    except (LookupError, ValueError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    return 0
