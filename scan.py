#!/usr/bin/env python3
"""
ICTMD Türkiye Akademik Yayın Tarayıcı
Kullanım:
  python scan.py --test                      → 3 akademisyen test taraması
  python scan.py --year 2025 --month 11      → Tek ay
  python scan.py --year 2025 --months 10,11,12   → Birden fazla ay
  python scan.py --year 2025 --month-range 2-6   → Ay aralığı
  python scan.py --year 2025                 → Tüm yıl
  python scan.py --all-time                  → Tüm yıllar
  python scan.py --demo                      → Örnek çıktı
"""
import json
import sys
import time
import argparse
import uuid
from datetime import datetime
from pathlib import Path
from collections import defaultdict

import requests

# ── Renkler ──────────────────────────────────────────────────────────────────
R  = "\033[0m"
B  = "\033[1m"
GR = "\033[32m"
YL = "\033[33m"
BL = "\033[34m"
CY = "\033[36m"
RD = "\033[31m"
DIM= "\033[2m"

TYPE_LABELS = {
    "article": "Makale", "conference": "Bildiri",
    "book": "Kitap", "book-chapter": "Kitap Bölümü",
    "preprint": "Önbaskı", "thesis": "Tez",
    "event": "Etkinlik", "other": "Diğer",
}
MONTHS_TR = ["","Ocak","Şubat","Mart","Nisan","Mayıs","Haziran",
             "Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"]

ORCID_HEADERS = {"Accept": "application/vnd.orcid+json"}
SS_HEADERS    = {"User-Agent": "ICTMD-AcadWatch/1.0"}

ORCID_TYPE_MAP = {
    "journal-article": "article", "conference-paper": "conference",
    "conference-abstract": "conference", "book": "book",
    "book-chapter": "book-chapter", "edited-book": "book",
    "dissertation": "thesis", "preprint": "preprint",
    "working-paper": "preprint", "report": "other",
    "magazine-article": "article", "newsletter-article": "article",
    "other": "other", "artistic-performance": "event",
    "lecture-speech": "event", "online-resource": "other",
    "data-set": "other", "software": "other",
}


# ── ORCID ─────────────────────────────────────────────────────────────────────
def _sv(d):
    return d.get("value", "") if isinstance(d, dict) else (str(d) if d else "")

def fetch_orcid_works(orcid: str) -> list:
    url = f"https://pub.orcid.org/v3.0/{orcid}/works"
    try:
        r = requests.get(url, headers=ORCID_HEADERS, timeout=30)
        if r.status_code != 200:
            return []
        return r.json().get("group", [])
    except Exception as e:
        print(f"  {RD}ORCID hata {orcid}: {e}{R}")
        return []

def parse_orcid_works(groups, year=None, months=None, all_time=False):
    """months: set[int] | None  (None = ay filtresi yok)"""
    pubs = []
    for grp in groups:
        for s in grp.get("work-summary", []):
            pd = s.get("publication-date") or {}
            y_val = _sv(pd.get("year"))
            m_val = _sv(pd.get("month"))
            try: py = int(y_val)
            except: py = None
            try: pm = int(m_val)
            except: pm = None

            if not all_time:
                if year and py != year: continue
                if months and pm is not None and pm not in months: continue

            title_obj = s.get("title") or {}
            title = _sv(title_obj.get("title")) or "Başlıksız"
            wtype = ORCID_TYPE_MAP.get(s.get("type", "other"), "other")
            journal = _sv(s.get("journal-title"))

            doi = None
            for eid in (s.get("external-ids") or {}).get("external-id", []):
                if eid.get("external-id-type") == "doi":
                    doi = eid.get("external-id-value"); break

            pubs.append({
                "title": title, "type": wtype,
                "year": py, "month": pm,
                "journal": journal, "doi": doi, "source": "orcid",
                "month_certain": pm is not None,
            })
    return pubs


# ── Semantic Scholar ───────────────────────────────────────────────────────────
def find_ss_author(name: str) -> str | None:
    url = "https://api.semanticscholar.org/graph/v1/author/search"
    params = {"query": name, "fields": "authorId,name,paperCount", "limit": 5}
    try:
        r = requests.get(url, params=params, headers=SS_HEADERS, timeout=20)
        if r.status_code == 429:
            time.sleep(10)
            r = requests.get(url, params=params, headers=SS_HEADERS, timeout=20)
        if r.status_code != 200: return None
        results = r.json().get("data", [])
        return results[0]["authorId"] if results else None
    except: return None

