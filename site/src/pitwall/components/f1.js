// pitwall-specific encodings: tyre compounds and race neutralisations.
import {html, svg} from "npm:htl";

export const compounds = ["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"];

// Broadcast tyre colours, checked with the dataviz validator on the dark surface. HARD (white)
// and MEDIUM (yellow) are kept for recognition, so every stint also carries its letter.
const tones = {
  SOFT: "#e10600",
  MEDIUM: "#ffd12e",
  HARD: "#f0f0f0",
  INTERMEDIATE: "#2dbd6e",
  WET: "#0067ad",
  UNKNOWN: "#6b6b7b"
};

/** Plot colour scale for compounds (fixed order, never re-assigned by a filter). */
export const compoundColor = {domain: [...compounds, "UNKNOWN"], range: [...compounds, "UNKNOWN"].map((c) => tones[c])};

export const compoundLetter = (c) => ({SOFT: "S", MEDIUM: "M", HARD: "H", INTERMEDIATE: "I", WET: "W"})[c] ?? "?";

/** Compounds whose fill is light enough to need dark text on top. */
export const lightCompounds = new Set(["MEDIUM", "HARD"]);

/** Tyre badge — a sidewall ring in the compound colour with its letter, as on TV graphics. */
export function tyre(compound, size = 26) {
  const c = tones[compound] ?? tones.UNKNOWN;
  return svg`<svg width=${size} height=${size} viewBox="0 0 28 28" role="img" aria-label=${`${compound} tyre`}>
    <circle cx="14" cy="14" r="13.5" fill="#0b0b10"/>
    <circle cx="14" cy="14" r="9.5" fill="none" stroke=${c} stroke-width="3.2"/>
    <text x="14" y="18.3" text-anchor="middle" font-size="11" font-weight="700" fill="#f0f0f0"
      font-family="Titillium Web, system-ui, sans-serif">${compoundLetter(compound)}</text>
  </svg>`;
}

/** Legend row of tyre badges (text stays in ink; the badge carries the colour). */
export function tyreLegend(list = compounds) {
  return html`<div class="pw-legend">${list.map(
    (c) => html`<span>${tyre(c, 22)} ${c[0] + c.slice(1).toLowerCase()}</span>`
  )}</div>`;
}

/** Background washes for laps run under the Safety Car / VSC / a red flag. */
export const neutralisationFill = {SC: "#f0f0f0", VSC: "#f0f0f0", RED: "#e10600"};
export const neutralisationOpacity = {SC: 0.1, VSC: 0.06, RED: 0.22};

/** Merge consecutive neutralised laps into periods: [{type, from, to}]. */
export function periods(laps) {
  const out = [];
  for (const d of [...laps].sort((a, b) => a.neutralisation.localeCompare(b.neutralisation) || a.lap_number - b.lap_number)) {
    const last = out.at(-1);
    if (last && last.type === d.neutralisation && d.lap_number === last.to + 1) last.to = d.lap_number;
    else out.push({type: d.neutralisation, from: d.lap_number, to: d.lap_number});
  }
  return out;
}

/** Periods worth a text label: the most severe first, skipping any that would overlap one already
 * labelled (e.g. a Safety Car that ends in a red flag is labelled "RED FLAG" only). */
export function labelledPeriods(list) {
  const severity = {RED: 0, SC: 1, VSC: 2};
  const kept = [];
  for (const p of [...list].sort((a, b) => severity[a.type] - severity[b.type] || a.from - b.from)) {
    if (!kept.some((k) => p.from <= k.to + 1 && k.from <= p.to + 1)) kept.push(p);
  }
  return kept;
}
