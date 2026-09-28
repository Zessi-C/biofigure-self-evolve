# 触发钩子：让 agent 每次都想起查图库

## 为什么需要这一层

技能自带的 `description` 仅在"技能列表被注入上下文"阶段生效，但在实际运行中往往存在局限：

- **列表很长**：omp 等 harness 常集中列出数十乃至上百个技能条目，其中绘图类亦包含若干细分项（MiloR 四面板、富集气泡图、投影 UMAP……）。候选过于庞杂时，模型容易误选其他技能条目。
- **子代理看不到技能列表**（仅当 harness 支持子代理）：委派时子代理通常仅接收一段任务描述，最典型的失效场景在于「父代理查了图库、子代理未查」：生成图表时会完全遗失父代理刚刚确认的偏好。不支持子代理的 harness 不受此条影响。
- **描述可能被截断**：部分 harness 会对文本长度施加限制，仅展示技能描述的前若干字符。

因此，除在 `description` 开头明确触发条件外，还须在**每轮交互均保持可见的常驻层**配置一条简短的触发钩子。针对 agent 频繁忽略图库检索的情况，这是最具针对性的解决措施。

## 一条命令装上（推荐）

建议在安装技能时即刻配置触发钩子，切勿延后处理：

```bash
python3 <技能目录>/scripts/install_hook.py            # 自动装到检测到的 harness 全局指令层
python3 <技能目录>/scripts/install_hook.py --check     # 验证（全部就绪 → 退出码 0）
python3 <技能目录>/scripts/install_hook.py --project /path/to/项目   # omp 等按项目读 AGENTS.md
python3 <技能目录>/scripts/install_hook.py --uninstall --project /path/to/项目
```

脚本执行逻辑：

- 自动检测：依次探查 `$DSH_HOME/AGENTS.md`（或 `~/.dsh/AGENTS.md`）、`~/.claude/CLAUDE.md` 与 `~/.omp/AGENTS.md`，检测到对应层级即自动完成安装
- 写入方式：写入由 HTML 成对注释 `<!-- biofigure-self-evolve:trigger-hook:begin/end -->` 标识的 5 行代码块；**重复运行仅覆盖该区块**（保持幂等性），原有文件内容完全保持原样
- `--dry-run` 仅输出拟写入的具体内容；`--check` 逐层报告"已装/未装/无此文件"状态
- 区块内部记录技能目录的**绝对路径**，若技能路径发生迁移，重新运行脚本即可完成刷新

## 钩子文本（手工装时复制）

```markdown
## 生信绘图（biofigure-self-evolve）
任何生信/统计图的产出、修改、复刻、学习，以及把这类任务委派给子代理之前，先读
`skill://biofigure-self-evolve`（omp；其他 harness 用 <技能目录>/SKILL.md），并跑
`python3 <技能目录>/scripts/retrieve.py "<需求>"` 检索图库；交付说明必须写明
"复用了 NNN-slug 的 XX"或"图库未命中"。委派时把技能入口或检索结果写进委派提示。
```

若仅需单行文本注入记忆层，可采用如下精简版本：

```text
画任何生信图之前：先读 skill://biofigure-self-evolve 并跑 retrieve.py 检索图库，交付时说明复用了哪条。
```

## 装到哪里

| Harness | 常驻层位置 | 说明 |
|---|---|---|
| DeepSeek Harness (dsh) | `~/.dsh/AGENTS.md`（全局）或 `<项目>/AGENTS.md` | `@deepseek-ai/dsh-agent-instructions` 会依次加载工作区中的 `AGENTS.md` / `CLAUDE.md` 以及全局 `~/.dsh/AGENTS.md`；若环境变量 `DSH_HOME` 另有指定，则映射为 `$DSH_HOME/AGENTS.md` |
| omp | `<项目>/AGENTS.md`；或该项目的记忆层（`memory://root/...`，落盘在 `~/.omp/agent/memories/<项目>/`） | omp 的候选指令文件名包含 `AGENTS.md`；`~/.omp/AGENTS.md` 的读取取决于具体版本，全局配置虽无不良影响，但**项目级 `AGENTS.md` 才是确定生效的层级**，建议使用 `--project` 逐个配置 |
| Claude Code | `~/.claude/CLAUDE.md` 或 `<项目>/CLAUDE.md` | 编写规则与 `AGENTS.md` 完全一致 |
| Codex / Cursor / 其他 | `AGENTS.md`、`.cursor/rules` 等 | 依据对应环境支持的规则文件进行配置，内容直接采用前述钩子文本 |

## 验证

安装完成后应进行实际验证，切勿直接假定生效：

```bash
python3 <技能目录>/scripts/install_hook.py --check   # 每层都应为"已装"
```

随后新建会话进行端到端测试，在不提及图库的前提下直接要求"帮我画个 UMAP"，观察模型是否优先调用 `retrieve.py`。若未执行检索，即表明触发钩子未注入上下文，应检查指令文件位置与 harness 的加载机制，或改用 `--project` 部署至项目级。

另一项客观凭据是**复用台账**：`retrieve.py` 每次执行检索均会向 `library/USAGE.jsonl` 追加一条记录，由 `summary.py` 计算命中率及"未命中需求"。若在已有实际绘图行为的情况下台账长期为空，即可断定触发环节未能正常生效。

## 注意

- 触发钩子仅承担**唤起**职责；图表学习、复用机制以及偏好整理的具体规约均以 `SKILL.md` 为准，切勿在此重复冗长的操作规范。
- 钩子中所填写的技能路径必须采用绝对路径（如 `/home/zeiss/.agents/skills/biofigure-self-evolve`），相对路径在不同 harness 的工作目录下极易解析失败。
- 部署钩子后仍须保留 `description` 中的触发词：模型可能将钩子视作背景信息而予以忽略，而技能描述作为结构化入口，二者构成互补关系。
- 同一份"绘图约定"切勿既写入钩子又冗余同步至 harness 记忆层：钩子仅作索引指针（引导读取技能与运行检索），偏好正文应严格保存在 `PREFERENCES.md` 单一源头，以防多处维护造成配置漂移。
