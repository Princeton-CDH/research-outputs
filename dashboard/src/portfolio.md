---
title: Portfolio
toc: false
---

# Portfolio

The full body of **realized** work — everything Released or Done — and the projects behind it. (View/download impact lives on [Impact](/).)

```js
const outputs = await FileAttachment("data/outputs.json").json();
const projects = await FileAttachment("data/projects.json").json();
const realized = outputs.filter((o) => o.realized);

const roleColor = {
  domain: ["Faculty", "CDH", "Post Doc", "Unknown"],
  range: ["#E69F00", "#0072B2", "#009E73", "#9AA0A6"], // Okabe–Ito, colorblind-safe
  legend: true,
};
const trunc = (s, n = 30) => (s && s.length > n ? s.slice(0, n - 1) + "…" : s);
```

<div class="grid grid-cols-4">
  <div class="card">
    <h2>Projects</h2>
    <span class="big">${projects.length}</span>
  </div>
  <div class="card">
    <h2>Realized outputs</h2>
    <span class="big">${realized.length}</span>
    <span class="muted">of ${outputs.length} total</span>
  </div>
  <div class="card">
    <h2>With a DOI / link</h2>
    <span class="big">${realized.filter((o) => o.has_link).length}</span>
  </div>
  <div class="card">
    <h2>Faculty-led</h2>
    <span class="big">${realized.filter((o) => o.lead_role === "Faculty").length}</span>
    <span class="muted">${realized.filter((o) => o.lead_role === "CDH").length} CDH-led</span>
  </div>
</div>

<div class="card">${
  resize((width) =>
    Plot.plot({
      width,
      title: "Projects by status",
      subtitle: "A project can hold more than one status",
      marginLeft: 170,
      x: { label: "Projects", grid: true },
      y: { label: null },
      marks: [
        Plot.barX(
          projects.flatMap((p) => p.status.map((s) => ({ status: s }))),
          Plot.groupY(
            { x: "count" },
            { y: "status", sort: { y: "x", reverse: true }, fill: "var(--theme-foreground-focus)", tip: true }
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
      title: "Realized outputs by type and lead",
      subtitle: "Bar length = number of outputs; color = lead role",
      marginLeft: 160,
      x: { label: "Outputs", grid: true },
      y: { label: null },
      color: roleColor,
      marks: [
        Plot.barX(
          realized.flatMap((o) =>
            (o.type.length ? o.type : ["Uncategorized"]).map((t) => ({ type: t, lead_role: o.lead_role }))
          ),
          Plot.groupY(
            { x: "count" },
            { y: "type", fill: "lead_role", sort: { y: "x", reverse: true }, tip: true }
          )
        ),
        Plot.ruleX([0]),
      ],
    })
  )
}</div>

## Every realized output

```js
const realizedRows = realized.map((o) => ({
  Output: o.output_name,
  Project: o.project,
  Type: o.type.join(", ") || "—",
  Lead: o.lead ?? "—",
  Role: o.lead_role,
  Completed: o.completed_date ?? "",
  DOI: o.link,
}));
const query = view(
  Inputs.search(realizedRows, { placeholder: `Search ${realizedRows.length} realized outputs…` })
);
```

```js
Inputs.table(query, {
  rows: 22,
  sort: "Completed",
  reverse: true,
  format: {
    DOI: (l) => (l ? html`<a href=${l} target="_blank" title=${l}>↗ open</a>` : ""),
  },
  layout: "auto",
})
```
