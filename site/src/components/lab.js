// Shared building blocks for every project section. Project-specific encodings (e.g. tyre
// compounds) belong in site/src/<project>/components/.
import * as d3 from "npm:d3";

/** Lab colours: `accent` for the main series, `ink` for secondary ones. */
export const palette = {accent: "#2a9d8f", ink: "#264653", muted: "#8f8f8f"};

/** Arrow table → array of plain objects. */
export function rows(table) {
  return Array.from(table, (row) => row.toJSON());
}

/** Number formats used across the site. */
export const fmt = {
  count: d3.format(","),
  seconds: (s) => `${d3.format(".1f")(s)} s`,
  percent: d3.format(".0%")
};
