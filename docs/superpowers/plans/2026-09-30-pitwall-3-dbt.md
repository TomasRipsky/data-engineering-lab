# pitwall — Plan 3: dbt models

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A dbt project that turns `raw.openf1_*` into documented, tested race-strategy marts (laps, stints with tyre degradation, pit stops, undercut attempts, results) in the dev BigQuery project, runnable with `make transform`.

**Architecture:** Three layers, each in its own BigQuery dataset: `staging` (views, one per raw table, typing/renaming/dedup only), `intermediate` (views: safety-car laps, laps enriched with tyres/pits/positions), `marts` (tables with a stated grain). Business rules — clean lap, degradation slope, undercut success — live in exactly one model each and are pinned by dbt unit tests written before the SQL. Shared column descriptions are doc blocks, so every column is described once in plain language.

**Tech Stack:** dbt-core 1.12, dbt-bigquery 1.12, dbt_utils 1.4.1, BigQuery Standard SQL, uv.

**Spec:** `docs/superpowers/specs/2026-09-29-pitwall-design.md` (§2 glossary, §6 transformation, §10 testing). Earlier plans: `2026-09-29-pitwall-1-extractor.md`, `2026-09-30-pitwall-2-gcp-loader.md`.

## Global Constraints

- SQL: lowercase keywords, CTEs over nested subqueries, every model starts with a `-- grain:` comment and states its grain in its YAML description.
- Every model and every column has a plain-language description (reader knows nothing about F1); shared columns use doc blocks from `transform/models/docs.md`.
- Generic test inputs go under `arguments:` (dbt ≥ 1.10.5 syntax); framework options (`severity`) under `config:`.
- Schemas: dev/prod write to datasets `staging`, `intermediate`, `marts` (created by Terraform); target `ci` writes to `<DBT_CI_SCHEMA>_<layer>` (Plan 4).
- Cost guards in the profile: `maximum_bytes_billed` 1 GB per query, 300 s job timeout.
- `profiles.yml` is never committed (lab rule); `transform/profiles.yml.example` is, and uses `env_var()` + OAuth only.
- BigQuery `qualify` is always paired with `where true`.
- Only dev is touched. `PITWALL_BQ_PROJECT` comes from the Makefile (`pitwall-tr-$(ENV)`).
- Data quality: ingestion rejects only structural breakage (Plan 1 contracts); semantic rules live in dbt. `error` severity only for what would corrupt marts (null/duplicate keys, impossible values); everything else `warn`. Every data test stores failing rows in the `audit` dataset (`store_failures`).
- Columns OpenF1 never fills (`drivers.country_code`, `race_control.qualifying_phase` in races) are not carried into staging.
- Out of v1 marts: `weather` and `overtakes` (declared as sources, no staging model — YAGNI until a page needs them).

## Review Focus

1. **Safety-car periods without an end message** (21 deployments, 18 endings in 2025 — races finishing under SC or red-flagged) → the period runs to the next deployment of the same type or the session's last lap, never swallowing a later period; unit test in Task 4.
2. **Laps with no `date_start`** (21 in 2025) → the lap end falls back to the next lap's start, so positions are still assigned; unit test in Task 5.
3. **Sessions without pit data** (some 2023 races) → pit stops inferred from tyre changes, flagged `source = 'stint_change'`; unit test in Task 7.
4. **Sprint grids come from "Sprint Qualifying", called "Sprint Shootout" in 2023** → grid mapped for all three names; unit test in Task 6.
5. **Red-flag laps (up to 1,454 s) and other outliers** must not distort degradation → clean laps exclude anything slower than 1.2 × the session median; unit tests in Tasks 5 and 7.

---

### Task 1: dbt project skeleton

**Files:**
- Modify: `projects/pitwall/pyproject.toml`, `projects/pitwall/Makefile`, `projects/pitwall/.gitignore`
- Create: `projects/pitwall/transform/dbt_project.yml`, `packages.yml`, `profiles.yml.example`, `macros/generate_schema_name.sql`, `models/sources.yml`, `models/docs.md`

**Interfaces:**
- Produces: `audit` dataset (Terraform), `make bootstrap` creating projects inside `ORG_ID`; source `openf1` with tables `openf1_<endpoint>` in `{{ env_var('PITWALL_BQ_PROJECT') }}.raw`; doc blocks `meeting_key`, `session_key`, `driver_number`, `lap_number`, `compound`, `tyre_age_laps`, `position`, `neutralisation`, `grain_note`; `make transform`.

- [ ] **Step 1: Branch**

```bash
cd "/Users/tomasripsky/Data Engineering/Claude Code Enviroment"
git switch dev && git pull --ff-only
URL=$(gh issue create --title "feat(pitwall): dbt race-strategy models" \
  --label "type:feat,project:pitwall" \
  --body "Plan 3 of pitwall: docs/superpowers/plans/2026-09-30-pitwall-3-dbt.md")
git switch -c "feat/${URL##*/}-pitwall-dbt"
```

- [ ] **Step 1b: Projects belong to the organization; add the `audit` dataset**

In `projects/pitwall/Makefile`, in the `bootstrap` target: change the usage hint to `BILLING_ACCOUNT=... ORG_ID=651783965785`, add a guard line after the BILLING_ACCOUNT one:

```make
	@test -n "$(ORG_ID)" || { echo "set ORG_ID (see: gcloud organizations list)"; exit 1; }
```

and change the create line to:

```make
	gcloud projects create $(PROJECT_ID) --name="pitwall $(ENV)" --organization=$(ORG_ID)
```

In `projects/pitwall/infra/gcp/main.tf` change `datasets` to:

```hcl
  datasets = ["raw", "staging", "intermediate", "marts", "audit"]
```

Run: `cd projects/pitwall && make -n bootstrap BILLING_ACCOUNT=x ORG_ID=651783965785 | head -3 && make plan`
Expected: the create line carries `--organization=651783965785`; the plan adds exactly 2 resources (dataset `audit` + its pipeline IAM member). Then `terraform -chdir=infra/gcp apply -auto-approve -var env=dev -var project_id=pitwall-tr-dev` (US$0: an empty dataset).

```bash
git add Makefile infra/gcp/main.tf
git commit -m "fix(pitwall): create projects inside the organization; add audit dataset"
```

- [ ] **Step 2: Dependencies**

```bash
cd projects/pitwall && uv add --group transform dbt-core dbt-bigquery
```

Add to `pyproject.toml`:

```toml
[tool.uv]
default-groups = ["dev", "transform"]
```

Run: `uv sync && uv run dbt --version`
Expected: `Core: 1.12.x` and `bigquery: 1.12.x`.

- [ ] **Step 3: Project files**

`projects/pitwall/transform/dbt_project.yml`:

```yaml
name: pitwall
version: "1.0.0"
profile: pitwall

model-paths: ["models"]
macro-paths: ["macros"]
test-paths: ["tests"]

clean-targets: ["target", "dbt_packages"]

data_tests:
  pitwall:
    +store_failures: true # failing rows land in the `audit` dataset for inspection
    +schema: audit

models:
  pitwall:
    staging:
      +schema: staging
      +materialized: view
    intermediate:
      +schema: intermediate
      +materialized: view
    marts:
      +schema: marts
      +materialized: table
```

`projects/pitwall/transform/packages.yml`:

```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: 1.4.1
```

`projects/pitwall/transform/profiles.yml.example`:

```yaml
# Copied to profiles.yml by `make transform`. OAuth = your gcloud ADC locally, WIF in CI.
pitwall:
  target: dev
  outputs:
    dev: &bigquery
      type: bigquery
      method: oauth
      project: "{{ env_var('PITWALL_BQ_PROJECT') }}"
      dataset: staging
      location: us-central1
      threads: 4
      job_execution_timeout_seconds: 300
      maximum_bytes_billed: 1000000000 # 1 GB per query: a second cost guard next to the quota
    prod:
      <<: *bigquery
    ci:
      <<: *bigquery
      dataset: "{{ env_var('DBT_CI_SCHEMA', 'ci_local') }}"
```

`projects/pitwall/transform/macros/generate_schema_name.sql`:

```sql
{#
    dev/prod: one dataset per layer (staging, intermediate, marts), created by Terraform.
    ci: every layer prefixed with the per-PR dataset name, e.g. ci_pr_12_marts.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set layer = (custom_schema_name or 'staging') | trim -%}
    {%- if target.name == 'ci' -%}
        {{ target.schema }}_{{ layer }}
    {%- else -%}
        {{ layer }}
    {%- endif -%}
{%- endmacro %}
```

`projects/pitwall/transform/models/docs.md`:

```markdown
{% docs meeting_key %}
Identifier of a Grand Prix weekend (a "meeting"): one race weekend at one circuit, e.g. the 2025 Chinese Grand Prix is 1255.
{% enddocs %}

{% docs session_key %}
Identifier of one on-track session. pitwall only keeps the two kinds of race: the Sunday **Race** and the shorter Saturday **Sprint**.
{% enddocs %}

{% docs driver_number %}
The driver's permanent car number (e.g. 1, 44, 81). Unique within a session.
{% enddocs %}

{% docs lap_number %}
Lap counter within a session, starting at 1. A lap is one full tour of the circuit.
{% enddocs %}

{% docs compound %}
Tyre type: SOFT (fastest, wears out quickly), MEDIUM, HARD (slowest, lasts longest), INTERMEDIATE and WET (for rain). UNKNOWN when the source does not say.
{% enddocs %}

{% docs tyre_age_laps %}
How many laps this set of tyres had already done when the lap started. Sets can be reused from earlier sessions, so a stint may start above 0.
{% enddocs %}

{% docs position %}
Running order: 1 is the leader. Taken from the latest position update recorded before the lap ended.
{% enddocs %}

{% docs neutralisation %}
`SC` if the Safety Car was on track during this lap, `VSC` for the Virtual Safety Car, empty otherwise. Everyone drives slowly under either, so these laps say nothing about tyre wear, and pit stops cost less time.
{% enddocs %}

{% docs ingested_at %}
When pitwall downloaded this record from OpenF1 (UTC).
{% enddocs %}
```

`projects/pitwall/transform/models/sources.yml`:

```yaml
version: 2

sources:
  - name: openf1
    description: Raw OpenF1 data, rebuilt from the GCS lake by `pitwall load`. One table per API endpoint, Race and Sprint sessions only.
    database: "{{ env_var('PITWALL_BQ_PROJECT') }}"
    schema: raw
    tables:
      - name: openf1_meetings
        description: One row per race weekend (and testing) of each ingested season.
      - name: openf1_sessions
        description: One row per session (practice, qualifying, sprint, race) of each ingested season.
      - name: openf1_drivers
        description: Drivers taking part in each session, with their team.
      - name: openf1_laps
        description: One row per lap per driver, with lap and sector times.
      - name: openf1_stints
        description: Tyre stints — continuous runs on one set of tyres.
      - name: openf1_pit
        description: Pit-lane visits, with time spent in the lane and stationary.
      - name: openf1_position
        description: Every change in running order, with its timestamp.
      - name: openf1_weather
        description: Weather at the track about once a minute (not modelled in v1).
      - name: openf1_race_control
        description: Messages from race control — flags, safety car, penalties.
      - name: openf1_session_result
        description: Final classification of each session.
      - name: openf1_overtakes
        description: Position swaps between two drivers (not modelled in v1).
      - name: openf1_starting_grid
        description: Starting grid, attached by OpenF1 to the qualifying session that produced it.
```

- [ ] **Step 4: Makefile and ignores**

Append to `projects/pitwall/.gitignore`:

```
# dbt
transform/target/
transform/logs/
transform/dbt_packages/
```

In `projects/pitwall/Makefile`, add `transform` to `.PHONY` and add after the `load` target:

```make
transform/profiles.yml: transform/profiles.yml.example
	cp $< $@

transform: transform/profiles.yml ## Build and test the dbt models in $(PROJECT_ID)
	cd transform && uv run dbt deps --quiet && uv run dbt build --target $(ENV) --profiles-dir .
```

- [ ] **Step 5: Verify the skeleton**

Run: `cd projects/pitwall && cp transform/profiles.yml.example transform/profiles.yml && cd transform && uv run dbt deps && uv run dbt debug --profiles-dir . && uv run dbt parse --profiles-dir .`
Expected: `All checks passed!` from `debug` (it connects to BigQuery with your ADC); `parse` succeeds; `package-lock.yml` is created.

Also check the `ci` target parses (the schema macro is proven in Task 9, once models exist):

Run: `DBT_CI_SCHEMA=ci_pr_0 uv run dbt parse --profiles-dir . --target ci`
Expected: parse succeeds.

