[中文](README.md)

# biofigure-self-evolve

A self-evolving library and reuse engine for bioinformatics figures. The agent stores how figures in papers are drawn as entries in a local library, and reuses them when you plot your own data; entries and preferences keep updating with use. Entry organization follows [FigureYa](https://github.com/ying-ge/FigureYa) (iMetaMed 2025), with maintenance delegated to the agent instead of manual curation.

## How it works

- **Learning**: send the agent a paper, PDF, article, or screenshot. It decides whether to record a single figure, a group, or a composite layout, and traces the original plotting code first (inline code > GitHub repo > paper DOI → PMC code availability); only without any code lead does it infer from the image, and the record says so.
- **Reuse**: when you need a plot, it retrieves entries by `use_when` / `data_shape`, borrows the technical skeleton, and decides axes, thresholds, and colors against your current data. With several candidates it returns the top three, ranked by data shape match, then intent match, then verification status.
- **Recycling**: a satisfying result becomes a new entry; feedback on an existing entry goes into its template defaults and is logged in the entry's evolution section; habits that recur across figures settle into `library/PREFERENCES.md`.

Completion of a learned entry is judged by a checklist. The record format is in [references/figure-record.md](references/figure-record.md); trigger behavior is in SKILL.md.

## Install

```bash
git clone https://github.com/Zessi-C/biofigure-self-evolve.git ~/.agents/skills/biofigure-self-evolve
```

Works with any agent that follows the agents/skills convention (a directory containing a SKILL.md with name/description frontmatter). Other harnesses work as long as they can read files, fetch pages, and run scripts; those with their own plugin format only need a thin adapter. Dependencies:

- Scripts need only the Python 3 standard library (PyYAML optional; a restricted built-in parser otherwise).
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
references/                 # record schema, per-source ingestion, chart_types controlled vocabulary (~40 types), preference profile format
scripts/                    # init_library.py / build_index.py
```

The frontmatter is a deliberately narrow YAML subset (scalars, single-line lists, one nesting level) that parses reliably without a YAML library. Key fields: `chart_types` (controlled vocabulary), `data_shape` (input format in one line), `use_when` / `not_when` (semantic matching at reuse), `related` (links between functionally adjacent entries), `verified` (actual runs only).

`library/figures/*`, `INDEX.*`, and `PREFERENCES.md` are gitignored, so learned entries stay out of the public repo; the shipped `000-example-grouped-boxplot` demonstrates the format and serves as the skeleton for new entries. Mind the original papers' copyright if you share learned entries.

## Scripts

```bash
python3 scripts/init_library.py    # initialize the library skeleton (idempotent; --path to place it elsewhere and write the config)
python3 scripts/build_index.py     # rebuild the index in full with consistency checks; rerun after editing any figure.md
```

## License

MIT, see [LICENSE](LICENSE).
