const $ = (sel) => document.querySelector(sel);

async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    if (typeof body === "string") {
      opts.body = body;
    } else {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
  }
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}

function fmtMoney(value) {
  if (value === null || value === undefined) return "—";
  return "$" + Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 });
}

function fmtPct(value) {
  if (value === null || value === undefined) return "—";
  return Number(value).toFixed(2) + "%";
}

function fmtMinutes(value) {
  if (value === null || value === undefined) return "—";
  const hours = value / 60;
  if (hours >= 1) return hours.toFixed(1) + " h";
  return value.toFixed(1) + " min";
}

async function refreshReport() {
  const report = await api("GET", "/api/report");

  const tiles = [
    { label: "You actually paid", value: fmtMoney(report.total_actual) },
    { label: "Best OpenRouter routing would have cost", value: fmtMoney(report.total_best_openrouter) },
    {
      label: "Estimated savings",
      value: fmtMoney(report.total_savings),
      good: report.total_savings > 0,
    },
    { label: "Savings %", value: fmtPct(report.savings_pct), good: report.savings_pct > 0 },
  ];
  $("#stat-tiles").innerHTML = tiles
    .map(
      (t) => `<div class="stat-tile"><div class="label">${t.label}</div>
        <div class="value ${t.good ? "good" : ""}">${t.value}</div></div>`
    )
    .join("");

  $("#missing-price-note").textContent =
    report.entries_missing_price_data > 0
      ? `${report.entries_missing_price_data} usage entr${report.entries_missing_price_data === 1 ? "y has" : "ies have"} no OpenRouter price data yet (tracked model with no snapshot, and live lookup unavailable) — excluded from the savings total above.`
      : "";

  drawChart(report.timeseries || []);
  return report;
}

function drawChart(series) {
  const svg = $("#chart");
  const tooltip = $("#chart-tooltip");
  svg.innerHTML = "";
  if (series.length === 0) {
    svg.innerHTML =
      '<text x="450" y="110" text-anchor="middle" fill="var(--text-muted)" font-size="13">No usage logged yet</text>';
    return;
  }

  const W = 900, H = 220, padL = 60, padR = 20, padT = 16, padB = 28;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const maxVal = Math.max(1e-9, ...series.flatMap((d) => [d.actual, d.best_openrouter]));
  const n = series.length;
  const x = (i) => padL + (n === 1 ? plotW / 2 : (i / (n - 1)) * plotW);
  const y = (v) => padT + plotH - (v / maxVal) * plotH;

  const ns = "http://www.w3.org/2000/svg";
  const makeLine = (key, colorVar) => {
    const points = series.map((d, i) => `${x(i)},${y(d[key])}`).join(" ");
    const el = document.createElementNS(ns, "polyline");
    el.setAttribute("points", points);
    el.setAttribute("fill", "none");
    el.setAttribute("stroke", `var(${colorVar})`);
    el.setAttribute("stroke-width", "2");
    el.setAttribute("stroke-linecap", "round");
    el.setAttribute("stroke-linejoin", "round");
    return el;
  };

  for (let i = 0; i <= 4; i++) {
    const gy = padT + (plotH / 4) * i;
    const line = document.createElementNS(ns, "line");
    line.setAttribute("x1", padL);
    line.setAttribute("x2", W - padR);
    line.setAttribute("y1", gy);
    line.setAttribute("y2", gy);
    line.setAttribute("stroke", "var(--gridline)");
    line.setAttribute("stroke-width", "1");
    svg.appendChild(line);
  }

  svg.appendChild(makeLine("best_openrouter", "--series-2"));
  svg.appendChild(makeLine("actual", "--series-1"));

  series.forEach((d, i) => {
    ["actual", "best_openrouter"].forEach((key, idx) => {
      const c = document.createElementNS(ns, "circle");
      c.setAttribute("cx", x(i));
      c.setAttribute("cy", y(d[key]));
      c.setAttribute("r", "3.5");
      c.setAttribute("fill", `var(${idx === 0 ? "--series-1" : "--series-2"})`);
      c.setAttribute("data-index", i);
      c.style.cursor = "pointer";
      c.addEventListener("mousemove", (evt) => showTooltip(evt, d));
      c.addEventListener("mouseleave", () => (tooltip.style.display = "none"));
      svg.appendChild(c);
    });
  });

  function showTooltip(evt, d) {
    const rect = svg.getBoundingClientRect();
    tooltip.style.display = "block";
    tooltip.style.left = evt.clientX - rect.left + 12 + "px";
    tooltip.style.top = evt.clientY - rect.top - 10 + "px";
    tooltip.innerHTML = `<strong>${d.date}</strong><br/>Actual: ${fmtMoney(d.actual)}<br/>OpenRouter: ${fmtMoney(
      d.best_openrouter
    )}`;
  }
}

