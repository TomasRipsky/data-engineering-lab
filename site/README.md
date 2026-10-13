# Lab site

https://tomasripsky.github.io/data-engineering-lab/ — the portfolio hub: one card per project,
each linking to the project's own site (lab ADR 0007). Plain HTML, no build, no third-party
requests; `.github/workflows/lab-site.yml` uploads this folder to GitHub Pages on every push to
`main` that changes it.

- `index.html` — the hub. A new project gets a card here (its question, two lines, its stack, its
  own colours and an original illustration — never trademarked logos or photos) in the same PR
  that registers it in the root `README.md`.
- `pitwall/*.html` — redirect stubs. pitwall's dashboard lived at `/data-engineering-lab/pitwall/`
  until 2026-10-13; these keep every old link working without JavaScript. Do not delete them.

Preview: open `index.html` in a browser.
