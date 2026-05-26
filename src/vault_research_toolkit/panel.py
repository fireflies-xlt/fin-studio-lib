"""Panel：数据面板的读写 + vault 查找。

协议规范见 fin-studio `docs/panel-protocol.md`。

面板物理布局：
- 一面板 = 一份 md，放在 `<vault>/DataPanels/<filename>.md`
- 文件名 = 唯一标识（无独立 panel_id 字段）
- frontmatter 4 字段：title / asset / maintained_by / last_updated
- body 为任意合法 markdown

Producer 通常只用 `write_panel(...)` 一个函数；UI / 索引侧用 `read_panel` / `list_panels`。
"""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from . import frontmatter

PANELS_DIR = "DataPanels"


@dataclass(frozen=True)
class Panel:
    """已写入磁盘的一份 panel。"""

    filename: str
    """不含扩展名的文件名（= panel 的稳定标识）。"""

    title: str
    asset: str
    maintained_by: str
    """产出该 panel 的 skill id。"""

    last_updated: dt.date | None
    body: str
    path: Path
    """绝对路径（调试 / 编辑器跳转用）。"""


# --------------------------------------------------------------------------- #
# vault 定位
# --------------------------------------------------------------------------- #


def find_vault_root(start: Path | str | None = None) -> Path:
    """沿父目录查找包含 `DataPanels/` 子目录的 vault 根。

    优先级：
    1. 显式传入的 `start` 起点
    2. 环境变量 `VAULT_ROOT`
    3. `Path.cwd()`

    Raises:
        FileNotFoundError: 找到根都没匹配。
    """
    if start is None:
        env = os.environ.get("VAULT_ROOT")
        start = Path(env) if env else Path.cwd()
    cur = Path(start).resolve()
    for candidate in (cur, *cur.parents):
        if (candidate / PANELS_DIR).is_dir():
            return candidate
    raise FileNotFoundError(
        f"未找到 vault 根（含 `{PANELS_DIR}/` 子目录），从 {cur} 起回溯到文件系统根都没匹配"
    )


def _panel_path(filename: str, vault_root: Path | str | None) -> Path:
    if not filename or "/" in filename or "\\" in filename or filename.endswith(".md"):
        raise ValueError(
            f"非法 panel filename: {filename!r}；需为不含扩展名 / 路径分隔符的纯文件名"
        )
    root = Path(vault_root) if vault_root else find_vault_root()
    panels_dir = root / PANELS_DIR
    panels_dir.mkdir(parents=True, exist_ok=True)
    return panels_dir / f"{filename}.md"


# --------------------------------------------------------------------------- #
# write / read
# --------------------------------------------------------------------------- #


def write_panel(
    *,
    filename: str,
    title: str,
    asset: str,
    maintained_by: str,
    body: str,
    last_updated: dt.date | None = None,
    params: dict | None = None,
    vault_root: Path | str | None = None,
) -> Path:
    """写一份 panel 到 `<vault>/DataPanels/<filename>.md`，覆盖已存在的同名文件。

    `last_updated` 默认填今天（UTC）。
    `params` 是本次 producer 运行收到的参数字典；写入 frontmatter `params:` 子对象，
    供 UI「重刷」按钮无脑复用同一份输入。
    返回写入的绝对路径。
    """
    path = _panel_path(filename, vault_root)
    meta: dict = {
        "title": title,
        "asset": asset,
        "maintained_by": maintained_by,
        "last_updated": last_updated or dt.date.today(),
    }
    if params:
        meta["params"] = dict(params)
    frontmatter.write(path, meta, body.rstrip("\n") + "\n")
    return path


def read_panel(filename: str, *, vault_root: Path | str | None = None) -> Panel:
    """读一份已存在 panel。"""
    path = _panel_path(filename, vault_root)
    if not path.is_file():
        raise FileNotFoundError(f"panel 不存在: {path}")
    return _load_panel(path)


def list_panels(
    *,
    vault_root: Path | str | None = None,
    asset: str | None = None,
) -> list[Panel]:
    """列出 vault 内所有 panel，可按 `asset` 过滤。"""
    root = Path(vault_root) if vault_root else find_vault_root()
    panels_dir = root / PANELS_DIR
    if not panels_dir.is_dir():
        return []
    panels: list[Panel] = []
    for md in sorted(panels_dir.glob("*.md")):
        try:
            p = _load_panel(md)
        except (ValueError, OSError):
            continue
        if asset and p.asset != asset:
            continue
        panels.append(p)
    return panels


def _load_panel(path: Path) -> Panel:
    meta, body = frontmatter.read(path)
    last_updated = meta.get("last_updated")
    if isinstance(last_updated, str):
        try:
            last_updated = dt.date.fromisoformat(last_updated)
        except ValueError:
            last_updated = None
    elif not isinstance(last_updated, dt.date):
        last_updated = None
    return Panel(
        filename=path.stem,
        title=str(meta.get("title") or path.stem),
        asset=str(meta.get("asset") or ""),
        maintained_by=str(meta.get("maintained_by") or ""),
        last_updated=last_updated,
        body=body,
        path=path,
    )


# --------------------------------------------------------------------------- #
# 渲染 helper：表格生成器（零依赖，给 producer 用）
# --------------------------------------------------------------------------- #


def rows_to_md(
    rows: Iterable[Iterable[object]],
    *,
    headers: Iterable[object] | None = None,
) -> str:
    """把二维序列渲染成 GitHub-flavored markdown 表格。

    `headers` 为空时，rows 的第一行被当作表头。所有 cell 走 `str(...)` 转换；
    `None` 渲染为空字符串；管道符 `|` 转义为 `\\|`。
    """
    rows_list = [list(r) for r in rows]
    if headers is None:
        if not rows_list:
            return ""
        headers_list = rows_list[0]
        body_rows = rows_list[1:]
    else:
        headers_list = list(headers)
        body_rows = rows_list

    def cell(v: object) -> str:
        if v is None:
            return ""
        return str(v).replace("|", "\\|").replace("\n", " ")

    out = ["| " + " | ".join(cell(h) for h in headers_list) + " |"]
    out.append("| " + " | ".join("---" for _ in headers_list) + " |")
    for row in body_rows:
        out.append("| " + " | ".join(cell(v) for v in row) + " |")
    return "\n".join(out)


def df_to_md(df: object, *, index: bool = False) -> str:
    """pandas DataFrame → markdown 表格。

    pandas 是 producer 的依赖（不是 toolkit 的），故 lazy 访问 `df` 的属性。
    """
    if not hasattr(df, "columns") or not hasattr(df, "itertuples"):
        raise TypeError(f"df_to_md 需要 pandas DataFrame，收到: {type(df).__name__}")
    cols = list(df.columns)  # type: ignore[attr-defined]
    headers = (["", *cols] if index else cols)
    rows: list[list[object]] = []
    for row in df.itertuples(index=index):  # type: ignore[attr-defined]
        rows.append(list(row))
    return rows_to_md(rows, headers=headers)
