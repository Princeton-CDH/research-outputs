// Observable Framework config.
export default {
  title: "CDH Research",
  // Served from a GitHub Pages project site at princeton-cdh.github.io/research-outputs/.
  // Must match the GitHub repo name; drop this (or set "/") for a custom domain / root deploy.
  base: "/research-outputs/",
  pages: [
    { name: "Impact", path: "/index" },
    { name: "Portfolio", path: "/portfolio" },
  ],
  // Exported embed module: external sites (e.g. the CDH Wagtail site) can
  // `import {Chart} from ".../research-outputs/pub-year-chart.js"` to render
  // the publication-year chart. GitHub Pages sends Access-Control-Allow-Origin: *.
  dynamicPaths: ["/pub-year-chart.js"],
  cleanUrls: true,
};