- [ ] **Step 6: Commit**

```bash
cd "/Users/tomasripsky/Data Engineering/Claude Code Enviroment/projects/pitwall"
git add pyproject.toml uv.lock Makefile .gitignore transform/dbt_project.yml transform/packages.yml \
  transform/package-lock.yml transform/profiles.yml.example transform/macros transform/models
git commit -m "feat(pitwall): add dbt project skeleton, sources and doc blocks"
```

---

### Task 2: Staging models

**Files:**
- Create: `projects/pitwall/transform/models/staging/stg_openf1__{meetings,sessions,drivers,laps,stints,pit,position,race_control,session_result,starting_grid}.sql`
- Create: `projects/pitwall/transform/models/staging/_staging.yml`
- Create: `projects/pitwall/transform/tests/assert_stint_lap_ranges_are_valid.sql`

**Interfaces:**
- Produces (columns later tasks use):
  - `stg_openf1__meetings`: meeting_key, meeting_name, meeting_official_name, season, location, country_name, circuit_short_name, circuit_type, starts_at, ends_at
  - `stg_openf1__sessions`: session_key, meeting_key, session_type, session_name, season, starts_at, ends_at, is_cancelled, circuit_short_name, country_name
  - `stg_openf1__drivers`: session_key, meeting_key, driver_number, full_name, name_acronym, team_name, team_colour_hex
  - `stg_openf1__laps`: session_key, meeting_key, driver_number, lap_number, started_at, lap_time_s, sector_1_s, sector_2_s, sector_3_s, speed_trap_kph, is_pit_out_lap
  - `stg_openf1__stints`: session_key, meeting_key, driver_number, stint_number, first_lap, last_lap, compound, tyre_age_at_start, has_valid_lap_range
  - `stg_openf1__pit`: session_key, meeting_key, driver_number, lap_number, pitted_at, pit_lane_time_s, stationary_time_s
  - `stg_openf1__position`: session_key, meeting_key, driver_number, recorded_at, position
  - `stg_openf1__race_control`: session_key, meeting_key, recorded_at, lap_number, driver_number, category, flag, message
  - `stg_openf1__session_result`: session_key, meeting_key, driver_number, finish_position, laps_completed, points, did_not_finish, did_not_start, disqualified, gap_to_leader
  - `stg_openf1__starting_grid`: qualifying_session_key, meeting_key, driver_number, grid_position, qualifying_lap_time_s

- [ ] **Step 1: Write the tests first (YAML + singular test)**

`projects/pitwall/transform/models/staging/_staging.yml`:

```yaml
version: 2

models:
  - name: stg_openf1__meetings
    description: "Grain: one row per race weekend. Cleaned copy of the OpenF1 meetings table."
    columns:
      - name: meeting_key
        description: "{{ doc('meeting_key') }}"
        data_tests: [unique, not_null]
      - name: meeting_name
        description: Short name, e.g. "Chinese Grand Prix".
      - name: meeting_official_name
        description: Full sponsored name of the event.
      - name: season
        description: Championship year.
      - name: location
        description: City or area of the circuit.
      - name: country_name
        description: Country hosting the race.
      - name: circuit_short_name
        description: Short circuit name, e.g. "Shanghai".
      - name: circuit_type
        description: '"Permanent" race track or "Temporary" street circuit.'
      - name: starts_at
        description: Start of the weekend's first session (UTC).
      - name: ends_at
        description: End of the weekend's last session (UTC).

  - name: stg_openf1__sessions
    description: "Grain: one row per session of an ingested season (all session types)."
    columns:
      - name: session_key
        description: "{{ doc('session_key') }}"
        data_tests: [unique, not_null]
      - name: meeting_key
        description: "{{ doc('meeting_key') }}"
        data_tests: [not_null]
      - name: session_type
        description: '"Practice", "Qualifying" or "Race" (a Sprint counts as a race).'
      - name: session_name
        description: '"Race", "Sprint", "Qualifying", "Sprint Qualifying" ("Sprint Shootout" in 2023), "Practice 1", ...'
      - name: season
        description: Championship year.
      - name: starts_at
        description: Scheduled start (UTC).
      - name: ends_at
        description: Scheduled end (UTC).
      - name: is_cancelled
        description: True when the session did not take place.
      - name: circuit_short_name
        description: Short circuit name.
      - name: country_name
        description: Host country.

  - name: stg_openf1__drivers
    description: "Grain: one row per driver per session."
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [session_key, driver_number]
    columns:
      - name: session_key
        description: "{{ doc('session_key') }}"
      - name: meeting_key
        description: "{{ doc('meeting_key') }}"
      - name: driver_number
        description: "{{ doc('driver_number') }}"
        data_tests: [not_null]
      - name: full_name
        description: Driver's name as broadcast, e.g. "Oscar PIASTRI".
      - name: name_acronym
        description: Three-letter code shown on TV timing, e.g. "PIA".
      - name: team_name
        description: Team the driver raced for in this session.
      - name: team_colour_hex
        description: Team colour as a hex code (used by the dashboard), e.g. "#FF8000".

  - name: stg_openf1__laps
    description: "Grain: one row per lap of one driver in one session."
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [session_key, driver_number, lap_number]
    columns:
      - name: session_key
        description: "{{ doc('session_key') }}"
        data_tests: [not_null]
      - name: meeting_key
        description: "{{ doc('meeting_key') }}"
      - name: driver_number
        description: "{{ doc('driver_number') }}"
        data_tests: [not_null]
      - name: lap_number
        description: "{{ doc('lap_number') }}"
        data_tests: [not_null]
      - name: started_at
        description: When the lap started (UTC). Missing for a few laps.
      - name: lap_time_s
        description: Lap time in seconds. Missing when timing failed (often lap 1 or laps ending in the pits).
      - name: sector_1_s
        description: Time through the first third of the lap, in seconds.
      - name: sector_2_s
        description: Time through the second third of the lap, in seconds.
      - name: sector_3_s
        description: Time through the last third of the lap, in seconds.
      - name: speed_trap_kph
        description: Speed at the fastest point of the track (km/h).
      - name: is_pit_out_lap
        description: True for the lap that starts in the pit lane after a stop (slow, not representative).

  - name: stg_openf1__stints
    description: "Grain: one row per stint — the laps one driver completes on one set of tyres."
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [session_key, driver_number, stint_number]
    columns:
      - name: session_key
        description: "{{ doc('session_key') }}"
      - name: meeting_key
        description: "{{ doc('meeting_key') }}"
      - name: driver_number
        description: "{{ doc('driver_number') }}"
      - name: stint_number
        description: 1 for the tyres the driver started on, 2 after the first stop, and so on.
      - name: first_lap
        description: First lap driven on this set of tyres.
      - name: last_lap
        description: Last lap driven on this set of tyres (usually the lap of the next pit stop).
      - name: compound
        description: "{{ doc('compound') }}"
        data_tests:
          - accepted_values:
              arguments:
                values: [SOFT, MEDIUM, HARD, INTERMEDIATE, WET, UNKNOWN]
      - name: tyre_age_at_start
        description: Laps these tyres had already done before the stint began.
      - name: has_valid_lap_range
        description: False when OpenF1 sent a missing or inverted lap range; such stints are kept here but left out of the marts.

  - name: stg_openf1__pit
    description: "Grain: one row per pit-lane visit."
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [session_key, driver_number, lap_number]
    columns:
      - name: session_key
        description: "{{ doc('session_key') }}"
      - name: meeting_key
        description: "{{ doc('meeting_key') }}"
      - name: driver_number
        description: "{{ doc('driver_number') }}"
      - name: lap_number
        description: Lap on which the driver entered the pit lane (the "in-lap").
      - name: pitted_at
        description: When the car entered the pit lane (UTC).
      - name: pit_lane_time_s
        description: Seconds from pit entry to pit exit (~20 s is typical).
      - name: stationary_time_s
        description: Seconds the car stood still while tyres were changed (~2–3 s). Missing before 2025.

  - name: stg_openf1__position
    description: "Grain: one row per change in running order for one driver."
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [session_key, driver_number, recorded_at]
    columns:
      - name: session_key
        description: "{{ doc('session_key') }}"
      - name: meeting_key
        description: "{{ doc('meeting_key') }}"
      - name: driver_number
        description: "{{ doc('driver_number') }}"
      - name: recorded_at
        description: When the new position took effect (UTC).
      - name: position
        description: "{{ doc('position') }}"

  - name: stg_openf1__race_control
    description: "Grain: one row per race-control message (flags, safety car, incidents)."
    columns:
      - name: session_key
        description: "{{ doc('session_key') }}"
      - name: meeting_key
        description: "{{ doc('meeting_key') }}"
      - name: recorded_at
        description: When the message was issued (UTC).
      - name: lap_number
        description: Race leader's lap when the message was issued.
      - name: driver_number
        description: Driver the message is about, if any.
      - name: category
        description: '"Flag", "SafetyCar", "Other", ...'
      - name: flag
        description: Flag shown, e.g. GREEN, YELLOW, RED, CHEQUERED.
      - name: message
        description: Message text, e.g. "SAFETY CAR DEPLOYED".

  - name: stg_openf1__session_result
    description: "Grain: one row per driver per finished session."
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [session_key, driver_number]
    columns:
      - name: session_key
        description: "{{ doc('session_key') }}"
      - name: meeting_key
        description: "{{ doc('meeting_key') }}"
      - name: driver_number
        description: "{{ doc('driver_number') }}"
      - name: finish_position
        description: Classified finishing position; empty for drivers who were not classified.
      - name: laps_completed
        description: Laps the driver completed.
      - name: points
        description: Championship points scored.
      - name: did_not_finish
        description: True if the driver retired (DNF).
      - name: did_not_start
        description: True if the driver did not take the start (DNS).
      - name: disqualified
        description: True if the driver was disqualified (DSQ).
      - name: gap_to_leader
        description: Gap to the winner as text — seconds ("11.097") or laps ("+1 LAP").

  - name: stg_openf1__starting_grid
    description: "Grain: one row per driver per starting grid. OpenF1 attaches a grid to the qualifying session that produced it."
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [qualifying_session_key, driver_number]
    columns:
      - name: qualifying_session_key
        description: The qualifying session that set this grid ("Qualifying" → Race, "Sprint Qualifying"/"Sprint Shootout" → Sprint).
      - name: meeting_key
        description: "{{ doc('meeting_key') }}"
      - name: driver_number
        description: "{{ doc('driver_number') }}"
      - name: grid_position
        description: Starting position (1 = pole position).
      - name: qualifying_lap_time_s
        description: The qualifying lap time that earned the grid slot, in seconds.
```

`projects/pitwall/transform/tests/assert_stint_lap_ranges_are_valid.sql`:

```sql
-- A stint needs both ends and must end on or after the lap it starts. OpenF1 has a handful of
-- missing or inverted ranges (10 in 2025); they are reported (warn) and kept out of the marts.
{{ config(severity='warn') }}

select session_key, driver_number, stint_number, first_lap, last_lap
from {{ ref('stg_openf1__stints') }}
where not has_valid_lap_range
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd projects/pitwall/transform && uv run dbt build --profiles-dir . --select staging`
Expected: failure — `assert_stint_lap_ranges_are_valid` depends on `stg_openf1__stints`, which does not exist yet (dbt also warns that the YAML patches models it cannot find).

- [ ] **Step 3: Write the staging models**

`stg_openf1__meetings.sql`:

```sql
-- grain: one row per meeting (race weekend)
with source as (
    select * from {{ source('openf1', 'openf1_meetings') }}
),

deduplicated as (
    select * from source
    where true
    qualify row_number() over (partition by meeting_key order by _ingested_at desc) = 1
)

select
    meeting_key,
    meeting_name,
    meeting_official_name,
    year as season,
    location,
    country_name,
    circuit_short_name,
    circuit_type,
    date_start as starts_at,
    date_end as ends_at
from deduplicated
```

`stg_openf1__sessions.sql`:

```sql
-- grain: one row per session
with source as (
    select * from {{ source('openf1', 'openf1_sessions') }}
),

deduplicated as (
    select * from source
    where true
    qualify row_number() over (partition by session_key order by _ingested_at desc) = 1
)

select
    session_key,
    meeting_key,
    session_type,
    session_name,
    year as season,
    date_start as starts_at,
    date_end as ends_at,
    coalesce(is_cancelled, false) as is_cancelled,
    circuit_short_name,
    country_name
from deduplicated
```

`stg_openf1__drivers.sql`:

