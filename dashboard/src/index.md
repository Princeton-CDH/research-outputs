---
title: Impact
toc: false
---

# Research output impact

How the CDH portfolio's published outputs are being viewed, downloaded, cited, and used — drawn from the yearly metrics rollup (${maxYear - 2} years of history, through ${maxYear}).

```js
const metrics = await FileAttachment("data/metrics.json").json();
const outputs = await FileAttachment("data/outputs.json").json();
const projects = await FileAttachment("data/projects.json").json();
```

```js
// Reference values used across the page.
const maxYear = d3.max(metrics, (d) => d.year);
const fmt = d3.format(",");
const signed = d3.format("+,");

// Shorten long output names for labels; the full name stays in the tooltip.
// Kept long enough to read the opening words of each title.
const truncate = (s, n = 50) => (s && s.length > n ? s.slice(0, n - 1) + "…" : s);

// Project axis labels carry the project's date span (years) where known,
// e.g. "Remarx · 2024–2026"; projects without dates show the bare name.
const projectDates = new Map(projects.map((p) => [p.project, [p.start_date, p.end_date]]));
const projectLabel = (name, n = 44) => {
  const [s, e] = projectDates.get(name) ?? [];
  const ys = s ? s.slice(0, 4) : "";
  const ye = e ? e.slice(0, 4) : "";
  const span = ys || ye ? (ys === ye ? ` · ${ys}` : ` · ${ys}–${ye}`) : "";
  return truncate(name, n) + span;
};

const realizedCount = outputs.filter((o) => o.realized).length;
const linkedCount = outputs.filter((o) => o.has_link).length;
// Distinct projects that actually have a realized output — matches the project
// axis of the charts below (the full CDH catalog is much larger).
const projectsWithOutputs = new Set(
  outputs.filter((o) => o.realized).map((o) => o.project)
).size;

const sumAt = (metricType, year, field = "lifetime_count") =>
  d3.sum(
    metrics.filter((d) => d.metric_type === metricType && d.year === year),
    (d) => d[field] ?? 0
  );

const viewsLatest = sumAt("Views", maxYear);
const downloadsLatest = sumAt("Downloads", maxYear);
const citationsLatest = sumAt("Citation Count", maxYear);
const downloadsGain = sumAt("Downloads", maxYear, "yearly_delta");
```

<div class="grid grid-cols-4">
  <div class="card">
    <h2>Projects with outputs</h2>
    <span class="big">${fmt(projectsWithOutputs)}</span>
    <span class="muted">tracked in the metrics below</span>
  </div>
  <div class="card">
    <h2>Realized outputs</h2>
    <span class="big">${fmt(realizedCount)}</span>
    <span class="muted">${fmt(linkedCount)} with a DOI / link</span>
  </div>
  <div class="card">
    <h2>Lifetime downloads · ${maxYear}</h2>
    <span class="big">${fmt(downloadsLatest)}</span>
  </div>
  <div class="card">
    <h2>Lifetime views · ${maxYear}</h2>
    <span class="big">${fmt(viewsLatest)}</span>
    <span class="muted">${fmt(citationsLatest)} citations</span>
  </div>
  <div class="card">
    <h2>Downloads gained in ${maxYear}</h2>
    <span class="big">${signed(downloadsGain)}</span>
    <span class="muted">year-over-year</span>
  </div>
</div>

