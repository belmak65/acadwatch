"""
ICTMD Türkiye Akademik Takip - Rapor Üretici
Aylık HTML raporu oluşturur.
"""
from datetime import datetime
from collections import defaultdict

MONTHS_TR = {
    1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan",
    5: "Mayıs", 6: "Haziran", 7: "Temmuz", 8: "Ağustos",
    9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık",
}

TYPE_LABELS = {
    "article": "Makale",
    "conference": "Bildiri",
    "book": "Kitap",
    "book-chapter": "Kitap Bölümü",
    "preprint": "Önbaskı",
    "thesis": "Tez",
    "event": "Etkinlik",
    "other": "Diğer",
}

TYPE_COLORS = {
    "article": "#0d6efd",
    "conference": "#198754",
    "book": "#6f42c1",
    "book-chapter": "#d63384",
    "preprint": "#fd7e14",
    "thesis": "#20c997",
    "event": "#e83e8c",
    "other": "#6c757d",
}


def _prev_month(year, month):
    if month == 1:
        return year - 1, 12
    return year, month - 1


def generate_report(
    year: int,
    month: int,
    current_data: dict,
    prev_data: dict,
    academicians: list,
) -> str:
    """HTML raporu oluştur ve string olarak döndür."""

    month_name = MONTHS_TR.get(month, str(month))
    prev_year, prev_month = _prev_month(year, month)
    prev_month_name = MONTHS_TR.get(prev_month, str(prev_month))

    # Yayınları akademisyen bazında grupla
    def group_by_acad(data):
        grouped = defaultdict(list)
        for pub in data.get("publications", []):
            grouped[pub["academician_name"]].append(pub)
        return grouped

    curr_grouped = group_by_acad(current_data)
    prev_grouped = group_by_acad(prev_data) if prev_data else {}

    # İstatistikler
    total_curr = len(current_data.get("publications", []))
    total_prev = len(prev_data.get("publications", [])) if prev_data else 0
    active_curr = len([a for a in academicians if curr_grouped.get(a["name"])])
    active_prev = len([a for a in academicians if prev_grouped.get(a["name"])]) if prev_data else 0

    type_counts = defaultdict(int)
    for pub in current_data.get("publications", []):
        type_counts[pub.get("type", "other")] += 1

    # Rapor tablosu satırları
    table_rows = ""
    for acad in sorted(academicians, key=lambda x: x["name"]):
        name = acad["name"]
        curr_pubs = curr_grouped.get(name, [])
        prev_pubs = prev_grouped.get(name, [])
        curr_count = len(curr_pubs)
        prev_count = len(prev_pubs)
        diff = curr_count - prev_count

        if curr_count == 0 and prev_count == 0:
            continue  # Boş satırları atla

        diff_html = ""
        if diff > 0:
            diff_html = f'<span class="badge bg-success">+{diff}</span>'
        elif diff < 0:
            diff_html = f'<span class="badge bg-danger">{diff}</span>'
        else:
            diff_html = f'<span class="badge bg-secondary">0</span>'

        institution = acad.get("institution", "")
        profile_url = acad.get("profileUrl", "")
        name_html = f'<a href="{profile_url}" target="_blank">{name}</a>' if profile_url else name

        types_html = ""
        for t, c in sorted(defaultdict(int, {p.get("type", "other"): 1 for p in curr_pubs}).items()):
            color = TYPE_COLORS.get(t, "#6c757d")
            label = TYPE_LABELS.get(t, t)
            types_html += f'<span class="badge" style="background-color:{color}">{label}</span> '

        table_rows += f"""
        <tr>
          <td>{name_html}</td>
          <td class="text-muted small">{institution}</td>
          <td class="text-center fw-bold">{curr_count}</td>
          <td class="text-center text-muted">{prev_count}</td>
          <td class="text-center">{diff_html}</td>
          <td>{types_html}</td>
        </tr>"""

    # Detaylı yayın listesi
    detail_sections = ""
    for acad in sorted(academicians, key=lambda x: x["name"]):
        name = acad["name"]
        curr_pubs = curr_grouped.get(name, [])
        if not curr_pubs:
            continue

        pub_rows = ""
        for pub in curr_pubs:
            t = pub.get("type", "other")
            color = TYPE_COLORS.get(t, "#6c757d")
            label = TYPE_LABELS.get(t, t)
            title = pub.get("title", "")
            journal = pub.get("journal", "")
            doi = pub.get("doi", "")
            url = pub.get("url", "")
            source = pub.get("source", "")
            source_map = {"orcid": "ORCID", "semantic_scholar": "Semantic Scholar", "manual": "Manuel"}
            source_label = source_map.get(source, source)

            title_html = title
            if doi:
                title_html = f'<a href="https://doi.org/{doi}" target="_blank">{title}</a>'
            elif url:
                title_html = f'<a href="{url}" target="_blank">{title}</a>'

            pub_rows += f"""
            <tr>
              <td><span class="badge" style="background-color:{color}">{label}</span></td>
              <td>{title_html}</td>
              <td class="text-muted small">{journal}</td>
              <td><span class="badge bg-light text-dark border small">{source_label}</span></td>
            </tr>"""

        profile_url = acad.get("profileUrl", "")
        institution = acad.get("institution", "")
        header_link = f'<a href="{profile_url}" target="_blank" class="text-decoration-none">{name}</a>' if profile_url else name

        detail_sections += f"""
        <div class="mb-4">
          <h5 class="border-bottom pb-2">
            {header_link}
            <small class="text-muted fw-normal ms-2">{institution}</small>
            <span class="badge bg-primary ms-2">{len(curr_pubs)} yayın</span>
          </h5>
          <table class="table table-sm table-hover">
            <thead class="table-light">
              <tr><th style="width:110px">Tür</th><th>Başlık</th><th>Dergi/Yer</th><th>Kaynak</th></tr>
            </thead>
            <tbody>{pub_rows}</tbody>
          </table>
        </div>"""

    type_stats_html = ""
    for t, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
        color = TYPE_COLORS.get(t, "#6c757d")
        label = TYPE_LABELS.get(t, t)
        pct = round(cnt / total_curr * 100) if total_curr > 0 else 0
        type_stats_html += f"""
        <div class="d-flex align-items-center mb-2">
          <span class="badge me-2" style="background-color:{color};min-width:90px">{label}</span>
          <div class="progress flex-grow-1 me-2" style="height:18px">
            <div class="progress-bar" style="width:{pct}%;background-color:{color}">{cnt}</div>
          </div>
          <span class="text-muted small">{pct}%</span>
        </div>"""

    scan_date = current_data.get("scan_date", "")
    if scan_date:
        try:
            scan_date = datetime.fromisoformat(scan_date).strftime("%d.%m.%Y %H:%M")
        except Exception:
            pass

    html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ICTMD Türkiye — {month_name} {year} Yayın Raporu</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f8f9fa; }}
    .report-header {{ background: linear-gradient(135deg,#1a237e,#283593); color:#fff; padding:2rem; border-radius:0 0 1rem 1rem; margin-bottom:2rem; }}
    .stat-card {{ background:#fff; border-radius:.75rem; box-shadow:0 2px 8px rgba(0,0,0,.08); padding:1.5rem; text-align:center; }}
    .stat-number {{ font-size:2.5rem; font-weight:700; line-height:1; }}
    @media print {{
      .no-print {{ display:none; }}
      body {{ background:#fff; }}
      .report-header {{ background:#1a237e !important; -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
    }}
    a {{ color:#1a237e; }}
    .table th {{ font-size:.85rem; text-transform:uppercase; letter-spacing:.5px; }}
  </style>
</head>
<body>
<div class="report-header">
  <div class="container">
    <div class="d-flex justify-content-between align-items-start flex-wrap gap-3">
      <div>
        <h1 class="h3 mb-1">ICTMD Türkiye — Aylık Akademik Yayın Raporu</h1>
        <p class="mb-0 opacity-75">
          <strong>{month_name} {year}</strong> dönemi &nbsp;|&nbsp;
          Önceki dönem: {prev_month_name} {prev_year} &nbsp;|&nbsp;
          Oluşturulma: {datetime.now().strftime("%d.%m.%Y %H:%M")}
        </p>
        {f'<p class="mb-0 opacity-50 small">Tarama tarihi: {scan_date}</p>' if scan_date else ''}
      </div>
      <button onclick="window.print()" class="btn btn-light no-print">Yazdır / PDF</button>
    </div>
  </div>
</div>

<div class="container pb-5">

  <!-- Özet kartlar -->
  <div class="row g-3 mb-4">
    <div class="col-6 col-md-3">
      <div class="stat-card">
        <div class="stat-number text-primary">{total_curr}</div>
        <div class="text-muted small mt-1">Bu Ay Yayın</div>
      </div>
    </div>
    <div class="col-6 col-md-3">
      <div class="stat-card">
        <div class="stat-number text-secondary">{total_prev}</div>
        <div class="text-muted small mt-1">Geçen Ay Yayın</div>
      </div>
    </div>
    <div class="col-6 col-md-3">
      <div class="stat-card">
        <div class="stat-number text-success">{active_curr}</div>
        <div class="text-muted small mt-1">Aktif Akademisyen</div>
      </div>
    </div>
    <div class="col-6 col-md-3">
      <div class="stat-card">
        <div class="stat-number {'text-success' if total_curr >= total_prev else 'text-danger'}">
          {'+'if total_curr >= total_prev else ''}{total_curr - total_prev}
        </div>
        <div class="text-muted small mt-1">Değişim</div>
      </div>
    </div>
  </div>

  <div class="row g-4 mb-4">
    <!-- Yayın türü dağılımı -->
    <div class="col-md-4">
      <div class="card border-0 shadow-sm h-100">
        <div class="card-body">
          <h6 class="card-title text-uppercase text-muted small mb-3">Yayın Türü Dağılımı</h6>
          {type_stats_html if type_stats_html else '<p class="text-muted">Veri yok</p>'}
        </div>
      </div>
    </div>

    <!-- Özet karşılaştırma tablosu -->
    <div class="col-md-8">
      <div class="card border-0 shadow-sm">
        <div class="card-body">
          <h6 class="card-title text-uppercase text-muted small mb-3">
            Akademisyen Karşılaştırması — {month_name} vs {prev_month_name}
          </h6>
          <div style="max-height:320px;overflow-y:auto">
          <table class="table table-sm table-hover mb-0">
            <thead class="table-light sticky-top">
              <tr>
                <th>Akademisyen</th>
                <th class="text-muted small">Kurum</th>
                <th class="text-center">{month_name}</th>
                <th class="text-center">{prev_month_name}</th>
                <th class="text-center">Fark</th>
                <th>Türler</th>
              </tr>
            </thead>
            <tbody>
              {table_rows if table_rows else '<tr><td colspan="6" class="text-center text-muted">Bu ay yayın bulunamadı</td></tr>'}
            </tbody>
          </table>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Detaylı yayın listesi -->
  <div class="card border-0 shadow-sm">
    <div class="card-body">
      <h5 class="card-title mb-4">
        {month_name} {year} — Akademisyen Bazlı Yayın Listesi
      </h5>
      {detail_sections if detail_sections else '<p class="text-muted text-center py-4">Bu ay için yayın kaydı bulunamadı.</p>'}
    </div>
  </div>

</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""

    return html