```sql
-- grain: one row per driver per session
with source as (
    select * from {{ source('openf1', 'openf1_drivers') }}
),

deduplicated as (
    select * from source
    where true
    qualify row_number() over (
        partition by session_key, driver_number order by _ingested_at desc
    ) = 1
)

select
    session_key,
    meeting_key,
    driver_number,
    full_name,
    name_acronym,
    team_name,
    concat('#', team_colour) as team_colour_hex
from deduplicated
```

`stg_openf1__laps.sql`:

```sql
-- grain: one row per lap of one driver in one session
with source as (
    select * from {{ source('openf1', 'openf1_laps') }}
),

deduplicated as (
    select * from source
    where true
    qualify row_number() over (
        partition by session_key, driver_number, lap_number order by _ingested_at desc
    ) = 1
)

select
    session_key,
    meeting_key,
    driver_number,
    lap_number,
    date_start as started_at,
    lap_duration as lap_time_s,
    duration_sector_1 as sector_1_s,
    duration_sector_2 as sector_2_s,
    duration_sector_3 as sector_3_s,
    st_speed as speed_trap_kph,
    coalesce(is_pit_out_lap, false) as is_pit_out_lap
from deduplicated
```

`stg_openf1__stints.sql`:

```sql
-- grain: one row per stint (one driver on one set of tyres in one session)
with source as (
    select * from {{ source('openf1', 'openf1_stints') }}
),

deduplicated as (
    select * from source
    where true
    qualify row_number() over (
        partition by session_key, driver_number, stint_number order by _ingested_at desc
    ) = 1
)

select
    session_key,
    meeting_key,
    driver_number,
    stint_number,
    lap_start as first_lap,
    lap_end as last_lap,
    coalesce(upper(compound), 'UNKNOWN') as compound,
    tyre_age_at_start,
    coalesce(lap_start <= lap_end, false) as has_valid_lap_range
from deduplicated
```

`stg_openf1__pit.sql`:

```sql
-- grain: one row per pit-lane visit
with source as (
    select * from {{ source('openf1', 'openf1_pit') }}
),

deduplicated as (
    select * from source
    where true
    qualify row_number() over (
        partition by session_key, driver_number, lap_number order by _ingested_at desc
    ) = 1
)

select
    session_key,
    meeting_key,
    driver_number,
    lap_number,
    date as pitted_at,
    coalesce(lane_duration, pit_duration) as pit_lane_time_s,
    stop_duration as stationary_time_s
from deduplicated
```

`stg_openf1__position.sql`:

```sql
-- grain: one row per change in running order for one driver
with source as (
    select * from {{ source('openf1', 'openf1_position') }}
),

deduplicated as (
    select * from source
    where true
    qualify row_number() over (
        partition by session_key, driver_number, date order by _ingested_at desc
    ) = 1
)

select
    session_key,
    meeting_key,
    driver_number,
    date as recorded_at,
    position
from deduplicated
```

`stg_openf1__race_control.sql`:

```sql
-- grain: one row per race-control message
with source as (
    select * from {{ source('openf1', 'openf1_race_control') }}
),

deduplicated as (
    select * from source
    where true
    qualify row_number() over (
        partition by session_key, date, message, driver_number order by _ingested_at desc
    ) = 1
)

select
    session_key,
    meeting_key,
    date as recorded_at,
    lap_number,
    driver_number,
    category,
    flag,
    message
from deduplicated
```

`stg_openf1__session_result.sql`:

```sql
-- grain: one row per driver per finished session
with source as (
    select * from {{ source('openf1', 'openf1_session_result') }}
),

deduplicated as (
    select * from source
    where true
    qualify row_number() over (
        partition by session_key, driver_number order by _ingested_at desc
    ) = 1
)

select
    session_key,
    meeting_key,
    driver_number,
    position as finish_position,
    number_of_laps as laps_completed,
    points,
    coalesce(dnf, false) as did_not_finish,
    coalesce(dns, false) as did_not_start,
    coalesce(dsq, false) as disqualified,
    gap_to_leader
from deduplicated
```

`stg_openf1__starting_grid.sql`:

```sql
-- grain: one row per driver per starting grid (keyed by the qualifying session that set it)
with source as (
    select * from {{ source('openf1', 'openf1_starting_grid') }}
),

deduplicated as (
    select * from source
    where true
    qualify row_number() over (
        partition by session_key, driver_number order by _ingested_at desc
    ) = 1
)

select
    session_key as qualifying_session_key,
    meeting_key,
    driver_number,
    position as grid_position,
    lap_duration as qualifying_lap_time_s
from deduplicated
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run dbt build --profiles-dir . --select staging`
Expected: 10 views created; all tests pass except `assert_stint_lap_ranges_are_valid`, which **warns** with 10 rows (known OpenF1 data: 6 missing and 4 inverted ranges).

- [ ] **Step 5: Commit**

```bash
git add transform/models/staging transform/tests
git commit -m "feat(pitwall): add staging models for OpenF1 raw tables"
```

---

### Task 3: Data-quality rules on the raw data

**Files:**
- Modify: `projects/pitwall/transform/models/sources.yml`
- Create: `projects/pitwall/transform/tests/assert_every_race_has_a_full_field.sql`

**Interfaces:**
- Produces: tests on every source table; failing rows stored in `audit` (config from Task 1). Nothing downstream consumes them; `error` tests stop `dbt build` before the marts are refreshed (and, in Plan 4, before the dashboard is published).

Severity rule: **error** = the value is impossible and would corrupt a mart (null/duplicate keys, positions or points out of range, non-positive times). **warn** = unusual but real (missing timings, unknown compounds, incomplete fields); it is recorded in `audit` and the build continues.

- [ ] **Step 1: Replace `models/sources.yml` with the tested version**

```yaml
version: 2

sources:
  - name: openf1
    description: Raw OpenF1 data, rebuilt from the GCS lake by `pitwall load`. One table per API endpoint, Race and Sprint sessions only.
    database: "{{ env_var('PITWALL_BQ_PROJECT') }}"
    schema: raw
    tables:
      - name: openf1_meetings
        description: One row per race weekend (and testing) of each ingested season.
        columns:
          - name: meeting_key
            data_tests: [unique, not_null]

      - name: openf1_sessions
        description: One row per session (practice, qualifying, sprint, race) of each ingested season.
        columns:
          - name: session_key
            data_tests: [unique, not_null]
          - name: session_type
            data_tests:
              - accepted_values:
                  arguments:
                    values: [Practice, Qualifying, Race]
                  config:
                    severity: warn

      - name: openf1_drivers
        description: Drivers taking part in each session, with their team. `country_code` is never filled by OpenF1 and is not modelled.
        data_tests:
          - dbt_utils.unique_combination_of_columns:
              arguments:
                combination_of_columns: [session_key, driver_number]
        columns:
          - name: driver_number
            data_tests:
              - not_null
              - dbt_utils.accepted_range:
                  arguments:
                    min_value: 1
                    max_value: 99
          - name: team_name
            data_tests:
              - not_null:
                  config:
                    severity: warn

      - name: openf1_laps
        description: One row per lap per driver, with lap and sector times.
        data_tests:
          - dbt_utils.unique_combination_of_columns:
              arguments:
                combination_of_columns: [session_key, driver_number, lap_number]
        columns:
          - name: lap_number
            data_tests:
              - not_null
              - dbt_utils.accepted_range:
                  arguments:
                    min_value: 1
                    max_value: 100
          - name: lap_duration
            data_tests:
              - dbt_utils.accepted_range:
                  arguments:
                    min_value: 30
                    inclusive: true
              # timing gaps happen (lap 1, pit laps); more than 2% missing in a race is suspicious
              - dbt_utils.not_null_proportion:
                  arguments:
                    at_least: 0.98
                    group_by_columns: [session_key]
                  config:
                    severity: warn
          - name: date_start
            data_tests:
              - dbt_utils.not_null_proportion:
                  arguments:
                    at_least: 0.98
                    group_by_columns: [session_key]
                  config:
                    severity: warn

      - name: openf1_stints
        description: Tyre stints — continuous runs on one set of tyres.
        data_tests:
          - dbt_utils.unique_combination_of_columns:
              arguments:
                combination_of_columns: [session_key, driver_number, stint_number]
        columns:
          - name: compound
            data_tests:
              - accepted_values:
                  arguments:
                    values: [SOFT, MEDIUM, HARD, INTERMEDIATE, WET]
                  config:
                    severity: warn
          - name: tyre_age_at_start
            data_tests:
              - dbt_utils.accepted_range:
                  arguments:
                    min_value: 0
                    max_value: 100

      - name: openf1_pit
        description: Pit-lane visits, with time spent in the lane and stationary. `stop_duration` is missing for some stops.
        data_tests:
          - dbt_utils.unique_combination_of_columns:
              arguments:
                combination_of_columns: [session_key, driver_number, lap_number]
        columns:
          - name: lane_duration
            data_tests:
              # a normal stop is 18–30 s; drive-throughs and red-flag stops are longer
              - dbt_utils.accepted_range:
                  arguments:
                    min_value: 10
                    max_value: 120
                  config:
                    severity: warn

      - name: openf1_position
        description: Every change in running order, with its timestamp.
        columns:
          - name: position
            data_tests:
              - not_null
              - dbt_utils.accepted_range:
                  arguments:
                    min_value: 1
                    max_value: 30

      - name: openf1_weather
        description: Weather at the track about once a minute (not modelled in v1).
        columns:
          - name: session_key
            data_tests: [not_null]

      - name: openf1_race_control
        description: >
          Messages from race control. Many fields are empty by design: `driver_number` only when a
          message concerns one car, `flag`/`scope`/`sector` only for flag messages,
          `qualifying_phase` only in qualifying (never in races).
        columns:
          - name: session_key
            data_tests: [not_null]
          - name: date
            data_tests: [not_null]

      - name: openf1_session_result
        description: Final classification. Position, gap and duration are empty for unclassified drivers (DNF, DNS, DSQ).
        columns:
          - name: position
            data_tests:
              - dbt_utils.accepted_range:
                  arguments:
                    min_value: 1
                    max_value: 30
          - name: points
            data_tests:
              - not_null
              - dbt_utils.accepted_range:
                  arguments:
                    min_value: 0
                    max_value: 30

      - name: openf1_overtakes
        description: Position swaps between two drivers (not modelled in v1).
        columns:
          - name: session_key
            data_tests: [not_null]

      - name: openf1_starting_grid
        description: Starting grid, attached by OpenF1 to the qualifying session that produced it.
        columns:
          - name: position
            data_tests:
              - not_null
              - dbt_utils.accepted_range:
                  arguments:
                    min_value: 1
                    max_value: 30
```

`projects/pitwall/transform/tests/assert_every_race_has_a_full_field.sql`:

```sql
-- A race has 20 cars (22 from 2026). Fewer than 18 drivers with laps means missing data.
{{ config(severity='warn') }}

select
    session_key,
    count(distinct driver_number) as drivers_with_laps
from {{ ref('stg_openf1__laps') }}
group by session_key
having count(distinct driver_number) < 18
```

- [ ] **Step 2: Prove a rule bites (RED on purpose), then restore**

Temporarily change `openf1_session_result.points` `max_value: 30` to `max_value: 10` and run:

Run: `cd projects/pitwall/transform && uv run dbt test --profiles-dir . --select source:openf1.openf1_session_result`
Expected: the `accepted_range` test on `points` FAILS (winners score 25) and `bq ls pitwall-tr-dev:audit` shows a table holding the failing rows. Restore `max_value: 30`.

- [ ] **Step 3: Run all source and data-quality tests**

Run: `uv run dbt test --profiles-dir . --select source:openf1 assert_every_race_has_a_full_field`
Expected: every `error` test passes. Warnings are allowed; list each warning with its row count in the ledger (the 2025 profile predicts: `compound` 1 unknown, possibly `lane_duration` outliers). A failing `error` test is a finding: investigate before relaxing any threshold.

- [ ] **Step 4: Commit**

```bash
git add transform/models/sources.yml transform/tests/assert_every_race_has_a_full_field.sql
git commit -m "feat(pitwall): add data-quality rules on raw OpenF1 tables with audit storage"
```

---

### Task 4: Safety-car laps (`int_neutralised_laps`)

**Files:**
- Create: `projects/pitwall/transform/models/intermediate/int_neutralised_laps.sql`, `models/intermediate/_intermediate.yml`

**Interfaces:**
- Consumes: `stg_openf1__race_control` (session_key, recorded_at, lap_number, category, message), `stg_openf1__laps` (session_key, lap_number).
- Produces: `int_neutralised_laps` — session_key, lap_number, neutralisation (`SC` | `VSC`); grain session × lap × neutralisation.

