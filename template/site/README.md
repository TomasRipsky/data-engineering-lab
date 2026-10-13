# Site

The project's public showcase: Observable Framework on GitHub Pages
(https://tomasripsky.github.io/template-project/ once Pages is enabled with a workflow build).
It follows the lab's standard (lab ADR 0008): **one long story page and a BI page**.

## The standard

**`src/index.md` — the story**, for a reader who knows neither the domain nor data engineering.
In this order:

1. **Sticky bar**: the brand (back to the top), section anchors, **BI**, GitHub.
2. **Hero**: an original illustration from the domain, the question as H1, two or three plain
   sentences, four live numbers.
3. **The answers**: four to six headline numbers, one sentence each, on tiles drawn from the domain
   (pitwall: pit boards; CityPulse: street signs).
4. **One section per question**: what the reader is looking at → the chart → its limits.
5. **A case file**: one concrete story chosen by a query, not by hand.
6. **The pipeline**, drawn in the domain's language, with what each stage guarantees and the stack.
7. **Decisions** (one box per ADR), **Quality**, **Limits, stated plainly**, **Run it yourself**, footer.

**`src/bi.md` — self-service**: a sticky filter bar, KPIs that follow it, a section per subject
with tables and charts, CSV downloads, an empty state for every block. Where a number cannot follow
a filter, it says so.

## Rules

1. **Data is exported, never queried from the site.** What the site reads is decided in dbt:
   report models (`rpt_*`), one grain each, documented and tested. A project command copies each
   one to a file in `src/data/` (git-ignored) before the build, with a read-only identity. The site
   needs no knowledge of the project's cloud or credentials.
2. **Every number is computed from the exported rows**, in the page. None is typed by hand, and a
   missing value is a dash, never a zero.
3. **Structure and theme are separate.** `src/components/lab.css` and `lab.js` are the skeleton
   shared by every lab project — do not fork them for looks. `src/style.css` sets the `--lab-*`
   variables and adds what is only this project's: personality comes from the domain.
4. **Charts** follow the `dataviz` skill: form first, colour last and validated with its script
   against the page background; colour never carries identity alone; one axis; tooltips. They are
   functions of the panel width, drawn through `resize()`.
5. **Browser-friendly data**: no 64-bit integers (they arrive as `BigInt`), dates as text, rounded
   numbers. Keep a big table as an Arrow table and read the slice you need, instead of turning
   every row into an object up front.
6. **No third-party requests** (self-host fonts; `globalStylesheets: []`), **original
   illustrations** only — never trademarked logos or photos — and animation that respects
   `prefers-reduced-motion`.
7. **Old URLs are public API**: when pages move, leave redirect pages (`head:` front matter with a
   meta refresh) behind.
8. In htl templates leave a space before `/>` after an interpolated attribute (`d=${path} />`).

## Build and publish

```bash
cd site
npm ci --ignore-scripts
npm run dev      # live reload on http://127.0.0.1:3000
npm run build    # into site/dist
```

Publish from a workflow: export the data with an identity that can read it, build in a **separate
job without cloud permissions** (npm packages run there), upload `site/dist` with
`actions/upload-pages-artifact` and deploy with `actions/deploy-pages`. pitwall's
`pitwall-pipeline.yml` is the reference. Then add the project's card to the lab's hub
(`site/index.html` in the lab repository).
