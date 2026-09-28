[中文](README.md)

# biofigure-self-evolve

**Scope**: two things only — which figure type to draw (selection + recipe reuse), and how to make the figure look right (aesthetics, layout conventions, style consistency, visual check before delivery). Statistical validity, data pipelines, and table/spreadsheet deliverables are out of scope.

A self-evolving library and reuse engine for bioinformatics figures. The agent stores how figures in papers are drawn as entries in a local library, and reuses them when you plot your own data; entries and preferences keep updating with use. Entry organization follows [FigureYa](https://github.com/ying-ge/FigureYa) (iMetaMed 2025), with maintenance delegated to the agent instead of manual curation.

## How it works

- **Trigger**: before producing, editing, replicating, or learning any bioinformatics/statistics figure, run `scripts/retrieve.py` against the library; state in the delivery which entry was reused (or that nothing matched); when delegating figure work to a subagent, pass the skill entry point or the retrieval result into the delegation prompt. When the skill description alone is not enough, install the short hook from `references/trigger-hook.md` into the project-level or global agent instructions.
- **Learning**: send the agent a paper, PDF, article, or screenshot. It decides whether to record a single figure, a group, or a composite layout, and traces the original plotting code first (inline code > GitHub repo > paper DOI → PMC code availability); only without any code lead does it infer from the image, and the record says so.
- **Reuse**: when you need a plot, it retrieves entries by `use_when` / `data_shape`, borrows the technical skeleton, and decides axes, thresholds, and colors against your current data. With several candidates it returns the top three, ranked by data shape match, then intent match, then verification status.
- **Learn from your own projects**: say "follow my previous style / add this recipe to the library" and the agent reads your project's plotting scripts first (the source of truth), then the rendered figures, and records your house style (color semantics, sizes, composition, naming, layout) as an entry with `source.type=project`.
- **Delivery**: for a family of figures, produce the list first (B0); before handing anything over, run the mandatory visual self-check (B5 + `references/delivery-checklist.md`); important figures get an independent QA pass — hand it to a subagent when the harness supports one, otherwise use `qa_prompt.py --self`; log the entry actually used (`retrieve.py --record-used`).
- **Optional helpers** (only if the project already keeps manifests): `figure_manifest.py` for figure inventory and `--diff` incremental re-rendering, `pair_check.py` for figure-to-table provenance. Figure-side housekeeping, not the core of this skill.
- **House style made enforceable**: `scripts/style_tokens.py` audits the project's plotting scripts (duplicated palettes, same name/different colors, theme/size spread) and `--emit` produces a shared theme file **inside that project**; the skill itself stores no concrete colors — style is described by slots (main/group/diverging/sequential palette, font scale, sizes, export spec). `scripts/mine_feedback.py` (optional; needs session logs) mines user corrections into preference candidates.
- **Recycling**: a satisfying result becomes a new entry; feedback on an existing entry goes into its template defaults and is logged in the entry's evolution section; habits that recur across figures settle into `library/PREFERENCES.md`.
- **Consolidation**: cross-figure preferences (`PREFERENCES.md`) and per-entry ones (each entry's reuse notes and evolution log) are periodically reconciled — promoted, merged, demoted, scoped down, or retired — and every pass leaves one dated line behind. `scripts/review_preferences.py` decides when a pass is due and lists the mechanically decidable items; the semantic merge stays with the agent.
- **Summary**: `scripts/summary.py` produces a periodic quantitative report — library size and monthly growth, reuse ledger (retrievals, hit rate, hottest entries, **unmatched requests -> what to learn next**), preference counts, structural warnings. The ledger is appended by `retrieve.py` on every retrieval and is the only objective evidence of whether the agent actually consults the library.
- **Migration**: entries can be packed into a bundle (zip with manifest and per-file checksums) and imported into another device's library; collisions can be skipped, overwritten, or renumbered. After importing into a new environment, run `verify_library.py` to re-check the templates.

Completion of a learned entry is judged by a checklist. The record format is in [references/figure-record.md](references/figure-record.md); trigger behavior is in SKILL.md.

## Install

```bash
git clone https://github.com/Zessi-C/biofigure-self-evolve.git ~/.agents/skills/biofigure-self-evolve

# right after cloning: install the always-on trigger hook (as important as the clone)
python3 ~/.agents/skills/biofigure-self-evolve/scripts/install_hook.py
python3 ~/.agents/skills/biofigure-self-evolve/scripts/install_hook.py --check
# harnesses that read a per-project AGENTS.md (e.g. omp):
python3 ~/.agents/skills/biofigure-self-evolve/scripts/install_hook.py --project /path/to/project
```

Works with any agent that follows the agents/skills convention (a directory containing a SKILL.md with name/description frontmatter). Other harnesses work as long as they can read files, fetch pages, and run scripts; those with their own plugin format only need a thin adapter. Dependencies:

- Scripts need only the Python 3 standard library (PyYAML optional; a restricted built-in parser otherwise; `figure_manifest.py` counts PDF pages more reliably when `pdfinfo` is available, otherwise falls back and leaves the count blank if unknown).
- Template verification needs R (ggplot2) and/or Python (matplotlib); whichever side is missing stays `unverified`.
- No vendor API, MCP, or network service involved.

## Repository layout

```text
SKILL.md                    # skill entry point: triggering and the learn/reuse/recycle behavior spec
library/
├── INDEX.json / INDEX.md   # index, rebuilt in full from all figure.md files by script, not published
├── PREFERENCES.md          # cross-figure preference profile (personal data, not published)
└── figures/NNN-slug/
    ├── figure.md           # single source of truth: frontmatter + visual dissection + recipe + reuse notes + evolution log
    ├── reference.png       # the original figure (personal reference only)
    ├── template.R / template.py   # self-contained dual templates, produce a figure with no arguments
    └── template_output_*   # template outputs, kept as known-good baselines
references/                 # record schema, per-source ingestion, chart_types controlled vocabulary (~40 types), preference profile format, trigger hook, delivery checklist
scripts/                    # install_hook / init_library / build_index / retrieve / review_preferences / summary / figure_manifest / pair_check / qa_prompt / style_tokens / mine_feedback / export_figure / import_figure / verify_library
```

The frontmatter is a deliberately narrow YAML subset (scalars, single-line lists, one nesting level) that parses reliably without a YAML library. Key fields: `chart_types` (controlled vocabulary), `data_shape` (input format in one line), `use_when` / `not_when` (semantic matching at reuse), `related` (links between functionally adjacent entries), `verified` (actual runs only).

`library/figures/*`, `INDEX.*`, and `PREFERENCES.md` are gitignored, so learned entries stay out of the public repo; the shipped `000-example-grouped-boxplot` demonstrates the format and serves as the skeleton for new entries. Mind the original papers' copyright if you share learned entries.

## Scripts

```bash
python3 scripts/init_library.py    # initialize the library skeleton (idempotent; --path to place it elsewhere and write the config)
python3 scripts/build_index.py     # rebuild the index in full with consistency checks; rerun after editing any figure.md
python3 scripts/build_index.py --check      # only compare the index against the records (exit 1 on drift), writes nothing

# Install the trigger hook (run once after installing the skill)
python3 scripts/install_hook.py                      # writes into detected harness-global instruction files (idempotent; --check/--uninstall/--dry-run)
python3 scripts/install_hook.py --project /path/to/project   # per-project AGENTS.md, e.g. for omp

# Retrieval before reuse, preference consolidation, periodic summary
python3 scripts/retrieve.py "two-group volcano plot with pathway labels"   # top-K candidates + preference digest (--all browse / --json for subagents; logs usage)
python3 scripts/review_preferences.py --check        # is a consolidation pass due? (exit 1 = yes)
python3 scripts/review_preferences.py                # consolidation report: merge/promote/demote/cross-entry/stale
python3 scripts/review_preferences.py --digest       # compact digest to paste into harness memory
python3 scripts/summary.py --check                   # is a quantitative summary due? (exit 1 = yes)
python3 scripts/summary.py --write                   # print the report and save library/SUMMARY.md

# Figure manifest (for figure families)
python3 scripts/figure_manifest.py figure/8.xxx --write      # create/refresh figure_manifest.csv (semantic columns preserved)
python3 scripts/figure_manifest.py figure/8.xxx --check      # unregistered files / superseded figures -> exit 1
python3 scripts/figure_manifest.py figure/8.xxx --diff old.csv --only unchanged   # skip re-rendering unchanged figures
python3 scripts/pair_check.py figure/8.xxx --tables table/8.xxx   # figure-to-table provenance check
python3 scripts/qa_prompt.py figure/8.xxx --task "final figures" --out /tmp/qa.md   # build the QA subagent prompt

# Project house style and preference candidates
python3 scripts/style_tokens.py code/                        # style audit (duplicated palettes / themes / sizes)
python3 scripts/style_tokens.py code/ --emit code/00.figure_theme.R   # emit a shared theme file
python3 scripts/mine_feedback.py --since 2026-08-01           # mine corrections -> preference candidates

# Cross-device entry migration (typical: learn figures locally while reading papers, reuse on a server)
python3 scripts/export_figure.py 003 --with-related   # pack entries into a bundle (id / numeric prefix / all)
python3 scripts/import_figure.py bundle.zip           # verify integrity then import, rebuilds the index; collisions rejected by default (--force overwrite / --rename renumber)
python3 scripts/verify_library.py                     # health check: trial-run templates in a temp dir, reports only
```

## License

MIT, see [LICENSE](LICENSE).