- [ ] **Step 1: Write the unit tests and the model's YAML**

`projects/pitwall/transform/models/intermediate/_intermediate.yml`:

```yaml
version: 2

models:
  - name: int_neutralised_laps
    description: >
      Grain: one row per session, lap and neutralisation type. A period starts with
      "(VIRTUAL) SAFETY CAR DEPLOYED" and ends on the lap of "SAFETY CAR IN THIS LAP" or
      "VIRTUAL SAFETY CAR ENDING". A period with no end message runs until the lap before the
      next deployment of the same type, or to the session's last lap.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [session_key, lap_number, neutralisation]
    columns:
      - name: session_key
        description: "{{ doc('session_key') }}"
      - name: lap_number
        description: "{{ doc('lap_number') }}"
      - name: neutralisation
        description: "{{ doc('neutralisation') }}"
        data_tests:
          - accepted_values:
              arguments:
                values: [SC, VSC]

unit_tests:
  - name: test_neutralised_laps_pair_starts_with_ends
    model: int_neutralised_laps
    given:
      - input: ref('stg_openf1__race_control')
        rows:
          - {session_key: 1, recorded_at: "2025-03-23 07:20:00", lap_number: 10, category: SafetyCar, message: SAFETY CAR DEPLOYED}
          - {session_key: 1, recorded_at: "2025-03-23 07:24:00", lap_number: 12, category: SafetyCar, message: SAFETY CAR IN THIS LAP}
          - {session_key: 1, recorded_at: "2025-03-23 07:50:00", lap_number: 30, category: SafetyCar, message: VIRTUAL SAFETY CAR DEPLOYED}
          - {session_key: 1, recorded_at: "2025-03-23 07:51:00", lap_number: 30, category: Flag, message: YELLOW IN TRACK SECTOR 2}
      - input: ref('stg_openf1__laps')
        rows:
          - {session_key: 1, lap_number: 32}
    expect:
      rows:
        - {session_key: 1, lap_number: 10, neutralisation: SC}
        - {session_key: 1, lap_number: 11, neutralisation: SC}
        - {session_key: 1, lap_number: 12, neutralisation: SC}
        - {session_key: 1, lap_number: 30, neutralisation: VSC}
        - {session_key: 1, lap_number: 31, neutralisation: VSC}
        - {session_key: 1, lap_number: 32, neutralisation: VSC}

  - name: test_unended_period_stops_before_the_next_one
    model: int_neutralised_laps
    given:
      - input: ref('stg_openf1__race_control')
        rows:
          # first SC has no end message; a second SC is deployed on lap 9 and ends on lap 10
          - {session_key: 2, recorded_at: "2025-03-23 07:10:00", lap_number: 5, category: SafetyCar, message: SAFETY CAR DEPLOYED}
          - {session_key: 2, recorded_at: "2025-03-23 07:20:00", lap_number: 9, category: SafetyCar, message: SAFETY CAR DEPLOYED}
          - {session_key: 2, recorded_at: "2025-03-23 07:23:00", lap_number: 10, category: SafetyCar, message: SAFETY CAR IN THIS LAP}
      - input: ref('stg_openf1__laps')
        rows:
          - {session_key: 2, lap_number: 30}
    expect:
      # laps 5-8 (first period, up to the lap before the next deployment) + 9-10; never 11-30
      rows:
        - {session_key: 2, lap_number: 5, neutralisation: SC}
        - {session_key: 2, lap_number: 6, neutralisation: SC}
        - {session_key: 2, lap_number: 7, neutralisation: SC}
        - {session_key: 2, lap_number: 8, neutralisation: SC}
        - {session_key: 2, lap_number: 9, neutralisation: SC}
        - {session_key: 2, lap_number: 10, neutralisation: SC}
```

Create the model as a stub that returns the right columns and no rows, so the unit tests can compile and fail:

`projects/pitwall/transform/models/intermediate/int_neutralised_laps.sql`:

```sql
-- grain: one row per session, lap and neutralisation type (SC or VSC)
select
    cast(null as int64) as session_key,
    cast(null as int64) as lap_number,
    cast(null as string) as neutralisation
from {{ ref('stg_openf1__race_control') }}
cross join {{ ref('stg_openf1__laps') }}
where false
```

- [ ] **Step 2: Run the unit tests to verify they fail**

Run: `uv run dbt build --profiles-dir . --select int_neutralised_laps`
Expected: both unit tests FAIL (actual has 0 rows, expected 6 each).

- [ ] **Step 3: Implement**

`projects/pitwall/transform/models/intermediate/int_neutralised_laps.sql`:

```sql
-- grain: one row per session, lap and neutralisation type (SC or VSC)
with messages as (
    select
        session_key,
        recorded_at,
        lap_number,
        case message
            when 'SAFETY CAR DEPLOYED' then 'SC'
            when 'VIRTUAL SAFETY CAR DEPLOYED' then 'VSC'
        end as started,
        case message
            when 'SAFETY CAR IN THIS LAP' then 'SC'
            when 'VIRTUAL SAFETY CAR ENDING' then 'VSC'
        end as ended
    from {{ ref('stg_openf1__race_control') }}
    where category = 'SafetyCar'
),

starts as (
    select
        session_key,
        started as neutralisation,
        recorded_at,
        lap_number as first_lap,
        lead(recorded_at) over (
            partition by session_key, started order by recorded_at
        ) as next_start_at,
        lead(lap_number) over (
            partition by session_key, started order by recorded_at
        ) as next_start_lap
    from messages
    where started is not null
),

ends as (
    select session_key, ended as neutralisation, recorded_at, lap_number
    from messages
    where ended is not null
),

last_laps as (
    select session_key, max(lap_number) as last_lap
    from {{ ref('stg_openf1__laps') }}
    group by session_key
),

periods as (
    select
        starts.session_key,
        starts.neutralisation,
        starts.first_lap,
        coalesce(
            min(ends.lap_number),
            any_value(starts.next_start_lap) - 1,
            any_value(last_laps.last_lap)
        ) as last_lap
    from starts
    left join ends
        on ends.session_key = starts.session_key
        and ends.neutralisation = starts.neutralisation
        and ends.recorded_at > starts.recorded_at
        and ends.recorded_at < coalesce(starts.next_start_at, timestamp '9999-12-31')
    left join last_laps
        on last_laps.session_key = starts.session_key
    group by starts.session_key, starts.neutralisation, starts.first_lap, starts.recorded_at
)

select distinct
    periods.session_key,
    lap_number,
    periods.neutralisation
from periods
cross join unnest(generate_array(periods.first_lap, periods.last_lap)) as lap_number
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run dbt build --profiles-dir . --select int_neutralised_laps`
Expected: 2 unit tests PASS, view created, data tests pass.

- [ ] **Step 5: Commit**

```bash
git add transform/models/intermediate
git commit -m "feat(pitwall): derive safety-car and VSC laps from race control"
```

---

### Task 5: Enriched laps (`int_laps_enriched`)

**Files:**
- Create: `projects/pitwall/transform/models/intermediate/int_laps_enriched.sql`
- Modify: `projects/pitwall/transform/models/intermediate/_intermediate.yml`

**Interfaces:**
- Consumes: `stg_openf1__laps`, `stg_openf1__stints`, `stg_openf1__pit`, `stg_openf1__position`, `int_neutralised_laps`.
- Produces: `int_laps_enriched` — session_key, meeting_key, driver_number, lap_number, started_at, ended_at, lap_time_s, sector_1_s, sector_2_s, sector_3_s, speed_trap_kph, stint_number, compound, tyre_age_laps, is_pit_in_lap, is_pit_out_lap, neutralisation, position_end_of_lap, session_median_lap_time_s, is_clean_lap.

- [ ] **Step 1: Append YAML and unit test**

Append under `models:` in `_intermediate.yml`:

```yaml
  - name: int_laps_enriched
    description: >
      Grain: one row per lap of one driver in one session. Each lap carries its tyres (compound,
      tyre age), whether it began or ended in the pits, any safety car, and the running order at
      the end of the lap. A **clean lap** is one that says something about tyre wear: not lap 1,
      not an in- or out-lap, no SC/VSC, has a time, and is no slower than 1.2 × the session's
      median lap (this removes red-flag and damage laps).
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [session_key, driver_number, lap_number]
    columns:
      - name: session_key
        description: "{{ doc('session_key') }}"
      - name: meeting_key
        description: "{{ doc('meeting_key') }}"
      - name: driver_number
        description: "{{ doc('driver_number') }}"
      - name: lap_number
        description: "{{ doc('lap_number') }}"
      - name: started_at
        description: When the lap started (UTC).
      - name: ended_at
        description: When the lap ended (UTC) — start plus lap time, or the next lap's start when either is missing.
      - name: lap_time_s
        description: Lap time in seconds.
      - name: sector_1_s
        description: First-sector time in seconds.
      - name: sector_2_s
        description: Second-sector time in seconds.
      - name: sector_3_s
        description: Third-sector time in seconds.
      - name: speed_trap_kph
        description: Top speed at the speed trap (km/h).
      - name: stint_number
        description: Which set of tyres this lap was driven on (1 = starting set).
      - name: compound
        description: "{{ doc('compound') }}"
      - name: tyre_age_laps
        description: "{{ doc('tyre_age_laps') }}"
      - name: is_pit_in_lap
        description: True if the driver entered the pits at the end of this lap.
      - name: is_pit_out_lap
        description: True if this lap started in the pit lane.
      - name: neutralisation
        description: "{{ doc('neutralisation') }}"
      - name: position_end_of_lap
        description: "{{ doc('position') }}"
      - name: session_median_lap_time_s
        description: Median lap time of the whole session, used to spot abnormally slow laps.
      - name: is_clean_lap
        description: True when the lap is representative of tyre performance (see model description).
```

Append under `unit_tests:`:

```yaml
  - name: test_laps_get_tyres_pits_positions_and_clean_flag
    model: int_laps_enriched
    given:
      - input: ref('stg_openf1__laps')
        rows:
          - {session_key: 1, meeting_key: 9, driver_number: 4, lap_number: 1, started_at: "2025-03-23 07:00:00", lap_time_s: 90.0, is_pit_out_lap: false}
          - {session_key: 1, meeting_key: 9, driver_number: 4, lap_number: 2, started_at: "2025-03-23 07:01:30", lap_time_s: 91.0, is_pit_out_lap: false}
          - {session_key: 1, meeting_key: 9, driver_number: 4, lap_number: 3, started_at: "2025-03-23 07:03:01", lap_time_s: 110.0, is_pit_out_lap: true}
          - {session_key: 1, meeting_key: 9, driver_number: 4, lap_number: 4, started_at: null, lap_time_s: 91.0, is_pit_out_lap: false}
          - {session_key: 1, meeting_key: 9, driver_number: 4, lap_number: 5, started_at: "2025-03-23 07:06:22", lap_time_s: 91.5, is_pit_out_lap: false}
      - input: ref('stg_openf1__stints')
        rows:
          - {session_key: 1, driver_number: 4, stint_number: 1, first_lap: 1, last_lap: 2, compound: MEDIUM, tyre_age_at_start: 3}
          - {session_key: 1, driver_number: 4, stint_number: 2, first_lap: 3, last_lap: 5, compound: HARD, tyre_age_at_start: 0}
      - input: ref('stg_openf1__pit')
        rows:
          - {session_key: 1, driver_number: 4, lap_number: 2}
      - input: ref('stg_openf1__position')
        rows:
          - {session_key: 1, driver_number: 4, recorded_at: "2025-03-23 07:00:05", position: 3}
          - {session_key: 1, driver_number: 4, recorded_at: "2025-03-23 07:02:00", position: 5}
          - {session_key: 1, driver_number: 4, recorded_at: "2025-03-23 07:04:00", position: 4}
      - input: ref('int_neutralised_laps')
        rows:
          - {session_key: 1, lap_number: 5, neutralisation: VSC}
    expect:
      rows:
        - {lap_number: 1, compound: MEDIUM, tyre_age_laps: 3, is_pit_in_lap: false, position_end_of_lap: 3, neutralisation: null, is_clean_lap: false}
        - {lap_number: 2, compound: MEDIUM, tyre_age_laps: 4, is_pit_in_lap: true, position_end_of_lap: 5, neutralisation: null, is_clean_lap: false}
        - {lap_number: 3, compound: HARD, tyre_age_laps: 0, is_pit_in_lap: false, position_end_of_lap: 4, neutralisation: null, is_clean_lap: false}
        - {lap_number: 4, compound: HARD, tyre_age_laps: 1, is_pit_in_lap: false, position_end_of_lap: 4, neutralisation: null, is_clean_lap: true}
        - {lap_number: 5, compound: HARD, tyre_age_laps: 2, is_pit_in_lap: false, position_end_of_lap: 4, neutralisation: VSC, is_clean_lap: false}
```

