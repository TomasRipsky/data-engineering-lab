# Site

The project's public site: Observable Framework on GitHub Pages
(https://tomasripsky.github.io/template-project/ once Pages is enabled with a workflow build).

## Conventions (shared by every lab project)

1. **Data is exported, never queried from the site.** A tested project command writes files into
   `src/data/` (git-ignored) before the build — e.g. pitwall's `pitwall site-export --out
   site/src/data`. Use a read-only identity and export only data you are happy to publish. The site
   needs no knowledge of the project's cloud or credentials.
2. **Pages** are the Markdown files in `src/`; list them in `observablehq.config.js`.
3. **Shared structure, own personality.** `src/components/lab.css` and `lab.js` (cards, big
   numbers, callouts, `rows`, `fmt`, palette) are the same in every project. On top, the project
   gets its **own theme** that makes its domain obvious at a glance — its stylesheet imports
   `observablehq:default.css`, a Framework theme and `./components/lab.css` — plus its own
   encodings and illustrations in `src/components/` (pitwall: dark pit-wall look, tyre and team
   colours, car SVGs). Use our own illustrations, never trademarked logos or photos. Design charts
   with the `dataviz` skill (validated palettes, one axis, legends, tooltips).
4. **Page skeleton** (every page):
   - H1 phrased as the question the page answers;
   - `<div class="tip" label="What am I looking at?">` explaining the page in plain language;
   - the charts;
   - `<div class="note">` with the limitations.
5. **Browser-friendly data**: no 64-bit integers (they arrive as `BigInt`) and no timestamps
   (format dates as strings); show medians for long-tailed durations.
6. **No third-party requests**: self-host fonts; `globalStylesheets: []` drops Google Fonts.

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
`pitwall-pipeline.yml` is the reference. Register the site in the lab's hub (`site/index.html`
in the lab repository).