async function refreshUsage() {
  const entries = await api("GET", "/api/usage");
  const tbody = $("#usage-table tbody");
  tbody.innerHTML = entries
    .slice()
    .sort((a, b) => (a.timestamp < b.timestamp ? 1 : -1))
    .map(
      (e) => `<tr>
        <td>${e.model}</td>
        <td>${e.provider_used}</td>
        <td>${new Date(e.timestamp).toLocaleString()}</td>
        <td>${e.prompt_tokens}</td>
        <td>${e.completion_tokens}</td>
        <td>${e.actual_cost !== null ? fmtMoney(e.actual_cost) : "auto"}</td>
        <td><button class="icon-btn" data-id="${e.id}" title="Delete">&times;</button></td>
      </tr>`
    )
    .join("");
  tbody.querySelectorAll("button[data-id]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await api("DELETE", `/api/usage/${btn.dataset.id}`);
      await refreshAll();
    });
  });
}

async function refreshTracked() {
  const tracked = await api("GET", "/api/tracked");
  const tbody = $("#tracked-table tbody");
  tbody.innerHTML = tracked
    .map(
      (t) => `<tr>
        <td>${t.model}</td>
        <td>${t.label || ""}</td>
        <td><button class="icon-btn" data-model="${encodeURIComponent(t.model)}" title="Stop tracking">&times;</button></td>
      </tr>`
    )
    .join("");
  tbody.querySelectorAll("button[data-model]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await api("DELETE", `/api/tracked/${btn.dataset.model}`);
      await refreshTracked();
    });
  });
}

async function refreshUptime() {
  const summaries = await api("GET", "/api/uptime");
  $("#uptime-empty").style.display = summaries.length === 0 ? "block" : "none";
  const tbody = $("#uptime-table tbody");
  tbody.innerHTML = summaries
    .map(
      (s) => `<tr>
        <td>${s.model}</td>
        <td>${s.provider}</td>
        <td>${fmtPct(s.latest_uptime_pct)}</td>
        <td>${fmtPct(s.average_uptime_pct)}</td>
        <td>${fmtMinutes(s.estimated_downtime_minutes)}</td>
        <td>${
          s.logged_incidents.length
            ? `${fmtMinutes(s.logged_incident_minutes)} (${s.logged_incidents.length})`
            : "—"
        }</td>
        <td>${fmtMinutes(s.tracked_minutes)}</td>
      </tr>`
    )
    .join("");
}

async function refreshAll() {
  await Promise.all([refreshReport(), refreshUsage(), refreshTracked(), refreshUptime()]);
}

$("#usage-form").addEventListener("submit", async (evt) => {
  evt.preventDefault();
  const form = evt.target;
  const data = Object.fromEntries(new FormData(form).entries());
  const payload = {
    model: data.model.trim(),
    provider_used: data.provider_used.trim(),
    timestamp: new Date(data.timestamp).toISOString(),
    prompt_tokens: Number(data.prompt_tokens || 0),
    completion_tokens: Number(data.completion_tokens || 0),
    actual_cost: data.actual_cost ? Number(data.actual_cost) : null,
    unit_prompt_price: data.unit_prompt_price ? Number(data.unit_prompt_price) : null,
    unit_completion_price: data.unit_completion_price ? Number(data.unit_completion_price) : null,
  };
  await api("POST", "/api/usage", payload);
  form.reset();
  await refreshAll();
});

$("#track-form").addEventListener("submit", async (evt) => {
  evt.preventDefault();
  const form = evt.target;
  const data = Object.fromEntries(new FormData(form).entries());
  await api("POST", "/api/tracked", { model: data.model.trim(), label: data.label.trim() });
  form.reset();
  await refreshTracked();
});

$("#snapshot-now").addEventListener("click", async () => {
  const btn = $("#snapshot-now");
  btn.disabled = true;
  btn.textContent = "Snapshotting…";
  try {
    await api("POST", "/api/snapshot");
    await refreshAll();
  } finally {
    btn.disabled = false;
    btn.textContent = "Snapshot now";
  }
});

$("#import-form").addEventListener("submit", async (evt) => {
  evt.preventDefault();
  const csv = new FormData(evt.target).get("csv");
  const resultEl = $("#import-result");
  try {
    const result = await api("POST", "/api/import-price-history", csv);
    resultEl.textContent = `Imported ${result.imported} price rows.`;
    await refreshReport();
  } catch (err) {
    resultEl.textContent = `Error: ${err.message}`;
  }
});

$("#import-downtime-form").addEventListener("submit", async (evt) => {
  evt.preventDefault();
  const csv = new FormData(evt.target).get("csv");
  const resultEl = $("#import-downtime-result");
  try {
    const result = await api("POST", "/api/import-downtime-history", csv);
    resultEl.textContent = `Imported ${result.imported} incident rows.`;
    await refreshUptime();
  } catch (err) {
    resultEl.textContent = `Error: ${err.message}`;
  }
});

refreshAll().catch((err) => console.error(err));