Why these rows: lap 1 is never clean; lap 2 is the in-lap; lap 3 the out-lap; lap 4 has **no start time** (Review Focus 2) so its end falls back to lap 5's start and still gets position 4; lap 5 is under VSC. Median of 90, 91, 110, 91, 91.5 is 91, so 110 would also fail the 1.2 × median rule.

Stub model so the test compiles:

```sql
-- grain: one row per lap of one driver in one session
select
    laps.session_key, laps.meeting_key, laps.driver_number, laps.lap_number,
    laps.started_at, cast(null as timestamp) as ended_at, laps.lap_time_s,
    laps.sector_1_s, laps.sector_2_s, laps.sector_3_s, laps.speed_trap_kph,
    cast(null as int64) as stint_number, cast(null as string) as compound,
    cast(null as int64) as tyre_age_laps, false as is_pit_in_lap, laps.is_pit_out_lap,
    cast(null as string) as neutralisation, cast(null as int64) as position_end_of_lap,
    cast(null as float64) as session_median_lap_time_s, false as is_clean_lap
from {{ ref('stg_openf1__laps') }} as laps
cross join {{ ref('stg_openf1__stints') }} as stints
cross join {{ ref('stg_openf1__pit') }} as pits
cross join {{ ref('stg_openf1__position') }} as positions
cross join {{ ref('int_neutralised_laps') }} as neutralised
where false
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run dbt build --profiles-dir . --select int_laps_enriched`
Expected: unit test FAILS (0 rows vs 5).

- [ ] **Step 3: Implement**

`projects/pitwall/transform/models/intermediate/int_laps_enriched.sql`:

```sql
-- grain: one row per lap of one driver in one session
with laps as (
    select * from {{ ref('stg_openf1__laps') }}
),

stints as (
    select * from {{ ref('stg_openf1__stints') }}
),

pits as (
    select session_key, driver_number, lap_number from {{ ref('stg_openf1__pit') }}
),

positions as (
    select session_key, driver_number, recorded_at, position
    from {{ ref('stg_openf1__position') }}
),

neutralised as (
    -- a lap can see a VSC turn into an SC: the SC wins
    select
        session_key,
        lap_number,
        if(countif(neutralisation = 'SC') > 0, 'SC', 'VSC') as neutralisation
    from {{ ref('int_neutralised_laps') }}
    group by session_key, lap_number
),

timed as (
    select
        laps.*,
        coalesce(
            timestamp_add(
                laps.started_at, interval cast(round(laps.lap_time_s * 1000) as int64) millisecond
            ),
            lead(laps.started_at) over (
                partition by laps.session_key, laps.driver_number order by laps.lap_number
            )
        ) as ended_at
    from laps
),

lap_positions as (
    select
        timed.session_key,
        timed.driver_number,
        timed.lap_number,
        positions.position
    from timed
    inner join positions
        on positions.session_key = timed.session_key
        and positions.driver_number = timed.driver_number
        and positions.recorded_at <= timed.ended_at
    where true
    qualify row_number() over (
        partition by timed.session_key, timed.driver_number, timed.lap_number
        order by positions.recorded_at desc
    ) = 1
),

enriched as (
    select
        timed.session_key,
        timed.meeting_key,
        timed.driver_number,
        timed.lap_number,
        timed.started_at,
        timed.ended_at,
        timed.lap_time_s,
        timed.sector_1_s,
        timed.sector_2_s,
        timed.sector_3_s,
        timed.speed_trap_kph,
        stints.stint_number,
        stints.compound,
        stints.tyre_age_at_start + (timed.lap_number - stints.first_lap) as tyre_age_laps,
        pits.lap_number is not null as is_pit_in_lap,
        timed.is_pit_out_lap,
        neutralised.neutralisation,
        lap_positions.position as position_end_of_lap,
        percentile_cont(timed.lap_time_s, 0.5) over (
            partition by timed.session_key
        ) as session_median_lap_time_s
    from timed
    left join stints
        on stints.session_key = timed.session_key
        and stints.driver_number = timed.driver_number
        and timed.lap_number between stints.first_lap and stints.last_lap
    left join pits
        on pits.session_key = timed.session_key
        and pits.driver_number = timed.driver_number
        and pits.lap_number = timed.lap_number
    left join neutralised
        on neutralised.session_key = timed.session_key
        and neutralised.lap_number = timed.lap_number
    left join lap_positions
        on lap_positions.session_key = timed.session_key
        and lap_positions.driver_number = timed.driver_number
        and lap_positions.lap_number = timed.lap_number
    where true
    -- overlapping stints in the source must not duplicate a lap: keep the later stint
    qualify row_number() over (
        partition by timed.session_key, timed.driver_number, timed.lap_number
        order by stints.stint_number desc
    ) = 1
)

select
    *,
    (
        lap_number > 1
        and lap_time_s is not null
        and not is_pit_in_lap
        and not is_pit_out_lap
        and neutralisation is null
        and lap_time_s <= 1.2 * session_median_lap_time_s
    ) as is_clean_lap
from enriched
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run dbt build --profiles-dir . --select int_laps_enriched`
Expected: unit test PASSES; view created; grain test passes on real data.

- [ ] **Step 5: Commit**

```bash
git add transform/models/intermediate
git commit -m "feat(pitwall): enrich laps with tyres, pit flags, positions and clean-lap rule"
```

---

### Task 6: Dimensions, laps and results marts

**Files:**
- Create: `projects/pitwall/transform/models/marts/dim_sessions.sql`, `dim_meetings.sql`, `dim_session_drivers.sql`, `fct_laps.sql`, `fct_session_results.sql`, `models/marts/_marts.yml`

**Interfaces:**
- Consumes: staging models (Task 2), `int_laps_enriched` (Task 4).
- Produces:
  - `dim_sessions`: session_key, meeting_key, session_name, season, starts_at, ends_at, circuit_short_name, country_name
  - `dim_meetings`: meeting_key, meeting_name, meeting_official_name, season, country_name, location, circuit_short_name, circuit_type, starts_at, ends_at
  - `dim_session_drivers`: session_key, driver_number, full_name, name_acronym, team_name, team_colour_hex
  - `fct_laps`: every `int_laps_enriched` column except `session_median_lap_time_s`
  - `fct_session_results`: session_key, meeting_key, driver_number, grid_position, finish_position, positions_gained, points, laps_completed, did_not_finish, did_not_start, disqualified, gap_to_leader

- [ ] **Step 1: YAML with tests and the grid unit test**

`projects/pitwall/transform/models/marts/_marts.yml`:

```yaml
version: 2

models:
  - name: dim_sessions
    description: "Grain: one row per Race or Sprint session that has lap data. The races pitwall analyses."
    columns:
      - name: session_key
        description: "{{ doc('session_key') }}"
        data_tests: [unique, not_null]
      - name: meeting_key
        description: "{{ doc('meeting_key') }}"
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_meetings')
                field: meeting_key
      - name: session_name
        description: '"Race" (Sunday, full distance) or "Sprint" (Saturday, about a third of the distance, no mandatory pit stop).'
        data_tests:
          - accepted_values:
              arguments:
                values: [Race, Sprint]
      - name: season
        description: Championship year.
      - name: starts_at
        description: Start time (UTC).
      - name: ends_at
        description: End time (UTC).
      - name: circuit_short_name
        description: Short circuit name.
      - name: country_name
        description: Host country.

  - name: dim_meetings
    description: "Grain: one row per race weekend with at least one analysed race."
    columns:
      - name: meeting_key
        description: "{{ doc('meeting_key') }}"
        data_tests: [unique, not_null]
      - name: meeting_name
        description: Short name, e.g. "Chinese Grand Prix".
      - name: meeting_official_name
        description: Full sponsored name.
      - name: season
        description: Championship year.
      - name: country_name
        description: Host country.
      - name: location
        description: City or area.
      - name: circuit_short_name
        description: Short circuit name.
      - name: circuit_type
        description: Permanent track or temporary street circuit.
      - name: starts_at
        description: Weekend start (UTC).
      - name: ends_at
        description: Weekend end (UTC).

  - name: dim_session_drivers
    description: "Grain: one row per driver per session. Drivers change teams between seasons, so team belongs to the session."
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [session_key, driver_number]
    columns:
      - name: session_key
        description: "{{ doc('session_key') }}"
        data_tests:
          - relationships:
              arguments:
                to: ref('dim_sessions')
                field: session_key
      - name: driver_number
        description: "{{ doc('driver_number') }}"
      - name: full_name
        description: Driver's name.
      - name: name_acronym
        description: Three-letter timing code.
      - name: team_name
        description: Team in this session.
      - name: team_colour_hex
        description: Team colour for charts.

  - name: fct_laps
    description: "Grain: one row per lap of one driver in one Race or Sprint. See int_laps_enriched for the clean-lap rule."
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [session_key, driver_number, lap_number]
    columns:
      - name: session_key
        description: "{{ doc('session_key') }}"
        data_tests:
          - relationships:
              arguments:
                to: ref('dim_sessions')
                field: session_key
      - name: meeting_key
        description: "{{ doc('meeting_key') }}"
      - name: driver_number
        description: "{{ doc('driver_number') }}"
      - name: lap_number
        description: "{{ doc('lap_number') }}"
      - name: started_at
        description: Lap start (UTC).
      - name: ended_at
        description: Lap end (UTC).
      - name: lap_time_s
        description: Lap time in seconds.
      - name: sector_1_s
        description: First-sector time in seconds.
      - name: sector_2_s
        description: Second-sector time in seconds.
      - name: sector_3_s
        description: Third-sector time in seconds.
      - name: speed_trap_kph
        description: Speed-trap speed (km/h).
      - name: stint_number
        description: Set of tyres this lap was driven on.
      - name: compound
        description: "{{ doc('compound') }}"
      - name: tyre_age_laps
        description: "{{ doc('tyre_age_laps') }}"
      - name: is_pit_in_lap
        description: Lap ends in the pits.
      - name: is_pit_out_lap
        description: Lap starts in the pit lane.
      - name: neutralisation
        description: "{{ doc('neutralisation') }}"
      - name: position_end_of_lap
        description: "{{ doc('position') }}"
      - name: is_clean_lap
        description: Representative of tyre performance (no pits, no safety car, no outlier).

  - name: fct_session_results
    description: "Grain: one row per driver per Race or Sprint: where they started, where they finished."
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [session_key, driver_number]
    columns:
      - name: session_key
        description: "{{ doc('session_key') }}"
        data_tests:
          - relationships:
              arguments:
                to: ref('dim_sessions')
                field: session_key
      - name: meeting_key
        description: "{{ doc('meeting_key') }}"
      - name: driver_number
        description: "{{ doc('driver_number') }}"
      - name: grid_position
        description: Starting position (1 = pole). Empty if the driver started from the pit lane or no grid was published.
      - name: finish_position
        description: Classified finishing position; empty if not classified.
      - name: positions_gained
        description: Grid position minus finishing position — positive means the driver moved forward.
      - name: points
        description: Championship points scored.
      - name: laps_completed
        description: Laps completed.
      - name: did_not_finish
        description: Retired from the race (DNF).
      - name: did_not_start
        description: Did not start (DNS).
      - name: disqualified
        description: Disqualified (DSQ).
      - name: gap_to_leader
        description: Gap to the winner — seconds or "+N LAP(S)".

unit_tests:
  - name: test_grids_map_to_their_race
    model: fct_session_results
    given:
      - input: ref('stg_openf1__session_result')
        rows:
          - {session_key: 11, meeting_key: 1, driver_number: 4, finish_position: 1}
          - {session_key: 12, meeting_key: 1, driver_number: 4, finish_position: 3}
          - {session_key: 21, meeting_key: 2, driver_number: 4, finish_position: 2}
      - input: ref('stg_openf1__starting_grid')
        rows:
          - {qualifying_session_key: 13, meeting_key: 1, driver_number: 4, grid_position: 5}
          - {qualifying_session_key: 14, meeting_key: 1, driver_number: 4, grid_position: 2}
          - {qualifying_session_key: 23, meeting_key: 2, driver_number: 4, grid_position: 7}
      - input: ref('stg_openf1__sessions')
        rows:
          - {session_key: 11, meeting_key: 1, session_type: Race, session_name: Race}
          - {session_key: 12, meeting_key: 1, session_type: Race, session_name: Sprint}
          - {session_key: 13, meeting_key: 1, session_type: Qualifying, session_name: Qualifying}
          - {session_key: 14, meeting_key: 1, session_type: Qualifying, session_name: Sprint Qualifying}
          - {session_key: 21, meeting_key: 2, session_type: Race, session_name: Sprint}
          - {session_key: 23, meeting_key: 2, session_type: Qualifying, session_name: Sprint Shootout}
    expect:
      rows:
        - {session_key: 11, driver_number: 4, grid_position: 5, finish_position: 1, positions_gained: 4}
        - {session_key: 12, driver_number: 4, grid_position: 2, finish_position: 3, positions_gained: -1}
        - {session_key: 21, driver_number: 4, grid_position: 7, finish_position: 2, positions_gained: 5}
```

