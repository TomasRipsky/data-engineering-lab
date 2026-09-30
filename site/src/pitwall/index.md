---
title: pitwall — F1 race strategy
style: pitwall.css
toc: false
---

```js
import {rows, fmt} from "../components/lab.js";
import {tyre, tyreLegend} from "./components/f1.js";
import {car, chequered} from "./components/art.js";
const races = rows(await FileAttachment("data/races.parquet").parquet());
const stops = rows(await FileAttachment("data/pit_stops.parquet").parquet());
const latest = races.at(-1);
const timed = stops.filter((d) => d.source === "pit" && d.pit_lane_time_s != null);
```

<div class="pw-hero">
  ${car()}
  <p class="pw-eyebrow">pitwall · Formula 1 race strategy</p>
  <h1>How are Formula 1 races won with tyres and pit stops?</h1>
  <p>Every race since 2023, turned into a few questions anyone can follow — no F1 knowledge needed.</p>
</div>
<div class="pw-kerb"></div>

<div class="tip" label="What am I looking at?">

A data pipeline that downloads every Formula 1 race since 2023 from [OpenF1](https://openf1.org), models it in BigQuery with dbt, and turns it into the questions below. It refreshes itself every Monday after a Grand Prix. Latest race included: **${latest.meeting_name}** (${latest.session_name}, ${latest.race_date}).

</div>

<div class="grid grid-cols-4">
  <div class="card"><h2>Races analysed</h2><span class="huge">${races.length}</span></div>
  <div class="card"><h2>Seasons</h2><span class="big">${d3.min(races, (d) => d.season)}–${d3.max(races, (d) => d.season)}</span></div>
  <div class="card"><h2>Pit stops</h2><span class="big">${fmt.count(stops.length)}</span></div>
  <div class="card"><h2>Median time in the pit lane</h2><span class="big">${fmt.seconds(d3.median(timed, (d) => d.pit_lane_time_s))}</span></div>
</div>

## The questions

<div class="grid grid-cols-3">
  <a class="card pw-question" href="./race-strategy">
    <h2>${tyre("SOFT", 24)} Race strategy</h2>
    <p>Who ran which tyres, and when did everyone stop — in any race.</p>
  </a>
  <a class="card pw-question" href="./tyre-wear">
    <h2>${tyre("MEDIUM", 24)} Tyre wear</h2>
    <p>How quickly does each tyre get slower, circuit by circuit?</p>
  </a>
  <a class="card pw-question" href="./undercut">
    <h2>${tyre("HARD", 24)} The undercut</h2>
    <p>Does pitting before the car ahead actually work?</p>
  </a>
</div>

## F1 in one minute

${tyreLegend()}

| Term | Meaning |
|---|---|
| **Grand Prix** | One race weekend at one circuit. |
| **Race / Sprint** | Sunday's full-distance race / Saturday's short race. Both are analysed here. |
| **Compound** | Tyre type. **Soft** is fastest but wears quickly, **Hard** is slowest but lasts; **Medium** sits between. **Intermediate** and **Wet** are for rain. |
| **Stint** | The laps a driver does on one set of tyres, between two pit stops. |
| **Pit stop** | Stop to change tyres: about 2–3 s stationary, about 20 s lost overall. |
| **Undercut** | Pitting before the car just ahead, so fresh tyres put you in front once they pit too. |
| **Safety Car** | Everyone slows down after an incident, which makes pitting cheaper. |

<p>${chequered()}</p>

How the data is built, and its limits: [About the data](./about).
