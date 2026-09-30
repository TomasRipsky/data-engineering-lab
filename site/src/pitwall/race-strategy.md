---
title: Race strategy
style: pitwall.css
---

```js
import "./components/fonts.js";
import {rows} from "../components/lab.js";
import {
  compoundColor,
  compoundLetter,
  lightCompounds,
  neutralisationFill,
  neutralisationOpacity,
  labelledPeriods,
  periods,
  tyre,
  tyreLegend
} from "./components/f1.js";
const races = rows(await FileAttachment("data/races.parquet").parquet());
const stints = rows(await FileAttachment("data/stints.parquet").parquet());
const stops = rows(await FileAttachment("data/pit_stops.parquet").parquet());
const neutralised = rows(await FileAttachment("data/neutralisations.parquet").parquet());
```

# Who ran which tyres, and when did everyone stop?

<div class="tip" label="What am I looking at?">

Each row is a driver, in finishing order, with a dot in their team's colour. Each coloured bar is a **stint** — the laps driven on one set of tyres — marked with the tyre's letter. The white diamonds are **pit stops**. Shaded columns are laps under the **Safety Car** (light) or a **red flag** (red). Read across a row for one driver's strategy; compare rows to see who stopped earlier or later, and on which tyres.

</div>

```js
const season = view(Inputs.select(d3.sort(new Set(races.map((d) => d.season)), (d) => -d), {label: "Season", format: String}));
```

```js
const race = view(
  Inputs.select(races.filter((d) => d.season === season).reverse(), {
    label: "Race",
    format: (d) => `${d.meeting_name} · ${d.session_name}`
  })
);
```

```js
const raceStints = stints.filter((d) => d.session_key === race.session_key && d.first_lap != null);
const raceStops = stops.filter((d) => d.session_key === race.session_key && d.lap_number != null);
const racePeriods = periods(neutralised.filter((d) => d.session_key === race.session_key));
const drivers = [...new Map(raceStints.map((d) => [d.name_acronym, d])).values()];
const order = d3.sort(drivers, (d) => d.finish_position ?? 99).map((d) => d.name_acronym);
const lastLap = d3.max(raceStints, (d) => d.last_lap) ?? 1;
const labelled = raceStints.filter((d) => d.laps_in_stint >= 3);
```

<div class="card">

${tyreLegend()}
<div class="pw-legend">
  <span><svg width="14" height="14"><path d="M7 1 L13 7 L7 13 L1 7 Z" fill="#f0f0f0"/></svg> Pit stop</span>
  <span><svg width="14" height="14"><path d="M7 1 L13 7 L7 13 L1 7 Z" fill="none" stroke="#f0f0f0" stroke-width="2"/></svg> Pit stop under Safety Car / red flag</span>
  <span><span class="pw-swatch" style="background: rgba(240,240,240,0.18)"></span> Safety Car / VSC</span>
  <span><span class="pw-swatch" style="background: rgba(225,6,0,0.4)"></span> Red flag</span>
</div>

```js
display(
  Plot.plot({
    title: `${race.meeting_name} ${race.season} · ${race.session_name}`,
    width,
    height: 28 * order.length + 70,
    marginLeft: 48,
    marginTop: 30,
    style: {background: "transparent", fontSize: "12px"},
    marginBottom: 42,
    x: {domain: [-2.5, lastLap], label: "Lap →", labelAnchor: "center", labelOffset: 36, grid: true, ticks: d3.ticks(0, lastLap, 10), tickFormat: "d"},
    y: {domain: order, label: null},
    color: compoundColor,
    marks: [
      Plot.rectX(racePeriods, {
        x1: (d) => d.from - 1,
        x2: "to",
        fill: {value: (d) => neutralisationFill[d.type], scale: null},
        fillOpacity: {value: (d) => neutralisationOpacity[d.type], scale: null},
        channels: {Neutralisation: "type", "From lap": "from", "To lap": "to"},
        tip: true
      }),
      Plot.text(labelledPeriods(racePeriods), {
        x: (d) => (d.from - 1 + d.to) / 2,
        frameAnchor: "top",
        dy: -16,
        text: (d) => (d.type === "RED" ? "RED FLAG" : d.type),
        fill: "#a3a3b3",
        fontWeight: 700
      }),
      Plot.dot(drivers, {x: -1.4, y: "name_acronym", r: 5, fill: {value: "team_colour_hex", scale: null}, title: "team_name"}),
      Plot.barX(raceStints, {
        x1: (d) => d.first_lap - 1,
        x2: "last_lap",
        y: "name_acronym",
        fill: "compound",
        rx: 4,
        insetLeft: 1,
        insetRight: 1,
        insetTop: 3,
        insetBottom: 3,
        channels: {
          Driver: "full_name",
          Team: "team_name",
          Stint: "stint_number",
          Laps: "laps_in_stint",
          "Tyre age at start": "tyre_age_at_start",
          "Wear (s/lap)": "degradation_s_per_lap"
        },
        tip: {format: {x1: false, x2: false, y: false, fill: true}}
      }),
      Plot.text(labelled.filter((d) => lightCompounds.has(d.compound)), {
        x: (d) => (d.first_lap - 1 + d.last_lap) / 2,
        y: "name_acronym",
        text: (d) => compoundLetter(d.compound),
        fill: "#15151e",
        fontWeight: 700
      }),
      Plot.text(labelled.filter((d) => !lightCompounds.has(d.compound)), {
        x: (d) => (d.first_lap - 1 + d.last_lap) / 2,
        y: "name_acronym",
        text: (d) => compoundLetter(d.compound),
        fill: "#ffffff",
        fontWeight: 700
      }),
      Plot.dot(raceStops, {
        x: "lap_number",
        y: "name_acronym",
        symbol: "diamond",
        r: 5,
        fill: {value: (d) => (d.neutralisation ? "#15151e" : "#f0f0f0"), scale: null},
        stroke: {value: (d) => (d.neutralisation ? "#f0f0f0" : "#15151e"), scale: null},
        strokeWidth: 2,
        channels: {
          "Pit lane (s)": "pit_lane_time_s",
          "Stationary (s)": "stationary_time_s",
          "Tyres": (d) => `${d.compound_before ?? "?"} → ${d.compound_after ?? "?"}`,
          "Under": "neutralisation"
        },
        tip: {format: {fill: false, stroke: false}}
      })
    ]
  })
);
```

</div>

```js
const results = d3
  .sort(drivers, (d) => d.finish_position ?? 99)
  .map((d) => ({
    Finish: d.finish_position ?? "—",
    Driver: d.full_name,
    Team: d.team_name,
    Grid: d.grid_position ?? "—",
    Stops: raceStops.filter((s) => s.driver_number === d.driver_number).length,
    Tyres: d3
      .sort(raceStints.filter((s) => s.driver_number === d.driver_number), (s) => s.stint_number)
      .map((s) => s.compound)
  }));
display(
  Inputs.table(results, {
    select: false,
    rows: 25,
    format: {Tyres: (list) => html`<span style="display:inline-flex;gap:2px">${list.map((c) => tyre(c, 18))}</span>`}
  })
);
```

<div class="note">

Pit stops under the Safety Car or a red flag cost much less time, so they are drawn hollow. Some 2023 races have no official pit data: their stops are inferred from tyre changes and have no timing. Sprint starting grids are not published by the source, so they show as —. A few stints with broken lap records in the source are left out.

</div>
