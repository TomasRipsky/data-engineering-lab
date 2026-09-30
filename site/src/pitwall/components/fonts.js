// Titillium Web (SIL OFL 1.1, see ../fonts/OFL-LICENSE.txt), served by this site: no third-party
// font requests, so no visitor IPs go to a font CDN. FileAttachment makes Framework copy the files.
import {FileAttachment} from "npm:@observablehq/stdlib";

const files = {
  400: FileAttachment("../fonts/titillium-web-latin-400-normal.woff2"),
  600: FileAttachment("../fonts/titillium-web-latin-600-normal.woff2"),
  700: FileAttachment("../fonts/titillium-web-latin-700-normal.woff2"),
  900: FileAttachment("../fonts/titillium-web-latin-900-normal.woff2")
};

export const fontsLoaded = Promise.all(
  Object.entries(files).map(async ([weight, file]) => {
    const face = new FontFace("Titillium Web", `url(${await file.url()})`, {weight, display: "swap"});
    document.fonts.add(await face.load());
  })
);
