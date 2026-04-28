/* ═══════════════════════════════════════════════════════════════════════════
   SUIVI PR — Frontend JavaScript
   ═══════════════════════════════════════════════════════════════════════════ */

"use strict";

/* ── STATE ──────────────────────────────────────────────────────────────────── */
let allPRs       = [];
let selectedPRId = null;
let donutChart   = null;
let processingLimits = {};
let allDocuments  = [];
let hybridSteps  = [];
let editingDocId = null;

/* ── INIT ───────────────────────────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", () => {
  clock();
  setInterval(clock, 1000);
  headerDate();
  loadProcessingLimits();
  loadDocuments();
  loadPRList();
  loadKPIData();
  bindForm();
  bindSearch();
  bindImportExport();
  bindStatusDropdown();
  bindModalClose();
  bindHelpButton();
  bindDocumentsButton();
  bindKPIControls();
  bindKPISearch();
});

/* ── CLOCK ──────────────────────────────────────────────────────────────────── */
function clock() {
  const el = document.getElementById("clockDisplay");
  if (!el) return;
  const now = new Date();
  el.textContent = now.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function headerDate() {
  const el = document.getElementById("headerDate");
  if (!el) return;
  el.textContent = new Date().toLocaleDateString("fr-FR", { weekday: "long", year: "numeric", month: "long", day: "numeric" });
}

/* ── API HELPERS ────────────────────────────────────────────────────────────── */
async function api(path, method = "GET", body = null) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  return res.json();
}

async function loadProcessingLimits() {
  processingLimits = await api("/api/processing-limits");
}

function showProcessingLimitsHelp() {
  const html = Object.entries(processingLimits).map(([cat, data]) => `
    <div class="help-category" style="margin-bottom:20px;padding:12px;border:1px solid #E0E0E0;border-radius:6px">
      <h4 style="margin:0 0 10px 0;color:#2C3E50"><span class="glyphicon glyphicon-file"></span> ${cat}</h4>
      <div style="font-weight:bold;margin-bottom:8px;color:#C0392B">Délai max de traitement : ${data.max_weeks} semaines</div>
      <div style="font-size:13px;margin-bottom:10px">
        <span style="color:#666">Répartition par étape :</span>
      </div>
      <ul style="margin:0;padding-left:20px;font-size:13px">
        ${Object.entries(data.steps).map(([step, weeks]) => `
          <li style="margin:4px 0"><strong>${step}</strong>: ${weeks} semaine${weeks > 1 ? 's' : ''}</li>
        `).join('')}
      </ul>
    </div>
  `).join('');
  
  Swal.fire({
    title: 'Guide des Délais de Traitement',
    html: html,
    icon: 'info',
    width: 500,
    confirmButtonText: 'Fermer',
    didOpen: () => {
      const popup = Swal.getPopup();
      popup.style.maxHeight = '70vh';
      popup.style.overflowY = 'auto';
    }
  });
}

function bindHelpButton() {
  const helpBtn = document.getElementById("btnProcessingHelp");
  if (helpBtn) {
    helpBtn.addEventListener("click", showProcessingLimitsHelp);
  }
}

/* ── DOCUMENTS MANAGEMENT ───────────────────────────────────────────────────── */
function bindDocumentsButton() {
  const docsBtn = document.getElementById("btnDocuments");
  if (docsBtn) {
    docsBtn.addEventListener("click", openDocumentsModal);
  }
}

async function loadDocuments() {
  try {
    allDocuments = await api("/api/documents");
  } catch (err) {
    console.error("[v0] Failed to load documents:", err);
    allDocuments = [];
  }
}

function openDocumentsModal() {
  const modal = document.getElementById("documentsModal");
  if (modal) {
    modal.style.display = "flex";
    renderDocumentsList();
    
    // Set default color button selection (blue #2196F3)
    const colorPicker = document.getElementById("docColorPicker");
    if (colorPicker) {
      colorPicker.querySelectorAll(".color-btn").forEach(btn => {
        btn.classList.remove("selected");
        if (btn.style.background === "#2196F3" || btn.style.backgroundColor === "#2196F3") {
          btn.classList.add("selected");
        }
      });
    }
  }
}

function renderDocumentsList() {
  const container = document.getElementById("documentsList");
  if (!container) return;
  
  const pendingDocs = allDocuments.filter(doc => !doc.done);
  
  if (pendingDocs.length === 0) {
    container.innerHTML = '<div style="text-align:center;color:#999;padding:20px"><span class="glyphicon glyphicon-inbox"></span><p>Aucun document en attente</p></div>';
    return;
  }
  
  container.innerHTML = pendingDocs.map(doc => `
    <div class="document-item">
      <input type="checkbox" class="document-checkbox" 
             ${doc.done ? 'checked' : ''} 
             onchange="toggleDocument('${doc.id}', this.checked)" 
             id="checkbox-${doc.id}">
      <div class="document-color-tag" style="background-color:${doc.color}"></div>
      <div class="document-info">
        <div class="document-name">${escapeHtml(doc.name)}</div>
        <span class="document-status" style="border-color:${doc.color};color:${doc.color}">${escapeHtml(doc.status)}</span>
      </div>
      <div class="document-actions">
        <button class="btn-doc-edit" onclick="openDocumentEdit('${doc.id}')" title="Modifier">
          <span class="glyphicon glyphicon-pencil"></span>
        </button>
        <button class="btn-doc-delete" onclick="deleteDocument('${doc.id}')" title="Supprimer">
          <span class="glyphicon glyphicon-trash"></span>
        </button>
      </div>
    </div>
  `).join('');
}

async function addDocument() {
  const name = document.getElementById("docName").value.trim();
  const status = document.getElementById("docStatus").value.trim();
  const color = document.getElementById("docColor").value;
  
  if (!name) {
    showToast("Veuillez entrer un nom de document", "error");
    return;
  }
  
  const result = await api("/api/documents", "POST", {
    name: name,
    status: status || "En attente",
    color: color
  });
  
  if (result.error) {
    showToast(result.error, "error");
    return;
  }
  
  allDocuments.push(result);
  document.getElementById("docName").value = "";
  document.getElementById("docStatus").value = "";
  document.getElementById("docColor").value = "#3498db";
  
  renderDocumentsList();
  showToast("Document ajouté avec succès", "success");
}

async function toggleDocument(docId, isDone) {
  const doc = allDocuments.find(d => d.id === docId);
  if (!doc) return;
  
  const result = await api(`/api/documents/${docId}`, "PUT", {
    ...doc,
    done: isDone ? 1 : 0
  });
  
  if (result.error) {
    showToast("Erreur lors de la mise à jour", "error");
    return;
  }
  
  doc.done = result.done;
  renderDocumentsList();
}

async function deleteDocument(docId) {
  Swal.fire({
    title: 'Supprimer le document ?',
    text: 'Cette action est irréversible.',
    icon: 'warning',
    showCancelButton: true,
    confirmButtonText: 'Supprimer',
    cancelButtonText: 'Annuler',
    confirmButtonColor: '#C0392B'
  }).then(async (result) => {
    if (!result.isConfirmed) return;
    
    const apiResult = await api(`/api/documents/${docId}`, "DELETE");
    if (apiResult.error) {
      showToast("Erreur lors de la suppression", "error");
      return;
    }
    
    allDocuments = allDocuments.filter(d => d.id !== docId);
    renderDocumentsList();
    showToast("Document supprimé", "success");
  });
}

function openDocumentEdit(docId) {
  const doc = allDocuments.find(d => d.id === docId);
  if (!doc) return;
  
  editingDocId = docId;
  document.getElementById("editDocName").value = doc.name;
  document.getElementById("editDocStatus").value = doc.status;
  document.getElementById("editDocColor").value = doc.color;
  
  // Mark the correct color button as selected
  const editColorPicker = document.getElementById("editDocColorPicker");
  if (editColorPicker) {
    editColorPicker.querySelectorAll(".color-btn").forEach(btn => {
      btn.classList.remove("selected");
      if (btn.style.background === doc.color || btn.style.backgroundColor === doc.color) {
        btn.classList.add("selected");
      }
    });
  }
  
  const modal = document.getElementById("documentEditModal");
  if (modal) {
    modal.style.display = "flex";
  }
}

