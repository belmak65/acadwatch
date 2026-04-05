"""
ICTMD Türkiye Akademik Takip — Flask Uygulaması
"""
import json
import os
import uuid
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, render_template, send_file, abort

import scanner as sc
import report_generator as rg
import acad_helpers as ah

app = Flask(__name__)

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
ACAD_FILE = BASE_DIR / "academicians.json"

DATA_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

# ---- Bellek içi tarama durumu ----
_scan_jobs: dict[str, dict] = {}  # scan_id -> status dict
_scan_lock = threading.Lock()


# ---- Yardımcı fonksiyonlar ----

def load_academicians() -> list:
    with open(ACAD_FILE, encoding="utf-8") as f:
        return json.load(f)


def data_path(year: int, month: int) -> Path:
    return DATA_DIR / f"{year}_{month:02d}.json"


def load_month_data(year: int, month: int) -> dict:
    p = data_path(year, month)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {"year": year, "month": month, "scan_date": None, "publications": []}


def save_month_data(year: int, month: int, data: dict):
    p = data_path(year, month)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def prev_month(year: int, month: int):
    if month == 1:
        return year - 1, 12
    return year, month - 1


def pub_id() -> str:
    return str(uuid.uuid4())


# ---- Flask Rotaları ----

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/academicians")
def api_academicians():
    return jsonify(load_academicians())


@app.route("/api/months")
def api_months():
    """Mevcut veri dosyalarındaki ay listesi."""
    months = []
    for p in sorted(DATA_DIR.glob("*.json")):
        stem = p.stem  # e.g. "2026_03"
        parts = stem.split("_")
        if len(parts) == 2:
            try:
                months.append({"year": int(parts[0]), "month": int(parts[1])})
            except ValueError:
                pass
    return jsonify(months)


@app.route("/api/publications/<int:year>/<int:month>")
def api_publications(year, month):
    data = load_month_data(year, month)
    return jsonify(data)


@app.route("/api/publications/<int:year>/<int:month>", methods=["DELETE"])
def api_delete_publication(year, month):
    pub_id_val = request.args.get("id")
    if not pub_id_val:
        return jsonify({"error": "id gerekli"}), 400
    data = load_month_data(year, month)
    original_count = len(data["publications"])
    data["publications"] = [p for p in data["publications"] if p.get("id") != pub_id_val]
    if len(data["publications"]) == original_count:
        return jsonify({"error": "Yayın bulunamadı"}), 404
    save_month_data(year, month, data)
    return jsonify({"ok": True})


@app.route("/api/publications/manual", methods=["POST"])
def api_add_manual():
    body = request.get_json()
    required = ["academician_name", "title", "year", "month"]
    for field in required:
        if not body.get(field):
            return jsonify({"error": f"{field} zorunlu"}), 400

    year = int(body["year"])
    month = int(body["month"])

    data = load_month_data(year, month)

    pub = {
        "id": pub_id(),
        "academician_name": body["academician_name"],
        "title": body["title"],
        "type": body.get("type", "other"),
        "year": year,
        "month": month,
        "journal": body.get("journal", ""),
        "doi": body.get("doi", ""),
        "url": body.get("url", ""),
        "authors": body.get("authors", ""),
        "notes": body.get("notes", ""),
        "source": "manual",
        "is_manual": True,
        "added_at": datetime.now().isoformat(),
        "month_certain": True,
    }

    data["publications"].append(pub)
    save_month_data(year, month, data)
    return jsonify({"ok": True, "publication": pub})


# ---- Tarama ----

def _run_scan(scan_id: str, year: int, month: int):
    """Arka planda tarama çalıştır."""
    academicians = load_academicians()
    total = len(academicians)

    def update(i, t, name):
        with _scan_lock:
            _scan_jobs[scan_id].update({
                "current": i,
                "total": t,
                "current_name": name,
                "progress": round(i / t * 100) if t > 0 else 0,
            })

    try:
        results = sc.scan_all(academicians, year, month, progress_callback=update)

        # Mevcut veriyi yükle (manuel eklenenler korunacak)
        data = load_month_data(year, month)
        existing_manual = [p for p in data["publications"] if p.get("is_manual")]

        # Tarama sonuçlarını işle
        new_pubs = []
        seen_dois = set()
        seen_titles = set()

        # Manuel yayınların DOI ve başlıklarını kaydet
        for pub in existing_manual:
            if pub.get("doi"):
                seen_dois.add(pub["doi"].lower())
            seen_titles.add(pub["title"].lower().strip())

        for result in results:
            acad = result["academician"]
            for pub in result["publications"]:
                # Tekrar kontrolü
                doi = pub.get("doi")
                title = pub.get("title", "").lower().strip()

                if doi and doi.lower() in seen_dois:
                    continue
                if title and title in seen_titles:
                    continue

                if doi:
                    seen_dois.add(doi.lower())
                if title:
                    seen_titles.add(title)

                new_pubs.append({
                    "id": pub_id(),
                    "academician_name": ah.name(acad),
                    "academician_orcid": acad.get("orcid", ""),
                    "title": pub.get("title", ""),
                    "type": pub.get("type", "other"),
                    "year": pub.get("year", year),
                    "month": pub.get("month", month),
                    "journal": pub.get("journal", ""),
                    "doi": pub.get("doi"),
                    "url": pub.get("url", ""),
                    "source": pub.get("source", ""),
                    "is_manual": False,
                    "month_certain": pub.get("month_certain", False),
                    "scanned_at": datetime.now().isoformat(),
                })

        data["publications"] = existing_manual + new_pubs
        data["scan_date"] = datetime.now().isoformat()
        save_month_data(year, month, data)

        with _scan_lock:
            _scan_jobs[scan_id].update({
                "status": "done",
                "found": len(new_pubs),
                "total_in_db": len(data["publications"]),
            })

    except Exception as e:
        with _scan_lock:
            _scan_jobs[scan_id].update({
                "status": "error",
                "error": str(e),
            })


