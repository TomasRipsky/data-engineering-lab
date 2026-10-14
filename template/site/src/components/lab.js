// Building blocks shared by every Data Engineering Lab project site (lab ADR 0008). Keep this file
// generic: a project's own encodings and illustrations go in their own files next to it.
import * as d3 from "npm:d3";
import {html} from "npm:htl";

/** Series colours of the shared skeleton (the CSS variables of lab.css, for Plot marks). */
export const series = ["#3987e5", "#d95926", "#2aa198"];
// Plot marks cannot read CSS variables: keep these equal to the theme's --lab-* values.
export const ink = {text: "#f0f0f0", soft: "#c9c9d6", muted: "#a3a3b3", line: "#2c2c38", surface: "#101014"};

/** Arrow table → array of plain objects. */
export function rows(table) {
  return Array.from(table, (row) => row.toJSON());
}

/** Number formats used across the site. A missing value is a dash, never a zero. */
const dash = (f) => (x) => (x == null || Number.isNaN(x) ? "—" : f(x));
export const fmt = {
  count: dash(d3.format(",")),
  seconds: dash((s) => `${d3.format(".1f")(s)} s`),
  seconds2: dash((s) => `${d3.format(".2f")(s)} s`),
  percent: dash(d3.format(".0%")),
  signed: dash((x) => `${x > 0 ? "+" : x < 0 ? "−" : ""}${d3.format(".1f")(Math.abs(x))}`),
  one: dash(d3.format(".1f")),
  date: dash((iso) => d3.utcFormat("%-d %b %Y")(new Date(`${iso}T00:00:00Z`)))
};

/** Median of a field, ignoring missing values; null when nothing is left. */
export function median(list, accessor) {
  const m = d3.median(list, (d) => accessor(d) ?? NaN);
  return m === undefined ? null : m;
}

/** A button that saves `data` (an array of objects) as a CSV file. */
export function downloadButton(data, filename) {
  const button = html`<button class="btn ghost small" type="button">Download CSV</button>`;
  button.onclick = () => {
    const url = URL.createObjectURL(new Blob([d3.csvFormat(data)], {type: "text/csv"}));
    const a = Object.assign(document.createElement("a"), {href: url, download: filename});
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000); // revoking at once can cancel the download
  };
  return button;
}

/** What a block shows when the current filters leave it without rows. */
export function emptyState(what = "data") {
  return html`<p class="empty">No ${what} for this selection.</p>`;
}