async function saveDocumentEdit() {
  if (!editingDocId) return;
  
  const name = document.getElementById("editDocName").value.trim();
  const status = document.getElementById("editDocStatus").value.trim();
  const color = document.getElementById("editDocColor").value;
  
  if (!name) {
    showToast("Veuillez entrer un nom de document", "error");
    return;
  }
  
  const doc = allDocuments.find(d => d.id === editingDocId);
  if (!doc) return;
  
  const result = await api(`/api/documents/${editingDocId}`, "PUT", {
    name: name,
    status: status || "En attente",
    color: color,
    done: doc.done
  });
  
  if (result.error) {
    showToast("Erreur lors de la modification", "error");
    return;
  }
  
  doc.name = result.name;
  doc.status = result.status;
  doc.color = result.color;
  
  closeModal("documentEditModal");
  renderDocumentsList();
  showToast("Document modifié avec succès", "success");
}

function escapeHtml(text) {
  const map = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'};
  return text.replace(/[&<>"']/g, m => map[m]);
}

/* ── HYBRID PR MANAGEMENT ──────────────────────────────────────────────────── */
let editingHybridPRId = null;
let editingStepId = null;

async function openStepEdit(prId, stepId) {
  editingHybridPRId = prId;
  editingStepId = stepId;

  // Fetch the full PR (with tasks) from the API
  const pr = await api(`/api/pr/${prId}`);
  if (!pr || !pr.tasks) return;

  const stepData = pr.tasks[stepId];
  if (!stepData) return;

  document.getElementById("editStepTitle").value = stepData.title || "";
  document.getElementById("editStepDesc").value = stepData.desc || "";

  const modal = document.getElementById("stepEditModal");
  if (modal) modal.style.display = "flex";
}

async function saveStepEdit() {
  if (!editingHybridPRId || !editingStepId) return;
  
  const title = document.getElementById("editStepTitle").value.trim();
  const desc = document.getElementById("editStepDesc").value.trim();
  
  if (!title) {
    showToast("Veuillez entrer un titre pour l'étape", "error");
    return;
  }
  
  const result = await api(`/api/pr/${editingHybridPRId}/step/${editingStepId}`, "PUT", {
    title: title,
    desc: desc
  });
  
  if (result.error) {
    showToast("Erreur lors de la modification", "error");
    return;
  }
  
  closeModal("stepEditModal");
  selectPR(editingHybridPRId);
  showToast("Étape modifiée avec succès", "success");
}

function openHybridCategoryEdit(prId) {
  editingHybridPRId = prId;
  const pr = allPRs.find(p => p.id === prId);
  if (!pr) return;
  
  document.getElementById("hybridCategoryNameInput").value = pr.category;
  const modal = document.getElementById("hybridCategoryEditModal");
  if (modal) modal.style.display = "flex";
}

async function saveHybridCategoryName() {
  if (!editingHybridPRId) return;
  
  const newName = document.getElementById("hybridCategoryNameInput").value.trim();
  if (!newName) {
    showToast("Veuillez entrer un nom de catégorie", "error");
    return;
  }
  
  const result = await api(`/api/pr/${editingHybridPRId}`, "PUT", {
    category: newName
  });
  
  if (result.error) {
    showToast("Erreur lors de la modification", "error");
    return;
  }
  
  const pr = allPRs.find(p => p.id === editingHybridPRId);
  if (pr) {
    pr.category = newName;
    // baseCategory stays "Hybride" — don't change it
  }
  
  closeModal("hybridCategoryEditModal");
  selectPR(editingHybridPRId);
  showToast("Catégorie modifiée avec succès", "success");
}

async function openAddHybridStepModal(prId) {
  editingHybridPRId = prId;
  document.getElementById("hybridStepTitle").value = "";
  document.getElementById("hybridStepDesc").value = "";
  const modal = document.getElementById("hybridAddStepModal");
  if (modal) modal.style.display = "flex";
}

async function saveNewHybridStep() {
  if (!editingHybridPRId) return;
  
  const title = document.getElementById("hybridStepTitle").value.trim();
  const desc = document.getElementById("hybridStepDesc").value.trim();
  
  if (!title) {
    showToast("Veuillez entrer un titre pour l'étape", "error");
    return;
  }
  
  const result = await api(`/api/pr/${editingHybridPRId}/add-step`, "POST", {
    title: title,
    desc: desc
  });
  
  if (result.error) {
    showToast("Erreur lors de l'ajout de l'étape", "error");
    return;
  }
  
  closeModal("hybridAddStepModal");
  selectPR(editingHybridPRId);
  showToast("Étape ajoutée avec succès", "success");
}

/* ── KPI PROCESSING DELAYS ──────────────────────────────────────────────────── */
async function loadKPIData() {
  await renderKPITable("");
}

function bindKPIControls() {
  const filterSelect = document.getElementById("kpiCategoryFilter");
  const updateBtn = document.getElementById("btnUpdateKPI");
  const exportBtn = document.getElementById("btnExportKPI");
  
  if (filterSelect) {
    filterSelect.addEventListener("change", (e) => {
      renderKPITable(e.target.value);
    });
  }
  
  if (updateBtn) {
    updateBtn.addEventListener("click", async () => {
      updateBtn.disabled = true;
      updateBtn.innerHTML = '<span class="glyphicon glyphicon-refresh" style="animation:spin 1s linear infinite"></span> Mise à jour...';
      await renderKPITable(document.getElementById("kpiCategoryFilter").value);
      updateBtn.disabled = false;
      updateBtn.innerHTML = '<span class="glyphicon glyphicon-refresh"></span> Mise à jour';
      showToast("Délais recalculés avec succès", "success");
    });
  }

  if (exportBtn) {
    exportBtn.addEventListener("click", () => {
      const category = document.getElementById("kpiCategoryFilter").value;
      let url = "/api/export-kpi";
      if (category) url += `?category=${encodeURIComponent(category)}`;
      window.location.href = url;
      showToast("Export KPI en cours...", "success");
    });
  }
}

async function renderKPITable(category = "") {
  // Clear search when changing category filter
  const searchInput = document.getElementById("kpiSearchInput");
  if (searchInput) {
    searchInput.value = "";
  }
  await filterKPITable("", category);
}

function getKPIIndicator(category, delayWeeks, status) {
  if (status !== "cloturee") {
    return '<span class="kpi-indicator warning"><span class="glyphicon glyphicon-time"></span> En cours</span>';
  }
  
  let maxWeeks = 0;
  if (category === "ED") maxWeeks = 10;
  else if (category === "CR") maxWeeks = 11;
  else if (category === "COU") maxWeeks = 14;
  else if (category === "REG") maxWeeks = 10;
  else if (category === "Hybride") maxWeeks = 14; // Default to 14 for hybrid
  
  if (maxWeeks === 0) {
    return '<span class="kpi-indicator warning"><span class="glyphicon glyphicon-question-sign"></span> N/A</span>';
  }
  
  if (delayWeeks <= maxWeeks) {
    return `<span class="kpi-indicator ontime"><span class="glyphicon glyphicon-ok"></span> À temps</span>`;
  } else {
    const excess = (delayWeeks - maxWeeks).toFixed(1);
    return `<span class="kpi-indicator late"><span class="glyphicon glyphicon-alert"></span> +${excess}s</span>`;
  }
}

/* ── LOAD ALL PR ────────────────────────────────────────────────────────────── */
async function loadPRList(query = "") {
  const url = query ? `/api/pr?q=${encodeURIComponent(query)}` : "/api/pr";
  allPRs = await fetch(url).then(r => r.json());
  renderPRList();
  updateDashboard();
}

/* ── RENDER PR LIST ─────────────────────────────────────────────────────────── */
function renderPRList() {
  const container = document.getElementById("prList");
  const badge     = document.getElementById("prCountBadge");
  badge.textContent = allPRs.length;

  if (!allPRs.length) {
    container.innerHTML = `
      <div class="no-pr">
        <span class="glyphicon glyphicon-inbox"></span>
        <p>Aucune demande trouvée</p>
      </div>`;
    return;
  }

  container.innerHTML = allPRs.map(pr => {
    const baseCat = pr.baseCategory || pr.category;
    let lateIndicator = "";
    if (pr.late_steps > 0) {
      lateIndicator = `<span class="pr-delay-badge badge-late" title="${pr.late_steps} étape(s) en retard">
        <span class="glyphicon glyphicon-warning-sign"></span> ${pr.late_steps} retard
      </span>`;
    } else if (pr.warning_steps > 0) {
      lateIndicator = `<span class="pr-delay-badge badge-warning" title="${pr.warning_steps} étape(s) à risque">
        <span class="glyphicon glyphicon-time"></span> ${pr.warning_steps} risque
      </span>`;
    }
    
    let exceedIndicator = "";
    if (pr.exceeded) {
      exceedIndicator = `<span class="pr-delay-badge badge-exceed" title="Délai max dépassé (${pr.processing_weeks} / ${pr.max_weeks} semaines)">
        <span class="glyphicon glyphicon-alert"></span> Dépassé
      </span>`;
    }
    
    return `
    <div class="pr-item ${pr.id === selectedPRId ? "selected" : ""}" data-id="${pr.id}" onclick="selectPR('${pr.id}')">
      <div class="pr-item-top">
        <div>
          <div class="pr-item-number">PR #${pr.number}</div>
          <div class="pr-item-title" title="${escHtml(pr.title)}">${escHtml(pr.title)}</div>
        </div>
        <div class="pr-item-actions">
          <button class="pr-action-btn edit-btn" title="Modifier" onclick="editPR(event,'${pr.id}')">
            <span class="glyphicon glyphicon-pencil"></span>
          </button>
          <button class="pr-action-btn del-btn" title="Supprimer" onclick="deletePR(event,'${pr.id}')">
            <span class="glyphicon glyphicon-trash"></span>
          </button>
        </div>
      </div>
      <div class="pr-item-meta">
        <span class="pr-cat-badge">${pr.category}</span>
        <span class="pr-date"><span class="glyphicon glyphicon-calendar"></span> ${pr.createdDate}</span>
      </div>
      <div class="pr-item-progress" style="margin-bottom:4px">
        <div class="mini-progress-track">
          <div class="mini-progress-fill" style="width:${pr.progress}%"></div>
        </div>
        <span class="mini-progress-pct">${pr.progress}%</span>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:4px">
        <span class="status-badge status-${pr.status.replace("-", "")}"
              onclick="openStatusMenu(event,'${pr.id}')" data-id="${pr.id}">
          ${statusDot(pr.status)} ${statusLabel(pr.status)}
        </span>
        <small style="color:var(--grey-400);font-size:10px">${pr.completed_tasks}/${pr.total_tasks} étapes</small>
      </div>
      <div style="display:flex;gap:4px;flex-wrap:wrap;margin-top:4px">
        ${lateIndicator}
        ${exceedIndicator}
      </div>
    </div>`;
  }).join("");
}

function statusLabel(s) {
  return { "en-cours": "En Cours", "cloturee": "Clôturée", "blockee": "Bloquée", "annulee": "Annulée" }[s] || s;
}
function statusDot(s) {
  const c = { "en-cours": "#FFC107", "cloturee": "#28A745", "blockee": "#C0392B", "annulee": "#BDBDBD" }[s] || "#ccc";
  return `<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:${c};margin-right:2px"></span>`;
}
function escHtml(str) {
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/* ── DELAY ICON ─────────────────────────────────────────────────────────────── */
function delayIcon(delay) {
  if (delay === "ontime") {
    return `<span class="delay-icon delay-ontime" title="Dans les délais">
              <span class="glyphicon glyphicon-ok-circle"></span>
            </span>`;
  }
  if (delay === "warning") {
    return `<span class="delay-icon delay-warning" title="Risque de retard (1–5 jours)">
              <span class="glyphicon glyphicon-time"></span>
            </span>`;
  }
  if (delay === "late") {
    return `<span class="delay-icon delay-late" title="En retard (plus de 5 jours)">
              <span class="glyphicon glyphicon-warning-sign"></span>
            </span>`;
  }
  return "";
}

/* ── DASHBOARD ──────────────────────────────────────────────────────────────── */
function updateDashboard() {
  const total    = allPRs.length;
  const cloturee = allPRs.filter(p => p.status === "cloturee").length;
  const enCours  = allPRs.filter(p => p.status === "en-cours").length;
  const blockee  = allPRs.filter(p => p.status === "blockee").length;
  const annulee  = allPRs.filter(p => p.status === "annulee").length;
  const avgProg  = total ? Math.round(allPRs.reduce((a, p) => a + p.progress, 0) / total) : 0;
  const totalLate    = allPRs.reduce((a, p) => a + (p.late_steps || 0), 0);
  const totalWarning = allPRs.reduce((a, p) => a + (p.warning_steps || 0), 0);

  animateCount("kpiTotal",    total);
  animateCount("kpiAvg",      avgProg);
  animateCount("kpiCloturee", cloturee);
  animateCount("kpiEnCours",  enCours);
  animateCount("kpiBlockee",  blockee);
  animateCount("kpiAnnulee",  annulee);

  const donutTotalEl = document.getElementById("donutTotal");
  if (donutTotalEl) donutTotalEl.textContent = total;

  renderDonut(cloturee, enCours, blockee, annulee);
  renderStatusBars(total, cloturee, enCours, blockee, annulee);
  renderRecentActivity();
  renderAlertBanner(totalLate, totalWarning);
  loadAndRenderAlerts();
}

function animateCount(id, target) {
  const el = document.getElementById(id);
  if (!el) return;
  const start    = parseInt(el.textContent) || 0;
  const duration = 600;
  let start_time = null;
  const step = (timestamp) => {
    if (!start_time) start_time = timestamp;
    const progress = Math.min((timestamp - start_time) / duration, 1);
    el.textContent = Math.round(start + (target - start) * easeOut(progress));
    if (progress < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}
function easeOut(t) { return 1 - Math.pow(1 - t, 3); }

function renderDonut(cloturee, enCours, blockee, annulee) {
  const ctx = document.getElementById("donutChart");
  if (!ctx) return;
  const data   = [enCours, cloturee, blockee, annulee];
  const colors = ["#FFC107", "#28A745", "#C0392B", "#BDBDBD"];
  const labels = ["En Cours", "Clôturée", "Bloquée", "Annulée"];

  if (donutChart) donutChart.destroy();
  donutChart = new Chart(ctx, {
    type: "doughnut",
    data: { labels, datasets: [{ data, backgroundColor: colors, borderWidth: 0, hoverOffset: 6 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      cutout: "72%",
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => ` ${c.label}: ${c.raw}` } } }
    }
  });

  const legend = document.getElementById("donutLegend");
  if (legend) {
    legend.innerHTML = labels.map((l, i) => `
      <div class="legend-item">
        <span class="legend-dot" style="background:${colors[i]}"></span>
        <span class="legend-name">${l}</span>
        <span class="legend-count">${data[i]}</span>
      </div>`).join("");
  }
}

function renderStatusBars(total, cloturee, enCours, blockee, annulee) {
  const container = document.getElementById("statusBars");
  if (!container) return;
  const max   = Math.max(cloturee, enCours, blockee, annulee, 1);
  const items = [
    { label: "En Cours", count: enCours,  color: "#FFC107" },
    { label: "Clôturée", count: cloturee, color: "#28A745" },
    { label: "Bloquée",  count: blockee,  color: "#C0392B" },
    { label: "Annulée",  count: annulee,  color: "#BDBDBD" },
  ];
  container.innerHTML = items.map(item => `
    <div class="status-bar-item">
      <div class="status-bar-label">
        <span class="status-bar-name">${item.label}</span>
        <span class="status-bar-count">${item.count}</span>
      </div>
      <div class="status-bar-track">
        <div class="status-bar-fill" style="width:${(item.count / max) * 100}%;background:${item.color}"></div>
      </div>
    </div>`).join("");
}

function renderRecentActivity() {
  const container = document.getElementById("recentActivity");
  if (!container) return;
  const recent = [...allPRs].sort((a, b) => b.createdDate.localeCompare(a.createdDate)).slice(0, 5);
  if (!recent.length) {
    container.innerHTML = `<div class="no-activity"><span class="glyphicon glyphicon-inbox"></span><p>Aucune PR pour le moment</p></div>`;
    return;
  }
    const icons = { "ED": "#E74C3C", "CR": "#3498DB", "COU": "#2ECC71", "REG": "#F39C12", "Hybride": "#9B59B6" };
  container.innerHTML = recent.map(pr => {
    const baseCat = pr.baseCategory || pr.category;
    const iconColor = icons[baseCat] || icons[pr.category] || "#ccc";
    return `
    <div class="activity-item" onclick="selectPR('${pr.id}')">
      <div class="activity-icon" style="background:${iconColor}22;color:${iconColor}">
        <span class="glyphicon glyphicon-file"></span>
      </div>
      <div class="activity-body">
        <div class="activity-num">PR #${pr.number} — ${pr.category}</div>
        <div class="activity-title" title="${escHtml(pr.title)}">${escHtml(pr.title)}</div>
        <div class="activity-date">${pr.createdDate}</div>
      </div>
      <div>
        <span class="status-badge status-${pr.status.replace("-", "")}">${statusLabel(pr.status)}</span>
      </div>
    </div>`;
  }).join("");
}

/* ── ALERT BANNER ───────────────────────────────────────────────────────────── */
function renderAlertBanner(totalLate, totalWarning) {
  const banner = document.getElementById("alertBanner");
  if (!banner) return;
  if (totalLate === 0 && totalWarning === 0) {
    banner.style.display = "none";
    return;
  }
  banner.style.display = "flex";
  let msg = "";
  if (totalLate > 0) {
    msg += `<span class="alert-item alert-late">
              <span class="glyphicon glyphicon-warning-sign"></span>
              <strong>${totalLate}</strong> étape${totalLate > 1 ? "s" : ""} en retard critique
            </span>`;
  }
  if (totalWarning > 0) {
    msg += `<span class="alert-item alert-warning">
              <span class="glyphicon glyphicon-time"></span>
              <strong>${totalWarning}</strong> étape${totalWarning > 1 ? "s" : ""} à risque de retard
            </span>`;
  }
  const msgEl = document.getElementById("alertBannerMsg");
  if (msgEl) msgEl.innerHTML = msg;
}

async function loadAndRenderAlerts() {
  const container = document.getElementById("alertsList");
  if (!container) return;
  const alerts = await fetch("/api/alerts").then(r => r.json());
  const panel   = document.getElementById("alertsPanel");

  if (!alerts.length) {
    if (panel) panel.style.display = "none";
    return;
  }
  if (panel) panel.style.display = "block";

  container.innerHTML = alerts.map(a => `
    <div class="alert-row alert-row-${a.delay}" onclick="selectPR('${a.pr_id}')">
      <div class="alert-row-icon">
        ${a.delay === "late"
          ? `<span class="glyphicon glyphicon-warning-sign"></span>`
          : `<span class="glyphicon glyphicon-time"></span>`}
      </div>
      <div class="alert-row-body">
        <div class="alert-row-pr">PR #${a.pr_number} — <span class="alert-row-title">${escHtml(a.pr_title)}</span></div>
        <div class="alert-row-step">Étape ${a.task_id} : ${escHtml(a.task_title)}</div>
        <div class="alert-row-dates">
          <span><span class="glyphicon glyphicon-calendar"></span> Prév : ${a.date_prev || "—"}</span>
          <span><span class="glyphicon glyphicon-ok"></span> Réelle : ${a.date_reelle || "—"}</span>
        </div>
      </div>
      <div class="alert-row-badge">
        ${a.delay === "late"
          ? `<span class="delay-chip chip-late">En retard</span>`
          : `<span class="delay-chip chip-warning">Risque</span>`}
      </div>
    </div>`).join("");
}

/* ── SELECT PR — SHOW CHECKLIST ─────────────────────────────────────────────── */
async function selectPR(prId) {
  selectedPRId = prId;
  renderPRList();
  const pr = await api(`/api/pr/${prId}`);
  if (pr.error) return showToast(pr.error, "error");

  showView("checklistView");

  const baseCat = pr.baseCategory || pr.category;
  document.getElementById("checklistTitle").textContent    = `PR #${pr.number} — ${pr.title}`;
  document.getElementById("checklistSubtitle").textContent = `${pr.category} · ${pr.createdDate}`;

  const meta = document.getElementById("checklistMeta");
  let metaHTML = `<div><strong>Catégorie :</strong> ${pr.category}${baseCat === "Hybride" && pr.category !== "Hybride" ? ' <span style="font-size:11px;color:#9B59B6">(Hybride)</span>' : ''}</div>
                  <div><strong>Statut :</strong> ${statusLabel(pr.status)}</div>
                  <div><strong>Date :</strong> ${pr.createdDate}</div>`;
  
  // Add Hybrid buttons if applicable — check baseCategory
  if (baseCat === "Hybride") {
    metaHTML += `<div style="margin-top:12px;display:flex;gap:8px">
      <button class="btn-primary" onclick="openHybridCategoryEdit('${pr.id}')" style="padding:6px 12px;font-size:12px">
        <span class="glyphicon glyphicon-pencil"></span> Renommer
      </button>
      <button class="btn-primary" onclick="openAddHybridStepModal('${pr.id}')" style="padding:6px 12px;font-size:12px;background:#27AE60">
        <span class="glyphicon glyphicon-plus"></span> Ajouter étape
      </button>
    </div>`;
  }
  
  meta.innerHTML = metaHTML;

  renderChecklist(prId, pr.tasks, pr.progress, baseCat);
  
  // Show processing time info
  showProcessingTimeInfo(pr);
}

function showProcessingTimeInfo(pr) {
  const prData = allPRs.find(p => p.id === pr.id);
  if (!prData) return;
  
  const infoDiv = document.getElementById("processingTimeInfo");
  const textSpan = document.getElementById("processingTimeText");
  
  if (prData.processing_weeks === 0) {
    infoDiv.style.display = "none";
    return;
  }
  
  const baseCat = prData.baseCategory || prData.category;
  const limits = processingLimits[baseCat] || {};
  const maxWeeks = limits.max_weeks || 0;
  const isExceeded = prData.exceeded;
  
  let message = `<strong>Durée totale :</strong> ${prData.processing_weeks} semaine${prData.processing_weeks > 1 ? 's' : ''} `;
  if (maxWeeks > 0) {
    message += `/ ${maxWeeks} semaines max`;
    if (isExceeded) {
      message += ` <span style="color:#C0392B;font-weight:bold;">— Délai dépassé !</span>`;
      infoDiv.style.background = "#F8D7DA";
      infoDiv.style.borderColor = "#F5C6CB";
      infoDiv.style.color = "#721C24";
    } else {
      infoDiv.style.background = "#D4EDDA";
      infoDiv.style.borderColor = "#C3E6CB";
      infoDiv.style.color = "#155724";
    }
  }
  
  textSpan.innerHTML = message;
  infoDiv.style.display = "block";
}

function renderChecklist(prId, tasks, progress, baseCategoryOverride) {
  updateProgressUI(progress);
  const container = document.getElementById("checklistContainer");
  if (!tasks || !Object.keys(tasks).length) {
    container.innerHTML = `<p style="color:var(--grey-400)">Aucune étape définie.</p>`;
    return;
  }
  
  const pr = allPRs.find(p => p.id === prId);
  const baseCat = baseCategoryOverride || (pr && (pr.baseCategory || pr.category));
  const isHybride = baseCat === "Hybride";
  
  container.innerHTML = Object.entries(tasks).map(([tid, task]) => {
    const done  = task.done;
    const delay = task.delay || "";
    const editBtn = isHybride ? `<button class="btn-step-edit" onclick="event.stopPropagation();openStepEdit('${prId}','${tid}')" title="Modifier"><span class="glyphicon glyphicon-pencil"></span></button>` : '';
    return `
    <div class="task-item ${done ? "task-done" : ""} ${delay ? "task-delay-" + delay : ""}" id="taskItem-${tid}">
      <div class="task-header" onclick="toggleTaskBody('${tid}')">
        <div class="task-num">${tid}</div>
        <div class="task-checkbox ${done ? "checked" : ""}" onclick="toggleTask(event,'${prId}','${tid}')"></div>
        <div class="task-info">
          <div class="task-title">${escHtml(task.title)} ${delayIcon(delay)}</div>
          <div class="task-desc">${escHtml(task.desc)}</div>
        </div>
        ${editBtn}
        <button class="task-toggle-btn" id="toggleBtn-${tid}">
          <span class="glyphicon glyphicon-chevron-down"></span>
        </button>
      </div>
      <div class="task-body" id="taskBody-${tid}">
        <div class="task-fields">
          <div class="task-field">
            <label><span class="glyphicon glyphicon-calendar"></span> Date prévisionnelle</label>
            <input type="date" class="input-custom" value="${task.date_prev || ""}"
                   onchange="handleDatePrev('${prId}','${tid}',this.value)" />
          </div>
          <div class="task-field">
            <label><span class="glyphicon glyphicon-ok"></span> Date réelle</label>
            <input type="date" class="input-custom" value="${task.date_reelle || ""}"
                   onchange="handleDateReelle('${prId}','${tid}',this.value)" />
          </div>
          <div class="task-field task-field-full">
            <label><span class="glyphicon glyphicon-comment"></span> Notes / Commentaires</label>
            <textarea class="task-note-area" placeholder="Ajouter une note..."
                      onchange="updateTaskField('${prId}','${tid}','note',this.value)">${escHtml(task.note || "")}</textarea>
          </div>
        </div>
        <div class="task-delay-status" id="delayStatus-${tid}">
          ${renderDelayStatus(delay, task.date_prev, task.date_reelle)}
        </div>
      </div>
    </div>`;
  }).join("");
}

function renderDelayStatus(delay, datePrev, dateReelle) {
  if (!datePrev || !dateReelle) return "";
  const labels = {
    "ontime":  `<span class="delay-status-chip chip-ontime"><span class="glyphicon glyphicon-ok-circle"></span> Dans les délais</span>`,
    "warning": `<span class="delay-status-chip chip-warning"><span class="glyphicon glyphicon-time"></span> Risque de retard (1–5 jours)</span>`,
    "late":    `<span class="delay-status-chip chip-late"><span class="glyphicon glyphicon-warning-sign"></span> En retard (plus de 5 jours)</span>`,
  };
  return labels[delay] || "";
}

function toggleTaskBody(tid) {
  const body = document.getElementById(`taskBody-${tid}`);
  const btn  = document.getElementById(`toggleBtn-${tid}`);
  if (!body || !btn) return;
  body.classList.toggle("open");
  btn.classList.toggle("open");
}

async function toggleTask(event, prId, tid) {
  event.stopPropagation();
  const checkbox = event.currentTarget;
  const done     = !checkbox.classList.contains("checked");
  const res      = await api(`/api/pr/${prId}/task/${tid}`, "PATCH", { done });
  checkbox.classList.toggle("checked", done);
  const item = document.getElementById(`taskItem-${tid}`);
  if (item) item.classList.toggle("task-done", done);
  updateProgressUI(res.progress);
  // refresh mini progress in sidebar list
  const listFill = document.querySelector(`.pr-item[data-id="${prId}"] .mini-progress-fill`);
  if (listFill) listFill.style.width = res.progress + "%";
  const listPct = document.querySelector(`.pr-item[data-id="${prId}"] .mini-progress-pct`);
  if (listPct) listPct.textContent = res.progress + "%";
  const pr = allPRs.find(p => p.id === prId);
  if (pr) {
    pr.progress       = res.progress;
    pr.late_steps    = res.late_steps;
    pr.warning_steps = res.warning_steps;
    updateDashboard();
  }
}

async function handleDateReelle(prId, tid, value) {
  const res = await api(`/api/pr/${prId}/task/${tid}`, "PATCH", { date_reelle: value });
  refreshTaskDelayUI(prId, tid, res);
}

async function handleDatePrev(prId, tid, value) {
  const res = await api(`/api/pr/${prId}/task/${tid}`, "PATCH", { date_prev: value });
  refreshTaskDelayUI(prId, tid, res);
}

function refreshTaskDelayUI(prId, tid, res) {
  const delay = res.delay || "";
  // Update delay icon in title
  const titleEl = document.querySelector(`#taskItem-${tid} .task-title`);
  if (titleEl) {
    // Strip previous icon (last child span.delay-icon) and re-append
    const existingIcon = titleEl.querySelector(".delay-icon");
    if (existingIcon) existingIcon.remove();
    if (delay) titleEl.insertAdjacentHTML("beforeend", " " + delayIcon(delay));
  }
  // Update delay status chip
  const statusEl = document.getElementById(`delayStatus-${tid}`);
  if (statusEl) {
    const prevInput   = document.querySelector(`#taskItem-${tid} input[type=date]:first-of-type`);
    const reelleInput = document.querySelector(`#taskItem-${tid} input[type=date]:last-of-type`);
    statusEl.innerHTML = renderDelayStatus(
      delay,
      prevInput   ? prevInput.value   : "",
      reelleInput ? reelleInput.value : ""
    );
  }
  // Update border color class
  const item = document.getElementById(`taskItem-${tid}`);
  if (item) {
    item.classList.remove("task-delay-ontime", "task-delay-warning", "task-delay-late");
    if (delay) item.classList.add("task-delay-" + delay);
  }
  // Refresh sidebar PR card and dashboard
  const pr = allPRs.find(p => p.id === prId);
  if (pr) {
    pr.late_steps    = res.late_steps    || 0;
    pr.warning_steps = res.warning_steps || 0;
    renderPRList();
    renderAlertBanner(
      allPRs.reduce((a, p) => a + (p.late_steps || 0), 0),
      allPRs.reduce((a, p) => a + (p.warning_steps || 0), 0)
    );
    loadAndRenderAlerts();
    // Refresh processing time display if this PR is currently selected
    if (selectedPRId === prId) {
      loadPRList("").then(() => {
        const updatedPR = allPRs.find(p => p.id === prId);
        if (updatedPR) {
          showProcessingTimeInfo(updatedPR);
        }
      });
    }
  }
}

async function updateTaskField(prId, tid, field, value) {
  await api(`/api/pr/${prId}/task/${tid}`, "PATCH", { [field]: value });
}

function updateProgressUI(progress) {
  const bar  = document.getElementById("progressBarFill");
  const pct  = document.getElementById("progressPct");
  const ring = document.getElementById("ringFill");
  const rl   = document.getElementById("ringLabel");
  const circ = 175.93;
  if (bar)  bar.style.width = progress + "%";
  if (pct)  pct.textContent = progress + "%";
  if (ring) ring.style.strokeDashoffset = circ - (circ * progress / 100);
  if (rl)   rl.textContent = progress + "%";
}

/* ── FORM — CREATE / EDIT ───────────────────────────────────────────────────── */
function bindForm() {
  document.querySelectorAll(".cat-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".cat-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById("prCategory").value = btn.dataset.cat;
    });
  });

  document.getElementById("prForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const editingId = document.getElementById("editingId").value;
    const body = {
      number:   document.getElementById("prNumber").value,
      title:    document.getElementById("prTitle").value.trim(),
      category: document.getElementById("prCategory").value,
      prDate:   document.getElementById("prDate").value,
    };
    
    if (!body.number || !body.title || !body.category || !body.prDate) {
      return showToast("Veuillez remplir tous les champs", "error");
    }
    let res;
    if (editingId) {
      res = await api(`/api/pr/${editingId}`, "PUT", body);
    } else {
      res = await api("/api/pr", "POST", body);
    }
    if (res.error) return showToast(res.error, "error");
    showToast(editingId ? "PR mise à jour" : "PR créée avec succès", "success");
    resetForm();
    await loadPRList();
  });

  document.getElementById("btnCancel").addEventListener("click", resetForm);
}

