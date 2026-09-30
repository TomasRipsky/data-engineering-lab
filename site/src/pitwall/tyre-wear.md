---
title: Tyre wear
style: pitwall.css
---

```js
import "./components/fonts.js";
import {rows} from "../components/lab.js";
import {compoundColor, tyre, tyreLegend} from "./components/f1.js";
const wear = rows(await FileAttachment("data/tyre_wear.parquet").parquet());
const stints = rows(await FileAttachment("data/stints.parquet").parquet());
const dry = ["SOFT", "MEDIUM", "HARD"];
const FUEL_S_PER_LAP = 0.055; // same assumption as the export (pitwall.site_data)
```

# How quickly does each tyre get slower?

<div class="tip" label="What am I looking at?">

As a tyre wears out, each lap gets slower. For every clean lap (no pit stop, no Safety Car) we compare its time with the average of that driver's stint, then take the median across all drivers and seasons at the circuit. A line that climbs steeply means that tyre loses grip quickly there.

But cars also get lighter as fuel burns — about **${FUEL_S_PER_LAP} s faster every lap** — which hides the wear. Switch the correction off to see how much: on many circuits the raw lines even point *down*.

</div>

```js
const circuits = d3.sort(new Set(wear.map((d) => d.circuit_short_name)));
const circuit = view(Inputs.select(circuits, {label: "Circuit", value: circuits.includes("Sakhir") ? "Sakhir" : circuits[0]}));
const corrected = view(Inputs.toggle({label: "Correct for fuel burn", value: true}));
```

```js
const y = corrected ? "median_delta_fuel_corrected_s" : "median_delta_s";
const circuitWear = d3.sort(
  wear.filter((d) => d.circuit_short_name === circuit && dry.includes(d.compound)),
  (d) => d.tyre_age_laps
);
```

<div class="card">

${tyreLegend(dry)}

```js
display(
  Plot.plot({
    title: `${circuit}: seconds slower than the stint average, by tyre age${corrected ? " (fuel-corrected)" : ""}`,
    width,
    height: 400,
    style: {background: "transparent", fontSize: "12px"},
    marginBottom: 42,
    x: {label: "Tyre age (laps) →", labelAnchor: "center", labelOffset: 36, grid: true},
    y: {label: "↑ Slower (s)", grid: true, tickFormat: "+.1f"},
    color: compoundColor,
    marks: [
      Plot.ruleY([0], {stroke: "#6b6b7b"}),
      Plot.line(circuitWear, {x: "tyre_age_laps", y, stroke: "compound", strokeWidth: 2, curve: "monotone-x"}),
      Plot.dot(circuitWear, {
        x: "tyre_age_laps",
        y,
        fill: "compound",
        r: 4,
        stroke: "#15151e",
        strokeWidth: 2,
        channels: {"Laps measured": "laps"},
        tip: true
      }),
    ]
  })
);
```

</div>

```js
const byCompound = d3
  .rollups(
    stints.filter((d) => d.circuit_short_name === circuit && d.degradation_s_per_lap !== null && dry.includes(d.compound)),
    (v) => ({stints: v.length, median: d3.median(v, (d) => d.degradation_s_per_lap) + (corrected ? FUEL_S_PER_LAP : 0)}),
    (d) => d.compound
  )
  .sort((a, b) => dry.indexOf(a[0]) - dry.indexOf(b[0]))
  .map(([compound, s]) => ({Tyre: compound, "Seconds lost per lap (median)": s.median, Stints: s.stints}));
display(
  Inputs.table(byCompound, {
    select: false,
    format: {
      Tyre: (c) => html`<span style="display:inline-flex;gap:.4rem;align-items:center">${tyre(c, 18)} ${c}</span>`,
      "Seconds lost per lap (median)": (x) => x.toFixed(3)
    }
  })
);
```

<div class="note">

The fuel correction is an assumption: about 1.8 kg of fuel burned per lap at roughly 0.03 s per kg, i.e. about ${FUEL_S_PER_LAP} s per lap, the same for every car and circuit. Real fuel effects vary a little, so treat the corrected numbers as estimates. The curves pool stints of different lengths, which flattens them at high tyre ages; the table's per-stint figure (the slope of each stint on its own) is the more precise measure. Only tyre ages with at least 5 clean laps are shown.

</div>
