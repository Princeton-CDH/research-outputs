// Shared "Outputs by publication year" chart, used two ways:
//  - imported by index.md, which passes its reactive metric/project/zoom filters;
//  - exported as an embeddable module (see dynamicPaths in observablehq.config.js)
//    so external sites can `import {Chart}` and render the unfiltered chart.
import * as Plot from "npm:@observablehq/plot";
import * as d3 from "npm:d3";
import {FileAttachment, resize} from "observablehq:stdlib";

// Shared output-type color scale (Okabe–Ito, CVD-validated in this order;
// gray marks the rare misc type).
export const typeColor = {
  domain: ["Publication", "Presentation / Poster", "Software Release", "Dataset", "Grey Literature", "Website", "WebArchive"],
  range: ["#0072B2", "#E69F00", "#009E73", "#56B4E9", "#CC79A7", "#D55E00", "#9AA0A6"],
  legend: true,
};

const fmt = d3.format(",");
const truncate = (s, n = 50) => (s && s.length > n ? s.slice(0, n - 1) + "…" : s);

// Websites: impact comes from typical annual web traffic (median across
// trusted years). 2026 is excluded — AI-crawler traffic inflated it 28–75×.
const WEB_EXCLUDED_YEARS = new Set([2026]);

export function pubYearPlot(
  width,
  {outputs, metrics},
  {project = null, zoomFrom = -Infinity, zoomTo = Infinity, stroke = "white"} = {}
) {
  const maxYear = d3.max(metrics, (d) => d.year);

  const [zoomLo, zoomHi] = d3.extent([zoomFrom, zoomTo]); // tolerate swapped ends
  const inZoom = (iso) => {
    const y = +iso.slice(0, 4);
    return y >= zoomLo && y <= zoomHi;
  };

  // Y-axis rows come from EVERY realized, dated output (respecting the project
  // filter and the zoom window) — so the axis shows the current project list
  // even for projects whose outputs have no data yet for the selected metric.
  const axisProjects = outputs
    .filter(
      (o) =>
        o.realized &&
        o.completed_date &&
        inZoom(o.completed_date) &&
        (project == null || o.project === project)
    )
    .map((o) => ({ project: o.project, pub_year: +o.completed_date.slice(0, 4), date: o.completed_date }));
  // Projects sorted by the date of their first output, earliest at the top
  // (full ISO dates, so same-year projects order by day too).
  const projectOrder = d3.groupSort(
    axisProjects,
    (v) => d3.min(v, (d) => d.date),
    (d) => d.project
  );
  const projIndex = new Map(projectOrder.map((p, i) => [p, i]));

  // Impact score: every realized, dated, LINKED output gets a baseline of 1;
  // lifetime downloads and citations (as of the latest harvest) add on a log
  // scale, with citations weighted 5x. Unlinked outputs are hidden.
  const lifetimeOf = (type) =>
    new Map(
      metrics
        .filter((d) => d.metric_type === type && d.year === maxYear && d.lifetime_count != null)
        .map((d) => [d.output_id, d.lifetime_count])
    );
  const dlByOutput = lifetimeOf("Downloads");
  const citeByOutput = lifetimeOf("Citation Count");

  const webByOutput = new Map(
    d3
      .rollups(
        metrics.filter(
          (d) =>
            d.metric_family === "web" &&
            d.lifetime_count != null &&
            !WEB_EXCLUDED_YEARS.has(d.year)
        ),
        (v) => d3.median(v, (d) => d.lifetime_count),
        (d) => d.output_id
      )
  );

  // One dot per linked output with a pub year (project filter respected).
  const byPubYear = outputs
    .filter(
      (o) =>
        o.realized &&
        o.completed_date &&
        o.has_link &&
        inZoom(o.completed_date) &&
        projIndex.has(o.project) &&
        (project == null || o.project === project)
    )
    .map((o) => {
      const downloads = dlByOutput.get(o.output_id) ?? 0;
      const citations = citeByOutput.get(o.output_id) ?? 0;
      const webUsers = webByOutput.get(o.output_id) ?? 0;
      return {
        ...o,
        type: o.type[0] ?? "Uncategorized",
        pub_date: new Date(o.completed_date),
        pub_year: +o.completed_date.slice(0, 4),
        downloads,
        citations,
        webUsers,
        score:
          1 +
          Math.log10(1 + downloads) +
          5 * Math.log10(1 + citations) +
          1.5 * Math.log10(1 + webUsers),
      };
    });
  // Dots sit at their exact publication date, so same-year outputs spread out
  // across the year; fan out only those sharing a (project, exact date) cell.
  for (const [, pts] of d3.groups(byPubYear, (d) => `${d.project}|${d.completed_date}`)) {
    const sorted = d3.sort(pts, (d) => -d.score); // largest first
    const n = sorted.length;
    sorted.forEach((d, i) => {
      d.yj = projIndex.get(d.project) + (n === 1 ? 0 : (i - (n - 1) / 2) * 0.3);
    });
  }

  return Plot.plot({
    width,
    title: "Outputs by publication year",
    subtitle: `Each dot is one published output, placed at its publication date and colored by type. Size is an impact score: a baseline for every work, plus its downloads and citations (log-scaled, citations weighted 5×, as of ${maxYear}); websites are sized by typical annual web traffic (bot-inflated years excluded). Click a dot to open it.`,
    marginLeft: 320,
    marginRight: 24,
    height: Math.max(240, 34 * projectOrder.length + 90),
    x: { label: "Publication date", grid: true, nice: true },
    y: {
      label: null,
      domain: [projectOrder.length - 0.5, -0.5], // row 0 (earliest first output) on top
      ticks: projectOrder.map((_, i) => i),
      tickFormat: (i) => truncate(projectOrder[i], 52),
      grid: true,
    },
    r: { range: [2.5, 18], label: "Impact score" },
    color: typeColor,
    marks: [
      Plot.dot(byPubYear, {
        x: "pub_date",
        y: "yj",
        r: "score",
        fill: "type",
        fillOpacity: 0.7,
        stroke,
        strokeWidth: 0.75,
        href: (d) => d.link,
        target: "_blank",
        tip: true,
        title: (d) =>
          `${d.output_name}\n${d.type}\nLead: ${d.lead ?? "—"} (${d.lead_role})\nPublished ${d.pub_year}\nImpact ${d.score.toFixed(1)} · ${
            d.webUsers
              ? `~${fmt(Math.round(d.webUsers))} web users/yr (typical)`
              : `${fmt(d.downloads)} downloads · ${fmt(d.citations)} citations`
          }\n↗ open`,
      }),
    ],
  });
}

// Embed entry point: self-loads the data baked in at build time and returns a
// responsive DOM node. External pages only need a container with a width.
export async function Chart(options) {
  const [metrics, outputs] = await Promise.all([
    FileAttachment("./data/metrics.json").json(),
    FileAttachment("./data/outputs.json").json(),
  ]);
  return resize((width) => pubYearPlot(width, {outputs, metrics}, options));
}
