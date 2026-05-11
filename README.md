# fin-studio-lib

[`fin-studio`](https://github.com/fireflies-xlt/fin-studio) 的协议工具仓库——把 vault 上的 section / frontmatter 协议与 research-类 skill 的通用调度骨架抽出来，给 fin-studio runtime 和任意 vault 仓库的 Python skills 共用。

主体包：`vault-research-toolkit`（`src/vault_research_toolkit/`）。仓库与具体 vault 解耦——`vault_root` 由 caller 注入，包本身仓库无关。

## 模块

| Module | 用途 |
|---|---|
| `vault_research_toolkit.frontmatter` | 读写 Markdown YAML frontmatter（`---\n…\n---\n`）。 |
| `vault_research_toolkit.sections` | 解析 / 遍历 / 替换 `<!--section ... -->` 块。与 `fin-studio/shared/markdown/sections.ts` 协议一致。 |
| `vault_research_toolkit.research` | 通用 `ResearchSkillSpec` + `main()`：建档 + 按 `freq` / `last_updated` 懒刷 sections 的调度骨架，资产无关。 |

## Section 协议

```markdown
<!--section
id: daily_basic
machine: true
source: research-stock/scripts/fetch_daily_basic.py
freq: daily
last_updated: 2026-05-08
-->

| 指标 | 值 |
| --- | --- |
| PE | 5.2 |

<!--/section-->
```

`source` 是 path-style：`<skillId>/scripts/<file>.py`，相对 `<vault_root>/.skills/` 解析；用 `importlib.util.spec_from_file_location` 按文件路径加载，目标文件须暴露 `fetch(info)` 与 `render(data)`。

## 怎么被使用

`runner: uv` 类型的 skill 在入口脚本顶部用 PEP 723 inline metadata 声明 PyPI 依赖；`vault-research-toolkit` 由 **fin-studio runtime** 在 spawn `uv run` 时通过 `--with-editable <toolkitPath>` 注入：

```bash
uv run --with-editable G:\project\finance_group\fin-studio-lib \
  vault/.skills/research-stock/scripts/refresh.py "平安银行"
```

`toolkitPath` 是 fin-studio 的设置项（「设置 → Skills（Python）→ Toolkit 目录」），指向**本仓库根目录**（包含 `pyproject.toml` 的那一级）。

> 未来若本包 publish 到 PyPI，fin-studio 会切换成 `--with vault-research-toolkit==X.Y`；skill 端可以选择写进 PEP 723 `dependencies` 自己锁版本，也可以继续走 runtime 注入。

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
| [`fin-research-agent`](https://github.com/fireflies-xlt/fin-research-agent) | 个人 / 小团队的 vault + 一组 Python skills，依赖本包提供的调度骨架 |

> 本地开发推荐把三个仓库 clone 到同一父目录（`<root>/fin-studio` / `<root>/fin-studio-lib` / `<root>/fin-research-agent`），fin-studio 设置面板的 Toolkit 目录会自动探测到 sibling 路径。

## 许可证

MIT。
