// Original illustrations for the pitwall section (no official F1 imagery or logos).
import {html, svg} from "npm:htl";

/** Side view of a generic single-seater, wheels painted with soft (rear) and medium (front) sidewalls. */
export function car({livery = "#e10600"} = {}) {
  return svg`<svg class="pw-car" viewBox="0 0 560 170" role="img" aria-label="Illustration of a Formula 1 car">
    <defs>
      <linearGradient id="pw-livery" x1="0" x2="1" y1="0" y2="0">
        <stop offset="0" stop-color="#7a0300"/>
        <stop offset="0.45" stop-color=${livery}/>
        <stop offset="1" stop-color="#ff3b30"/>
      </linearGradient>
      <linearGradient id="pw-speed" x1="0" x2="1">
        <stop offset="0" stop-color="#f0f0f0" stop-opacity="0"/>
        <stop offset="1" stop-color="#f0f0f0" stop-opacity="0.45"/>
      </linearGradient>
    </defs>
    <g stroke="url(#pw-speed)" stroke-width="3" stroke-linecap="round">
      <line x1="0" y1="72" x2="90" y2="72"/>
      <line x1="20" y1="94" x2="120" y2="94"/>
      <line x1="0" y1="116" x2="80" y2="116"/>
    </g>
    <path d="M104 50 h52 v11 h-52z" fill="#23232d"/>
    <path d="M118 61 h10 v44 h-10z" fill="#23232d"/>
    <path d="M110 131 H500 L512 138 H104 Z" fill="#0b0b10"/>
    <path d="M122 110 C150 90 204 80 250 80 L322 76 C352 72 374 80 398 88 L476 104 C496 108 514 114 524 122 L526 131 L118 131 Z"
      fill="url(#pw-livery)"/>
    <path d="M190 112 L384 106 L398 121 L186 124 Z" fill="#000" fill-opacity="0.28"/>
    <path d="M286 79 C298 58 334 56 354 70" fill="none" stroke="#23232d" stroke-width="7" stroke-linecap="round"/>
    <circle cx="316" cy="73" r="9" fill="#f0f0f0"/>
    <path d="M500 130 h56 v7 h-56z" fill="#23232d"/>
    <text x="428" y="117" font-size="19" font-weight="900" font-style="italic" fill="#f0f0f0"
      font-family="Titillium Web, system-ui, sans-serif">01</text>
    <g>
      <circle cx="160" cy="131" r="35" fill="#0b0b10"/>
      <circle cx="160" cy="131" r="25" fill="none" stroke="#e10600" stroke-width="4"/>
      <circle cx="160" cy="131" r="10" fill="#2e2e3d"/>
      <circle cx="470" cy="133" r="30" fill="#0b0b10"/>
      <circle cx="470" cy="133" r="21" fill="none" stroke="#ffd12e" stroke-width="4"/>
      <circle cx="470" cy="133" r="9" fill="#2e2e3d"/>
    </g>
  </svg>`;
}

/** Chequered flag strip, used as a section divider. */
export function chequered({columns = 24, rows = 2, cell = 10} = {}) {
  const cells = [];
  for (let r = 0; r < rows; ++r) for (let c = 0; c < columns; ++c) if ((r + c) % 2 === 0) cells.push([c, r]);
  return svg`<svg width=${columns * cell} height=${rows * cell} role="img" aria-label="Chequered flag">
    <rect width=${columns * cell} height=${rows * cell} fill="#f0f0f0"/>
    ${cells.map(([c, r]) => svg`<rect x=${c * cell} y=${r * cell} width=${cell} height=${cell} fill="#0b0b10"/>`)}
  </svg>`;
}

/** The pipeline drawn as a lap: each stage is a sector, the site is the chequered flag. */
export function pipelineLap(stages) {
  return html`<ol class="pw-lap">${stages.map(
    ([name, detail], i) => html`<li>
      <span class="pw-sector">${i === stages.length - 1 ? chequered({columns: 4, rows: 2, cell: 6}) : `S${i + 1}`}</span>
      <strong>${name}</strong>
      <small>${detail}</small>
    </li>`
  )}</ol>`;
}