function resetForm() {
  document.getElementById("editingId").value   = "";
  document.getElementById("prNumber").value    = "";
  document.getElementById("prTitle").value     = "";
  document.getElementById("prDate").value      = "";
  document.getElementById("prCategory").value  = "";
  document.querySelectorAll(".cat-btn").forEach(b => b.classList.remove("active"));
  document.getElementById("formTitle").textContent   = "Nouvelle Demande";
  document.getElementById("submitLabel").textContent = "Créer la PR";
  document.getElementById("btnCancel").style.display = "none";
}

async function editPR(event, prId) {
  event.stopPropagation();
  const pr = await api(`/api/pr/${prId}`);
  if (pr.error) return showToast(pr.error, "error");
  const baseCat = pr.baseCategory || pr.category;
  document.getElementById("editingId").value  = prId;
  document.getElementById("prNumber").value   = pr.number;
  document.getElementById("prTitle").value    = pr.title;
  document.getElementById("prDate").value     = pr.createdDate;
  document.getElementById("prCategory").value = baseCat;
  document.querySelectorAll(".cat-btn").forEach(b => {
    b.classList.toggle("active", b.dataset.cat === baseCat);
  });
  document.getElementById("formTitle").textContent   = "Modifier la PR";
  document.getElementById("submitLabel").textContent = "Enregistrer";
  document.getElementById("btnCancel").style.display = "";
  document.getElementById("prNumber").scrollIntoView({ behavior: "smooth" });
}

