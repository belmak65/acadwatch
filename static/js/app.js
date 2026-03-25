/* ICTMD Türkiye Akademik Takip — Frontend */

const MONTHS_TR = ["", "Ocak","Şubat","Mart","Nisan","Mayıs","Haziran",
                   "Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"];

const TYPE_LABELS = {
  article: "Makale",
  conference: "Bildiri",
  book: "Kitap",
  "book-chapter": "Kitap Bölümü",
  preprint: "Önbaskı",
  thesis: "Tez",
  event: "Etkinlik",
  other: "Diğer",
};

// ---- State ----
let currentYear = new Date().getFullYear();
let currentMonth = new Date().getMonth() + 1;
let allAcademicians = [];
let currentPublications = [];
let selectedAcadName = null;
let activeTypeFilter = "";
let scanPollInterval = null;

// ---- Init ----
document.addEventListener("DOMContentLoaded", () => {
  initYearSelector();
  setSelectors(currentYear, currentMonth);
  loadAcademicians();
  loadData(currentYear, currentMonth);
  bindEvents();
});

function initYearSelector() {
  const sel = document.getElementById("sel-year");
  const thisYear = new Date().getFullYear();
  for (let y = thisYear + 1; y >= 2020; y--) {
    const opt = document.createElement("option");
    opt.value = y;
    opt.textContent = y;
    sel.appendChild(opt);
  }
}

function setSelectors(year, month) {
  document.getElementById("sel-year").value = year;
  document.getElementById("sel-month").value = month;
}

function getSelectedYearMonth() {
  return {
    year: parseInt(document.getElementById("sel-year").value),
    month: parseInt(document.getElementById("sel-month").value),
  };
}

// ---- Event bindings ----
function bindEvents() {
  document.getElementById("sel-year").addEventListener("change", onMonthChange);
  document.getElementById("sel-month").addEventListener("change", onMonthChange);

  document.getElementById("btn-prev-month").addEventListener("click", () => {
    const { year, month } = getSelectedYearMonth();
    let ny = year, nm = month - 1;
    if (nm < 1) { nm = 12; ny--; }
    setSelectors(ny, nm);
    onMonthChange();
  });

  document.getElementById("btn-next-month").addEventListener("click", () => {
    const { year, month } = getSelectedYearMonth();
    let ny = year, nm = month + 1;
    if (nm > 12) { nm = 1; ny++; }
    setSelectors(ny, nm);
    onMonthChange();
  });

  document.getElementById("btn-scan").addEventListener("click", startScan);
  document.getElementById("btn-report").addEventListener("click", generateReport);
  document.getElementById("btn-save-manual").addEventListener("click", saveManual);
  document.getElementById("btn-clear-filter").addEventListener("click", () => {
    document.getElementById("sel-type-filter").value = "";
    activeTypeFilter = "";
    renderPublications();
  });
  document.getElementById("sel-type-filter").addEventListener("change", (e) => {
    activeTypeFilter = e.target.value;
    renderPublications();
  });
  document.getElementById("acad-search").addEventListener("input", (e) => {
    renderAcademicianList(e.target.value.toLowerCase());
  });
}

function onMonthChange() {
  const { year, month } = getSelectedYearMonth();
  currentYear = year;
  currentMonth = month;
  selectedAcadName = null;
  loadData(year, month);
}

// ---- Data loading ----
async function loadAcademicians() {
  try {
    const res = await fetch("/api/academicians");
    allAcademicians = await res.json();
    populateManualSelect();
    renderAcademicianList();
  } catch (e) {
    console.error("Akademisyen yükleme hatası:", e);
  }
}

async function loadData(year, month) {
  try {
    const [pubRes, statRes] = await Promise.all([
      fetch(`/api/publications/${year}/${month}`),
      fetch(`/api/stats/${year}/${month}`),
    ]);
    const pubData = await pubRes.json();
    currentPublications = pubData.publications || [];
    renderAcademicianList();
    renderPublications();

    if (statRes.ok) {
      const stats = await statRes.json();
      renderStats(stats);
    }
  } catch (e) {
    console.error("Veri yükleme hatası:", e);
  }
}

