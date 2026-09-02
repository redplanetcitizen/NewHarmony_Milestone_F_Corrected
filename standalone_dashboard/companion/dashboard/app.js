const $ = id => document.getElementById(id);
const ALL_SECTORS = "__all__";
let data;
let state = {mode: "frozen", ecology: "physical", year: 2019, sector: ALL_SECTORS, pollutant: "CO2", shadows: false};

const pct = value => value == null || value === "" ? "n.d." : `${(100 * Number(value)).toLocaleString("it-IT", {maximumFractionDigits: 2})}%`;
const num = value => Number(value).toLocaleString("it-IT", {maximumFractionDigits: 0});
const idx = value => value == null || value === "" ? "n.d." : Number(value).toLocaleString("it-IT", {maximumFractionDigits: 1});
const mass = value => {
  if (value == null || value === "") return "n.d.";
  const kg = Number(value);
  if (Math.abs(kg) < 1000) return `${kg.toLocaleString("it-IT", {maximumFractionDigits: 1})} kg`;
  const tonnes = kg / 1000;
  if (Math.abs(tonnes) < 1e6) return `${tonnes.toLocaleString("it-IT", {maximumFractionDigits: 1})} t`;
  return `${(tonnes / 1e6).toLocaleString("it-IT", {maximumFractionDigits: 2})} Mt`;
};
const escapeHtml = value => String(value).replace(/[&<>"']/g, char => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
})[char]);

function modeData() { return data.modes[state.mode]; }
function annualRows() { return modeData().annual.filter(row => state.shadows || Number(row.published) === 1); }
function sectorEconomicRows() {
  if (state.sector === ALL_SECTORS) return [];
  const visible = new Set(annualRows().map(row => Number(row.year)));
  return modeData().sector_economy.filter(row => row.sector_name === state.sector && visible.has(Number(row.year)));
}
function physicalRows() {
  const source = state.sector === ALL_SECTORS ? modeData().physical_ecological : modeData().physical_sector_contributions;
  return source.filter(row => row.pollutant === state.pollutant &&
    (state.sector === ALL_SECTORS || row.sector_name === state.sector) &&
    (state.shadows || Number(row.published) === 1));
}
function associationRows(pollutant = state.pollutant) {
  return modeData().qualitative_associations.filter(row => row.pollutant === pollutant &&
    (state.sector === ALL_SECTORS || row.sector_name === state.sector) && Number(row.year) === state.year);
}

function drawEmpty(canvas, message) {
  const dpr = devicePixelRatio || 1, width = canvas.clientWidth, height = 300;
  canvas.width = width * dpr; canvas.height = height * dpr;
  const context = canvas.getContext("2d"); context.scale(dpr, dpr); context.clearRect(0, 0, width, height);
  context.fillStyle = "#64706a"; context.font = "14px Segoe UI"; context.textAlign = "center";
  const words = message.split(" "); let lines = [""];
  words.forEach(word => {
    const candidate = `${lines[lines.length - 1]} ${word}`.trim();
    if (context.measureText(candidate).width > width - 60) lines.push(word); else lines[lines.length - 1] = candidate;
  });
  lines.forEach((text, i) => context.fillText(text, width / 2, height / 2 + (i - (lines.length - 1) / 2) * 20));
}

function line(canvas, series, labels, options = {}) {
  const values = series.flatMap(item => item.values).filter(Number.isFinite);
  if (!values.length || !labels.length) { drawEmpty(canvas, options.emptyMessage || "Nessun dato disponibile"); return; }
  const dpr = devicePixelRatio || 1, width = canvas.clientWidth, height = 300;
  canvas.width = width * dpr; canvas.height = height * dpr;
  const context = canvas.getContext("2d"); context.scale(dpr, dpr); context.clearRect(0, 0, width, height);
  const margin = {l: 58, r: 15, t: 20, b: 35};
  const minimum = options.min ?? Math.min(...values), maximum = options.max ?? Math.max(...values), span = maximum - minimum || 1;
  const x = i => margin.l + (width - margin.l - margin.r) * (labels.length === 1 ? .5 : i / (labels.length - 1));
  const y = v => margin.t + (height - margin.t - margin.b) * (1 - (v - minimum) / span);
  context.font = "11px Segoe UI"; context.strokeStyle = "#ddd7ca"; context.fillStyle = "#69736d"; context.textAlign = "left";
  for (let step = 0; step < 5; step++) {
    const value = minimum + span * step / 4, yy = y(value);
    context.beginPath(); context.moveTo(margin.l, yy); context.lineTo(width - margin.r, yy); context.stroke();
    const label = options.percent ? `${Math.round(value * 100)}%` : (options.axisFormatter ? options.axisFormatter(value) : Math.round(value));
    context.fillText(label, 4, yy + 4);
  }
  labels.forEach((value, i) => context.fillText(value, x(i) - 12, height - 10));
  series.forEach(item => {
    context.strokeStyle = item.color; context.lineWidth = 2.5; context.beginPath();
    item.values.forEach((value, i) => i ? context.lineTo(x(i), y(value)) : context.moveTo(x(i), y(value))); context.stroke();
    item.values.forEach((value, i) => { context.fillStyle = item.color; context.beginPath(); context.arc(x(i), y(value), 3, 0, Math.PI * 2); context.fill(); });
  });
}