async function deletePR(event, prId) {
  event.stopPropagation();
  const result = await Swal.fire({
    title: "Supprimer cette PR ?",
    text:  "Cette action est irréversible.",
    icon:  "warning",
    showCancelButton:    true,
    confirmButtonColor:  "#C0392B",
    cancelButtonColor:   "#95A5A6",
    confirmButtonText:   "Supprimer",
    cancelButtonText:    "Annuler",
  });
  if (!result.isConfirmed) return;
  const res = await api(`/api/pr/${prId}`, "DELETE");
  if (res.error) return showToast(res.error, "error");
  showToast("PR supprimée", "success");
  if (selectedPRId === prId) {
    selectedPRId = null;
    showView("dashboardView");
  }
  await loadPRList();
}

/* ── SEARCH ─────────────────────────────────────────────────────────────────── */
function bindSearch() {
  let debounceTimer;
  document.getElementById("searchInput").addEventListener("input", (e) => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => loadPRList(e.target.value), 250);
  });
}

/* ── STATUS DROPDOWN ─────────────────────────────────────────────────────────── */
let activeStatusPRId = null;

function openStatusMenu(event, prId) {
  event.stopPropagation();
  activeStatusPRId = prId;
  const dropdown = document.getElementById("statusDropdown");
  dropdown.style.display = "block";
  const rect = event.currentTarget.getBoundingClientRect();
  dropdown.style.top  = (rect.bottom + 4 + window.scrollY) + "px";
  dropdown.style.left = rect.left + "px";
}

