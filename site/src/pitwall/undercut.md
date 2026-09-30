---
title: The undercut
style: pitwall.css
---

```js
import "./components/fonts.js";
import {rows, fmt} from "../components/lab.js";
const attempts = rows(await FileAttachment("data/undercuts.parquet").parquet())
  .filter((d) => d.is_success !== null)
  .map((d) => ({...d, success: d.is_success ? 1 : 0}));
const red = "#e10600";
```

# Does pitting first work?

<div class="tip" label="What am I looking at?">

The **undercut**: a driver stuck right behind a rival pits first. Fresh tyres are faster, so by the time the rival pits too, the driver may come out in front. We count an attempt when the car directly ahead pits within the next 3 laps, and a **success** when the attacker is ahead once both have stopped.

</div>

```js
const greenOnly = view(Inputs.toggle({label: "Only stops under green flag", value: true}));
```

```js
const shown = attempts.filter((d) => !greenOnly || !d.attacker_pitted_under_neutralisation);
const rate = d3.mean(shown, (d) => d.success);
const bySeason = d3
  .rollups(shown, (v) => ({rate: d3.mean(v, (d) => d.success), n: v.length}), (d) => d.season)
  .map(([season, s]) => ({season: String(season), ...s}))
  .sort((a, b) => a.season.localeCompare(b.season));
const byTeam = d3
  .rollups(shown, (v) => ({rate: d3.mean(v, (d) => d.success), n: v.length}), (d) => d.attacker_team)
  .map(([team, s]) => ({team, ...s}))
  .filter((d) => d.n >= 8);
```

```js
const best = d3.greatest(byTeam, (d) => d.rate);
```

<div class="grid grid-cols-3">
  <div class="card"><h2>It worked</h2><span class="huge">${fmt.percent(rate)}</span></div>
  <div class="card"><h2>Attempts</h2><span class="big">${fmt.count(shown.length)}</span></div>
  <div class="card"><h2>Best team at it</h2><span class="big">${best ? `${best.team} · ${fmt.percent(best.rate)}` : "—"}</span></div>
</div>

<div class="card">

```js
display(Plot.plot({
  title: "Success rate by season",
  width,
  height: 240,
  style: {background: "transparent", fontSize: "12px"},
  y: {label: "↑ Worked (%)", percent: true, domain: [0, 100], grid: true},
  x: {label: null, type: "band", paddingInner: 0.6},
  marks: [
    Plot.barY(bySeason, {x: "season", y: "rate", fill: red, rx: 4, channels: {Attempts: "n"}, tip: true}),
    Plot.text(bySeason, {x: "season", y: "rate", text: (d) => fmt.percent(d.rate), dy: -10, fill: "#f0f0f0", fontWeight: 700}),
    Plot.ruleY([0], {stroke: "#6b6b7b"})
  ]
}));
```

</div>

<div class="card">

```js
display(Plot.plot({
  title: "Success rate by team (8 or more attempts)",
  width,
  height: 26 * byTeam.length + 50,
  marginLeft: 130,
  style: {background: "transparent", fontSize: "12px"},
  x: {label: "Worked (%) →", percent: true, domain: [0, 100], grid: true},
  y: {label: null, paddingInner: 0.25},
  marks: [
    Plot.barX(byTeam, {y: "team", x: "rate", sort: {y: "-x"}, fill: red, rx: 4, channels: {Attempts: "n"}, tip: true}),
    Plot.text(byTeam, {y: "team", x: "rate", text: (d) => `${fmt.percent(d.rate)} · ${d.n}`, dx: 8, textAnchor: "start", fill: "#a3a3b3"}),
    Plot.ruleX([0], {stroke: "#6b6b7b"})
  ]
}));
```

</div>

```js
display(Inputs.table(
  shown.map((d) => ({
    Season: String(d.season),
    Race: `${d.meeting_name} · ${d.session_name}`,
    Attacker: `${d.attacker} (${d.attacker_team})`,
    Defender: `${d.defender} (${d.defender_team})`,
    "Pitted on lap": d.attacker_pit_lap,
    "Rival pitted on lap": d.defender_pit_lap,
    Worked: d.is_success ? "✔ yes" : "✘ no"
  })),
  {select: false, rows: 12}
));
```

<div class="note">

**Limitations.** Only positions are used, not the time gaps between cars, and the rival may have had reasons of their own to pit. Stops during a red flag (free tyre changes) are excluded; stops under a Safety Car are hidden by the toggle above.

</div>