Stub `fct_session_results.sql` so the unit test compiles:

```sql
-- grain: one row per driver per Race or Sprint session
select
    results.session_key, results.meeting_key, results.driver_number,
    cast(null as int64) as grid_position, results.finish_position,
    cast(null as int64) as positions_gained, results.points, results.laps_completed,
    results.did_not_finish, results.did_not_start, results.disqualified, results.gap_to_leader
from {{ ref('stg_openf1__session_result') }} as results
cross join {{ ref('stg_openf1__starting_grid') }} as grid
cross join {{ ref('stg_openf1__sessions') }} as sessions
where false
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run dbt build --profiles-dir . --select fct_session_results`
Expected: unit test FAILS (0 rows vs 3).

- [ ] **Step 3: Implement the five models**

`dim_sessions.sql`:

```sql
-- grain: one row per Race or Sprint session with lap data
with sessions as (
    select * from {{ ref('stg_openf1__sessions') }}
),

sessions_with_laps as (
    select distinct session_key from {{ ref('stg_openf1__laps') }}
)

select
    sessions.session_key,
    sessions.meeting_key,
    sessions.session_name,
    sessions.season,
    sessions.starts_at,
    sessions.ends_at,
    sessions.circuit_short_name,
    sessions.country_name
from sessions
inner join sessions_with_laps
    on sessions_with_laps.session_key = sessions.session_key
where sessions.session_type = 'Race'
    and not sessions.is_cancelled
```

`dim_meetings.sql`:

```sql
-- grain: one row per race weekend with at least one analysed race
with meetings as (
    select * from {{ ref('stg_openf1__meetings') }}
),

analysed as (
    select distinct meeting_key from {{ ref('dim_sessions') }}
)

select
    meetings.meeting_key,
    meetings.meeting_name,
    meetings.meeting_official_name,
    meetings.season,
    meetings.country_name,
    meetings.location,
    meetings.circuit_short_name,
    meetings.circuit_type,
    meetings.starts_at,
    meetings.ends_at
from meetings
inner join analysed
    on analysed.meeting_key = meetings.meeting_key
```

`dim_session_drivers.sql`:

```sql
-- grain: one row per driver per Race or Sprint session
select
    drivers.session_key,
    drivers.driver_number,
    drivers.full_name,
    drivers.name_acronym,
    drivers.team_name,
    drivers.team_colour_hex
from {{ ref('stg_openf1__drivers') }} as drivers
inner join {{ ref('dim_sessions') }} as sessions
    on sessions.session_key = drivers.session_key
```

`fct_laps.sql`:

```sql
-- grain: one row per lap of one driver in one Race or Sprint session
select
    laps.session_key,
    laps.meeting_key,
    laps.driver_number,
    laps.lap_number,
    laps.started_at,
    laps.ended_at,
    laps.lap_time_s,
    laps.sector_1_s,
    laps.sector_2_s,
    laps.sector_3_s,
    laps.speed_trap_kph,
    laps.stint_number,
    laps.compound,
    laps.tyre_age_laps,
    laps.is_pit_in_lap,
    laps.is_pit_out_lap,
    laps.neutralisation,
    laps.position_end_of_lap,
    laps.is_clean_lap
from {{ ref('int_laps_enriched') }} as laps
inner join {{ ref('dim_sessions') }} as sessions
    on sessions.session_key = laps.session_key
```

`fct_session_results.sql`:

```sql
-- grain: one row per driver per Race or Sprint session
with results as (
    select * from {{ ref('stg_openf1__session_result') }}
),

grid as (
    select * from {{ ref('stg_openf1__starting_grid') }}
),

sessions as (
    select * from {{ ref('stg_openf1__sessions') }}
),

grid_by_race as (
    -- OpenF1 attaches each grid to the qualifying session that produced it
    select
        race.session_key,
        grid.driver_number,
        grid.grid_position
    from grid
    inner join sessions as quali
        on quali.session_key = grid.qualifying_session_key
    inner join sessions as race
        on race.meeting_key = quali.meeting_key
        and race.session_type = 'Race'
        and race.session_name = case quali.session_name
            when 'Qualifying' then 'Race'
            when 'Sprint Qualifying' then 'Sprint'
            when 'Sprint Shootout' then 'Sprint'
        end
)

select
    results.session_key,
    results.meeting_key,
    results.driver_number,
    grid_by_race.grid_position,
    results.finish_position,
    grid_by_race.grid_position - results.finish_position as positions_gained,
    results.points,
    results.laps_completed,
    results.did_not_finish,
    results.did_not_start,
    results.disqualified,
    results.gap_to_leader
from results
left join grid_by_race
    on grid_by_race.session_key = results.session_key
    and grid_by_race.driver_number = results.driver_number
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run dbt build --profiles-dir . --select +dim_sessions +dim_meetings +dim_session_drivers +fct_laps +fct_session_results`
Expected: unit test PASSES; five tables created; all data tests pass.

- [ ] **Step 5: Commit**

```bash
git add transform/models/marts
git commit -m "feat(pitwall): add session, meeting and driver dimensions, laps and results facts"
```

---

### Task 7: Stints and pit stops (`fct_stints`, `fct_pit_stops`)

**Files:**
- Create: `projects/pitwall/transform/models/marts/fct_stints.sql`, `fct_pit_stops.sql`, `transform/tests/assert_clean_lap_times_are_plausible.sql`
- Modify: `projects/pitwall/transform/models/marts/_marts.yml`

**Interfaces:**
- Consumes: `stg_openf1__stints`, `stg_openf1__pit`, `int_laps_enriched`.
- Produces:
  - `fct_stints`: session_key, meeting_key, driver_number, stint_number, compound, first_lap, last_lap, laps_in_stint, tyre_age_at_start, clean_laps, mean_clean_lap_time_s, degradation_s_per_lap
  - `fct_pit_stops`: session_key, meeting_key, driver_number, lap_number, pit_lane_time_s, stationary_time_s, source, compound_before, compound_after, position_before, position_after, is_under_neutralisation

- [ ] **Step 1: YAML, unit tests, stubs**

Append under `models:` in `_marts.yml`:

```yaml
  - name: fct_stints
    description: >
      Grain: one row per stint — one driver on one set of tyres in one race. **Degradation** is how
      many seconds slower each extra lap on these tyres gets: the slope of a straight line fitted
      through clean lap times against tyre age. It needs at least 5 clean laps; otherwise it is
      empty. Limitation: cars also get lighter as fuel burns (about 0.03–0.06 s per lap faster),
      which hides part of the tyre wear, so real degradation is a little higher than shown.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [session_key, driver_number, stint_number]
    columns:
      - name: session_key
        description: "{{ doc('session_key') }}"
      - name: meeting_key
        description: "{{ doc('meeting_key') }}"
      - name: driver_number
        description: "{{ doc('driver_number') }}"
      - name: stint_number
        description: 1 for the starting tyres, 2 after the first stop, and so on.
      - name: compound
        description: "{{ doc('compound') }}"
      - name: first_lap
        description: First lap on these tyres.
      - name: last_lap
        description: Last lap on these tyres.
      - name: laps_in_stint
        description: Number of laps driven on these tyres.
      - name: tyre_age_at_start
        description: Laps the tyres had already done when the stint began.
      - name: clean_laps
        description: Laps in the stint that count for degradation (see int_laps_enriched).
      - name: mean_clean_lap_time_s
        description: Average clean lap time in seconds.
      - name: degradation_s_per_lap
        description: Seconds lost per extra lap of tyre age. Empty with fewer than 5 clean laps.

  - name: fct_pit_stops
    description: >
      Grain: one row per pit stop. When a race has no pit data at all (some 2023 races), stops are
      inferred from tyre changes: the last lap of each stint that is followed by another stint.
      Those rows have source "stint_change" and no durations.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [session_key, driver_number, lap_number]
    columns:
      - name: session_key
        description: "{{ doc('session_key') }}"
      - name: meeting_key
        description: "{{ doc('meeting_key') }}"
      - name: driver_number
        description: "{{ doc('driver_number') }}"
      - name: lap_number
        description: Lap on which the driver came into the pits (the in-lap).
      - name: pit_lane_time_s
        description: Seconds from pit entry to pit exit.
      - name: stationary_time_s
        description: Seconds the car stood still (2025 onwards).
      - name: source
        description: '"pit" when OpenF1 recorded the stop, "stint_change" when inferred from a tyre change.'
        data_tests:
          - accepted_values:
              arguments:
                values: [pit, stint_change]
      - name: compound_before
        description: Tyres the driver came in on.
      - name: compound_after
        description: Tyres the driver left on. Empty for stops without a tyre change (e.g. a penalty).
      - name: position_before
        description: Running order at the end of the lap before the stop.
      - name: position_after
        description: Running order at the end of the lap after the stop (the out-lap).
      - name: is_under_neutralisation
        description: True if the driver pitted under the Safety Car or VSC, when a stop costs less time.
```

Append under `unit_tests:`:

```yaml
  - name: test_degradation_is_the_slope_of_clean_laps  # also: invalid stint 3 never reaches the mart
    model: fct_stints
    given:
      - input: ref('stg_openf1__stints')
        rows:
          - {session_key: 1, meeting_key: 9, driver_number: 4, stint_number: 1, compound: MEDIUM, first_lap: 2, last_lap: 8, tyre_age_at_start: 0, has_valid_lap_range: true}
          - {session_key: 1, meeting_key: 9, driver_number: 4, stint_number: 2, compound: HARD, first_lap: 9, last_lap: 12, tyre_age_at_start: 0, has_valid_lap_range: true}
          - {session_key: 1, meeting_key: 9, driver_number: 4, stint_number: 3, compound: SOFT, first_lap: null, last_lap: null, tyre_age_at_start: 0, has_valid_lap_range: false}
      - input: ref('int_laps_enriched')
        rows:
          - {session_key: 1, driver_number: 4, stint_number: 1, lap_number: 2, tyre_age_laps: 0, lap_time_s: 95.0, is_clean_lap: false}
          - {session_key: 1, driver_number: 4, stint_number: 1, lap_number: 3, tyre_age_laps: 1, lap_time_s: 90.1, is_clean_lap: true}
          - {session_key: 1, driver_number: 4, stint_number: 1, lap_number: 4, tyre_age_laps: 2, lap_time_s: 90.2, is_clean_lap: true}
          - {session_key: 1, driver_number: 4, stint_number: 1, lap_number: 5, tyre_age_laps: 3, lap_time_s: 90.3, is_clean_lap: true}
          - {session_key: 1, driver_number: 4, stint_number: 1, lap_number: 6, tyre_age_laps: 4, lap_time_s: 90.4, is_clean_lap: true}
          - {session_key: 1, driver_number: 4, stint_number: 1, lap_number: 7, tyre_age_laps: 5, lap_time_s: 90.5, is_clean_lap: true}
          - {session_key: 1, driver_number: 4, stint_number: 1, lap_number: 8, tyre_age_laps: 6, lap_time_s: 130.0, is_clean_lap: false}
          - {session_key: 1, driver_number: 4, stint_number: 2, lap_number: 10, tyre_age_laps: 1, lap_time_s: 91.0, is_clean_lap: true}
          - {session_key: 1, driver_number: 4, stint_number: 2, lap_number: 11, tyre_age_laps: 2, lap_time_s: 91.2, is_clean_lap: true}
    expect:
      rows:
        - {stint_number: 1, laps_in_stint: 7, clean_laps: 5, mean_clean_lap_time_s: 90.3, degradation_s_per_lap: 0.1}
        - {stint_number: 2, laps_in_stint: 4, clean_laps: 2, mean_clean_lap_time_s: 91.1, degradation_s_per_lap: null}

  - name: test_pit_stops_fall_back_to_tyre_changes
    model: fct_pit_stops
    given:
      - input: ref('stg_openf1__pit')
        rows:
          - {session_key: 1, meeting_key: 9, driver_number: 4, lap_number: 20, pit_lane_time_s: 21.5, stationary_time_s: 2.4}
      - input: ref('stg_openf1__stints')
        rows:
          - {session_key: 1, meeting_key: 9, driver_number: 4, stint_number: 1, compound: MEDIUM, first_lap: 1, last_lap: 20}
          - {session_key: 1, meeting_key: 9, driver_number: 4, stint_number: 2, compound: HARD, first_lap: 21, last_lap: 50}
          - {session_key: 2, meeting_key: 8, driver_number: 4, stint_number: 1, compound: SOFT, first_lap: 1, last_lap: 15}
          - {session_key: 2, meeting_key: 8, driver_number: 4, stint_number: 2, compound: HARD, first_lap: 16, last_lap: 57}
      - input: ref('int_laps_enriched')
        rows:
          - {session_key: 1, driver_number: 4, lap_number: 19, position_end_of_lap: 2, neutralisation: null}
          - {session_key: 1, driver_number: 4, lap_number: 20, position_end_of_lap: 2, neutralisation: SC}
          - {session_key: 1, driver_number: 4, lap_number: 21, position_end_of_lap: 6, neutralisation: SC}
    expect:
      rows:
        - {session_key: 1, lap_number: 20, source: pit, compound_before: MEDIUM, compound_after: HARD, position_before: 2, position_after: 6, is_under_neutralisation: true}
        - {session_key: 2, lap_number: 15, source: stint_change, compound_before: SOFT, compound_after: HARD, position_before: null, position_after: null, is_under_neutralisation: false}
```