function bindStatusDropdown() {
  document.querySelectorAll(".status-option").forEach(opt => {
    opt.addEventListener("click", async () => {
      const status = opt.dataset.status;
      const res    = await api(`/api/pr/${activeStatusPRId}/status`, "PATCH", { status });
      if (res.error) return showToast(res.error, "error");
      document.getElementById("statusDropdown").style.display = "none";
      showToast("Statut mis à jour", "success");
      await loadPRList();
    });
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".status-dropdown") && !e.target.closest(".status-badge")) {
      document.getElementById("statusDropdown").style.display = "none";
    }
  });
}

/* ── IMPORT / EXPORT ─────────────────────────────────────────────────���───────── */
function bindImportExport() {
  document.getElementById("btnImport").addEventListener("click", () => {
    document.getElementById("importFileInput").click();
  });

  document.getElementById("importFileInput").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res  = await fetch("/api/import", { method: "POST", body: formData });
      const json = await res.json();
      if (json.error) return showToast(json.error, "error");
      showToast(json.message, "success");
      await loadPRList();
    } catch (err) {
      showToast("Erreur lors de l'import", "error");
    }
    e.target.value = "";
  });

  document.getElementById("btnExportModal").addEventListener("click", () => {
    document.getElementById("exportModal").classList.add("open");
  });

  document.getElementById("btnDoExport").addEventListener("click", () => {
    const from = document.getElementById("exportFrom").value;
    const to   = document.getElementById("exportTo").value;
    let url    = "/api/export";
    const params = [];
    if (from) params.push(`from=${from}`);
    if (to)   params.push(`to=${to}`);
    if (params.length) url += "?" + params.join("&");
    window.location.href = url;
    document.getElementById("exportModal").classList.remove("open");
    showToast("Export en cours...", "success");
  });
}