function renderStats(stats) {
  const curr = stats.total_publications;
  const prev = stats.prev_total_publications;
  const diff = curr - prev;
  const diffStr = diff > 0 ? `+${diff}` : `${diff}`;
  const diffColor = diff > 0 ? "text-success" : diff < 0 ? "text-danger" : "text-muted";

  document.getElementById("stat-curr").textContent = curr;
  document.getElementById("stat-prev").textContent = prev;
  document.getElementById("stat-active").textContent = stats.active_academicians;
  document.getElementById("stat-curr-sub").innerHTML =
    `<span class="${diffColor}">${diffStr} geçen aya göre</span>`;
  document.getElementById("stat-prev-sub").textContent =
    `${stats.prev_active_academicians} aktif akademisyen`;

  if (stats.scan_date) {
    try {
      const d = new Date(stats.scan_date);
      document.getElementById("stat-scan-date").textContent =
        d.toLocaleString("tr-TR", { day:"2-digit", month:"2-digit", year:"numeric",
                                     hour:"2-digit", minute:"2-digit" });
    } catch {
      document.getElementById("stat-scan-date").textContent = stats.scan_date;
    }
  } else {
    document.getElementById("stat-scan-date").textContent = "Henüz taranmadı";
  }

  document.getElementById("badge-total").textContent = `${curr} yayın`;
  document.getElementById("badge-active").textContent = `${stats.active_academicians} aktif`;
}

// ---- Academician list ----
function renderAcademicianList(searchQuery = "") {
  const container = document.getElementById("acad-list");
  const pubsByAcad = {};
  for (const pub of currentPublications) {
    pubsByAcad[pub.academician_name] = (pubsByAcad[pub.academician_name] || 0) + 1;
  }

  const filtered = searchQuery
    ? allAcademicians.filter(a =>
        a.name.toLowerCase().includes(searchQuery) ||
        (a.institution || "").toLowerCase().includes(searchQuery))
    : allAcademicians;

  // Sırala: yayın sayısı azalan, sonra isim artan
  const sorted = [...filtered].sort((a, b) => {
    const diff = (pubsByAcad[b.name] || 0) - (pubsByAcad[a.name] || 0);
    return diff !== 0 ? diff : a.name.localeCompare(b.name, "tr");
  });

  // "Tümü" seçeneği
  const allItem = document.createElement("div");
  allItem.className = "acad-item" + (selectedAcadName === null ? " active" : "");
  allItem.innerHTML = `
    <div>
      <div class="acad-name fw-semibold">Tüm Yayınlar</div>
      <div class="acad-inst">${allAcademicians.length} akademisyen</div>
    </div>
    <div class="acad-badge has-pubs">${currentPublications.length}</div>`;
  allItem.addEventListener("click", () => {
    selectedAcadName = null;
    renderPublications();
    container.querySelectorAll(".acad-item").forEach(el => el.classList.remove("active"));
    allItem.classList.add("active");
    document.getElementById("pub-list-title").textContent = "Tüm Yayınlar";
  });

  const frag = document.createDocumentFragment();
  frag.appendChild(allItem);

  sorted.forEach(acad => {
    const count = pubsByAcad[acad.name] || 0;
    const item = document.createElement("div");
    item.className = "acad-item" + (selectedAcadName === acad.name ? " active" : "");
    item.dataset.name = acad.name;
    item.innerHTML = `
      <div style="min-width:0">
        <div class="acad-name text-truncate">${acad.name}</div>
        <div class="acad-inst text-truncate">${acad.institution || "—"}</div>
      </div>
      <div class="acad-badge ${count > 0 ? "has-pubs" : ""}">${count || ""}</div>`;
    item.addEventListener("click", () => {
      selectedAcadName = acad.name;
      renderPublications();
      container.querySelectorAll(".acad-item").forEach(el => el.classList.remove("active"));
      item.classList.add("active");
      document.getElementById("pub-list-title").textContent = acad.name;
    });
    frag.appendChild(item);
  });

  container.innerHTML = "";
  container.appendChild(frag);
}

