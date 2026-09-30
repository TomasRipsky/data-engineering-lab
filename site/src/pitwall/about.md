---
title: About the data
style: pitwall.css
---

```js
import {rows} from "../components/lab.js";
import {pipelineLap} from "./components/art.js";
const races = rows(await FileAttachment("data/races.parquet").parquet());
const latest = races.at(-1);
```

# Where do these numbers come from?

<div class="tip" label="What am I looking at?">

How this section is built, where the numbers come from, and what they can't tell you. Latest race included: **${latest.meeting_name} ${latest.season}** (${latest.race_date}).

</div>

${pipelineLap([
  ["OpenF1 API", "timing data for every race since 2023"],
  ["Extractor", "Python, polite to the API, idempotent"],
  ["Lake", "Parquet files in Google Cloud Storage"],
  ["Warehouse", "BigQuery, rebuilt from the lake"],
  ["dbt", "tested models: stints, stops, undercuts"],
  ["Export", "read-only account, a few small files"],
  ["This site", "rebuilt every Monday by GitHub Actions"]
])}

<div class="grid grid-cols-2">
<div class="card">

### Source
[OpenF1](https://openf1.org), an unofficial open API of Formula 1 timing data, from 2023 onwards. Race and Sprint sessions only.

### Pipeline
A Python extractor stores every Grand Prix in a Google Cloud Storage lake; BigQuery and dbt turn it into tested tables. GitHub Actions runs it every Monday and rebuilds this site, with no stored passwords or keys (Workload Identity Federation). The site only receives files exported by a read-only account.

</div>
<div class="card">

### Quality
Impossible values stop the pipeline, so this site keeps the last good version. Unusual-but-real data — red-flag stops, wet races, a few broken tyre records — is kept, flagged and explained.

### Definitions
A **clean lap** excludes the first lap, laps entering or leaving the pits, Safety Car laps and anything slower than 1.2 × the race's median lap. **Tyre wear** is the trend of clean laps against tyre age. The undercut rules are on [its page](./undercut).

</div>
</div>

Code, tests and design decisions: [github.com/TomasRipsky/data-engineering-lab](https://github.com/TomasRipsky/data-engineering-lab/tree/main/projects/pitwall).

<div class="note">

OpenF1 is unofficial and not affiliated with Formula 1. Its data has gaps (for example missing pit timings in some 2023 races); the pipeline documents and works around them rather than hiding them. Illustrations on this site are original.

</div>