The chart below shows **all published outputs**, sized by an impact score. Pick a metric for the ranked charts further down (the metric types aren't comparable); the project filter applies to everything. Website analytics are kept separate — see [Website traffic](#website-traffic) below.

```js
const pubMetricTypes = Array.from(
  new Set(metrics.filter((d) => d.metric_family === "publication").map((d) => d.metric_type))
);
const metricOrder = ["Downloads", "Views", "Citation Count"];
pubMetricTypes.sort((a, b) => metricOrder.indexOf(a) - metricOrder.indexOf(b));

const projectNames = Array.from(
  new Set(metrics.filter((d) => d.metric_family === "publication").map((d) => d.project))
).sort();

const metricType = view(
  Inputs.select(pubMetricTypes, { label: "Metric", value: "Downloads" })
);
const project = view(
  Inputs.select(["All projects", ...projectNames], {
    label: "Project",
    value: "All projects",
  })
);
```

<div class="card">${
  resize((width) =>
    Plot.plot({
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
        tickFormat: (i) => projectLabel(projectOrder[i]),
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
          stroke: "var(--theme-background)",
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
    })
  )
}</div>

```js
// Rows for the selected metric (and project, if narrowed).
const selected = metrics.filter(
  (d) =>
    d.metric_type === metricType &&
    (project === "All projects" || d.project === project)
);
// Latest-year slice with a real count, for "top" and "by project" views.
const latest = selected.filter((d) => d.year === maxYear && d.lifetime_count != null);

// Y-axis rows come from EVERY realized, dated output (respecting the project
// filter) — so the axis shows the current project list even for projects whose
// outputs have no data yet for the selected metric.
const axisProjects = outputs
  .filter(
    (o) =>
      o.realized &&
      o.completed_date &&
      (project === "All projects" || o.project === project)
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

// Websites: impact comes from typical annual web traffic (median across
// trusted years). 2026 is excluded — AI-crawler traffic inflated it 28–75×.
const WEB_EXCLUDED_YEARS = new Set([2026]);
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
      projIndex.has(o.project) &&
      (project === "All projects" || o.project === project)
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
// Pre-sorted dataset for the ranked bar chart.
const topOutputs = d3.sort(latest, (d) => -d.lifetime_count).slice(0, 15);
// Shared output-type color scale (Okabe–Ito, CVD-validated in this order;
// gray marks the rare misc type).
const typeColor = {
  domain: ["Publication", "Presentation / Poster", "Software Release", "Dataset", "Grey Literature", "Website", "WebArchive"],
  range: ["#0072B2", "#E69F00", "#009E73", "#56B4E9", "#CC79A7", "#D55E00", "#9AA0A6"],
  legend: true,
};
const byProject = d3
  .rollups(
    latest,
    (v) => d3.sum(v, (d) => d.lifetime_count),
    (d) => d.project,
    (d) => d.type
  )
  .flatMap(([project, types]) => types.map(([type, total]) => ({ project, type, total })));
// Projects ordered by their grand total, for the stacked chart's y-axis.
const byProjectOrder = d3
  .groupSort(byProject, (v) => -d3.sum(v, (d) => d.total), (d) => d.project);
```

## Published outputs (DOIs)

Downloads, views, and citations for outputs with a DOI (Zenodo, journals, datasets), reflecting the metric and project selected above.

<div class="card">${
  resize((width) =>
    Plot.plot({
      width,
      title: `Top outputs by lifetime ${metricType} (as of ${maxYear})`,
      subtitle: "Click a title to open its DOI.",
      marginLeft: 360,
      height: Math.max(200, 28 * Math.min(15, topOutputs.length) + 70),
      x: { label: `Lifetime ${metricType}`, grid: true },
      y: { axis: null, domain: topOutputs.map((d) => d.output_id) },
      color: typeColor,
      marks: [
        Plot.barX(topOutputs, {
          x: "lifetime_count",
          y: "output_id",
          fill: "type",
          tip: true,
          title: (d) => `${d.output_name}\n${d.type}\n${fmt(d.lifetime_count)} ${metricType}`,
        }),
        Plot.text(topOutputs, {
          x: 0,
          y: "output_id",
          text: (d) => truncate(d.output_name),
          href: (d) => d.link,
          target: "_blank",
          textAnchor: "end",
          dx: -6,
          fill: "currentColor",
        }),
        Plot.ruleX([0]),
      ],
    })
  )
}</div>

<div class="card">${
  resize((width) =>
    Plot.plot({
      width,
      title: `Lifetime ${metricType} by project (as of ${maxYear})`,
      marginLeft: 320,
      x: { label: `Lifetime ${metricType}`, grid: true },
      y: { label: null, domain: byProjectOrder, tickFormat: (s) => projectLabel(s) },
      color: typeColor,
      marks: [
        Plot.barX(byProject, {
          x: "total",
          y: "project",
          fill: "type",
          stroke: "var(--theme-background)",
          strokeWidth: 0.75,
          tip: true,
          title: (d) => `${d.project}\n${d.type}: ${fmt(d.total)} ${metricType}`,
        }),
        Plot.ruleX([0]),
      ],
    })
  )
}</div>

<div class="note">Metrics with no baseline year show a blank year-over-year gain (not zero). Bars link to the output's DOI where one exists.</div>

## Website traffic

Traffic for the project **websites** — a different unit and scale from the DOI metrics above, so shown on its own. The y-axis is **logarithmic** so all four sites stay legible despite very different sizes. **2026 is inflated 28–75× by automated/AI-crawler traffic** and is excluded from the impact scores above; from 2027 the harvest records GA4 *engaged sessions*, which filter most bot traffic, instead of active users.

```js
const web = metrics.filter((d) => d.metric_family === "web" && d.lifetime_count != null);
const webLatestYear = d3.max(web, (d) => d.year);
```

<div class="card">${
  resize((width) =>
    Plot.plot({
      width,
      title: "Website active users by year",
      subtitle: "Log scale — each line is one site",
      marginLeft: 64,
      x: { label: "Year", tickFormat: "d", domain: d3.extent(web, (d) => d.year) },
      y: { label: "Web traffic (log)", grid: true, type: "log" },
      color: { legend: true },
      marks: [
        Plot.line(web, { x: "year", y: "lifetime_count", stroke: "project", strokeWidth: 2 }),
        Plot.dot(web, {
          x: "year",
          y: "lifetime_count",
          fill: "project",
          r: 4,
          tip: true,
          title: (d) => `${d.output_name}\n${fmt(d.lifetime_count)} ${(d.metric_type || "active users").toLowerCase()} in ${d.year}`,
        }),
      ],
    })
  )
}</div>

```js
Inputs.table(
  d3.sort(web, (d) => d.year - webLatestYear || 0).map((d) => ({
    Site: d.output_name,
    Project: d.project,
    Year: d.year,
    Metric: d.metric_type,
    Traffic: d.lifetime_count,
    "YoY gain": d.yearly_delta,
  })),
  { rows: 12, sort: "Traffic", reverse: true }
)
```

<div class="note">Website analytics are harvested separately from DOI metrics and can jump sharply year-to-year (e.g. a measurement-method change), so read the trend, not a single figure.</div>
