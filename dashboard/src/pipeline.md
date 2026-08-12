---
title: Pipeline
toc: false
---

# Pipeline — what's coming

Planned and in-progress outputs that don't exist yet: everything at **To do**, **In progress**, or **Submitted**. As each is finished it flips to Released/Done and shows up on the [Impact](/) page.

```js
const outputs = await FileAttachment("data/outputs.json").json();
const PIPELINE = ["To do", "In progress", "Submitted"];
const pipeline = outputs.filter((o) => PIPELINE.includes(o.status));

const statusColor = {
  domain: PIPELINE,
  range: ["#9AA0A6", "#0072B2", "#E69F00"], // to do (grey) · in progress (blue) · submitted (orange)
  legend: true,
};
const countAt = (s) => pipeline.filter((o) => o.status === s).length;
const typeOf = (o) => (o.type.length ? o.type[0] : "Uncategorized");
```

<div class="grid grid-cols-4">
  <div class="card">
    <h2>In the pipeline</h2>
    <span class="big">${pipeline.length}</span>
    <span class="muted">of ${outputs.length} total outputs</span>
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
        title: "Pipeline by project",
        marginLeft: 220,
        x: { label: "Outputs", grid: true },
        y: { label: null, tickFormat: (s) => (s.length > 30 ? s.slice(0, 29) + "…" : s) },
        color: statusColor,
        marks: [
          Plot.barX(
            pipeline,
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
  <div class="card">${
    resize((width) =>
      Plot.plot({
        width,
        title: "Pipeline by output type",
        marginLeft: 160,
        x: { label: "Outputs", grid: true },
        y: { label: null },
        color: statusColor,
        marks: [
          Plot.barX(
            pipeline,
            Plot.groupY(
              { x: "count" },
              { y: typeOf, fill: "status", sort: { y: "x", reverse: true }, tip: true }
            )
          ),
          Plot.ruleX([0]),
        ],
      })
    )
  }</div>
</div>

## Every pipeline output

```js
const pipelineRows = pipeline.map((o) => ({
  Output: o.output_name,
  Project: o.project,
  Type: o.type.join(", ") || "—",
  Tier: o.tier ?? "",
  Status: o.status,
  Lead: o.lead ?? "—",
  Assignees: o.assignee.join(", ") || "—",
}));
const query = view(
  Inputs.search(pipelineRows, {
    placeholder: `Search ${pipelineRows.length} pipeline outputs…`,
  })
);
```

```js
Inputs.table(query, {
  rows: 20,
  sort: "Status",
  layout: "auto",
})
```