// ---- Publication list ----
function renderPublications() {
  const container = document.getElementById("pub-list");

  let pubs = currentPublications;
  if (selectedAcadName) {
    pubs = pubs.filter(p => p.academician_name === selectedAcadName);
  }
  if (activeTypeFilter) {
    pubs = pubs.filter(p => p.type === activeTypeFilter);
  }

  if (pubs.length === 0) {
    container.innerHTML = `
      <div class="text-center text-muted py-5">
        <i class="bi bi-inbox fs-2 d-block mb-2 opacity-25"></i>
        Bu dönem için yayın bulunamadı
      </div>`;
    return;
  }

  // Akademisyen bazında grupla
  const grouped = {};
  for (const pub of pubs) {
    if (!grouped[pub.academician_name]) grouped[pub.academician_name] = [];
    grouped[pub.academician_name].push(pub);
  }

  const frag = document.createDocumentFragment();

  // Tek akademisyen seçiliyse doğrudan listele
  if (selectedAcadName) {
    for (const pub of pubs) {
      frag.appendChild(makePubCard(pub, false));
    }
  } else {
    // Tüm görünümde akademisyen gruplaması
    const sortedNames = Object.keys(grouped).sort((a, b) =>
      grouped[b].length - grouped[a].length || a.localeCompare(b, "tr")
    );
    for (const name of sortedNames) {
      const header = document.createElement("div");
      header.className = "px-2 pt-3 pb-1 d-flex align-items-center gap-2";
      header.innerHTML = `
        <span class="fw-semibold small">${name}</span>
        <span class="badge bg-primary rounded-pill">${grouped[name].length}</span>`;
      frag.appendChild(header);
      for (const pub of grouped[name]) {
        frag.appendChild(makePubCard(pub, true));
      }
    }
  }

  container.innerHTML = "";
  container.appendChild(frag);
}

function makePubCard(pub, showAcad) {
  const div = document.createElement("div");
  div.className = "pub-card";

  const typeClass = `type-${pub.type || "other"}`;
  const typeLabel = TYPE_LABELS[pub.type] || pub.type || "Diğer";

  let titleHtml = pub.title || "Başlıksız";
  const link = pub.doi ? `https://doi.org/${pub.doi}` : pub.url;
  if (link) {
    titleHtml = `<a href="${link}" target="_blank" rel="noopener">${titleHtml}</a>`;
  }

  const sourceMap = { orcid: "ORCID", semantic_scholar: "S2", manual: "Manuel" };
  const sourceLabel = sourceMap[pub.source] || pub.source || "";
  const sourceClass = pub.source === "manual" ? "source-badge manual" : "source-badge";

  const uncertain = pub.month_certain === false
    ? '<span class="text-warning small" title="Ay bilgisi kesin değil">~</span>' : "";

  const metaParts = [];
  if (pub.journal) metaParts.push(`<span>${pub.journal}</span>`);
  if (pub.doi) metaParts.push(`<span class="dot">DOI: ${pub.doi}</span>`);
  if (pub.authors) metaParts.push(`<span class="dot">${pub.authors}</span>`);
  if (pub.notes) metaParts.push(`<span class="dot text-info">${pub.notes}</span>`);

  div.innerHTML = `
    <button class="btn btn-sm btn-outline-danger btn-del-pub"
            data-id="${pub.id}" title="Sil">
      <i class="bi bi-trash3"></i>
    </button>
    <div class="d-flex align-items-start gap-2 mb-1">
      <span class="type-badge ${typeClass} flex-shrink-0">${typeLabel}</span>
      ${uncertain}
      <div class="pub-title flex-grow-1">${titleHtml}</div>
    </div>
    <div class="pub-meta">
      ${showAcad ? `<span class="fw-medium text-dark">${pub.academician_name}</span>` : ""}
      <span class="${sourceClass}">${sourceLabel}</span>
      ${metaParts.join("")}
    </div>`;

  div.querySelector(".btn-del-pub").addEventListener("click", (e) => {
    e.stopPropagation();
    deletePub(pub.id, pub.year, pub.month);
  });

  return div;
}

// ---- Scan ----
async function startScan() {
  const { year, month } = getSelectedYearMonth();
  const btn = document.getElementById("btn-scan");
  btn.disabled = true;

  try {
    const res = await fetch("/api/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ year, month }),
    });
    const data = await res.json();
    const scanId = data.scan_id;

    showScanStatus(true);
    scanPollInterval = setInterval(() => pollScanStatus(scanId, year, month), 2000);
  } catch (e) {
    btn.disabled = false;
    showToast("Tarama başlatılamadı: " + e.message, "danger");
  }
}

async function pollScanStatus(scanId, year, month) {
  try {
    const res = await fetch(`/api/scan/status/${scanId}`);
    const data = await res.json();

    const pct = data.progress || 0;
    document.getElementById("scan-progress-bar").style.width = pct + "%";
    document.getElementById("scan-progress-pct").textContent = pct + "%";
    document.getElementById("scan-status-text").textContent =
      data.current_name ? `${data.current}/${data.total}: ${data.current_name}` : "Tarıyor...";

    if (data.status === "done" || data.status === "error") {
      clearInterval(scanPollInterval);
      scanPollInterval = null;
      showScanStatus(false);
      document.getElementById("btn-scan").disabled = false;

      if (data.status === "done") {
        showToast(`Tarama tamamlandı. ${data.found || 0} yeni yayın bulundu.`, "success");
        loadData(year, month);
      } else {
        showToast("Tarama sırasında hata: " + (data.error || "Bilinmeyen hata"), "danger");
      }
    }
  } catch (e) {
    console.error("Durum sorgu hatası:", e);
  }
}