Stub `fct_stints.sql`:

```sql
-- grain: one row per stint
select
    stints.session_key, stints.meeting_key, stints.driver_number, stints.stint_number,
    stints.compound, stints.first_lap, stints.last_lap, cast(null as int64) as laps_in_stint,
    stints.tyre_age_at_start, cast(null as int64) as clean_laps,
    cast(null as float64) as mean_clean_lap_time_s, cast(null as float64) as degradation_s_per_lap
from {{ ref('stg_openf1__stints') }} as stints
cross join {{ ref('int_laps_enriched') }} as laps
where false
```

Stub `fct_pit_stops.sql`:

```sql
-- grain: one row per pit stop
select
    pits.session_key, pits.meeting_key, pits.driver_number, pits.lap_number,
    pits.pit_lane_time_s, pits.stationary_time_s, cast(null as string) as source,
    cast(null as string) as compound_before, cast(null as string) as compound_after,
    cast(null as int64) as position_before, cast(null as int64) as position_after,
    false as is_under_neutralisation
from {{ ref('stg_openf1__pit') }} as pits
cross join {{ ref('stg_openf1__stints') }} as stints
cross join {{ ref('int_laps_enriched') }} as laps
where false
```

`projects/pitwall/transform/tests/assert_clean_lap_times_are_plausible.sql`:

```sql
-- Clean F1 race laps take between about 65 s (Austria) and 110 s (Monaco in traffic, Las Vegas).
{{ config(severity='warn') }}

select session_key, driver_number, lap_number, lap_time_s
from {{ ref('fct_laps') }}
where is_clean_lap
    and (lap_time_s < 60 or lap_time_s > 200)
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run dbt build --profiles-dir . --select fct_stints fct_pit_stops`
Expected: both unit tests FAIL (0 rows vs 2).

- [ ] **Step 3: Implement**

`fct_stints.sql`:

```sql
-- grain: one row per stint (one driver on one set of tyres in one session)
with stints as (
    select * from {{ ref('stg_openf1__stints') }}
),

clean_laps as (
    select
        session_key,
        driver_number,
        stint_number,
        count(*) as clean_laps,
        avg(lap_time_s) as mean_clean_lap_time_s,
        -- least-squares slope of lap time against tyre age
        covar_samp(lap_time_s, tyre_age_laps) / nullif(var_samp(tyre_age_laps), 0) as slope
    from {{ ref('int_laps_enriched') }}
    where is_clean_lap
    group by session_key, driver_number, stint_number
)

select
    stints.session_key,
    stints.meeting_key,
    stints.driver_number,
    stints.stint_number,
    stints.compound,
    stints.first_lap,
    stints.last_lap,
    stints.last_lap - stints.first_lap + 1 as laps_in_stint,
    stints.tyre_age_at_start,
    coalesce(clean_laps.clean_laps, 0) as clean_laps,
    round(clean_laps.mean_clean_lap_time_s, 3) as mean_clean_lap_time_s,
    if(clean_laps.clean_laps >= 5, round(clean_laps.slope, 4), null) as degradation_s_per_lap
from stints
left join clean_laps
    on clean_laps.session_key = stints.session_key
    and clean_laps.driver_number = stints.driver_number
    and clean_laps.stint_number = stints.stint_number
where stints.has_valid_lap_range -- invalid ranges stay in staging and in the audit warning
```

`fct_pit_stops.sql`:

```sql
-- grain: one row per pit stop
with pits as (
    select * from {{ ref('stg_openf1__pit') }}
),

stints as (
    select * from {{ ref('stg_openf1__stints') }}
),

laps as (
    select session_key, driver_number, lap_number, position_end_of_lap, neutralisation
    from {{ ref('int_laps_enriched') }}
),

sessions_with_pit_data as (
    select distinct session_key from pits
),

inferred as (
    -- no pit data for the whole session (e.g. some 2023 races): a tyre change means a stop
    select
        this_stint.session_key,
        this_stint.meeting_key,
        this_stint.driver_number,
        this_stint.last_lap as lap_number
    from stints as this_stint
    inner join stints as next_stint
        on next_stint.session_key = this_stint.session_key
        and next_stint.driver_number = this_stint.driver_number
        and next_stint.stint_number = this_stint.stint_number + 1
    where this_stint.session_key not in (select session_key from sessions_with_pit_data)
),

stops as (
    select
        session_key, meeting_key, driver_number, lap_number,
        pit_lane_time_s, stationary_time_s, 'pit' as source
    from pits
    union all
    select
        session_key, meeting_key, driver_number, lap_number,
        cast(null as float64), cast(null as float64), 'stint_change'
    from inferred
)

select
    stops.session_key,
    stops.meeting_key,
    stops.driver_number,
    stops.lap_number,
    stops.pit_lane_time_s,
    stops.stationary_time_s,
    stops.source,
    before_stop.compound as compound_before,
    after_stop.compound as compound_after,
    lap_before.position_end_of_lap as position_before,
    lap_after.position_end_of_lap as position_after,
    in_lap.neutralisation is not null as is_under_neutralisation
from stops
left join stints as before_stop
    on before_stop.session_key = stops.session_key
    and before_stop.driver_number = stops.driver_number
    and stops.lap_number between before_stop.first_lap and before_stop.last_lap
left join stints as after_stop
    on after_stop.session_key = stops.session_key
    and after_stop.driver_number = stops.driver_number
    and after_stop.first_lap = stops.lap_number + 1
left join laps as lap_before
    on lap_before.session_key = stops.session_key
    and lap_before.driver_number = stops.driver_number
    and lap_before.lap_number = stops.lap_number - 1
left join laps as lap_after
    on lap_after.session_key = stops.session_key
    and lap_after.driver_number = stops.driver_number
    and lap_after.lap_number = stops.lap_number + 1
left join laps as in_lap
    on in_lap.session_key = stops.session_key
    and in_lap.driver_number = stops.driver_number
    and in_lap.lap_number = stops.lap_number
where true
qualify row_number() over (
    partition by stops.session_key, stops.driver_number, stops.lap_number
    order by before_stop.stint_number desc, after_stop.stint_number
) = 1
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run dbt build --profiles-dir . --select fct_stints fct_pit_stops assert_clean_lap_times_are_plausible`
Expected: both unit tests PASS; tables built; grain and accepted-values tests pass; the plausibility test passes or warns (report its row count).

- [ ] **Step 5: Commit**

```bash
git add transform/models/marts transform/tests
git commit -m "feat(pitwall): add stint degradation and pit stops with tyre-change fallback"
```

---

### Task 8: Undercut attempts (`fct_undercut_attempts`)

**Files:**
- Create: `projects/pitwall/transform/models/marts/fct_undercut_attempts.sql`
- Modify: `projects/pitwall/transform/models/marts/_marts.yml`

**Interfaces:**
- Consumes: `int_laps_enriched` (session_key, driver_number, lap_number, position_end_of_lap), `fct_pit_stops` (session_key, driver_number, lap_number, is_under_neutralisation).
- Produces: `fct_undercut_attempts` — session_key, attacker_driver_number, defender_driver_number, attacker_pit_lap, defender_pit_lap, comparison_lap, attacker_position_before, attacker_position_after, defender_position_after, is_success, attacker_pitted_under_neutralisation.

- [ ] **Step 1: YAML, unit test, stub**

Append under `models:`:

```yaml
  - name: fct_undercut_attempts
    description: >
      Grain: one row per pit stop that is an undercut attempt. The **undercut**: pit before the
      car directly ahead, use the grip of new tyres to go faster, and be in front once they pit
      too. Definition: driver A pits on lap n while running directly behind driver B at the end
      of lap n−1; B pits on lap n+1, n+2 or n+3. **Success** means A is ahead of B at the end of
      B's out-lap (B's pit lap + 1), the first lap both have completed their stops. Limitations:
      time gaps are ignored, and stops under a Safety Car (flagged) are not a real undercut.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [session_key, attacker_driver_number, attacker_pit_lap]
    columns:
      - name: session_key
        description: "{{ doc('session_key') }}"
      - name: attacker_driver_number
        description: Driver who pitted first, trying the undercut.
      - name: defender_driver_number
        description: Driver directly ahead who responded by pitting within 3 laps.
      - name: attacker_pit_lap
        description: Lap on which the attacker pitted.
      - name: defender_pit_lap
        description: Lap on which the defender pitted.
      - name: comparison_lap
        description: Lap at whose end the two are compared (defender's out-lap).
      - name: attacker_position_before
        description: Attacker's position at the end of the lap before pitting.
      - name: attacker_position_after
        description: Attacker's position at the end of the comparison lap.
      - name: defender_position_after
        description: Defender's position at the end of the comparison lap.
      - name: is_success
        description: True if the attacker came out ahead; empty if either driver has no position (e.g. retired).
      - name: attacker_pitted_under_neutralisation
        description: True if the attacker pitted under the Safety Car or VSC — a cheap stop, not a genuine undercut.
```

Append under `unit_tests:`:

```yaml
  - name: test_undercut_success_failure_and_non_attempts
    model: fct_undercut_attempts
    given:
      - input: ref('fct_pit_stops')
        rows:
          # session 1: A=4 pits lap 20 behind B=81; B answers lap 22; A ahead after → success
          - {session_key: 1, driver_number: 4, lap_number: 20, is_under_neutralisation: false}
          - {session_key: 1, driver_number: 81, lap_number: 22, is_under_neutralisation: false}
          # session 2: same, but B stays ahead → failure
          - {session_key: 2, driver_number: 4, lap_number: 20, is_under_neutralisation: false}
          - {session_key: 2, driver_number: 81, lap_number: 22, is_under_neutralisation: false}
          # session 3: B answers too late (lap 25) → not an attempt
          - {session_key: 3, driver_number: 4, lap_number: 20, is_under_neutralisation: false}
          - {session_key: 3, driver_number: 81, lap_number: 25, is_under_neutralisation: false}
          # session 4: A was 2 places behind B → not an attempt
          - {session_key: 4, driver_number: 4, lap_number: 20, is_under_neutralisation: false}
          - {session_key: 4, driver_number: 81, lap_number: 21, is_under_neutralisation: false}
      - input: ref('int_laps_enriched')
        rows:
          - {session_key: 1, driver_number: 81, lap_number: 19, position_end_of_lap: 1}
          - {session_key: 1, driver_number: 4, lap_number: 19, position_end_of_lap: 2}
          - {session_key: 1, driver_number: 4, lap_number: 23, position_end_of_lap: 1}
          - {session_key: 1, driver_number: 81, lap_number: 23, position_end_of_lap: 2}
          - {session_key: 2, driver_number: 81, lap_number: 19, position_end_of_lap: 1}
          - {session_key: 2, driver_number: 4, lap_number: 19, position_end_of_lap: 2}
          - {session_key: 2, driver_number: 81, lap_number: 23, position_end_of_lap: 1}
          - {session_key: 2, driver_number: 4, lap_number: 23, position_end_of_lap: 2}
          - {session_key: 3, driver_number: 81, lap_number: 19, position_end_of_lap: 1}
          - {session_key: 3, driver_number: 4, lap_number: 19, position_end_of_lap: 2}
          - {session_key: 4, driver_number: 81, lap_number: 19, position_end_of_lap: 1}
          - {session_key: 4, driver_number: 4, lap_number: 19, position_end_of_lap: 3}
    expect:
      rows:
        - {session_key: 1, attacker_driver_number: 4, defender_driver_number: 81, defender_pit_lap: 22, comparison_lap: 23, is_success: true}
        - {session_key: 2, attacker_driver_number: 4, defender_driver_number: 81, defender_pit_lap: 22, comparison_lap: 23, is_success: false}
```

