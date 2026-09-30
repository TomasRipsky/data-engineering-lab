// Lab portfolio site — one GitHub Pages site for every lab project (lab ADR 0005).
export default {
  title: "Data Engineering Lab",
  root: "src",
  base: "/data-engineering-lab/",
  style: "style.css",
  // No third-party requests: drop Framework's default Google Fonts stylesheet (pitwall self-hosts its font).
  globalStylesheets: [],
  pages: [
    {
      name: "pitwall — F1 race strategy",
      path: "/pitwall/",
      pages: [
        {name: "Race strategy", path: "/pitwall/race-strategy"},
        {name: "Tyre wear", path: "/pitwall/tyre-wear"},
        {name: "The undercut", path: "/pitwall/undercut"},
        {name: "About the data", path: "/pitwall/about"}
      ]
    }
  ],
  footer:
    'Data Engineering Lab by Tomas Ripsky · <a href="https://github.com/TomasRipsky/data-engineering-lab">source on GitHub</a>'
};