function renderControls() {
  const available = annualRows();
  if (!available.some(row => Number(row.year) === state.year)) state.year = Number(available[0].year);
  $("year").innerHTML = available.map(row => `<option value="${row.year}" ${Number(row.year) === state.year ? "selected" : ""}>${row.year}${Number(row.published) ? "" : " · ombra"}</option>`).join("");
  $("sector").innerHTML = [`<option value="${ALL_SECTORS}" ${state.sector === ALL_SECTORS ? "selected" : ""}>Tutti i settori</option>`, ...data.sectors.map(sector => {
    const suffix = sector.ecologically_mapped ? "" : " · dato ecologico non disponibile";
    return `<option value="${escapeHtml(sector.sector_name)}" ${sector.sector_name === state.sector ? "selected" : ""}>${escapeHtml(sector.sector_name + suffix)}</option>`;
  })].join("");
  const pollutants = state.ecology === "physical" ? data.pollutants : data.pollutants;
  if (!pollutants.includes(state.pollutant)) state.pollutant = pollutants[0];
  $("pollutant").innerHTML = pollutants.map(name => {
    const unavailable = state.ecology === "physical" && !data.physical_pollutants.includes(name) ? " · coefficiente non disponibile" : "";
    return `<option value="${escapeHtml(name)}" ${name === state.pollutant ? "selected" : ""}>${escapeHtml(name + unavailable)}</option>`;
  }).join("");
}

function renderEconomicChart(annual) {
  if (state.sector === ALL_SECTORS) {
    $("economicTitle").textContent = "Prestazione economica complessiva";
    $("economicLegend").innerHTML = '<span class="fulfillment">Soddisfacimento globale</span><span class="harmony">Harmony globale</span>';
    line($("economicChart"), [
      {values: annual.map(row => Number(row.fulfillment)), color: "#237a57"},
      {values: annual.map(row => Number(row.harmony)), color: "#356a86"}
    ], annual.map(row => row.year), {percent: true, min: Math.min(...annual.map(row => Number(row.harmony))) - .03, max: 1});
    return;
  }
  const rows = sectorEconomicRows();
  $("economicTitle").textContent = `${state.sector} · risultato anno per anno`;
  $("economicLegend").innerHTML = '<span class="fulfillment">Produzione / fabbisogno-obiettivo</span><span class="harmony">Harmony diagnostica settoriale</span>';
  line($("economicChart"), [
    {values: rows.map(row => Number(row.gross_requirement_coverage)), color: "#237a57"},
    {values: rows.map(row => Number(row.diagnostic_sector_harmony)), color: "#356a86"}
  ], rows.map(row => row.year), {percent: true, min: Math.min(...rows.map(row => Number(row.diagnostic_sector_harmony))) - .03, max: 1,
    emptyMessage: "Diagnostica settoriale non disponibile"});
}

