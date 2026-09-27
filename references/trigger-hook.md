# 触发钩子：让 agent 每次都想起查图库

## 为什么需要这一层

技能自带的 `description` 只在"技能列表被注入上下文"时起作用，而现实中它经常不够：

- **列表很长**：omp 一类 harness 会把几十上百个技能一起列出来，画图类的还有若干条（MiloR 四面板、富集气泡图、投影 UMAP……）。模型在这一堆里挑错人很正常。
- **子代理看不到技能列表**：把画图任务委派给子代理（omp 的 `task`、dsh 的 `subagent`）时，子代理往往只拿到一段任务文本。最典型的失手就是"父代理查了图库、子代理没查"——画出来的图把父代理刚确认过的偏好全丢了。
- **描述可能被截断**：部分 harness 只展示描述的前若干字符。

所以除了把触发条件写进 `description` 开头，还要在**每一轮都能看到的常驻层**放一条短钩子。这是用户抱怨"agent 老是不查图库"时最有效的一步。

## 一条命令装上（推荐）

装技能时就把钩子装上，别留给"以后再说"：

```bash
python3 <技能目录>/scripts/install_hook.py            # 自动装到检测到的 harness 全局指令层
python3 <技能目录>/scripts/install_hook.py --check     # 验证（全部就绪 → 退出码 0）
python3 <技能目录>/scripts/install_hook.py --project /path/to/项目   # omp 等按项目读 AGENTS.md
python3 <技能目录>/scripts/install_hook.py --uninstall --project /path/to/项目
```

脚本行为：

- 自动检测：`$DSH_HOME/AGENTS.md`（或 `~/.dsh/AGENTS.md`）、`~/.claude/CLAUDE.md`、`~/.omp/AGENTS.md`——存在哪层就装哪层
- 写入方式：一个 5 行的块，用成对 HTML 注释 `<!-- biofigure-self-evolve:trigger-hook:begin/end -->` 包住；**重复运行只替换这个块**（幂等），文件里原有的内容一行不动
- `--dry-run` 只打印将要写入的内容；`--check` 逐层报告"已装/未装/无此文件"
- 块里写的是技能目录的**绝对路径**，技能搬家后重跑一次即可刷新

## 钩子文本（手工装时复制）

```markdown
## 生信绘图（biofigure-self-evolve）
任何生信/统计图的产出、修改、复刻、学习，以及把这类任务委派给子代理之前，先读
`skill://biofigure-self-evolve`（omp；其他 harness 用 <技能目录>/SKILL.md），并跑
`python3 <技能目录>/scripts/retrieve.py "<需求>"` 检索图库；交付说明必须写明
"复用了 NNN-slug 的 XX"或"图库未命中"。委派时把技能入口或检索结果写进委派提示。
```

只要一行、塞进记忆层时用这个最小版：

```text
画任何生信图之前：先读 skill://biofigure-self-evolve 并跑 retrieve.py 检索图库，交付时说明复用了哪条。
```

## 装到哪里

| Harness | 常驻层位置 | 说明 |
|---|---|---|
| DeepSeek Harness (dsh) | `~/.dsh/AGENTS.md`（全局）或 `<项目>/AGENTS.md` | `@deepseek-ai/dsh-agent-instructions` 会加载工作区的 `AGENTS.md` / `CLAUDE.md`，以及 `~/.dsh/AGENTS.md`；`DSH_HOME` 不同则换成 `$DSH_HOME/AGENTS.md` |
| omp | `<项目>/AGENTS.md`；或该项目的记忆层（`memory://root/...`，落盘在 `~/.omp/agent/memories/<项目>/`） | omp 的候选指令文件名里有 `AGENTS.md`；`~/.omp/AGENTS.md` 是否被读取决于版本，装了不亏，但**项目级 `AGENTS.md` 是确定生效的那层**，用 `--project` 逐个装 |
| Claude Code | `~/.claude/CLAUDE.md` 或 `<项目>/CLAUDE.md` | 与 `AGENTS.md` 同一套写法 |
| Codex / Cursor / 其他 | `AGENTS.md`、`.cursor/rules` 等 | 认哪个文件就用哪个，内容照抄钩子文本 |

## 验证

装完做一次验证，别假设它生效了：

```bash
python3 <技能目录>/scripts/install_hook.py --check   # 每层都应为"已装"
```

然后新开一个会话，直接说"帮我画个 UMAP"（不提图库），看它有没有先跑 `retrieve.py`。没跑就说明钩子没进上下文：检查文件位置与 harness 的加载规则，或者改用 `--project` 装到项目级。

另一条客观证据是**复用台账**：`retrieve.py` 每次检索都会往 `library/USAGE.jsonl` 追加一行，`summary.py` 会算出命中率与"未命中需求"。台账长期为空而你明明画过图，就说明触发环节没生效。

## 注意

- 钩子只负责**唤起**；具体怎么学、怎么复用、怎么整理偏好，仍然以 `SKILL.md` 为准，不要在这里重复长篇规范。
- 钩子里给出的技能路径必须是绝对路径（如 `/home/zeiss/.agents/skills/biofigure-self-evolve`），相对路径在不同 harness 的工作目录下会解析失败。
- 装了钩子之后仍要保留 `description` 的触发词：钩子可能被模型当作背景信息忽略，而技能描述是结构化入口，两者互补。
- 同一份"绘图约定"不要既写在钩子里又抄进 harness 记忆层：钩子只留指针（去读技能、去跑检索），偏好正文只存 `PREFERENCES.md` 一处，否则早晚漂移。
