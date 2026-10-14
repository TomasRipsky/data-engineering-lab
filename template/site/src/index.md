---
title: template-project — the question this project answers
toc: false
---

```js
import {fmt, ink, series} from "./components/lab.js";
```

```js
// Replace with the project's exported files, one per dbt report model:
//   const rows_ = rows(await FileAttachment("data/<model>.parquet").parquet());
// Every number on the page is computed here from those rows — never typed by hand.
const sample = [
  {label: "A", value: 12},
  {label: "B", value: 31},
  {label: "C", value: 22}
];
const total = d3.sum(sample, (d) => d.value);
function sampleChart(width) {
  return Plot.plot({
    width,
    height: 240,
    marginBottom: 42,
    style: {background: "transparent", fontSize: "12px"},
    x: {label: null, type: "band", paddingInner: 0.5},
    y: {label: "↑ Value", grid: true},
    marks: [
      Plot.barY(sample, {x: "label", y: "value", fill: series[0], rx: 4, tip: true}),
      Plot.text(sample, {x: "label", y: "value", text: "value", dy: -10, fill: ink.text, fontWeight: 700}),
      Plot.ruleY([0], {stroke: "#6b6b7b"})
    ]
  });
}
```

<header class="top">
  <a class="brand" href="#top" aria-label="template-project, back to the top">template-project</a>
  <nav aria-label="Sections">
    <a href="#answer">The answers</a>
    <a href="#analysis">Analysis</a>
    <a href="#case">Case file</a>
    <a href="#pipeline">Pipeline</a>
    <a href="#quality">Quality</a>
    <a class="bi-link" href="./bi">BI</a>
    <a class="gh" href="https://github.com/TomasRipsky/template-project">GitHub ↗</a>
  </nav>
</header>

<section class="hero" id="top">
  <div class="hero-copy">
    <p class="eyebrow">Domain · what kind of project · the data's range</p>
    <h1>The question, with the <em>key words</em> in the accent colour?</h1>
    <p class="lede">Two or three sentences for a reader who knows neither the domain nor data engineering: what the project looks at, and what it turns it into.</p>
    <div class="stats" aria-live="polite">
      <div class="stat"><b>${fmt.count(total)}</b><span>a number that shows the scale</span></div>
      <div class="stat"><b>${sample.length}</b><span>another one</span></div>
      <div class="stat"><b>—</b><span>a third</span></div>
      <div class="stat"><b>—</b><span>how fresh the data is</span></div>
    </div>
  </div>
  <!-- the hero illustration: original, from the domain, animated only if it respects reduced motion -->
</section>

<section id="answer" class="band">
<div class="wrap">
  <h2><span class="num">1</span>The answers</h2>
  <p class="sub">The four to six things the data says, each as one number and one sentence, on tiles drawn from the domain. Each is explained further down.</p>
  <div class="answers">
    <div class="answer"><b>${fmt.percent(sample[1].value / total)}</b><p>One sentence that says what the number means, in plain words.</p></div>
    <div class="answer"><b>${fmt.count(sample[0].value)}</b><p>Another answer.</p></div>
  </div>
</div>
</section>

<section id="analysis" class="wrap">
  <h2><span class="num">2</span>One section per question</h2>
  <p class="sub">Before every chart: what the reader is looking at, in plain language, with each term of the domain explained where it first appears.</p>
  <div class="panel">
    <h3>The chart's title <small>what is measured, in which unit</small></h3>
    ${resize((width) => sampleChart(width))}
  </div>
  <p class="footnote">After every chart: its limits — what is left out, how small the sample is, what a careful reader should doubt.</p>
</section>

<section id="case" class="band">
<div class="wrap">
  <h2><span class="num">3</span>Case file</h2>
  <p class="sub">One concrete story told with the data — chosen by a query, not by hand, so it changes when the data does. Picking it is also the best test of the data: an odd case is usually a bug.</p>
  <div class="case">
    <div><span class="big">The headline</span><ol><li>What happened, step by step, computed from the rows.</li></ol><p class="verdict">What the reader should take from it.</p></div>
    <div class="panel"><h3>The chart of that case</h3><p class="empty">A chart goes here.</p></div>
  </div>
</div>
</section>

<section id="pipeline" class="wrap">
  <h2><span class="num">4</span>The pipeline</h2>
  <p class="sub">The pipeline drawn in the domain's own language (a subway map, a lap of a circuit), stage by stage, with what each stage guarantees.</p>
  <div class="grid2">
    <div class="box"><h3>What each stage guarantees</h3><ul class="check yes"><li><b>Stage</b> — its guarantee.</li></ul></div>
    <div class="box"><h3>Built with</h3><table class="stack"><tr><td>Layer</td><td>Technology</td></tr><tr><td>Cost</td><td>What it costs per month, and the guard rails</td></tr></table></div>
  </div>
</section>

<section id="decisions" class="band">
<div class="wrap">
  <h2><span class="num">5</span>Decisions worth explaining</h2>
  <div class="grid3">
    <div class="box"><p class="adr"><a href="https://github.com/TomasRipsky/template-project/tree/main/docs/decisions">ADR 0001</a></p><h3>The decision</h3><p>Why, in two sentences, and what lost.</p></div>
  </div>
</div>
</section>

<section id="quality" class="wrap">
  <h2><span class="num">6</span>Quality</h2>
  <div class="grid2">
    <div class="box"><h3>What is checked</h3><ul class="check yes"><li><b>Tests</b> — what they pin.</li></ul></div>
    <div class="box"><h3>What the source gets wrong, and what we do</h3><ul class="check no"><li><b>A known defect</b> — how it is handled.</li></ul></div>
  </div>
</section>

<section id="limits" class="band">
<div class="wrap">
  <h2><span class="num">7</span>Limits, stated plainly</h2>
  <ul class="limits"><li><b>A limit.</b> What the project does not claim.</li></ul>
</div>
</section>

<section class="wrap run" id="run">
  <h2><span class="num">8</span>Run it yourself</h2>
<pre><span class="c"># the shortest path that works without a cloud account</span>
git clone https://github.com/TomasRipsky/template-project.git && cd template-project
make setup && make test</pre>
  <p><a class="btn" href="https://github.com/TomasRipsky/template-project">Source on GitHub</a><a class="btn ghost" href="./bi">Explore the data (BI)</a><a class="btn ghost" href="https://tomasripsky.github.io/data-engineering-lab/">More projects</a></p>
</section>

<footer class="foot">
  <div class="wrap">
    <span>template-project by Tomas Ripsky · part of the <a href="https://tomasripsky.github.io/data-engineering-lab/">Data Engineering Lab</a></span>
    <span>Data source and any disclaimer it requires.</span>
  </div>
</footer>
