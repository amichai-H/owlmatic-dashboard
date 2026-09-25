"use strict";
const element = (id) => document.getElementById(id);
let token = "", sources = [], cursor = null, requestVersion = 0;
const receipts = new Map();
const number = (value) => value == null ? "Not available" : value.toLocaleString();
function node(tag, text, className) {
  const result = document.createElement(tag);
  if (text != null) result.textContent = text;
  if (className) result.className = className;
  return result;
}
function table(target, headings, rows) {
  target.replaceChildren();
  if (!rows.length) { target.append(node("p", "No data shared for this breakdown.", "muted")); return; }
  const result = node("table"), head = node("thead"), row = node("tr"), body = node("tbody");
  for (const heading of headings) row.append(node("th", heading));
  head.append(row);
  for (const values of rows) { const tr = node("tr"); for (const value of values) tr.append(node("td", value)); body.append(tr); }
  result.append(head, body); target.append(result);
}
function metricCard([title, value, note, state = false]) {
  const card = node("article", null, "card");
  card.append(node("h2", title), node("strong", value, state ? "metric-state" : null), node("p", note));
  return card;
}
function measurementCards(measurement) {
  if (!measurement) return [["Agent measurements", "Not available", "This source has not shared agent measurements. Enable collection and measurement export to compare token usage.", true]];
  const operational = measurement.estimated_operational_savings;
  const measured = measurement.measured_agent_tokens;
  const net = measurement.estimated_net_savings;
  return [
    ["Estimated operational savings", operational == null ? "Evidence missing" : number(operational), operational == null ? "A compatible manual baseline, complete task usage, and attribution are needed." : "Tokens compared with recorded manual tasks, before creation and maintenance costs. Historical estimate; can be negative.", operational == null],
    ["Measured execution tokens", measured == null ? "Not recorded" : number(measured), `${measurement.measured_tasks} of ${measurement.observed_tasks} attributed tasks measured; ${measurement.unattributed_tasks} unattributed.`, measured == null],
    ["Estimated net savings", net == null ? (operational == null ? "Evidence missing" : "Costs missing") : number(net), net == null ? (operational == null ? "Complete the task comparison and account for creation and maintenance before calculating net savings." : "Import creation and maintenance usage, then declare cost coverage complete. Missing costs are not counted as zero.") : "Tokens after recorded creation and maintenance costs.", net == null]
  ];
}
function contextSummary(measurement) {
  if (!measurement) return "";
  const tokens = measurement.estimated_context_reference_tokens;
  const bytes = measurement.context_bytes_reduced;
  let message = "Tool-output context: ";
  if (tokens != null) message += `${number(Math.abs(tokens))} ${tokens < 0 ? "more" : "fewer"} reference tokens`;
  else if (bytes != null) message += `${number(Math.abs(bytes))} ${bytes < 0 ? "more" : "fewer"} bytes`;
  else return message + "a complete visible tool-result comparison is not available.";
  if (tokens == null) message += ". Reference token counts were not available for this comparison";
  return message + ". Counts each tool result once; this is separate from provider token usage.";
}
function render() {
  const snapshot = sources.find((source) => source.source_id === element("source").value);
  if (!snapshot) {
    for (const id of ["metrics", "chart", "workflows", "days", "coverage", "window", "measurement", "measurement-detail", "context-summary", "measurement-window"]) element(id).replaceChildren();
    return;
  }
  const usage = snapshot.usage, savings = snapshot.savings;
  const measurement = snapshot.measurements;
  element("measurement").replaceChildren(...measurementCards(measurement).map(metricCard));
  element("context-summary").textContent = contextSummary(measurement);
  element("measurement-window").textContent = measurement ? `Retained imported tasks (separate from the calendar window below) · latest observation ${measurement.latest_observation_at || "unknown"}. Historical comparison, not a guaranteed minimum.` : "Enable local measurement and explicitly share it in a v2 export.";
  table(element("measurement-detail"), ["Workflow", "Host / model", "Workload", "Quality", "Samples", "Manual token range", "Measured / observed tasks", "Operational estimate", "Net estimate", "Missing evidence / assumptions"], (measurement?.workflows || []).map(row => [row.workflow_ref, row.host_models.join(", "), row.workloads.join(", "), row.quality, number(row.baseline_samples), `${number(row.baseline_min_tokens)} – ${number(row.baseline_max_tokens)}`, `${row.measured_tasks} / ${row.observed_tasks}`, number(row.estimated_operational_savings), number(row.estimated_net_savings), row.issues.join(", ")]));
  element("window").textContent = `${snapshot.days} UTC calendar days · generated ${snapshot.generated_at} · sequence ${snapshot.sequence} · received ${receipts.get(snapshot.source_id) || "unknown"} · retained local runs`;
  const metrics = [
    ["Workflow executions", number(usage.runs), `${usage.running} running · ${usage.execution_errors} execution errors`],
    ["Verified tasks", number(usage.verified), "Includes valid negative findings"],
    ["Workflow runtime", `${(usage.duration_ms / 1000).toLocaleString()}s`, "Machine runtime, not time saved"]
  ];
  if (savings?.net_tokens_saved != null) metrics.push(["Configured-baseline estimate", number(savings.net_tokens_saved), "Separate legacy estimate; do not add it to measured comparisons"]);
  element("metrics").replaceChildren(...metrics.map(metricCard));
  element("coverage").textContent = savings ? `${savings.modeled_runs} of ${usage.terminal} terminal executions have a savings baseline. Manual equivalent: ${number(savings.manual_tokens)} tokens; Owlmatic: ${number(savings.owlmatic_tokens)}; setup: ${number(savings.setup_tokens)}.` : "No legacy configured estimate is included. Agent measurements above use their own recorded task evidence.";
  const workflows = snapshot.workflows || [];
  const workflowSavings = workflows.some(w => w.savings?.net_tokens_saved != null);
  table(element("workflows"), ["Workflow", "Runs", "Verified", "Execution errors", ...(workflowSavings ? ["Legacy net estimate"] : [])], workflows.map(w => [w.ref, number(w.usage.runs), number(w.usage.verified), number(w.usage.execution_errors), ...(workflowSavings ? [number(w.savings?.net_tokens_saved)] : [])]));
  const daily = snapshot.daily || [];
  const dailySavings = daily.some(d => d.estimated_tokens_saved_before_setup != null);
  table(element("days"), ["Date (UTC)", "Runs", "Verified", ...(dailySavings ? ["Legacy estimate before setup"] : [])], daily.map(d => [d.day, number(d.runs), number(d.verified), ...(dailySavings ? [number(d.estimated_tokens_saved_before_setup)] : [])]));
  element("chart").replaceChildren();
  const max = Math.max(1, ...daily.map(d => d.runs));
  for (const day of daily) { const bar = node("div", null, "bar"); bar.style.height = `${Math.max(1, day.runs / max * 100)}%`; bar.title = `${day.day}: ${day.runs} runs`; bar.setAttribute("role", "img"); bar.setAttribute("aria-label", bar.title); element("chart").append(bar); }
  if (!daily.length) element("chart").append(node("p", "Daily activity was not shared.", "muted"));
}
async function load(append = false) {
  const version = ++requestVersion, selected = element("source").value;
  element("status").textContent = "Loading metrics…";
  try {
    const response = await fetch(`/api/v2/sources${append && cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`, {headers: {Authorization: `Bearer ${token}`}, cache: "no-store"});
    if (!response.ok) throw new Error(response.status === 401 ? "Read token rejected. Disconnect and try a valid read token." : "Could not load metrics. Check the receiver.");
    const data = await response.json();
    if (version !== requestVersion) return;
    if (!append) receipts.clear();
    for (const item of data.receipts || []) receipts.set(item.source_id, item.received_at);
    const merged = new Map((append ? sources : []).map(source => [source.source_id, source]));
    for (const source of data.sources) merged.set(source.source_id, source);
    sources = [...merged.values()]; cursor = data.next_cursor || null;
    element("source").replaceChildren(...sources.map(source => { const option = node("option", source.source_label || `Unnamed source · ${source.source_id.slice(0, 8)}`); option.title = source.source_id; option.value = source.source_id; return option; }));
    if (sources.some(source => source.source_id === selected)) element("source").value = selected;
    element("login").hidden = true; element("dashboard").hidden = false; element("more").hidden = !cursor;
    element("status").textContent = sources.length ? `${sources.length} sources loaded. Select one to inspect its latest exported snapshot. Refresh does not upload new local runs.` : "Connected. No snapshots received yet. Configure Owlmatic, then run owlmatic export push.";
    render();
  } catch (error) { if (version === requestVersion) element("status").textContent = error.message; }
}
element("connect").addEventListener("submit", event => { event.preventDefault(); token = element("token").value; element("token").value = ""; load(); });
element("source").addEventListener("change", render);
element("refresh").addEventListener("click", () => load());
element("more").addEventListener("click", () => load(true));
element("disconnect").addEventListener("click", () => { requestVersion++; token = ""; sources = []; cursor = null; receipts.clear(); element("dashboard").hidden = true; element("login").hidden = false; element("metrics").replaceChildren(); element("chart").replaceChildren(); element("workflows").replaceChildren(); element("days").replaceChildren(); element("source").replaceChildren(); element("coverage").textContent = ""; element("window").textContent = ""; element("measurement").replaceChildren(); element("measurement-detail").replaceChildren(); element("measurement-window").textContent = ""; element("context-summary").textContent = ""; element("status").textContent = "Disconnected."; });