function renderEcologicalChart() {
  if (state.ecology === "qualitative") {
    const rows = associationRows();
    const selected = state.sector === ALL_SECTORS ? null : rows[0];
    $("pollutantTitle").textContent = state.sector === ALL_SECTORS ? `${state.pollutant} · mappa delle associazioni` : `${state.pollutant} · ${state.sector}`;
    drawEmpty($("ecoChart"), "La modalità qualitativa classifica le associazioni 0/1/2 e non costruisce una traiettoria quantitativa.");
    $("ecoNote").textContent = "0 = nessuna associazione; 1 = operativa; 2 = caratteristica. Le categorie non sono masse né livelli di pericolosità.";
    return {signal: selected?.association_label || (state.sector === ALL_SECTORS ? "categorie" : "nessuna")};
  }
  const rows = physicalRows();
  if (state.sector === ALL_SECTORS) {
    const values = rows.map(row => row.index_2019_100 == null || row.index_2019_100 === "" ? NaN : Number(row.index_2019_100));
    $("pollutantTitle").textContent = `${state.pollutant} · pressione fisica aggregata`;
    $("ecoNote").textContent = "Indice della massa diretta, base 2019 = 100. Il semaforo segnala la variazione della pressione, non la pericolosità.";
    line($("ecoChart"), [{values, color: "#b84337"}], rows.map(row => row.year), {
      min: values.some(Number.isFinite) ? Math.min(95, ...values.filter(Number.isFinite)) : undefined,
      max: values.some(Number.isFinite) ? Math.max(105, ...values.filter(Number.isFinite)) : undefined,
      emptyMessage: "Coefficiente fisico non disponibile per questo inquinante"
    });
    return rows.find(row => Number(row.year) === state.year) || {signal: "n.d."};
  }
  const tonnes = rows.map(row => Number(row.value_kg) / 1000);
  $("pollutantTitle").textContent = `${state.pollutant} · ${state.sector} · tonnellate dirette`;
  $("ecoNote").textContent = "Stima fisica con intensità 2012 costante, riscalata per l’attività reale. Semaforo settoriale n.d.: mancano soglie documentate specifiche.";
  line($("ecoChart"), [{values: tonnes, color: "#b84337"}], rows.map(row => row.year), {
    axisFormatter: value => Number(value).toLocaleString("it-IT", {notation: "compact", maximumFractionDigits: 1}),
    emptyMessage: "Coefficiente fisico non disponibile per questa coppia settore–inquinante"
  });
  return {signal: "n.d.", value_kg: rows.find(row => Number(row.year) === state.year)?.value_kg};
}

function associationBadge(row) {
  return `<span class="association level-${row.association_level}">${escapeHtml(row.association_label)}</span>`;
}

function renderContributionPanel() {
  if (state.ecology === "qualitative") {
    let rows = modeData().qualitative_associations.filter(row => Number(row.year) === state.year &&
      (state.sector === ALL_SECTORS ? row.pollutant === state.pollutant : row.sector_name === state.sector));
    rows.sort((a, b) => Number(b.association_level) - Number(a.association_level) || (state.sector === ALL_SECTORS ? a.sector_name : a.pollutant).localeCompare(state.sector === ALL_SECTORS ? b.sector_name : b.pollutant));
    $("contributionTitle").textContent = state.sector === ALL_SECTORS ? `Associazioni settoriali · ${state.pollutant}` : `Profilo qualitativo · ${state.sector}`;
    $("sectors").innerHTML = rows.map(row => `<div class="association-row"><button type="button" data-pollutant="${escapeHtml(row.pollutant)}">${escapeHtml(state.sector === ALL_SECTORS ? row.sector_name : row.pollutant)}</button>${associationBadge(row)}</div>`).join("") || '<p class="empty-note">Nessuna associazione documentata.</p>';
  } else {
    let rows;
    if (state.sector === ALL_SECTORS) {
      rows = modeData().physical_top_sectors[`${state.year}|${state.pollutant}`] || [];
      $("contributionTitle").textContent = `Maggiori masse settoriali · ${state.pollutant}`;
    } else {
      rows = modeData().physical_sector_contributions.filter(row => row.sector_name === state.sector && Number(row.year) === state.year)
        .sort((a, b) => Number(b.value_kg) - Number(a.value_kg)).slice(0, 10);
      $("contributionTitle").textContent = `Masse principali · ${state.sector}`;
    }
    const maximum = Math.max(1, ...rows.map(row => Number(row.value_kg)));
    $("sectors").innerHTML = rows.map(row => `<div class="bar-row ${row.pollutant === state.pollutant ? "selected-bar" : ""}" data-pollutant="${escapeHtml(row.pollutant)}"><button type="button" class="bar-label-button">${escapeHtml(state.sector === ALL_SECTORS ? row.sector_name : row.pollutant)}</button><div class="bar-track"><div class="bar-fill" style="width:${100 * Number(row.value_kg) / maximum}%"></div></div><span class="bar-value">${escapeHtml(mass(row.value_kg))}</span></div>`).join("") || '<p class="empty-note">Massa fisica non disponibile.</p>';
  }
  $("sectors").querySelectorAll("[data-pollutant]").forEach(row => row.addEventListener("click", () => { state.pollutant = row.dataset.pollutant; render(); }));
}