/* ── MODAL ──────────────────────────────────────────────────────────────────── */
function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.style.display = "none";
  }
}

// Close modal when clicking outside of modal-content
document.addEventListener("click", (e) => {
  if (e.target.classList.contains("modal")) {
    e.target.style.display = "none";
  }
});

function bindModalClose() {
  document.getElementById("closeExportModal").addEventListener("click", () => {
    document.getElementById("exportModal").classList.remove("open");
  });
  document.getElementById("cancelExport").addEventListener("click", () => {
    document.getElementById("exportModal").classList.remove("open");
  });
  document.getElementById("exportModal").addEventListener("click", (e) => {
    if (e.target === document.getElementById("exportModal"))
      document.getElementById("exportModal").classList.remove("open");
  });
  document.getElementById("btnBackToDash").addEventListener("click", () => {
    selectedPRId = null;
    renderPRList();
    showView("dashboardView");
  });
}

/* ── VIEW TOGGLE ─────────────────────────────────────────────────────────────── */
function showView(viewId) {
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active-view"));
  const view = document.getElementById(viewId);
  if (view) view.classList.add("active-view");
}

/* ── PR DOCUMENT CHECKLIST ──────────────────────────────────────────────────── */
let prDocsCurrentPRId   = null;
let prDocsCurrentPRBase = null; // base category
let prDocsItems         = [];
let prDocEditingId      = null;

async function openPRDocsModal() {
  if (!selectedPRId) return;
  prDocsCurrentPRId = selectedPRId;
  const pr = allPRs.find(p => p.id === selectedPRId);
  prDocsCurrentPRBase = pr ? (pr.baseCategory || pr.category) : "";

  // Update subtitle
  const sub = document.getElementById("prDocsSubtitle");
  if (sub && pr) sub.textContent = `PR #${pr.number} — ${pr.title}`;

  // Show add section only for Hybride
  const addSection = document.getElementById("prDocsAddSection");
  if (addSection) {
    addSection.style.display = prDocsCurrentPRBase === "Hybride" ? "block" : "none";
  }

  // Load docs from API
  await refreshPRDocs();

  const modal = document.getElementById("prDocsModal");
  if (modal) modal.style.display = "flex";
}

async function refreshPRDocs() {
  prDocsItems = await api(`/api/pr/${prDocsCurrentPRId}/docs`);
  renderPRDocsList();
}

function renderPRDocsList() {
  const container = document.getElementById("prDocsList");
  if (!container) return;

  const total    = prDocsItems.length;
  const done     = prDocsItems.filter(d => d.done).length;
  const pct      = total ? Math.round((done / total) * 100) : 0;

  const fill  = document.getElementById("prDocsProgressFill");
  const label = document.getElementById("prDocsProgressLabel");
  if (fill)  fill.style.width = pct + "%";
  if (label) label.textContent = `${done} / ${total} documents`;

  if (!total) {
    container.innerHTML = `<div class="pr-docs-empty"><span class="glyphicon glyphicon-inbox"></span><p>Aucun document dans cette liste</p></div>`;
    return;
  }

  const isHybride = prDocsCurrentPRBase === "Hybride";
  container.innerHTML = prDocsItems.map(doc => `
    <div class="pr-doc-item ${doc.done ? 'pr-doc-done' : ''}">
      <label class="pr-doc-check-label">
        <input type="checkbox" class="pr-doc-checkbox"
               ${doc.done ? 'checked' : ''}
               onchange="togglePRDoc('${doc.id}', this.checked)">
        <span class="pr-doc-custom-check">
          <span class="glyphicon glyphicon-ok"></span>
        </span>
      </label>
      <span class="pr-doc-name">${escapeHtml(doc.name)}</span>
      ${isHybride ? `
        <div class="pr-doc-actions">
          <button class="btn-pr-doc-edit" onclick="openPRDocEdit('${doc.id}')" title="Modifier">
            <span class="glyphicon glyphicon-pencil"></span>
          </button>
          <button class="btn-pr-doc-delete" onclick="deletePRDoc('${doc.id}')" title="Supprimer">
            <span class="glyphicon glyphicon-trash"></span>
          </button>
        </div>` : ''}
    </div>
  `).join('');
}

async function togglePRDoc(docId, isDone) {
  await api(`/api/pr/${prDocsCurrentPRId}/docs/${docId}`, "PATCH", { done: isDone });
  const doc = prDocsItems.find(d => d.id === docId);
  if (doc) doc.done = isDone;
  renderPRDocsList();
}

async function addPRDoc() {
  const input = document.getElementById("prDocNewName");
  const name = input ? input.value.trim() : "";
  if (!name) { showToast("Veuillez entrer un nom de document", "error"); return; }

  const result = await api(`/api/pr/${prDocsCurrentPRId}/docs`, "POST", { name });
  if (result.error) { showToast(result.error, "error"); return; }

  prDocsItems.push(result);
  if (input) input.value = "";
  renderPRDocsList();
  showToast("Document ajouté", "success");
}

function openPRDocEdit(docId) {
  const doc = prDocsItems.find(d => d.id === docId);
  if (!doc) return;
  prDocEditingId = docId;
  const nameInput = document.getElementById("prDocEditName");
  if (nameInput) nameInput.value = doc.name;
  const modal = document.getElementById("prDocEditModal");
  if (modal) modal.style.display = "flex";
}

async function savePRDocEdit() {
  if (!prDocEditingId) return;
  const name = document.getElementById("prDocEditName").value.trim();
  if (!name) { showToast("Veuillez entrer un nom", "error"); return; }

  const result = await api(`/api/pr/${prDocsCurrentPRId}/docs/${prDocEditingId}`, "PATCH", { name });
  if (result.error) { showToast("Erreur lors de la modification", "error"); return; }

  const doc = prDocsItems.find(d => d.id === prDocEditingId);
  if (doc) doc.name = result.name;
  closeModal("prDocEditModal");
  renderPRDocsList();
  showToast("Document modifié", "success");
}

