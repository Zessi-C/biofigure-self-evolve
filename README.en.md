[中文](README.md)

# biofigure-self-evolve

A self-evolving bioinformatics figure skill. When you read a paper and like a figure, the agent dissects how it was drawn and stores that as an entry in a local library. When you later need to plot your own data, it checks the library first and imitates what it has learned instead of designing from scratch. The longer you use it, the larger the library grows and the closer it fits your habits.

## What it does

Seeing a good figure in a paper and wanting the same one for your data usually means going back to the original text to guess parameters, writing code from scratch, and tweaking styles over and over. Existing template collections such as [FigureYa](https://github.com/ying-ge/FigureYa) help, but they are maintained by hand, and what they cover never changes with what you read.

This skill hands the job to the agent. It has two parts: a local figure library inside the skill directory, and SKILL.md, which tells the agent how to maintain and use that library. In daily use:

- **Learning**: papers, PDFs, WeChat articles, or screenshots you send the agent get dissected into a record of how the figure is built: which layers it has, what input format it needs, how color and layout are handled. Each record ships with runnable R and Python templates.
- **Reuse**: when you actually need a plot, the agent looks for entries with a similar function and adapts them to your data.
- **Recycling**: if you are happy with the result, the plot becomes a new entry; your feedback on an existing entry goes straight into its template.

That is the "self-evolve" in the name: the library grows with use.

## How to trigger it

No commands to memorize. Talk normally:

- "learn this figure" / "add this figure to the library" when sending material;
- drop a paper or a screenshot, and if the agent spots figures worth learning, it asks before storing anything;
- "draw this like the reference" / "make me a volcano plot" / "a survival curve": the agent checks the library first, imitates a similar entry if there is one, and designs normally otherwise. Once you are satisfied, it asks whether to keep the recipe;
- "what can the library draw": lists the entries learned so far.

In an interactive session the agent confirms with you before learning, and when several candidates match at reuse time. In non-interactive settings such as background jobs and pipelines it does not interrupt: it picks the best candidate, runs, and reports which entry it used and what it assumed.

## How self-evolution works

1. **The library widens**: every learned figure adds an entry. This is the main growth path.
2. **Entries converge**: feedback on the drawing itself (legend to the bottom, labels too cramped, your usual thresholds) goes into that entry's template defaults and recipe. Each change is logged in the entry's evolution section.
3. **Preferences settle across figures**: habits that show up on figure after figure (a palette you always pick, a legend position you always want) get written to `library/PREFERENCES.md`. A habit becomes a stable preference after it is observed twice, and details you never state are then handled the way you evidently like them.

The loops have limits: the agent only records observable signals (your explicit choices, feedback on finished figures, habits you state), and invents none. In every entry, the description of the original figure is fact and never changes; only the recipe and templates evolve, and every change is traceable.

## What happens when a figure is learned

**First, decide what to learn and at what granularity.** The novelty in bioinformatics figures often lies in combinations and paired narratives rather than single panels. The test is one question: if you delete one figure, does the other lose information? If yes, learn them as a group. In an overview UMAP whose cluster numbers index the row of detail panels below it, the two are incomplete apart, so the record states each panel's narrative role. If each figure stands alone but reads stronger side by side (a UMAP column next to a dotplot and a heatmap, say), learn them as a composite layout and record how the panels link: shared row order, shared colors, shared numbering. Fully independent figures are learned separately, with the `related` field pointing between entries of similar function.

**Then, trace the original code. A rendered image is indirect evidence; code is the source of truth.** When the material contains code leads, the agent follows a four-step path: code pasted in the text is used directly as the first-hand recipe; a mentioned GitHub repository gets its file tree listed through the API so the plotting scripts can be pulled; a paper-only lead is resolved by DOI and then searched for in the code availability section of the PMC full text; only when all of that fails does the agent fall back to reading the image, and the record then says so ("code not traced"). This step catches real errors: once, the original plotting script found via PMC showed the Sankey was drawn with `ggsankey`, not the `ggalluvial` it looked like, and the log2 axis with raw-count labels was implemented quite differently from what visual guessing suggested.

**Finally, write the record, write the templates, run them.** Every entry requires R and Python templates, both self-contained with embedded realistic fake data, both producing a figure when run without arguments. `verified: both` is only set after both actually ran; anything unrun stays `unverified`. The entry then goes through an 11-item completion checklist (what question the figure answers, data shape, reproducible layers, specific colors, layout specs, panel linkage, edge cases and pitfalls, `related` registration, runnable templates, traceable original figure, traced code). Anything missing means it is not learned yet.

## Imitation, not copying

On reuse, what gets extracted is the technical skeleton: layer organization, mappings, color logic, layout strategy, linkage design. Axes, thresholds, color values, and group counts are all decided fresh against your current data and purpose. When an entry only partially matches, only that part is borrowed. Records are written at the same level: "qualitative palette plus cluster numbers at density centers", never "eight clusters must use these eight hex codes".

## Install

```bash
git clone https://github.com/Zessi-C/biofigure-self-evolve.git ~/.agents/skills/biofigure-self-evolve
```

Works with any agent that follows the agents/skills convention (a directory with a `SKILL.md` plus name/description frontmatter counts as a skill). Dependencies are light:

- The scripts run on the Python 3 standard library. If PyYAML is installed it is used; otherwise a restricted built-in parser takes over. Both paths are tested.
- Template verification needs R (ggplot2) and/or Python (matplotlib) on the machine. Whichever side is missing, that side's templates stay honestly marked `unverified`.
- The library and the preference profile are plain text files. No vendor API, no MCP, no network service involved.
- Other harnesses work the same way: anything that can read files, fetch pages, and run scripts can drive this skill. Harnesses with their own plugin format only need a thin adapter to wire in SKILL.md; the skill itself stays unchanged.

## Inside the library

```text
library/
├── INDEX.json / INDEX.md     # index, rebuilt in full from all figure.md files by script, never hand-edited
├── PREFERENCES.md            # cross-figure preference profile (personal data, stays out of the public repo)
└── figures/NNN-slug/
    ├── figure.md             # core record: metadata + visual dissection + recipe + reuse notes (+ evolution log)
    ├── reference.png         # the original figure, for personal reference only
    ├── template.R / template.py   # self-contained dual templates, produce a figure with no arguments
    └── template_output_*     # template outputs, kept as known-good baselines
```

`figure.md` is the single source of truth; the index is only its projection. The frontmatter uses a deliberately narrow YAML subset (scalars, single-line lists, one level of nesting) so it parses reliably even without a YAML library. Key fields:

- `chart_types` picks from a controlled vocabulary of nearly 40 bioinformatics chart types (see [references/chart-taxonomy.md](references/chart-taxonomy.md)), so learning and retrieval speak the same language;
- `data_shape` states in one line what input the figure needs, enough to tell at a glance whether your table fits;
- `use_when` / `not_when` drive the semantic matching at reuse time;
- `related` links functionally adjacent entries into groups (a plain KM curve vs a KM curve with a risk table), so retrieval returns candidates with their differences explained instead of a pile of near-identical hits;
- `verified` only reflects actual runs, never wishful marking.

## Scripts

```bash
python3 scripts/init_library.py    # initialize the library skeleton (idempotent; --path to place it elsewhere and write the config)
python3 scripts/build_index.py     # rebuild the index in full, with consistency checks along the way
```

`build_index.py` checks for missing required fields, ids that disagree with directory names, dangling `related` references, and more. Run it once after syncing across devices, and always after hand-editing any `figure.md`.

## Sync and privacy

The whole skill directory, library included, is one git repository: `git push` / `git pull` is your sync. For private sync, point the remote at your own private repository.

Entries you learn stay out of the public repo by default: `.gitignore` excludes `library/figures/*` (one example entry is kept) as well as `INDEX.json`, `INDEX.md`, and `PREFERENCES.md`, which are your personal data. The shipped `figures/000-example-grouped-boxplot` is an original example demonstrating the full format, and doubles as the skeleton to copy for new entries. If you later share learned entries publicly, mind the copyright of the original papers.

## Design tradeoffs

- SKILL.md stays around 230 lines: it is read on every trigger, so it only goes as deep as needed to steer behavior; details live in `references/` (record schema, per-source ingestion, chart vocabulary).
- Numbers are never reused: a new entry takes the current maximum plus one, deleting an entry removes its directory and rebuilds the index, and stale `related` references to it get cleaned up (the script warns about them).
- Multiple candidates list the top three: entries with the same function often match several at once. They are ranked by data shape match, then intent match, then verification status, each with a one-line key difference, rather than dumped as a full list.

## Acknowledgments and license

- Code and docs are released under the MIT license, see [LICENSE](LICENSE).
- The organization (uniform entry structure + reference figure + index) draws on [FigureYa](https://github.com/ying-ge/FigureYa) (iMetaMed 2025); the difference is that maintenance here is delegated to the agent, closing the loop of learning, reuse, and recycling.