function renderKpis(annual, current, currentEco, coverage) {
  const published = annual.filter(row => Number(row.published) === 1);
  let cards;
  if (state.sector === ALL_SECTORS) {
    if (state.ecology === "physical") {
      cards = [["Soddisfacimento minimo", pct(Math.min(...published.map(row => row.fulfillment)))], ["Harmony media", pct(published.reduce((s, r) => s + Number(r.harmony), 0) / published.length)],
        [`Massa ${state.pollutant}`, mass(currentEco?.value_kg)], [`Indice ${state.pollutant} · 2019=100`, idx(currentEco?.index_2019_100)], ["Output ecologicamente coperto", pct(coverage.coverage_ratio)]];
    } else {
      const summary = modeData().qualitative_summary.find(row => Number(row.year) === state.year && row.pollutant === state.pollutant);
      cards = [["Soddisfacimento minimo", pct(Math.min(...published.map(row => row.fulfillment)))], ["Harmony media", pct(published.reduce((s, r) => s + Number(r.harmony), 0) / published.length)],
        ["Associazioni caratteristiche", summary?.characteristic_sector_count ?? "n.d."], ["Associazioni operative", summary?.operational_sector_count ?? "n.d."], ["Output ecologicamente coperto", pct(coverage.coverage_ratio)]];
    }
  } else {
    const rows = sectorEconomicRows(), sector = rows.find(row => Number(row.year) === state.year);
    const ecologicalValue = state.ecology === "physical" ? mass(currentEco?.value_kg) : (associationRows()[0]?.association_label || "nessuna");
    cards = [["Output del settore", sector ? `${num(sector.gross_output_real_musd)} M$` : "n.d."], ["Produzione / fabbisogno-obiettivo", pct(sector?.gross_requirement_coverage)],
      ["Harmony diagnostica settoriale", pct(sector?.diagnostic_sector_harmony)], [`${state.pollutant} · ${state.ecology === "physical" ? "massa" : "associazione"}`, ecologicalValue], ["Output ecologicamente coperto", pct(coverage.coverage_ratio)]];
  }
  $("kpis").innerHTML = cards.map(([label, value]) => `<div class="kpi"><div class="label">${escapeHtml(label)}</div><div class="value">${escapeHtml(value)}</div></div>`).join("");
}

function render() {
  renderControls();
  const annual = annualRows(), current = annual.find(row => Number(row.year) === state.year) || annual[0];
  const coverage = modeData().coverage.find(row => Number(row.year) === state.year);
  renderEconomicChart(annual);
  const currentEco = renderEcologicalChart();
  const currentSignal = currentEco?.signal || "n.d.";
  $("signal").className = `signal ${["verde", "giallo", "arancione", "rosso"].includes(currentSignal) ? currentSignal : "n-d"}`;
  $("signal").textContent = currentSignal;
  renderContributionPanel(); renderKpis(annual, current, currentEco, coverage);
  $("notice").innerHTML = state.ecology === "physical" ? '<strong>Contabilità fisica diretta.</strong> Masse stimate con coefficienti 2012 e rapporti di attività reale; il semaforo aggregato misura variazioni rispetto al 2019, non pericolosità.' : '<strong>Mappa qualitativa.</strong> Le classi 0/1/2 significano nessuna associazione, operativa o caratteristica; non sono quantità e non generano un semaforo.';
  $("repo").innerHTML = `<a href="${escapeHtml(data.meta.source_repository)}">${escapeHtml(data.meta.source_repository.replace("https://github.com/", ""))}</a>`;
  $("commit").textContent = data.meta.source_commit; $("hash").textContent = data.meta.source_tree_sha256; $("coverage").textContent = pct(coverage.coverage_ratio);
}

async function init() {
  data = await fetch("data.json").then(response => { if (!response.ok) throw Error(response.status); return response.json(); });
  state.pollutant = data.pollutants.includes("CO2") ? "CO2" : data.pollutants[0];
  $("mode").onchange = event => { state.mode = event.target.value; state.year = 2019; render(); };
  $("ecologyMode").onchange = event => { state.ecology = event.target.value; render(); };
  $("year").onchange = event => { state.year = Number(event.target.value); render(); };
  $("sector").onchange = event => { state.sector = event.target.value; render(); };
  $("pollutant").onchange = event => { state.pollutant = event.target.value; render(); };
  $("shadows").onchange = event => { state.shadows = event.target.checked; render(); };
  addEventListener("resize", render); render();
}

init().catch(error => document.body.innerHTML = `<pre>Impossibile caricare i dati: ${escapeHtml(error.message)}</pre>`);