Stub `fct_undercut_attempts.sql`:

```sql
-- grain: one row per pit stop that is an undercut attempt
select
    pits.session_key, pits.driver_number as attacker_driver_number,
    cast(null as int64) as defender_driver_number, pits.lap_number as attacker_pit_lap,
    cast(null as int64) as defender_pit_lap, cast(null as int64) as comparison_lap,
    cast(null as int64) as attacker_position_before, cast(null as int64) as attacker_position_after,
    cast(null as int64) as defender_position_after, cast(null as bool) as is_success,
    pits.is_under_neutralisation as attacker_pitted_under_neutralisation
from {{ ref('fct_pit_stops') }} as pits
cross join {{ ref('int_laps_enriched') }} as laps
where false
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run dbt build --profiles-dir . --select fct_undercut_attempts`
Expected: unit test FAILS (0 rows vs 2).

- [ ] **Step 3: Implement**

`fct_undercut_attempts.sql`:

```sql
-- grain: one row per pit stop that is an undercut attempt
with laps as (
    select session_key, driver_number, lap_number, position_end_of_lap
    from {{ ref('int_laps_enriched') }}
),

pits as (
    select session_key, driver_number, lap_number, is_under_neutralisation
    from {{ ref('fct_pit_stops') }}
),

attacker_stops as (
    select
        pits.session_key,
        pits.driver_number as attacker_driver_number,
        pits.lap_number as attacker_pit_lap,
        pits.is_under_neutralisation as attacker_pitted_under_neutralisation,
        lap_before.position_end_of_lap as attacker_position_before
    from pits
    inner join laps as lap_before
        on lap_before.session_key = pits.session_key
        and lap_before.driver_number = pits.driver_number
        and lap_before.lap_number = pits.lap_number - 1
),

car_ahead as (
    select
        attacker_stops.*,
        ahead.driver_number as defender_driver_number
    from attacker_stops
    inner join laps as ahead
        on ahead.session_key = attacker_stops.session_key
        and ahead.lap_number = attacker_stops.attacker_pit_lap - 1
        and ahead.position_end_of_lap = attacker_stops.attacker_position_before - 1
),

attempts as (
    select
        car_ahead.session_key,
        car_ahead.attacker_driver_number,
        car_ahead.defender_driver_number,
        car_ahead.attacker_pit_lap,
        car_ahead.attacker_position_before,
        car_ahead.attacker_pitted_under_neutralisation,
        min(response.lap_number) as defender_pit_lap
    from car_ahead
    inner join pits as response
        on response.session_key = car_ahead.session_key
        and response.driver_number = car_ahead.defender_driver_number
        and response.lap_number between car_ahead.attacker_pit_lap + 1
            and car_ahead.attacker_pit_lap + 3
    group by 1, 2, 3, 4, 5, 6
)

select
    attempts.session_key,
    attempts.attacker_driver_number,
    attempts.defender_driver_number,
    attempts.attacker_pit_lap,
    attempts.defender_pit_lap,
    attempts.defender_pit_lap + 1 as comparison_lap,
    attempts.attacker_position_before,
    attacker_after.position_end_of_lap as attacker_position_after,
    defender_after.position_end_of_lap as defender_position_after,
    attacker_after.position_end_of_lap < defender_after.position_end_of_lap as is_success,
    attempts.attacker_pitted_under_neutralisation
from attempts
left join laps as attacker_after
    on attacker_after.session_key = attempts.session_key
    and attacker_after.driver_number = attempts.attacker_driver_number
    and attacker_after.lap_number = attempts.defender_pit_lap + 1
left join laps as defender_after
    on defender_after.session_key = attempts.session_key
    and defender_after.driver_number = attempts.defender_driver_number
    and defender_after.lap_number = attempts.defender_pit_lap + 1
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run dbt build --profiles-dir . --select fct_undercut_attempts`
Expected: unit test PASSES; table built; grain test passes.

- [ ] **Step 5: Commit**

```bash
git add transform/models/marts
git commit -m "feat(pitwall): detect undercut attempts and their outcome"
```

---

### Task 9: Full build on dev, sanity checks, docs and PR

**Files:**
- Modify: `projects/pitwall/README.md`, `CHANGELOG.md`, `docs/superpowers/specs/2026-09-29-pitwall-design.md`

- [ ] **Step 1: Full build through the Makefile**

Run: `cd projects/pitwall && make transform`
Expected: every model builds; unit tests pass; data tests pass; warnings only from `assert_stint_lap_ranges_are_valid` (10 rows), the data-quality warns of Task 3 and possibly `assert_clean_lap_times_are_plausible`.

- [ ] **Step 2: Prove the CI schema macro**

Run: `cd transform && DBT_CI_SCHEMA=ci_pr_0 uv run dbt parse --profiles-dir . --target ci && python3 -c "import json; m=json.load(open('target/manifest.json')); print(sorted({n['schema'] for n in m['nodes'].values() if n['resource_type']=='model'}))"`
Expected: `['ci_pr_0_intermediate', 'ci_pr_0_marts', 'ci_pr_0_staging']`. Then `uv run dbt parse --profiles-dir .` again so `target/` reflects dev.

- [ ] **Step 3: Sanity queries (the numbers must make racing sense)**

```bash
bq --project_id=pitwall-tr-dev query --use_legacy_sql=false \
  'select compound, count(*) stints, round(avg(degradation_s_per_lap), 3) avg_deg_s_per_lap
   from marts.fct_stints where degradation_s_per_lap is not null group by 1 order by 3 desc'
bq --project_id=pitwall-tr-dev query --use_legacy_sql=false \
  'select count(*) attempts, countif(is_success) successes,
          round(countif(is_success) / count(*), 2) success_rate,
          countif(attacker_pitted_under_neutralisation) under_sc
   from marts.fct_undercut_attempts'
bq --project_id=pitwall-tr-dev query --use_legacy_sql=false \
  'select source, count(*) stops, round(avg(pit_lane_time_s), 1) avg_lane_s from marts.fct_pit_stops group by 1'
```

Expected: SOFT degrades faster than MEDIUM, and MEDIUM faster than HARD (a few hundredths to a tenth of a second per lap; noisy but ordered); some tens of undercut attempts with a success rate between 0.2 and 0.8; about 850 stops with source `pit`, averaging 20–30 s. If an expectation fails, investigate with superpowers:systematic-debugging before changing thresholds, and record the finding.

- [ ] **Step 4: README, glossary, CHANGELOG, spec**

In `projects/pitwall/README.md`:
- mermaid: replace `bq[(BigQuery raw)] -. Plan 3 .-> dbt[dbt]` with `bq[(BigQuery raw)] --> dbt[dbt: staging → marts]`;
- add Tech stack row `Transformation | dbt (BigQuery) | Tested SQL with stated grains; unit tests pin the racing rules`;
- add `make transform   # dbt build: staging → intermediate → marts, with tests` after `make load` in "Run it";
- add a section before "Cost & teardown":

```markdown
## F1 in one minute

| Term | Meaning |
|---|---|
| **Grand Prix (meeting)** | One race weekend at one circuit. |
| **Race / Sprint** | Sunday's full-distance race / Saturday's short race. pitwall analyses both. |
| **Compound** | Tyre type: SOFT (fast, wears quickly), MEDIUM, HARD (slow, durable), INTERMEDIATE/WET (rain). |
| **Stint** | Laps on one set of tyres, between two pit stops. |
| **Degradation** | Seconds per lap a car loses as its tyres wear. |
| **Pit stop** | Stop to change tyres: ~2–3 s stationary, ~20 s lost overall. |
| **Undercut** | Pitting before the car just ahead so that fresh tyres put you in front after they pit. |
| **Safety Car / VSC** | Everyone slows down after an incident, so pitting costs less. |

## Data model

| Model | One row is | Answers |
|---|---|---|
| `fct_laps` | a lap of a driver | pace, tyres and running order lap by lap |
| `fct_stints` | a set of tyres used by a driver | how fast each compound wears (degradation) |
| `fct_pit_stops` | a pit stop | when, how long, which tyres, positions lost |
| `fct_undercut_attempts` | an undercut attempt | did pitting first work? |
| `fct_session_results` | a driver's race result | grid vs finish |
| `dim_sessions`, `dim_meetings`, `dim_session_drivers` | a race / weekend / driver-in-race | names, dates, teams, colours |

Every column is documented in the dbt YAML (`transform/models/`); `dbt docs generate` renders it.

## Data quality

Ingestion rejects only structurally broken data (missing keys, wrong types). Everything else is
checked in dbt: impossible values (null keys, positions or points out of range) **fail** the build,
so the marts and the dashboard keep their last good version; unusual-but-real values **warn**. Every
failing row is stored in the BigQuery `audit` dataset.

Empty fields that are expected (not errors):

| Field | Empty when |
|---|---|
| `race_control.driver_number` | the message is not about one car (~80 %) |
| `race_control.flag`, `scope`, `sector` | the message is not a flag |
| `race_control.qualifying_phase` | always in races (qualifying only) |
| `session_result.position`, `gap_to_leader`, `duration` | the driver was not classified (DNF/DNS/DSQ) |
| `pit.stop_duration` | the stationary time was not measured |
| `laps.lap_duration`, `date_start` | timing gaps, mostly lap 1 and pit laps (< 1 %) |
| `drivers.country_code` | always — OpenF1 does not publish it (not modelled) |

Known source defects: a few stints with missing or inverted lap ranges (kept in staging, excluded
from `fct_stints`), and race-control messages that name a car in the text but not in `driver_number`.
```

In `CHANGELOG.md` under `## [Unreleased]` → `### Added`:
`- \`pitwall\`: dbt project (staging → intermediate → marts) with degradation, pit stops and undercut detection, unit-tested racing rules.`

In the spec §6:
- after "**Degradation slope:**" paragraph add: "A clean lap also excludes laps slower than 1.2 × the session median (red flags, damage). Fuel burn makes cars ~0.03–0.06 s/lap faster, so the slope under-states tyre wear; documented, not corrected."
- in the undercut paragraph replace "at the end of the first lap on which both have completed their stops" with "at the end of B's out-lap (B's pit lap + 1), the first lap on which both have completed their stops".
- in **Layers → staging**, append: "`weather` and `overtakes` stay as sources without staging models until a page needs them."
- add under `fct_pit_stops`: "Sessions with no pit data infer stops from consecutive stints (`source = 'stint_change'`)."
- in §10 Testing, add: "**Data quality (dbt sources):** error severity for impossible values (null/duplicate keys, out-of-range positions/points, non-positive times) — blocks the marts; warn for unusual-but-real data (null-rate expectations per session, unknown compounds, short fields); failing rows stored in the `audit` dataset (`store_failures`). Stints with missing/inverted lap ranges stay in staging and are excluded from `fct_stints`."
- in §9 Terraform datasets, add `audit`; in Bootstrap, projects are created inside the organization (`ORG_ID`).

- [ ] **Step 5: Commit, push, PR, review, merge**

```bash
cd "/Users/tomasripsky/Data Engineering/Claude Code Enviroment"
git add projects/pitwall/README.md CHANGELOG.md docs/superpowers/specs/2026-09-29-pitwall-design.md
git commit -m "docs(pitwall): document the data model, F1 glossary and metric definitions"
git push -u origin HEAD
gh pr create --base dev --title "feat(pitwall): dbt race-strategy models" --body "Closes #<issue>"
```

Run the `pr-reviewer` agent with this plan's Review Focus; fix Critical/Important findings with a failing unit/data test first; squash-merge.

- [ ] **Step 6: Second brain**

Enrich `03 - Production/Transformation - dbt.md` (layers and grain, unit tests vs data tests, doc blocks, `generate_schema_name` for CI, `qualify` + BigQuery quirk) and `02 - Fundamentals/Data Modeling.md` (facts vs dimensions with pitwall's grains); extend `07 - Laboratory/F1 Primer.md` with the clean-lap and undercut definitions and the fuel-effect caveat; update `07 - Laboratory/pitwall.md` "Next experiment" to Plan 4. Commit and push the vault.
