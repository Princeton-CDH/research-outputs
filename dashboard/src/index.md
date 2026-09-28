---
title: Impact
toc: false
---

# Research output impact

How the CDH portfolio's published outputs are being viewed, downloaded, cited, and used — drawn from the yearly metrics rollup (${maxYear - 2} years of history, through ${maxYear}).

```js
import {pubYearPlot, typeColor} from "./pub-year-chart.js";

const metrics = await FileAttachment("data/metrics.json").json();
const outputs = await FileAttachment("data/outputs.json").json();
```

```js
// Reference values used across the page.
const maxYear = d3.max(metrics, (d) => d.year);
const fmt = d3.format(",");
const signed = d3.format("+,");

// Shorten long output names for labels; the full name stays in the tooltip.
// Kept long enough to read the opening words of each title.
const truncate = (s, n = 50) => (s && s.length > n ? s.slice(0, n - 1) + "…" : s);

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

// Zoom: restrict the publication-year chart to a year window. Projects with
// no outputs in the window drop off the axis, so zooming also declutters.
const pubYearExtent = d3.extent(
  outputs.filter((o) => o.realized && o.completed_date),
  (o) => +o.completed_date.slice(0, 4)
);
const zoomFrom = view(
  Inputs.select(d3.range(pubYearExtent[0], pubYearExtent[1] + 1), {
    label: "From year",
    value: pubYearExtent[0],
    format: (y) => String(y), // years, not "2,026"
  })
);
const zoomTo = view(
  Inputs.select(d3.range(pubYearExtent[0], pubYearExtent[1] + 1), {
    label: "To year",
    value: pubYearExtent[1],
    format: (y) => String(y),
  })
);
```

<div class="card">${
  resize((width) =>
    pubYearPlot(width, {outputs, metrics}, {
      project: project === "All projects" ? null : project,
      zoomFrom,
      zoomTo,
      stroke: "var(--theme-background)",
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

// Pre-sorted dataset for the ranked bar chart. (The publication-year chart's
// data prep and shared typeColor scale live in ./pub-year-chart.js, which is
// also exported as an embeddable module — see observablehq.config.js.)
const topOutputs = d3.sort(latest, (d) => -d.lifetime_count).slice(0, 15);
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
      y: { label: null, domain: byProjectOrder, tickFormat: (s) => truncate(s, 52) },
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
