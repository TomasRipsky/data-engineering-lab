---
title: BI — template-project
toc: false
---

```js
import {downloadButton, emptyState, fmt} from "./components/lab.js";
```

```js
// Replace with the exported report models. Small tables (thousands of rows) filter fine in memory;
// for large Parquet files register them under `sql:` in the front matter and query them with
// DuckDB-WASM, as CityPulse does.
const data = [
  {group: "A", kind: "x", value: 12},
  {group: "A", kind: "y", value: 9},
  {group: "B", kind: "x", value: 31}
];
const all = "All";
const groupInput = Inputs.select([all, ...new Set(data.map((d) => d.group))], {label: "Group"});
const kindInput = Inputs.radio([all, ...new Set(data.map((d) => d.kind))], {label: "Kind", value: all});
const group = Generators.input(groupInput);
const kind = Generators.input(kindInput);
```

```js
// Every block below reads the filtered rows. Where a number cannot follow a filter, say so next to it.
const filtered = data.filter((d) => (group === all || d.group === group) && (kind === all || d.kind === kind));
const table = Inputs.table(filtered, {select: false});
```

<header class="top" id="top">
  <a class="brand" href="./" aria-label="template-project, the story">template-project <span class="badge">BI</span></a>
  <nav aria-label="Sections">
    <a href="#table">Table</a>
    <a class="bi-link" href="./">The story</a>
    <a class="gh" href="https://github.com/TomasRipsky/template-project">GitHub ↗</a>
  </nav>
</header>

<div class="filters">${groupInput}${kindInput}</div>

<section class="wrap bi-head">
  <p class="eyebrow">Self-service · the domain</p>
  <h1>Slice it your way — <em>${group === all ? "everything" : group}</em></h1>
  <p class="sub">What the filters do, and that every number below follows them.</p>
  <div class="kpis">
    <div class="kpi"><span>Rows</span><b>${fmt.count(filtered.length)}</b><small>what the number counts</small></div>
    <div class="kpi"><span>Total</span><b>${fmt.count(d3.sum(filtered, (d) => d.value))}</b><small>its unit</small></div>
  </div>
</section>

<section id="table" class="band">
<div class="wrap">
  <h2>A section per subject</h2>
  <p class="sub">Each with a sentence on how to read it, a chart or a table, and a CSV download.</p>
  <div class="panel">
    <div class="table-head"><h3>${fmt.count(filtered.length)} rows</h3>${downloadButton(filtered, "template-project.csv")}</div>
    ${filtered.length ? table : emptyState("rows")}
  </div>
</div>
</section>

<footer class="foot">
  <div class="wrap"><span>template-project by Tomas Ripsky · <a href="./">the story</a> · part of the <a href="https://tomasripsky.github.io/data-engineering-lab/">Data Engineering Lab</a></span></div>
</footer>