def fetch_ss_papers(author_id: str, year=None, months=None, all_time=False) -> list:
    """months: set[int] | None  (None = ay filtresi yok)"""
    url = f"https://api.semanticscholar.org/graph/v1/author/{author_id}/papers"
    params = {
        "fields": "title,year,publicationDate,publicationTypes,journal,externalIds,venue",
        "limit": 200,
    }
    try:
        r = requests.get(url, params=params, headers=SS_HEADERS, timeout=30)
        if r.status_code == 429:
            time.sleep(10)
            r = requests.get(url, params=params, headers=SS_HEADERS, timeout=30)
        if r.status_code != 200: return []

        pubs = []
        for p in r.json().get("data", []):
            py = p.get("year")
            pd_str = p.get("publicationDate", "") or ""
            pm = None
            if len(pd_str) >= 7:
                try: pm = int(pd_str[5:7])
                except: pass

            if not all_time:
                if year and py != year: continue
                if months:
                    if pm is None: continue   # tarih belirsizse atla
                    if pm not in months: continue

            ext = p.get("externalIds") or {}
            doi = ext.get("DOI")
            pub_types = p.get("publicationTypes") or []
            t = _map_ss_type(pub_types)
            j_obj = p.get("journal") or {}
            journal = j_obj.get("name", "") or p.get("venue", "")
            pubs.append({
                "title": p.get("title", "Başlıksız"), "type": t,
                "year": py, "month": pm,
                "journal": journal, "doi": doi, "source": "semantic_scholar",
                "month_certain": pm is not None,
            })
        return pubs
    except Exception as e:
        return []

def _map_ss_type(pub_types):
    s = " ".join(pub_types).lower()
    if "journalarticle" in s: return "article"
    if "conference" in s: return "conference"
    if "bookchapter" in s or ("book" in s and "chapter" in s): return "book-chapter"
    if "book" in s: return "book"
    if "preprint" in s: return "preprint"
    if "review" in s: return "article"
    return "other"


# ── Akademisyen tarama ─────────────────────────────────────────────────────────
def scan_one(acad: dict, year=None, months=None, all_time=False, verbose=True) -> list:
    """months: set[int] | None"""
    name   = acad["name"]
    orcid  = acad.get("orcid", "")
    pubs   = []
    seen_dois   = set()
    seen_titles = set()

    def _add(p_list):
        for p in p_list:
            doi   = (p.get("doi") or "").strip().lower()
            title = (p.get("title") or "").strip().lower()
            if doi and doi in seen_dois: continue
            if title and title in seen_titles: continue
            if doi: seen_dois.add(doi)
            if title: seen_titles.add(title)
            pubs.append(p)

    # ORCID
    if orcid:
        groups = fetch_orcid_works(orcid)
        orcid_pubs = parse_orcid_works(groups, year, months, all_time)
        _add(orcid_pubs)
        if verbose and orcid_pubs:
            print(f"    {DIM}ORCID: {len(orcid_pubs)} yayın{R}")
        time.sleep(0.4)

    # Semantic Scholar
    ss_id = find_ss_author(name)
    if ss_id:
        time.sleep(0.8)
        ss_pubs = fetch_ss_papers(ss_id, year, months, all_time)
        _add(ss_pubs)
        if verbose and ss_pubs:
            print(f"    {DIM}Semantic Scholar: {len(ss_pubs)} yeni yayın{R}")
    else:
        if verbose: print(f"    {DIM}Semantic Scholar: yazar bulunamadı{R}")

    return pubs


# ── Terminal çıktısı ───────────────────────────────────────────────────────────
def print_results(name: str, pubs: list):
    if not pubs:
        print(f"  {DIM}→ Yayın bulunamadı{R}")
        return
    for p in pubs:
        t_label = TYPE_LABELS.get(p["type"], p["type"])
        t_color = {
            "article":"[Makale]", "conference":"[Bildiri]",
            "book":"[Kitap]", "book-chapter":"[Kitap Bölümü]",
            "preprint":"[Önbaskı]", "event":"[Etkinlik]",
        }.get(p["type"], "[Diğer]")

        src = {"orcid": "ORCID", "semantic_scholar": "S2"}.get(p["source"], p["source"])
        date_str = f"{p['year']}"
        if p.get("month"): date_str += f"/{p['month']:02d}"
        uncertain = " ~" if not p.get("month_certain") else ""

        print(f"  {GR}{t_color}{R} {B}{p['title']}{R}")
        parts = []
        if p.get("journal"): parts.append(p["journal"])
        if p.get("doi"):     parts.append(f"DOI:{p['doi']}")
        parts.append(f"{date_str}{uncertain}")
        parts.append(f"kaynak:{src}")
        print(f"    {DIM}{' | '.join(parts)}{R}")


