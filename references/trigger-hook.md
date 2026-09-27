# 触发钩子：让 agent 每次都想起查图库

## 为什么需要这一层

技能自带的 `description` 只在"技能列表被注入上下文"时起作用，而现实中它经常不够：

- **列表很长**：omp 一类 harness 会把几十上百个技能一起列出来，画图类的还有若干条（MiloR 四面板、富集气泡图、投影 UMAP……）。模型在这一堆里挑错人很正常。
- **子代理看不到技能列表**：把画图任务委派给子代理（omp 的 `task`、dsh 的 `subagent`）时，子代理往往只拿到一段任务文本。实测里最典型的失手就是"父代理查了图库、子代理没查"——画出来的图把父代理刚确认过的偏好全丢了。
- **描述可能被截断**：部分 harness 只展示描述的前若干字符。

所以除了把触发条件写进 `description` 开头，还应该在**每一轮都能看到的常驻层**放一条短钩子。这是用户抱怨"agent 老是不查图库"时最有效的一步。

## 钩子文本（直接复制）

按 harness 的入口形式替换 `<技能目录>` 与 `skill://` 写法。**保持短**——它会在每一轮占用上下文。

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
| DeepSeek Harness (dsh) | `~/.dsh/AGENTS.md`（全局）或 `<项目>/AGENTS.md` | `@deepseek-ai/dsh-agent-instructions` 会加载工作区的 `AGENTS.md` / `CLAUDE.md`，以及 `~/.dsh/AGENTS.md` |
| omp | `<项目>/AGENTS.md`；或该项目的记忆层（`memory://root/...`，落盘在 `~/.omp/agent/memories/<项目>/`） | 项目根 `AGENTS.md` 对所有会话生效；记忆层适合"只在某个项目里画图"的情况 |
| Claude Code | `CLAUDE.md` 或 `~/.claude/CLAUDE.md` | 与 `AGENTS.md` 同一套写法 |
| Codex / Cursor / 其他 | `AGENTS.md`、`.cursor/rules` 等 | 认哪个文件就用哪个，内容照抄 |

装完做一次验证，别假设它生效了：

```bash
grep -c "biofigure-self-evolve" ~/.dsh/AGENTS.md <项目>/AGENTS.md   # 至少一处应为 1
```

然后新开一个会话，直接说"帮我画个 UMAP"（不提图库），看它有没有先跑 `retrieve.py`。没跑就说明钩子没进上下文，检查文件位置与 harness 的加载规则。

## 注意

- 钩子只负责**唤起**；具体怎么学、怎么复用、怎么整理偏好，仍然以 `SKILL.md` 为准，不要在这里重复长篇规范。
- 钩子里给出的 `<技能目录>` 要用绝对路径（如 `~/.agents/skills/biofigure-self-evolve`），相对路径在不同 harness 的工作目录下会解析失败。
- 装了钩子之后仍要保留 `description` 的触发词：钩子可能被模型当作背景信息忽略，而技能描述是结构化入口，两者互补。
