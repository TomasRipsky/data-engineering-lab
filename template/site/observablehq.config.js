// template-project's public site: https://tomasripsky.github.io/template-project/
// The lab's showcase standard (lab ADR 0008): one long story page (index.md) and a BI page (bi.md).
// The layout lives in the pages and in src/components/lab.css, so Framework's own chrome is off.
export default {
  title: "template-project",
  root: "src",
  base: "/template-project/",
  style: "style.css",
  // No third-party requests: drop Framework's default Google Fonts stylesheet.
  globalStylesheets: [],
  head: '<meta name="theme-color" content="#101014">',
  pages: [],
  sidebar: false,
  pager: false,
  toc: false,
  header: "",
  footer: ""
};
