---
title: Overview
toc: false
---

```js
const outputs = await FileAttachment("data/outputs.json").json();
const projects = await FileAttachment("data/projects.json").json();
const metrics = await FileAttachment("data/metrics.json").json();

const fmt = d3.format(",");
const realized = outputs.filter((o) => o.realized);
const maxYear = d3.max(metrics, (d) => d.year);
const allCommunities = Array.from(new Set(projects.flatMap((p) => p.community))).sort();

// Explode a multi-valued `community` field into one row per community.
const byCommunity = (items) =>
  items.flatMap((o) =>
    (o.community && o.community.length ? o.community : ["(unspecified)"]).map((c) => ({ ...o, _c: c }))
  );
const sumLatest = (mt) =>
  d3.sum(metrics.filter((d) => d.metric_type === mt && d.year === maxYear), (d) => d.lifetime_count ?? 0);

// Output lead-author role (person dimension), distinct from community (project lead).
const roleColor = {
  domain: ["Faculty", "CDH", "Post Doc", "Unknown"],
  range: ["#E69F00", "#0072B2", "#009E73", "#9AA0A6"],
  legend: true,
};
const trunc = (s, n = 40) => (s && s.length > n ? s.slice(0, n - 1) + "…" : s);
```

# CDH Research

The big picture of research coming out of the Center for Digital Humanities — across all its communities, from faculty collaborations to postdoc and graduate research, staff R&D, and service. Drill into [Impact](/impact) (views · downloads · citations), the [Pipeline](/pipeline) of what's coming, or the full [Portfolio](/portfolio).

<div class="grid grid-cols-4">
  <div class="card">
    <h2>CDH projects</h2>
    <span class="big">${fmt(projects.length)}</span>
    <span class="muted">${projects.filter((p) => p.cdh_built).length} built by CDH</span>
  </div>
  <div class="card">
    <h2>Communities</h2>
    <span class="big">${allCommunities.length}</span>
    <span class="muted">by project lead</span>
  </div>
  <div class="card">
    <h2>Realized outputs</h2>
    <span class="big">${fmt(realized.length)}</span>
    <span class="muted">${fmt(realized.filter((o) => o.has_link).length)} with a DOI</span>
  </div>
  <div class="card">
    <h2>Lifetime views · ${maxYear}</h2>
    <span class="big">${fmt(sumLatest("Views"))}</span>
    <span class="muted">${fmt(sumLatest("Citation Count"))} citations</span>
  </div>
</div>

## By community

Every project carries CDH's own **Project-Lead** classification, and outputs inherit it — so the whole portfolio can be read by community. (The person who *led a given output* is a separate lens — the color below.)

<div class="grid grid-cols-2">
  <div class="card">${
    resize((width) =>
      Plot.plot({
        width,
        title: "CDH projects by community",
        subtitle: "the full catalog; a project can have more than one lead",
        marginLeft: 150,
        x: { label: "Projects", grid: true },
        y: { label: null },
        marks: [
          Plot.barX(
            byCommunity(projects),
            Plot.groupY(
              { x: "count" },
              { y: "_c", sort: { y: "x", reverse: true }, fill: "var(--theme-foreground-focus)", tip: true }
            )
          ),
          Plot.ruleX([0]),
        ],
      })
    )
  }</div>
  <div class="card">${
    resize((width) =>
      Plot.plot({
        width,
        title: "Realized outputs by community",
        subtitle: "colored by the output's lead-author role",
        marginLeft: 150,
        color: roleColor,
        x: { label: "Outputs", grid: true },
        y: { label: null },
        marks: [
          Plot.barX(
            byCommunity(realized),
            Plot.groupY(
              { x: "count" },
              { y: "_c", fill: "lead_role", sort: { y: "x", reverse: true }, tip: true }
            )
          ),
          Plot.ruleX([0]),
        ],
      })
    )
  }</div>
</div>

<div class="card">${
  resize((width) =>
    Plot.plot({
      width,
      title: `Lifetime views by community (as of ${maxYear})`,
      marginLeft: 150,
      x: { label: "Lifetime views", grid: true },
      y: { label: null },
      marks: [
        Plot.barX(
          d3
            .rollups(
              byCommunity(metrics.filter((d) => d.metric_type === "Views" && d.year === maxYear && d.lifetime_count != null)),
              (v) => d3.sum(v, (x) => x.lifetime_count),
              (d) => d._c
            )
            .map(([community, total]) => ({ community, total })),
          { x: "total", y: "community", sort: { y: "x", reverse: true }, fill: "var(--theme-foreground-focus)", tip: true }
        ),
        Plot.ruleX([0]),
      ],
    })
  )
}</div>

<div class="note">"Community" is CDH's Project-Lead classification (Faculty / Postdoc / Graduate Student / Staff / External Collaborator), imported from the CDH projects catalog. Many projects have no tracked outputs yet, so the project counts above are broader than the output counts.</div>