def _months_label(months, year, all_time):
    if all_time:
        return "Tüm yıllar"
    if not months:
        return f"{year} (tüm aylar)"
    sorted_m = sorted(months)
    if len(sorted_m) == 1:
        return f"{MONTHS_TR[sorted_m[0]]} {year}"
    names = [MONTHS_TR[m] for m in sorted_m]
    return f"{', '.join(names)} {year}"


def print_summary(all_results: list, year, months, all_time):
    total = sum(len(r["pubs"]) for r in all_results)
    active = sum(1 for r in all_results if r["pubs"])
    print()
    print(f"{B}{'═'*60}{R}")
    print(f"{B}ÖZET{R}")
    print(f"  Dönem   : {_months_label(months, year, all_time)}")
    print(f"  Toplam  : {B}{GR}{total} yayın{R}")
    print(f"  Aktif   : {B}{active}/{len(all_results)} akademisyen{R}")
    print()

    # Tür dağılımı
    by_type = defaultdict(int)
    for r in all_results:
        for p in r["pubs"]:
            by_type[p["type"]] += 1
    if by_type:
        print(f"  {B}Tür dağılımı:{R}")
        for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
            bar = "█" * c
            print(f"    {TYPE_LABELS.get(t, t):<16} {YL}{bar}{R} {c}")

    print(f"{B}{'═'*60}{R}")


# ── JSON kayıt ────────────────────────────────────────────────────────────────
def save_json(all_results: list, year, months, all_time, path: Path):
    publications = []
    for r in all_results:
        acad = r["acad"]
        for p in r["pubs"]:
            publications.append({
                "id": str(uuid.uuid4()),
                "academician_name": acad["name"],
                "academician_orcid": acad.get("orcid", ""),
                "academician_institution": acad.get("institution", ""),
                "title": p["title"],
                "type": p["type"],
                "year": p["year"],
                "month": p.get("month"),
                "journal": p.get("journal", ""),
                "doi": p.get("doi"),
                "source": p["source"],
                "month_certain": p.get("month_certain", False),
            })

    out = {
        "scan_date": datetime.now().isoformat(),
        "filter": {
            "year": year,
            "months": sorted(months) if months else None,
            "all_time": all_time,
        },
        "total": len(publications),
        "publications": publications,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n{GR}✓{R} JSON kaydedildi: {B}{path}{R}  ({len(publications)} yayın)")
    return out


# ── HTML raporu ────────────────────────────────────────────────────────────────
def save_html(all_results: list, year, months, all_time, path: Path):
    from report_generator import generate_report

    publications = []
    for r in all_results:
        acad = r["acad"]
        for p in r["pubs"]:
            publications.append({**p, "academician_name": acad["name"]})

    # Rapor üretici tek ay bekliyor; çok aylıda ilk ayı ya da 0 ver
    disp_month = (sorted(months)[0] if months and len(months) == 1
                  else (sorted(months)[0] if months else 0))
    current_data = {"year": year or 0, "month": disp_month,
                    "scan_date": datetime.now().isoformat(),
                    "publications": publications}
    academicians = [r["acad"] for r in all_results]

    html = generate_report(year or 0, disp_month, current_data, {}, academicians)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"{GR}✓{R} HTML rapor kaydedildi: {B}{path}{R}")


