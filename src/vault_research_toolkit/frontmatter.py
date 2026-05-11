"""读写 Markdown 文件的 YAML frontmatter。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_DELIM = "---"


def read(path: Path) -> tuple[dict[str, Any], str]:
    """读取 `path`，返回 (meta, body)。若无 frontmatter，meta 为空 dict。"""
    text = Path(path).read_text(encoding="utf-8")
    return parse(text)


def parse(text: str) -> tuple[dict[str, Any], str]:
    """解析字符串形式的 Markdown；规则同 `read`。"""
    lines = text.splitlines(keepends=False)
    if not lines or lines[0].strip() != _DELIM:
        return {}, text
    end = -1
    for idx in range(1, len(lines)):
        if lines[idx].strip() == _DELIM:
            end = idx
            break
    if end == -1:
        return {}, text
    meta_text = "\n".join(lines[1:end])
    meta = yaml.safe_load(meta_text) or {}
    if not isinstance(meta, dict):
        meta = {}
    body = "\n".join(lines[end + 1 :])
    if body.startswith("\n"):
        body = body[1:]
    return meta, body


def write(path: Path, meta: dict[str, Any], body: str) -> None:
    """按 `---\n{yaml}\n---\n\n{body}` 格式写回。`body` 不带开头分隔符。"""
    Path(path).write_text(dump(meta, body), encoding="utf-8")


def dump(meta: dict[str, Any], body: str) -> str:
    """序列化 frontmatter + body 为字符串。保持 dict 插入顺序。"""
    yaml_text = yaml.safe_dump(
        meta,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).rstrip("\n")
    body = body.lstrip("\n")
    return f"{_DELIM}\n{yaml_text}\n{_DELIM}\n\n{body}"
