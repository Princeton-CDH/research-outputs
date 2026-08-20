---
title: Impact
toc: false
---

# Research output impact

How the CDH portfolio's published outputs are being viewed, downloaded, cited, and used — drawn from the yearly metrics rollup (${maxYear - 2} years of history, through ${maxYear}).

```js
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
const viewsGain = sumAt("Views", maxYear, "yearly_delta");
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
    <h2>Lifetime views · ${maxYear}</h2>
    <span class="big">${fmt(viewsLatest)}</span>
    <span class="muted">${fmt(citationsLatest)} citations</span>
  </div>
  <div class="card">
    <h2>Lifetime downloads · ${maxYear}</h2>
    <span class="big">${fmt(downloadsLatest)}</span>
  </div>
  <div class="card">
    <h2>Views gained in ${maxYear}</h2>
    <span class="big">${signed(viewsGain)}</span>
    <span class="muted">year-over-year</span>
  </div>
</div>

## Published outputs (DOIs)

Views, downloads, and citations for outputs with a DOI (Zenodo, journals, datasets). Website analytics are kept separate — see [Website traffic](#website-traffic) below. Pick a metric and (optionally) narrow to one project; the metric types aren't comparable, so everything here reflects the **one metric** you select.

```js
const pubMetricTypes = Array.from(
  new Set(metrics.filter((d) => d.metric_family === "publication").map((d) => d.metric_type))
);
const metricOrder = ["Views", "Downloads", "Citation Count"];
pubMetricTypes.sort((a, b) => metricOrder.indexOf(a) - metricOrder.indexOf(b));

const projectNames = Array.from(
  new Set(metrics.filter((d) => d.metric_family === "publication").map((d) => d.project))
).sort();

const metricType = view(
  Inputs.select(pubMetricTypes, { label: "Metric", value: "Views" })
);
const project = view(
  Inputs.select(["All projects", ...projectNames], {
    label: "Project",
    value: "All projects",
  })
);
```

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
  .map((o) => ({ project: o.project, pub_year: +o.completed_date.slice(0, 4) }));
const projectOrder = d3.groupSort(
  axisProjects,
  (v) => d3.min(v, (d) => d.pub_year),
  (d) => d.project
);
const projIndex = new Map(projectOrder.map((p, i) => [p, i]));
// One dot per output for the selected metric that has a pub year and a row.
const byPubYear = latest.filter((d) => d.pub_year != null && projIndex.has(d.project));
// Fan out dots that share a (project, year) cell so none hides inside another.
// Each dot gets a numeric y (row index ± a deterministic offset).
for (const [, pts] of d3.groups(byPubYear, (d) => `${d.project}|${d.pub_year}`)) {
  const sorted = d3.sort(pts, (d) => -(d.lifetime_count ?? 0)); // largest first
  const n = sorted.length;
  sorted.forEach((d, i) => {
    d.yj = projIndex.get(d.project) + (n === 1 ? 0 : (i - (n - 1) / 2) * 0.3);
  });
}
// Pre-sorted datasets for the ranked bar charts.
const movers = d3
  .sort(
    selected.filter((d) => d.year === maxYear && d.yearly_delta != null),
    (d) => -d.yearly_delta
  )
  .slice(0, 12);
const topOutputs = d3.sort(latest, (d) => -d.lifetime_count).slice(0, 15);
const byProject = d3
  .rollups(latest, (v) => d3.sum(v, (d) => d.lifetime_count), (d) => d.project)
  .map(([project, total]) => ({ project, total }));
```