# ── Ana akış ──────────────────────────────────────────────────────────────────
def demo_data():
    """Çıktı formatını göstermek için örnek veri üret."""
    return [
        {"acad": {"name": "Arzu Öztürkmen", "institution": "Boğaziçi Üniversitesi",
                  "orcid": "0000-0001-9497-7995", "field": "Müzik / Dans"}, "pubs": [
            {"title": "Dance as Cultural Heritage: Circassian Communities in Turkey",
             "type": "article", "year": 2024, "month": 11,
             "journal": "Journal of Ethnomusicology", "doi": "10.5406/jenthnomus.2024.01",
             "source": "orcid", "month_certain": True},
            {"title": "Memory and Movement: Displacement in Folk Dance Traditions",
             "type": "book-chapter", "year": 2024, "month": 9,
             "journal": "Routledge Handbook of Dance Ethnography", "doi": None,
             "source": "orcid", "month_certain": True},
        ]},
        {"acad": {"name": "Cenk Güray", "institution": "Hacettepe Üniversitesi",
                  "orcid": "0000-0002-9410-725X", "field": "Müzik / Dans"}, "pubs": [
            {"title": "Modal Concepts in Ottoman/Turkish Music Theory: A Re-evaluation",
             "type": "article", "year": 2024, "month": 10,
             "journal": "Musicologica Austriaca", "doi": "10.5281/musicol.2024.cenk",
             "source": "orcid", "month_certain": True},
            {"title": "Maqam and Mode: Cross-Cultural Perspectives",
             "type": "conference", "year": 2024, "month": 11,
             "journal": "ICTM World Conference Proceedings", "doi": None,
             "source": "semantic_scholar", "month_certain": True},
            {"title": "Türk Müziğinde Makam Dizileri ve Usul İlişkisi",
             "type": "article", "year": 2024, "month": 12,
             "journal": "Müzikoloji Dergisi", "doi": None,
             "source": "orcid", "month_certain": False},
        ]},
        {"acad": {"name": "Songül Karahasanoğlu", "institution": "İstanbul Teknik Üniversitesi",
                  "orcid": "0000-0003-3861-1088", "field": "Müzik / Dans"}, "pubs": [
            {"title": "Digital Archives and Oral Tradition: Turkish Folk Music Documentation",
             "type": "article", "year": 2024, "month": 10,
             "journal": "Ethnomusicology Forum", "doi": "10.1080/17411912.2024.00312",
             "source": "orcid", "month_certain": True},
        ]},
        {"acad": {"name": "Bülent Kurtişoğlu", "institution": "Ardahan Üniversitesi",
                  "orcid": "0000-0001-9550-9712", "field": "Müzik / Dans"}, "pubs": []},
        {"acad": {"name": "Ulaş Özdemir", "institution": "İstanbul Üniversitesi",
                  "orcid": "0000-0003-4528-517X", "field": "Müzik / Dans"}, "pubs": [
            {"title": "Aşık Geleneğinde Değişim ve Süreklilik",
             "type": "book", "year": 2024, "month": 8,
             "journal": "İstanbul Üniversitesi Yayınları", "doi": None,
             "source": "orcid", "month_certain": True},
        ]},
    ]


def _parse_months(args) -> set | None:
    """--month / --months / --month-range → set[int] | None"""
    if getattr(args, "all_time", False):
        return None

    result = set()

    if args.month:
        result.add(args.month)

    if args.months:
        for part in args.months.split(","):
            part = part.strip()
            if part:
                try:
                    result.add(int(part))
                except ValueError:
                    raise SystemExit(f"Hatalı ay değeri: '{part}'")

    if args.month_range:
        parts = args.month_range.split("-")
        if len(parts) != 2:
            raise SystemExit("--month-range formatı: BAŞ-SON  (örn: 2-6)")
        try:
            start, end = int(parts[0]), int(parts[1])
        except ValueError:
            raise SystemExit("--month-range sayısal değer gerektirir")
        if not (1 <= start <= end <= 12):
            raise SystemExit("--month-range 1-12 arasında olmalı, başlangıç ≤ bitiş")
        result.update(range(start, end + 1))

    return result if result else None


def _default_filenames(year, months, all_time):
    if all_time:
        return "results_all.json", "rapor_all.html"
    if not months:
        return f"results_{year}.json", f"rapor_{year}.html"
    sorted_m = sorted(months)
    if len(sorted_m) == 1:
        return f"results_{year}_{sorted_m[0]:02d}.json", f"rapor_{year}_{sorted_m[0]:02d}.html"
    return (f"results_{year}_{sorted_m[0]:02d}-{sorted_m[-1]:02d}.json",
            f"rapor_{year}_{sorted_m[0]:02d}-{sorted_m[-1]:02d}.html")