function showScanStatus(visible) {
  document.getElementById("scan-status").classList.toggle("d-none", !visible);
  if (!visible) {
    document.getElementById("scan-progress-bar").style.width = "0%";
    document.getElementById("scan-progress-pct").textContent = "0%";
  }
}

// ---- Report ----
async function generateReport() {
  const { year, month } = getSelectedYearMonth();
  const btn = document.getElementById("btn-report");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Hazırlanıyor...';

  try {
    const res = await fetch(`/api/report/${year}/${month}`);
    const data = await res.json();
    if (data.ok) {
      window.location.href = data.download_url;
      showToast("Rapor hazır, indiriliyor...", "success");
    } else {
      showToast("Rapor oluşturulamadı.", "danger");
    }
  } catch (e) {
    showToast("Rapor hatası: " + e.message, "danger");
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-file-earmark-text me-1"></i>Rapor';
  }
}

// ---- Manual add ----
function populateManualSelect() {
  const sel = document.getElementById("m-acad");
  allAcademicians.forEach(a => {
    const opt = document.createElement("option");
    opt.value = a.name;
    opt.textContent = a.name + (a.institution ? ` (${a.institution})` : "");
    sel.appendChild(opt);
  });
}

async function saveManual() {
  const { year, month } = getSelectedYearMonth();

  const acad = document.getElementById("m-acad").value;
  const title = document.getElementById("m-title").value.trim();
  const type = document.getElementById("m-type").value;
  const journal = document.getElementById("m-journal").value.trim();
  const myear = parseInt(document.getElementById("m-year").value) || year;
  const mmonth = parseInt(document.getElementById("m-month").value) || month;
  const doi = document.getElementById("m-doi").value.trim();
  const url = document.getElementById("m-url").value.trim();
  const authors = document.getElementById("m-authors").value.trim();
  const notes = document.getElementById("m-notes").value.trim();

  if (!acad || !title) {
    showToast("Akademisyen ve başlık zorunludur.", "danger");
    return;
  }

  try {
    const res = await fetch("/api/publications/manual", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ academician_name: acad, title, type, journal,
                             year: myear, month: mmonth, doi, url, authors, notes }),
    });
    const data = await res.json();
    if (data.ok) {
      bootstrap.Modal.getInstance(document.getElementById("modal-manual")).hide();
      document.getElementById("form-manual").reset();
      showToast("Yayın eklendi.", "success");
      // Seçili ay ile eşleşiyorsa yenile
      if (myear === currentYear && mmonth === currentMonth) {
        loadData(currentYear, currentMonth);
      }
    } else {
      showToast("Hata: " + (data.error || "Bilinmeyen hata"), "danger");
    }
  } catch (e) {
    showToast("Kayıt hatası: " + e.message, "danger");
  }
}

// Manuel modal açılırken ay/yıl doldur
document.addEventListener("show.bs.modal", (e) => {
  if (e.target.id === "modal-manual") {
    document.getElementById("m-year").value = currentYear;
    document.getElementById("m-month").value = currentMonth;
    if (selectedAcadName) {
      document.getElementById("m-acad").value = selectedAcadName;
    }
  }
});

// ---- Delete ----
async function deletePub(pubId, year, month) {
  if (!confirm("Bu yayını silmek istediğinizden emin misiniz?")) return;
  try {
    const res = await fetch(`/api/publications/${year}/${month}?id=${pubId}`, {
      method: "DELETE",
    });
    const data = await res.json();
    if (data.ok) {
      showToast("Yayın silindi.", "success");
      loadData(currentYear, currentMonth);
    } else {
      showToast("Silme hatası: " + (data.error || ""), "danger");
    }
  } catch (e) {
    showToast("Silme hatası: " + e.message, "danger");
  }
}

// ---- Toast ----
function showToast(message, type = "success") {
  const toastEl = document.getElementById("toast-msg");
  const body = document.getElementById("toast-body");
  toastEl.className = `toast align-items-center text-white border-0 bg-${type}`;
  body.textContent = message;
  const toast = bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 4000 });
  toast.show();
}