async function deletePRDoc(docId) {
  const confirmed = await Swal.fire({
    title: 'Supprimer ce document ?',
    text: 'Cette action est irréversible.',
    icon: 'warning',
    showCancelButton: true,
    confirmButtonText: 'Supprimer',
    cancelButtonText: 'Annuler',
    confirmButtonColor: '#C0392B'
  });
  if (!confirmed.isConfirmed) return;

  const result = await api(`/api/pr/${prDocsCurrentPRId}/docs/${docId}`, "DELETE");
  if (result.error) { showToast("Erreur lors de la suppression", "error"); return; }

  prDocsItems = prDocsItems.filter(d => d.id !== docId);
  renderPRDocsList();
  showToast("Document supprimé", "success");
}

/* ── COLOR PICKER ───────────────────────────────────────────────────────────── */
function selectDocColor(color, button, mode = "add") {
  const colorInput = mode === "edit" ? document.getElementById("editDocColor") : document.getElementById("docColor");
  const pickerContainer = mode === "edit" ? document.getElementById("editDocColorPicker") : document.getElementById("docColorPicker");
  
  colorInput.value = color;
  
  // Update selected state on all buttons
  pickerContainer.querySelectorAll(".color-btn").forEach(btn => {
    btn.classList.remove("selected");
  });
  button.classList.add("selected");
}

/* ── KPI SEARCH ───────────────────────────────────────────────────────────────── */
function bindKPISearch() {
  const searchInput = document.getElementById("kpiSearchInput");
  if (!searchInput) return;
  
  let searchTimeout;
  searchInput.addEventListener("input", (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      const searchTerm = e.target.value.toLowerCase();
      const category = document.getElementById("kpiCategoryFilter").value;
      filterKPITable(searchTerm, category);
    }, 300);
  });
}

async function filterKPITable(searchTerm = "", category = "") {
  const tableBody = document.getElementById("kpiTableBody");
  if (!tableBody) return;
  
  let url = "/api/kpi/processing-delays";
  if (category) {
    url += `?category=${encodeURIComponent(category)}`;
  }
  
  try {
    const data = await api(url);
    
    if (data.length === 0) {
      tableBody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:20px;color:#999">Aucune PR trouvée</td></tr>';
      return;
    }
    
    const filtered = data.filter(pr => {
      const searchLower = searchTerm.toLowerCase();
      return pr.number.toLowerCase().includes(searchLower) || pr.title.toLowerCase().includes(searchLower);
    });
    
    if (filtered.length === 0) {
      tableBody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:20px;color:#999">Aucune PR correspondante</td></tr>';
      return;
    }
    
    tableBody.innerHTML = filtered.map(pr => {
      const baseCat = pr.baseCategory || pr.category;
      const indicator = getKPIIndicator(baseCat, pr.delay_weeks, pr.status);
      const badgeClass = baseCat.toLowerCase();
      const lostDays = pr.lost_days || 0;
      return `
        <tr>
          <td title="PR #${escapeHtml(pr.number)}"><strong>PR #${escapeHtml(pr.number)}</strong></td>
          <td title="${escapeHtml(pr.title)}">${escapeHtml(pr.title)}</td>
          <td title="${pr.category}"><span class="status-badge status-${badgeClass}" style="font-size:11px">${pr.category}</span></td>
          <td title="${pr.delay_weeks} semaines"><strong>${pr.delay_weeks}</strong></td>
          <td>
            <div style="display:flex;gap:4px;align-items:center">
              <input type="number" class="lost-days-input" id="lost-days-${pr.id}" value="${lostDays}" min="0" placeholder="0" title="Jours à soustraire">
              <button class="lost-days-btn" onclick="saveLostDays('${pr.id}')" title="Confirmer">OK</button>
            </div>
          </td>
          <td title="${statusLabel(pr.status)}">${statusLabel(pr.status)}</td>
          <td>
            ${indicator}
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error("[v0] Failed to load KPI data:", err);
    tableBody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:20px;color:#c00">Erreur de chargement des données</td></tr>';
  }
}

async function saveLostDays(prId) {
  const input = document.getElementById(`lost-days-${prId}`);
  if (!input) return;
  
  const lostDays = parseInt(input.value) || 0;
  
  try {
    const result = await api(`/api/pr/${prId}/lost-days`, "POST", { lost_days: lostDays });
    if (result.error) {
      showToast("Erreur lors de la mise à jour", "error");
      return;
    }
    
    // Refresh the KPI table
    const category = document.getElementById("kpiCategoryFilter").value;
    const searchTerm = document.getElementById("kpiSearchInput").value;
    await filterKPITable(searchTerm, category);
    showToast("Jours perdus mis à jour", "success");
  } catch (err) {
    console.error("[v0] Error saving lost days:", err);
    showToast("Erreur lors de la sauvegarde", "error");
  }
}

/* ── TOAST ──────────────────────────────────────────────────────────────────── */
function showToast(message, type = "success") {
  const existing = document.querySelector(".toast-notification");
  if (existing) existing.remove();
  const icon  = type === "success"
    ? '<span class="glyphicon glyphicon-ok-circle"></span>'
    : '<span class="glyphicon glyphicon-exclamation-sign"></span>';
  const toast = document.createElement("div");
  toast.className = `toast-notification toast-${type}`;
  toast.innerHTML = `${icon} ${message}`;
  document.body.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add("show"));
  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 400);
  }, 3000);
}

/* ── FINANCIAL EVALUATIONS ──────────────────────────────────────────────────── */

let currentEvalId = null;
let currentPhase = "OI";
let currentEvalData = null;

// Initialize evaluations modal
document.addEventListener("DOMContentLoaded", () => {
  const btnEval = document.getElementById("btnEvaluations");
  if (btnEval) {
    btnEval.addEventListener("click", openEvaluationsModal);
  }
});

async function openEvaluationsModal() {
  const modal = document.getElementById("evaluationsModal");
  modal.style.display = "flex";
  modal.style.flexDirection = "column";
  
  // Load evaluations list
  await loadEvaluationsList();
}

async function loadEvaluationsList() {
  try {
    const response = await fetch("/api/evaluations");
    const evaluations = await response.json();
    
    const list = document.getElementById("evaluationsList");
    if (evaluations.length === 0) {
      list.innerHTML = '<div style="padding:16px;color:var(--grey-600);font-size:12px">Aucune évaluation pour le moment</div>';
      return;
    }
    
    list.innerHTML = evaluations.map(e => `
      <button onclick="loadEvaluation('${e.id}')" style="width:100%;padding:10px;margin:4px 0;background:var(--grey-100);border:1px solid var(--grey-300);border-radius:4px;cursor:pointer;text-align:left;transition:all 0.2s">
        <div style="font-weight:600;font-size:13px;color:var(--grey-900)">${escapeHtml(e.title)}</div>
        <div style="font-size:11px;color:var(--grey-600)">${new Date(e.created_date).toLocaleDateString('fr-FR')}</div>
        <div style="font-size:10px;color:#2196F3;margin-top:4px">Phase: ${e.current_phase}</div>
      </button>
    `).join('');
  } catch (err) {
    console.error("[v0] Error loading evaluations:", err);
    showToast("Erreur lors du chargement", "error");
  }
}

async function createNewEvaluation() {
  const title = prompt("Titre de la nouvelle évaluation:");
  if (!title || title.trim() === "") return;
  
  try {
    const response = await fetch("/api/evaluations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title.trim() })
    });
    const result = await response.json();
    currentEvalId = result.id;
    currentPhase = "OI";
    
    await loadEvaluation(result.id);
    await loadEvaluationsList();
    showToast("Évaluation créée", "success");
  } catch (err) {
    console.error("[v0] Error creating evaluation:", err);
    showToast("Erreur lors de la création", "error");
  }
}

async function loadEvaluation(evalId) {
  try {
    const response = await fetch(`/api/evaluations/${evalId}`);
    const data = await response.json();
    
    currentEvalId = evalId;
    currentPhase = "OI";
    currentEvalData = data;
    
    // Show editor
    document.getElementById("evaluationEditor").style.display = "block";
    document.getElementById("evalTitle").value = data.title;
    
    // Highlight selected eval in list
    document.querySelectorAll("#evaluationsList button").forEach(btn => {
      btn.style.background = "var(--grey-100)";
      btn.style.borderColor = "var(--grey-300)";
    });
    const selectedBtn = Array.from(document.querySelectorAll("#evaluationsList button")).find(btn => 
      btn.textContent.includes(data.title)
    );
    if (selectedBtn) {
      selectedBtn.style.background = "#E3F2FD";
      selectedBtn.style.borderColor = "#2196F3";
    }
    
    // Load phase
    switchPhase("OI");
  } catch (err) {
    console.error("[v0] Error loading evaluation:", err);
    showToast("Erreur lors du chargement", "error");
  }
}

async function saveEvalTitle() {
  if (!currentEvalId) return;
  
  const title = document.getElementById("evalTitle").value.trim();
  if (!title) {
    showToast("Le titre ne peut pas être vide", "error");
    return;
  }
  
  try {
    await fetch(`/api/evaluations/${currentEvalId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title })
    });
    
    currentEvalData.title = title;
    await loadEvaluationsList();
    showToast("Titre mis à jour", "success");
  } catch (err) {
    console.error("[v0] Error saving title:", err);
    showToast("Erreur lors de la sauvegarde", "error");
  }
}

