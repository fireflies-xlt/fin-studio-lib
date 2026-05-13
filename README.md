# fin-studio-lib

[`fin-studio`](https://github.com/fireflies-xlt/fin-studio) 的协议工具仓库——把 vault 上的 panel / frontmatter 协议抽出来，给 fin-studio runtime 和任意 vault 仓库的 Python panel-producer skills 共用。

主体包：`vault-research-toolkit`（`src/vault_research_toolkit/`）。仓库与具体 vault 解耦——`vault_root` 自动从 `3-DataPanels/` 探测或由 caller 注入，包本身仓库无关。

## 模块

| Module | 用途 |
|---|---|
| `vault_research_toolkit.frontmatter` | 读写 Markdown YAML frontmatter（`---\n…\n---\n`）。 |
| `vault_research_toolkit.panel` | Panel 协议工具：`write_panel` / `read_panel` / `list_panels` / `df_to_md` / `rows_to_md` / `find_vault_root`。 |

## Panel 协议（极简）

一面板 = 一份 md，放在 `<vault>/3-DataPanels/<filename>.md`：

```markdown
---
title: 三七互娱 · 日基础数据
asset: 三七互娱
category: stock
maintained_by: stock-daily-basic
last_updated: 2026-05-08
---

| 指标 | 值 |
| --- | --- |
| PE | 5.2 |
| PB | 0.6 |
```

**文件名 = 唯一标识**（无独立 `panel_id` 字段）；frontmatter 5 字段；body 任意合法 markdown。完整规范见 [`fin-studio/docs/panel-protocol.md`](https://github.com/fireflies-xlt/fin-studio/blob/main/docs/panel-protocol.md)。

## 怎么被使用

`runner: uv` 的 panel-producer skill 在入口脚本顶部用 PEP 723 inline metadata 声明 PyPI 依赖；`vault-research-toolkit` 由 **fin-studio runtime** 在 spawn `uv run` 时通过 `--with-editable <local>` 或 `--with <git-url>` 自动注入（取决于 `toolkitPath` 设置）：

```bash
uv run --with-editable G:\project\finance_group\fin-studio-lib \
  vault/.skills/stock-daily-basic/scripts/produce.py --name 三七互娱
```

最简 producer（参数用 argparse，便于 fin-studio 把 `params` dict 转 CLI flag）：

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["fin-data-client"]
# ///
import argparse
from vault_research_toolkit.panel import write_panel, df_to_md

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    args = p.parse_args()

    df = fetch_daily_basic(args.name)
    write_panel(
        filename=f"{args.name}.日基础数据",
        title=f"{args.name} · 日基础数据",
        asset=args.name,
        category="stock",
        maintained_by="stock-daily-basic",
        body=df_to_md(df),
        params={"name": args.name},
    )

if __name__ == "__main__":
    main()
```

`write_panel` 自动写到 `<vault>/3-DataPanels/<filename>.md` 并填 `last_updated`；`params` 透写进 frontmatter，给 fin-studio 重刷按钮复用。vault 根从 `VAULT_ROOT` 环境变量 / 父目录回溯 / `cwd` 三档探测。

> 未来若本包 publish 到 PyPI，fin-studio 会切换成 `--with vault-research-toolkit==X.Y`；skill 端可选写进 PEP 723 `dependencies` 自己锁版本。

## 本地开发

需要 [`uv`](https://docs.astral.sh/uv/)（fin-studio 设置面板可一键安装）。

```bash
uv venv
uv pip install -e ".[dev]"
uv run pytest        # 已加 pytest 用例时
```

## 相关仓库

| 仓库 | 关系 |
|---|---|
| [`fin-studio`](https://github.com/fireflies-xlt/fin-studio) | 协议定义方 + 桌面 GUI；通过 `toolkitPath` 设置项注入本包到 skill venv |
| [`fin-research-agent`](https://github.com/fireflies-xlt/fin-research-agent) | 示例 vault + 一组 panel-producer skills，依赖本包 |

> 本地开发推荐把三个仓库 clone 到同一父目录（`<root>/fin-studio` / `<root>/fin-studio-lib` / `<root>/fin-research-agent`），fin-studio 设置面板的 Toolkit 目录会自动探测到 sibling 路径。

## 许可证

MIT。
