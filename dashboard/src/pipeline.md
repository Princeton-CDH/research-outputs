---
title: Pipeline
toc: false
---

# Pipeline — what's coming

Planned and hypothetical outputs that don't exist yet. This list is **maintained
by hand** in `data/planned.csv` (unlike [realized](/portfolio) outputs, which are
generated from the canonical sources). When a planned item actually ships it
appears on [Impact](/) and [Portfolio](/portfolio) — at that point, delete its
row here.

```js
const planned = await FileAttachment("data/planned.json").json();

const STATUS = ["Hypothetical", "To do", "In progress", "Submitted"];
const statusColor = {
  domain: STATUS,
  // hypothetical (light grey) · to do (grey) · in progress (blue) · submitted (orange)
  range: ["#CCCCCC", "#9AA0A6", "#0072B2", "#E69F00"],
  legend: true,
};
const countAt = (s) => planned.filter((o) => o.status === s).length;
const typeOf = (o) => (o.type.length ? o.type[0] : "Uncategorized");
const milestoneOf = (o) => o.milestone ?? "No milestone";
```

<div class="grid grid-cols-4">
  <div class="card">
    <h2>Planned</h2>
    <span class="big">${planned.length}</span>
    <span class="muted">forecast outputs</span>
  </div>
  <div class="card"><h2>To do</h2><span class="big">${countAt("To do")}</span></div>
  <div class="card"><h2>In progress</h2><span class="big">${countAt("In progress")}</span></div>
  <div class="card"><h2>Submitted</h2><span class="big">${countAt("Submitted")}</span></div>
</div>

<div class="grid grid-cols-2">
  <div class="card">${
    resize((width) =>
      Plot.plot({
        width,
        title: "Planned by milestone",
        marginLeft: 160,
        x: { label: "Outputs", grid: true },
        y: { label: null, tickFormat: (s) => (s.length > 26 ? s.slice(0, 25) + "…" : s) },
        color: statusColor,
        marks: [
          Plot.barX(
            planned,
            Plot.groupY(
              { x: "count" },
              { y: milestoneOf, fill: "status", sort: { y: "x", reverse: true }, tip: true }
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
        title: "Planned by project",
        marginLeft: 220,
        x: { label: "Outputs", grid: true },
        y: { label: null, tickFormat: (s) => (s.length > 30 ? s.slice(0, 29) + "…" : s) },
        color: statusColor,
        marks: [
          Plot.barX(
            planned,
            Plot.groupY(
              { x: "count" },
              { y: "project", fill: "status", sort: { y: "x", reverse: true }, tip: true }
            )
          ),
          Plot.ruleX([0]),
        ],
      })
    )
  }</div>
</div>

## Every planned output

```js
const plannedRows = planned
  .slice()
  .sort((a, b) => d3.ascending(a.target_sort, b.target_sort))
  .map((o) => ({
    Output: o.name,
    Project: o.project,
    Type: o.type.join(", ") || "—",
    Tier: o.tier ?? "",
    Status: o.status,
    Milestone: o.milestone ?? "—",
    Target: o.target_date ?? "—",
    Priority: o.priority ?? "—",
    Owner: o.owner.join(", ") || "—",
  }));
const query = view(
  Inputs.search(plannedRows, {
    placeholder: `Search ${plannedRows.length} planned outputs…`,
  })
);
```

```js
Inputs.table(query, {
  rows: 20,
  layout: "auto",
})
```