async function deleteEvaluation() {
  if (!currentEvalId) return;
  
  if (!confirm("Êtes-vous sûr de vouloir supprimer cette évaluation ?")) return;
  
  try {
    await fetch(`/api/evaluations/${currentEvalId}`, { method: "DELETE" });
    currentEvalId = null;
    currentEvalData = null;
    document.getElementById("evaluationEditor").style.display = "none";
    await loadEvaluationsList();
    showToast("Évaluation supprimée", "success");
  } catch (err) {
    console.error("[v0] Error deleting evaluation:", err);
    showToast("Erreur lors de la suppression", "error");
  }
}

function switchPhase(phase) {
  currentPhase = phase;
  
  // Update tabs
  document.querySelectorAll(".eval-tab").forEach(tab => {
    if (tab.dataset.phase === phase) {
      tab.style.borderBottomColor = "#2196F3";
      tab.style.color = "#2196F3";
    } else {
      tab.style.borderBottomColor = "transparent";
      tab.style.color = "var(--grey-600)";
    }
  });
  
  // Update calculate button
  const phaseLabelMap = { OI: "OI", OA1: "OA1", OA2: "OA2" };
  document.getElementById("calculateBtn").textContent = `Évaluer ${phaseLabelMap[phase]}`;
  
  // Hide results
  document.getElementById("resultsSection").style.display = "none";
  
  // Reload phase table
  renderPhaseTable();
}

async function renderPhaseTable() {
  if (!currentEvalData) return;
  
  const phaseEntries = currentEvalData.entries[currentPhase] || [];
  const tableBody = document.getElementById("phaseTable");
  
  if (phaseEntries.length === 0) {
    tableBody.innerHTML = '<tr><td colspan="4" style="padding:16px;text-align:center;color:var(--grey-600)">Aucune entreprise ajoutée</td></tr>';
    return;
  }
  
  const sorted = [...phaseEntries].sort((a, b) => a.amount - b.amount);
  const cheapest = sorted[0]?.amount || 0;
  
  tableBody.innerHTML = sorted.map((entry, idx) => {
    const gap = entry.amount === cheapest ? 0 : ((entry.amount - cheapest) / cheapest) * 100;
    return `
      <tr style="border-bottom:1px solid var(--grey-300)">
        <td style="padding:10px;border:1px solid var(--grey-300)">${idx + 1}</td>
        <td style="padding:10px;border:1px solid var(--grey-300)">
          <input type="text" value="${escapeHtml(entry.company_name)}" class="form-input" style="width:100%;padding:6px" onchange="updateEntry('${entry.id}', 'company_name', this.value)">
        </td>
        <td style="padding:10px;border:1px solid var(--grey-300)">
          <input type="number" value="${entry.amount}" class="form-input" style="width:100%;padding:6px" onchange="updateEntry('${entry.id}', 'amount', this.value)">
        </td>
        <td style="padding:10px;border:1px solid var(--grey-300);text-align:center">
          <button onclick="deleteEntry('${entry.id}')" style="padding:4px 8px;background:#F44336;color:white;border:none;border-radius:3px;cursor:pointer;font-size:11px">
            <span class="glyphicon glyphicon-trash"></span>
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

async function addCompanyRow() {
  if (!currentEvalId) return;
  
  const nameInput = document.getElementById("newCompanyName");
  const amountInput = document.getElementById("newCompanyAmount");
  
  const company_name = nameInput.value.trim();
  const amount = parseFloat(amountInput.value);
  
  if (!company_name || isNaN(amount) || amount < 0) {
    showToast("Veuillez entrer un nom et un montant valide", "error");
    return;
  }
  
  try {
    const response = await fetch(`/api/evaluations/${currentEvalId}/entries`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        phase: currentPhase,
        company_name,
        amount,
        company_order: (currentEvalData.entries[currentPhase] || []).length + 1
      })
    });
    
    if (!response.ok) {
      showToast("Erreur lors de l'ajout", "error");
      return;
    }
    
    // Reload evaluation
    await loadEvaluation(currentEvalId);
    nameInput.value = "";
    amountInput.value = "";
    showToast("Entreprise ajoutée", "success");
  } catch (err) {
    console.error("[v0] Error adding entry:", err);
    showToast("Erreur lors de l'ajout", "error");
  }
}

async function updateEntry(entryId, field, value) {
  if (!currentEvalId) return;
  
  try {
    await fetch(`/api/evaluations/${currentEvalId}/entries/${entryId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [field]: value })
    });
    
    await loadEvaluation(currentEvalId);
  } catch (err) {
    console.error("[v0] Error updating entry:", err);
    showToast("Erreur lors de la mise à jour", "error");
  }
}

async function deleteEntry(entryId) {
  if (!currentEvalId || !confirm("Supprimer cette entrée ?")) return;
  
  try {
    await fetch(`/api/evaluations/${currentEvalId}/entries/${entryId}`, {
      method: "DELETE"
    });
    
    await loadEvaluation(currentEvalId);
    showToast("Entrée supprimée", "success");
  } catch (err) {
    console.error("[v0] Error deleting entry:", err);
    showToast("Erreur lors de la suppression", "error");
  }
}

async function calculatePhase() {
  if (!currentEvalId) return;
  
  const entries = currentEvalData.entries[currentPhase] || [];
  if (entries.length === 0) {
    showToast("Veuillez ajouter des entreprises", "error");
    return;
  }
  
  try {
    const response = await fetch(`/api/evaluations/${currentEvalId}/calculate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phase: currentPhase })
    });
    
    const results = await response.json();
    
    // Display results
    const resultsSection = document.getElementById("resultsSection");
    const keptDiv = document.getElementById("resultKept");
    const discardedDiv = document.getElementById("resultDiscarded");
    const nextPhaseContainer = document.getElementById("nextPhaseContainer");
    
    keptDiv.innerHTML = (results.kept || []).map(r =>
      `<div style="padding:6px 0;border-bottom:1px solid var(--grey-300)">
        <strong>${escapeHtml(r.company)}</strong> - ${r.amount.toFixed(2)} (écart: ${r.gap.toFixed(2)}%)
      </div>`
    ).join('');
    
    if (results.kept.length === 0) {
      keptDiv.innerHTML = '<div style="padding:6px;color:var(--grey-600)">Aucune</div>';
    }
    
    discardedDiv.innerHTML = (results.discarded || []).map(r =>
      `<div style="padding:6px 0;border-bottom:1px solid var(--grey-300)">
        <strong>${escapeHtml(r.company)}</strong> - ${r.amount.toFixed(2)} (écart: ${r.gap.toFixed(2)}%)
      </div>`
    ).join('');
    
    if (results.discarded.length === 0) {
      discardedDiv.innerHTML = '<div style="padding:6px;color:var(--grey-600)">Aucune</div>';
    }
    
    // Show next phase button if not in OA2
    nextPhaseContainer.style.display = (currentPhase !== "OA2") ? "block" : "none";
    
    resultsSection.style.display = "block";
    
    // Reload data to get updated results
    await loadEvaluation(currentEvalId);
    showToast(`Évaluation ${currentPhase} effectuée`, "success");
  } catch (err) {
    console.error("[v0] Error calculating phase:", err);
    showToast("Erreur lors du calcul", "error");
  }
}

function moveToNextPhase() {
  const nextPhases = { OI: "OA1", OA1: "OA2" };
  const nextPhase = nextPhases[currentPhase];
  
  if (!nextPhase) return;
  
  switchPhase(nextPhase);
}

async function exportEvaluation() {
  if (!currentEvalId) return;
  
  try {
    const response = await fetch(`/api/evaluations/${currentEvalId}/export`);
    const blob = await response.blob();
    
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `Evaluation_${currentEvalData.title || 'export'}.xlsx`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    a.remove();
    
    showToast("Fichier exporté", "success");
  } catch (err) {
    console.error("[v0] Error exporting:", err);
    showToast("Erreur lors de l'export", "error");
  }
}
