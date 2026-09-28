[中文](README.md)

# biofigure-self-evolve

**Scope**: Two functions only: determining which figure type to plot (selection and recipe reuse) and ensuring proper visual presentation (aesthetics, layout conventions, style consistency, and delivery self-check). Statistical validity, data pipelines, and table or spreadsheet deliverables are strictly out of scope.

The system pairs a **drawing guide** with a self-evolving bioinformatics figure library: it assists in selecting a chart type when none is specified, guides the implementation and visual refinement of specified charts, and generates designs from aesthetic principles when the library contains no match (learning aesthetics from a reference image if provided). A preference profile records cross-project drawing conventions. Every library entry functions as an independent plugin: removing any single entry leaves the skill and remaining entries fully functional. The agent records the construction of published figures as entries in a local library and reuses them when plotting user data; both entries and preferences evolve continuously through use. Entry organization follows [FigureYa](https://github.com/ying-ge/FigureYa) (iMetaMed 2025), delegating ongoing maintenance to the agent rather than requiring manual curation.

## How it works

- **Trigger**: Before producing, editing, replicating, or learning any bioinformatics or statistical figure, run `scripts/retrieve.py` against the library. State in the delivery which entry was reused (or that nothing matched). When delegating figure work to a subagent, pass the skill entry point or the retrieval result into the delegation prompt. If the skill description alone proves insufficient, install the short hook from `references/trigger-hook.md` into the project-level or global agent instructions.
- **Learning**: Provide the agent with a paper, PDF, article, or screenshot. It determines whether to record a single figure, a group, or a composite layout, and traces the original plotting code first (inline code > GitHub repo > paper DOI → PMC code availability); only in the absence of any code lead does it infer structure from the image, explicitly noting this visual inference in the record.
- **Reuse**: When generating a plot, the agent retrieves candidate entries by `use_when` and `data_shape`, adopts their technical skeleton, and calibrates axes, thresholds, and colors against the active dataset. Reuse means adapting the recipe rather than executing or copying the entry's reference implementation. When multiple candidates qualify, the system returns the top three, ranked successively by data shape match, intent match, and verification status.
- **Learn from your own projects**: Prompt the agent with "follow my previous style" or "add this recipe to the library", and it inspects the project's plotting scripts first as the ground truth, followed by the rendered figures. It then records the project's house style (color semantics, dimensions, composition, naming, and layout) as an entry with `source.type=project`.
- **Delivery**: For a family of figures, produce the inventory list first (B0). Prior to delivery, perform the mandatory delivery self-check (B6 + `references/delivery-checklist.md`). Important figures require an independent QA pass: delegate this to a subagent when the harness supports one, or execute `qa_prompt.py --self`. Finally, log the entry actually used (`retrieve.py --record-used`).
- **Optional helpers** (only if the project already keeps manifests): `figure_manifest.py` manages figure inventories and `--diff` incremental re-rendering, while `pair_check.py` verifies figure-to-table provenance. These utilities handle figure-side housekeeping rather than the core functions of this skill.
- **Aesthetics and preferences**: When the library contains no match, or when the user requests a specific aesthetic appearance, learn the **aesthetics** from the reference (color logic, type scale, whitespace, layout strategy) and record them in `PREFERENCES.md` rather than forcing a new entry; cross-project drawing conventions reside there as well and serve as defaults. Scripts and entry templates remain **self-contained**; within-project consistency derives from the preference profile, not from shared code. Optionally, `scripts/mine_feedback.py` (which requires session logs) mines user corrections into preference candidates.
- **Recycling**: A successful figure becomes a new entry. User feedback on an existing entry is incorporated into its template defaults and logged in the entry's evolution section, while recurring habits across multiple figures settle into `library/PREFERENCES.md`.
- **Consolidation**: Cross-figure preferences (`PREFERENCES.md`) and per-entry records (the reuse notes and evolution log of each entry) are periodically reconciled by promoting, merging, demoting, narrowing scope, or retiring entries; every pass leaves a single dated log line. The script `scripts/review_preferences.py` determines when a pass is due and identifies mechanically decidable items, while semantic merging remains delegated to the agent.
- **Summary**: The script `scripts/summary.py` generates a periodic quantitative report covering library size and monthly growth, the reuse ledger (retrievals, hit rate, hottest entries, and **unmatched requests -> what to learn next**), preference counts, and structural warnings. The ledger is updated by `retrieve.py` upon every retrieval and serves as the sole objective record of whether the agent consults the library.
- **Migration**: Entries can be packaged into a bundle (a zip archive with a manifest and per-file checksums) and imported into another device's library; naming collisions can be skipped, overwritten, or renumbered. After importing into a new environment, run `verify_library.py` to re-check the templates.

Completion of a learned entry is evaluated against a checklist. The record format is specified in [references/figure-record.md](references/figure-record.md); trigger behavior is defined in SKILL.md.

## Install

```bash
git clone https://github.com/Zessi-C/biofigure-self-evolve.git ~/.agents/skills/biofigure-self-evolve

# right after cloning: install the always-on trigger hook (as important as the clone)
python3 ~/.agents/skills/biofigure-self-evolve/scripts/install_hook.py
python3 ~/.agents/skills/biofigure-self-evolve/scripts/install_hook.py --check
# harnesses that read a per-project AGENTS.md (e.g. omp):
python3 ~/.agents/skills/biofigure-self-evolve/scripts/install_hook.py --project /path/to/project
```

The skill operates with any agent adhering to the agents/skills convention (a directory containing a SKILL.md with name and description frontmatter). Other harnesses function as long as they can read files, fetch pages, and execute scripts; platforms using custom plugin formats require only a thin adapter. Dependencies:

- Scripts require only the Python 3 standard library (PyYAML is optional, as a restricted built-in parser is provided; `figure_manifest.py` counts PDF pages more reliably when `pdfinfo` is available, falling back to leave the count blank if unknown).
- Entries prioritize recipes; the reference implementations (`template.R` / `template.py`) are optional. Verification requires R (ggplot2), Python (matplotlib), or both; missing environments leave the implementation marked as `unverified` or cause the field to be omitted.
- The skill requires no vendor APIs, MCP servers, or external network services.

## Repository layout

```text
SKILL.md                    # skill entry point: triggering and the learn/reuse/recycle behavior spec
library/
├── INDEX.json / INDEX.md   # index, rebuilt in full from all figure.md files by script, not published
├── PREFERENCES.md          # cross-figure preference profile (personal data, not published)
└── figures/NNN-slug/
    ├── figure.md           # single source of truth: frontmatter + visual dissection + recipe + reuse notes + evolution log
    ├── reference.png       # the original figure (personal reference only)
    ├── template.R / template.py   # optional reference implementations (how it is written, not an API to call)
    └── template_output_*   # template outputs, kept as known-good baselines
references/                 # record schema, per-source ingestion, chart_types controlled vocabulary (~40 types), preference profile format, trigger hook, delivery checklist
scripts/                    # install_hook / init_library / build_index / retrieve / review_preferences / summary / figure_manifest / pair_check / qa_prompt / mine_feedback / export_figure / import_figure / verify_library
```

The frontmatter adheres to a deliberately restricted YAML subset (scalars, single-line lists, and a single nesting level) that parses reliably without an external YAML library. Key fields include: `chart_types` (controlled vocabulary), `data_shape` (input format on a single line), `use_when` / `not_when` (semantic matching during reuse), `related` (links between functionally adjacent entries), and `verified` (confirmed execution runs only).

The paths `library/figures/*`, `INDEX.*`, and `PREFERENCES.md` are ignored by Git, ensuring that learned entries remain excluded from the public repository; the shipped example `000-example-grouped-boxplot` demonstrates the format and serves as the skeleton for new entries. Users must respect the original papers' copyright when sharing learned entries.

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

# Preference candidates
python3 scripts/mine_feedback.py --since 2026-08-01           # mine corrections -> preference candidates

# Cross-device entry migration (typical: learn figures locally while reading papers, reuse on a server)
python3 scripts/export_figure.py 003 --with-related   # pack entries into a bundle (id / numeric prefix / all)
python3 scripts/import_figure.py bundle.zip           # verify integrity then import, rebuilds the index; collisions rejected by default (--force overwrite / --rename renumber)
python3 scripts/verify_library.py                     # health check: trial-run templates in a temp dir, reports only
```

## License

MIT License; see [LICENSE](LICENSE).
