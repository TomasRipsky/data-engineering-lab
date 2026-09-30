# Lab site

One GitHub Pages site for the whole lab: https://tomasripsky.github.io/data-engineering-lab/
(lab ADR 0005). Built with Observable Framework.

## Adding a project section

1. **Pages** go in `src/<project>/` (`index.md` + one page per question). Add the section to
   `observablehq.config.js` and a card to `src/index.md`.
2. **Data** is exported by the project, never queried from the site: a tested project command
   writes files into `src/<project>/data/` (git-ignored) before the build — e.g.
   `pitwall site-export --out site/src/pitwall/data`. Use a read-only identity and export only
   data you are happy to publish.
3. **Shared look, own personality.** Everything structural is shared: `src/components/lab.js`
   (`rows`, `fmt`, palette) and `src/components/lab.css` (cards, big numbers, callouts). Each
   section then has its **own theme** that makes its domain obvious at a glance — a stylesheet in
   `src/<project>/` that imports `observablehq:default.css`, a Framework theme and
   `../components/lab.css`, set on every page with `style:` front matter — plus its own encodings
   and illustrations in `src/<project>/components/` (e.g. pitwall: dark pit-wall look, tyre and
   team colours, car/tyre SVGs). Use our own illustrations, never trademarked logos or photos.
   Design charts with the `dataviz` skill (validated palettes, one axis, legends, tooltips).
4. **Page skeleton** (every page):
   - H1 phrased as the question the page answers;
   - `<div class="tip" label="What am I looking at?">` explaining the page in plain language;
   - the charts;
   - `<div class="note">` with the limitations.
5. **Browser-friendly data**: no 64-bit integers (they arrive as `BigInt`) and no timestamps
   (format dates as strings); show medians for long-tailed durations.

## Build and publish

Today pitwall's pipeline exports its data, builds the site and deploys it (`make site` in
`projects/pitwall`). When a second project needs the site, a lab-level `lab-site` workflow will
collect every project's export and build once (see lab ADR 0005).