<div class="card">${
  resize((width) =>
    Plot.plot({
      width,
      title: "Outputs by publication year",
      subtitle: `Each dot is one output, placed at its publication year, sized by lifetime ${metricType} (as of ${maxYear}) and colored by its lead's role. Click a dot to open its DOI.`,
      marginLeft: 320,
      marginRight: 24,
      height: Math.max(240, 34 * projectOrder.length + 90),
      x: { label: "Publication year", tickFormat: "d", grid: true, nice: true },
      y: {
        label: null,
        domain: [projectOrder.length - 0.5, -0.5], // row 0 (earliest) on top
        ticks: projectOrder.map((_, i) => i),
        tickFormat: (i) => truncate(projectOrder[i], 52),
        grid: true,
      },
      r: { range: [3, 16], label: `Lifetime ${metricType}` },
      color: {
        domain: ["Faculty", "CDH", "Post Doc", "Unknown"],
        range: ["#E69F00", "#0072B2", "#009E73", "#9AA0A6"], // Okabe–Ito: colorblind-safe
        legend: true,
      },
      marks: [
        Plot.dot(byPubYear, {
          x: "pub_year",
          y: "yj",
          r: "lifetime_count",
          fill: "lead_role",
          fillOpacity: 0.7,
          stroke: "var(--theme-background)",
          strokeWidth: 0.75,
          href: (d) => d.link,
          target: "_blank",
          tip: true,
          title: (d) =>
            `${d.output_name}\nLead: ${d.lead ?? "—"} (${d.lead_role})\nPublished ${d.pub_year} · ${fmt(
              d.lifetime_count
            )} ${metricType}${d.link ? "\n↗ open DOI" : ""}`,
        }),
      ],
    })
  )
}</div>

<div class="card">${
  resize((width) =>
    Plot.plot({
      width,
      title: `${metricType} gained during ${maxYear} (top 12 movers)`,
      subtitle: "Click a title to open its DOI.",
      marginLeft: 360,
      x: { label: `Δ ${metricType}`, grid: true },
      y: { axis: null, domain: movers.map((d) => d.output_id) },
      marks: [
        Plot.barX(movers, {
          x: "yearly_delta",
          y: "output_id",
          fill: "var(--theme-green, #4caf50)",
          tip: true,
          title: (d) => `${d.output_name}\n${signed(d.yearly_delta)} ${metricType} in ${maxYear}`,
        }),
        Plot.text(movers, {
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
      title: `Top outputs by lifetime ${metricType} (as of ${maxYear})`,
      subtitle: "Click a title to open its DOI.",
      marginLeft: 360,
      height: Math.max(200, 28 * Math.min(15, topOutputs.length) + 70),
      x: { label: `Lifetime ${metricType}`, grid: true },
      y: { axis: null, domain: topOutputs.map((d) => d.output_id) },
      marks: [
        Plot.barX(topOutputs, {
          x: "lifetime_count",
          y: "output_id",
          fill: "var(--theme-foreground-focus)",
          tip: true,
          title: (d) => `${d.output_name}\n${fmt(d.lifetime_count)} ${metricType}`,
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
      y: { label: null, tickFormat: (s) => truncate(s, 52) },
      marks: [
        Plot.barX(byProject, {
          x: "total",
          y: "project",
          sort: { y: "x", reverse: true },
          fill: "var(--theme-foreground-focus)",
          tip: true,
        }),
        Plot.ruleX([0]),
      ],
    })
  )
}</div>

<div class="note">Metrics with no baseline year show a blank year-over-year gain (not zero). Bars link to the output's DOI where one exists.</div>

## Website traffic

Active users for the project **websites** — a different unit and scale from the DOI metrics above, so shown on its own. The y-axis is **logarithmic** so all four sites stay legible despite very different sizes.

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
      y: { label: "Active users (log)", grid: true, type: "log" },
      color: { legend: true },
      marks: [
        Plot.line(web, { x: "year", y: "lifetime_count", stroke: "project", strokeWidth: 2 }),
        Plot.dot(web, {
          x: "year",
          y: "lifetime_count",
          fill: "project",
          r: 4,
          tip: true,
          title: (d) => `${d.output_name}\n${fmt(d.lifetime_count)} active users in ${d.year}`,
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
    "Active users": d.lifetime_count,
    "YoY gain": d.yearly_delta,
  })),
  { rows: 12, sort: "Active users", reverse: true }
)
```

<div class="note">Website analytics are harvested separately from DOI metrics and can jump sharply year-to-year (e.g. a measurement-method change), so read the trend, not a single figure.</div>