@app.route("/api/scan", methods=["POST"])
def api_start_scan():
    body = request.get_json() or {}
    year = int(body.get("year", datetime.now().year))
    month = int(body.get("month", datetime.now().month))

    # Aynı ay için zaten çalışan iş var mı?
    with _scan_lock:
        for jid, job in _scan_jobs.items():
            if (job["year"] == year and job["month"] == month
                    and job["status"] == "running"):
                return jsonify({"scan_id": jid, "already_running": True})

    scan_id = str(uuid.uuid4())
    with _scan_lock:
        _scan_jobs[scan_id] = {
            "scan_id": scan_id,
            "year": year,
            "month": month,
            "status": "running",
            "current": 0,
            "total": 46,
            "progress": 0,
            "current_name": "",
            "started_at": datetime.now().isoformat(),
        }

    t = threading.Thread(target=_run_scan, args=(scan_id, year, month), daemon=True)
    t.start()

    return jsonify({"scan_id": scan_id, "status": "started"})


@app.route("/api/scan/status/<scan_id>")
def api_scan_status(scan_id):
    with _scan_lock:
        job = _scan_jobs.get(scan_id)
    if not job:
        return jsonify({"error": "Tarama bulunamadı"}), 404
    return jsonify(job)


# ---- Rapor ----

@app.route("/api/report/<int:year>/<int:month>")
def api_report(year, month):
    """HTML raporu oluştur ve kaydet, URL döndür."""
    academicians = load_academicians()
    current_data = load_month_data(year, month)
    py, pm = prev_month(year, month)
    prev_data = load_month_data(py, pm)

    html = rg.generate_report(year, month, current_data, prev_data, academicians)

    report_file = REPORTS_DIR / f"rapor_{year}_{month:02d}.html"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(html)

    return jsonify({
        "ok": True,
        "filename": report_file.name,
        "download_url": f"/api/report/{year}/{month}/download",
    })


@app.route("/api/report/<int:year>/<int:month>/download")
def api_report_download(year, month):
    report_file = REPORTS_DIR / f"rapor_{year}_{month:02d}.html"
    if not report_file.exists():
        # Raporu oluştur
        academicians = load_academicians()
        current_data = load_month_data(year, month)
        py, pm = prev_month(year, month)
        prev_data = load_month_data(py, pm)
        html = rg.generate_report(year, month, current_data, prev_data, academicians)
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(html)

    return send_file(
        report_file,
        mimetype="text/html",
        as_attachment=True,
        download_name=f"ICTMD_Rapor_{year}_{month:02d}.html",
    )


@app.route("/api/stats/<int:year>/<int:month>")
def api_stats(year, month):
    current_data = load_month_data(year, month)
    py, pm = prev_month(year, month)
    prev_data = load_month_data(py, pm)

    curr_pubs = current_data.get("publications", [])
    prev_pubs = prev_data.get("publications", [])

    from collections import Counter
    type_dist = Counter(p.get("type", "other") for p in curr_pubs)
    source_dist = Counter(p.get("source", "other") for p in curr_pubs)

    academicians = load_academicians()
    acad_names = {ah.name(a) for a in academicians}

    curr_active = len({p["academician_name"] for p in curr_pubs if p["academician_name"] in acad_names})
    prev_active = len({p["academician_name"] for p in prev_pubs if p["academician_name"] in acad_names})

    return jsonify({
        "year": year,
        "month": month,
        "total_publications": len(curr_pubs),
        "prev_total_publications": len(prev_pubs),
        "active_academicians": curr_active,
        "prev_active_academicians": prev_active,
        "type_distribution": dict(type_dist),
        "source_distribution": dict(source_dist),
        "scan_date": current_data.get("scan_date"),
    })


if __name__ == "__main__":
    print("ICTMD Türkiye Akademik Takip başlatılıyor...")
    print("http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