def main():
    parser = argparse.ArgumentParser(description="ICTMD Türkiye Akademik Tarayıcı")
    parser.add_argument("--test",        action="store_true", help="3 akademisyen test taraması")
    parser.add_argument("--demo",        action="store_true", help="Örnek veri ile çıktı formatını göster")
    parser.add_argument("--year",        type=int, default=datetime.now().year)
    parser.add_argument("--month",       type=int, default=None,  help="Tek ay (1-12)")
    parser.add_argument("--months",      type=str, default=None,  help="Virgülle ayrılmış aylar: 10,11,12")
    parser.add_argument("--month-range", type=str, default=None,  dest="month_range",
                        help="Ay aralığı: 2-6")
    parser.add_argument("--all-time",    action="store_true", help="Ay filtresi olmadan tüm yayınlar")
    parser.add_argument("--out",         default=None, help="JSON çıktı dosyası (varsayılan otomatik)")
    parser.add_argument("--html",        default=None, help="HTML rapor dosyası (varsayılan otomatik)")
    args = parser.parse_args()

    all_time = args.all_time
    year     = None if all_time else args.year
    months   = _parse_months(args)  # set[int] | None

    # Demo modu
    if args.demo:
        all_results = demo_data()
        label  = "DEMO (örnek veri)"
        period = "2024 (örnek)"
        print(f"\n{B}{'═'*60}")
        print(f"  ICTMD Türkiye Akademik Yayın Tarayıcı")
        print(f"{'═'*60}{R}")
        print(f"  Mod    : {B}{YL}DEMO — gerçek API çağrısı yapılmıyor{R}")
        print(f"  Amaç   : Çıktı formatını görmek için örnek veri")
        print(f"{B}{'═'*60}{R}\n")
        for i, r in enumerate(all_results, 1):
            acad = r["acad"]
            print(f"{BL}[{i}/{len(all_results)}]{R} {B}{acad['name']}{R}  {DIM}{acad.get('institution','')}{R}")
            print_results(acad["name"], r["pubs"])
            print()
        demo_months = {9, 10, 11, 12}
        print_summary(all_results, 2024, demo_months, False)
        d_out, d_html = _default_filenames(2024, demo_months, False)
        save_json(all_results, 2024, demo_months, False, Path(args.out or d_out))
        save_html(all_results, 2024, demo_months, False, Path(args.html or d_html))
        print()
        print(f"{YL}NOT: Bu demo verileridir. Gerçek tarama için yerel makinenizde çalıştırın:{R}")
        print(f"  pip install requests")
        print(f"  python scan.py --test --year 2024 --months 10,11,12")
        return

    # Akademisyenleri yükle
    acad_file = Path(__file__).parent / "academicians.json"
    with open(acad_file, encoding="utf-8") as f:
        all_academs = json.load(f)

    # Test veya tam mod
    if args.test:
        # ORCID'i olan 3 farklı kurumdan akademisyen seç
        test_names = ["Arzu Öztürkmen", "Cenk Güray", "Songül Karahasanoğlu"]
        academs = [a for a in all_academs if a["name"] in test_names]
        label = "TEST (3 akademisyen)"
    else:
        academs = all_academs
        label = f"TAM ({len(all_academs)} akademisyen)"

    period = _months_label(months, year, all_time)

    print(f"\n{B}{'═'*60}")
    print(f"  ICTMD Türkiye Akademik Yayın Tarayıcı")
    print(f"{'═'*60}{R}")
    print(f"  Mod    : {B}{label}{R}")
    print(f"  Dönem  : {B}{period}{R}")
    print(f"  Kaynaklar: ORCID + Semantic Scholar")
    print(f"{B}{'═'*60}{R}\n")

    all_results = []
    for i, acad in enumerate(academs, 1):
        print(f"{BL}[{i}/{len(academs)}]{R} {B}{acad['name']}{R}  {DIM}{acad.get('institution','')}{R}")
        pubs = scan_one(acad, year=year, months=months, all_time=all_time, verbose=True)
        print_results(acad["name"], pubs)
        all_results.append({"acad": acad, "pubs": pubs})
        print()

    print_summary(all_results, year, months, all_time)

    if not args.test or any(r["pubs"] for r in all_results):
        def_out, def_html = _default_filenames(year, months, all_time)
        out_path  = Path(args.out  or def_out)
        html_path = Path(args.html or def_html)
        save_json(all_results, year, months, all_time, out_path)
        save_html(all_results, year, months, all_time, html_path)
    else:
        print(f"{YL}Test sonuçsuz kaldı — JSON/HTML kaydedilmedi.{R}")

    print()


if __name__ == "__main__":
    main()
