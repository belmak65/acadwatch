"""
ICTMD Türkiye Akademik Takip - Tarama Modülü
ORCID API ve Semantic Scholar API üzerinden yayın tarama
"""
import requests
import time
import re
from datetime import datetime

ORCID_BASE = "https://pub.orcid.org/v3.0"
SS_BASE = "https://api.semanticscholar.org/graph/v1"

ORCID_HEADERS = {"Accept": "application/vnd.orcid+json"}
SS_HEADERS = {"User-Agent": "ICTMD-AcadWatch/1.0 (academic-tracking)"}

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

ORCID_TYPE_MAP = {
    "journal-article": "article",
    "conference-paper": "conference",
    "conference-abstract": "conference",
    "book": "book",
    "book-chapter": "book-chapter",
    "edited-book": "book",
    "dissertation": "thesis",
    "preprint": "preprint",
    "working-paper": "preprint",
    "report": "other",
    "supervised-student-publication": "other",
    "other": "other",
    "magazine-article": "article",
    "newsletter-article": "article",
    "online-resource": "other",
    "data-set": "other",
    "research-technique": "other",
    "invention": "other",
    "standards-and-policy": "other",
    "translation": "other",
    "annotation": "other",
    "artistic-performance": "event",
    "lecture-speech": "event",
    "physical-object": "other",
    "software": "other",
}


def _safe_str(val):
    if isinstance(val, dict):
        return val.get("value", "")
    return str(val) if val else ""


def scan_orcid(orcid: str, year: int, month: int) -> list:
    """ORCID API üzerinden yayınları tara."""
    if not orcid or not orcid.strip():
        return []

    url = f"{ORCID_BASE}/{orcid}/works"
    try:
        resp = requests.get(url, headers=ORCID_HEADERS, timeout=30)
        if resp.status_code == 404:
            return []
        if resp.status_code != 200:
            print(f"  ORCID {orcid} hata: HTTP {resp.status_code}")
            return []

        data = resp.json()
        publications = []

        for group in data.get("group", []):
            for summary in group.get("work-summary", []):
                pub_date = summary.get("publication-date") or {}
                pub_year_val = _safe_str(pub_date.get("year"))
                pub_month_val = _safe_str(pub_date.get("month"))

                try:
                    pub_year = int(pub_year_val) if pub_year_val else None
                except ValueError:
                    pub_year = None

                try:
                    pub_month = int(pub_month_val) if pub_month_val else None
                except ValueError:
                    pub_month = None

                if pub_year != year:
                    continue
                if pub_month is not None and pub_month != month:
                    continue

                title_obj = summary.get("title") or {}
                title = _safe_str(title_obj.get("title")) or "Başlıksız"

                work_type = summary.get("type", "other")
                mapped_type = ORCID_TYPE_MAP.get(work_type, "other")

                journal = _safe_str(summary.get("journal-title"))

                doi = None
                ext_ids = summary.get("external-ids") or {}
                for eid in ext_ids.get("external-id", []):
                    if eid.get("external-id-type") == "doi":
                        doi = eid.get("external-id-value")
                        break

                url_val = ""
                url_obj = summary.get("url") or {}
                url_val = _safe_str(url_obj) if url_obj else ""

                publications.append({
                    "title": title,
                    "type": mapped_type,
                    "year": pub_year,
                    "month": pub_month,
                    "journal": journal,
                    "doi": doi,
                    "url": url_val,
                    "source": "orcid",
                    "put_code": summary.get("put-code"),
                    "month_certain": pub_month is not None,
                })

        return publications

    except Exception as e:
        print(f"  ORCID tarama hatası {orcid}: {e}")
        return []


def find_ss_author_id(name: str) -> str | None:
    """Semantic Scholar'da yazar ID'sini bul."""
    url = f"{SS_BASE}/author/search"
    params = {
        "query": name,
        "fields": "authorId,name,affiliations,paperCount",
        "limit": 5,
    }
    try:
        resp = requests.get(url, params=params, headers=SS_HEADERS, timeout=30)
        if resp.status_code == 429:
            print("  SS rate limit, 10s bekleniyor...")
            time.sleep(10)
            resp = requests.get(url, params=params, headers=SS_HEADERS, timeout=30)
        if resp.status_code != 200:
            return None
        data = resp.json()
        results = data.get("data", [])
        if not results:
            return None
        # Türkiye/müzik bağlamında en iyi eşleşmeyi seç
        # Basit yaklaşım: ilk sonuç
        return results[0].get("authorId")
    except Exception as e:
        print(f"  SS yazar arama hatası {name}: {e}")
        return None


def scan_semantic_scholar(name: str, year: int, month: int, existing_dois: set = None) -> list:
    """Semantic Scholar üzerinden yayınları tara."""
    if existing_dois is None:
        existing_dois = set()

    author_id = find_ss_author_id(name)
    if not author_id:
        return []

    time.sleep(1)  # Rate limit koruması

    url = f"{SS_BASE}/author/{author_id}/papers"
    params = {
        "fields": "title,year,publicationDate,publicationTypes,journal,externalIds,openAccessPdf,venue",
        "limit": 200,
    }
    try:
        resp = requests.get(url, params=params, headers=SS_HEADERS, timeout=30)
        if resp.status_code == 429:
            print("  SS rate limit, 10s bekleniyor...")
            time.sleep(10)
            resp = requests.get(url, params=params, headers=SS_HEADERS, timeout=30)
        if resp.status_code != 200:
            return []

        data = resp.json()
        publications = []

        for paper in data.get("data", []):
            paper_year = paper.get("year")
            if paper_year != year:
                continue

            pub_date_str = paper.get("publicationDate", "")
            pub_month = None
            if pub_date_str and len(pub_date_str) >= 7:
                try:
                    pub_month = int(pub_date_str[5:7])
                except ValueError:
                    pass

            if pub_month is not None and pub_month != month:
                continue
            # Tarih bilgisi yoksa atla (yanlış eşleşme riski yüksek)
            if pub_month is None:
                continue

            ext_ids = paper.get("externalIds") or {}
            doi = ext_ids.get("DOI")

            # DOI ile tekrar kontrolü
            if doi and doi in existing_dois:
                continue

            pub_types = paper.get("publicationTypes") or []
            mapped_type = _map_ss_type(pub_types)

            journal_obj = paper.get("journal") or {}
            journal = journal_obj.get("name", "") or paper.get("venue", "")

            pdf_url = ""
            pdf_obj = paper.get("openAccessPdf") or {}
            pdf_url = pdf_obj.get("url", "")

            publications.append({
                "title": paper.get("title", "Başlıksız"),
                "type": mapped_type,
                "year": paper_year,
                "month": pub_month,
                "journal": journal,
                "doi": doi,
                "url": pdf_url or (f"https://doi.org/{doi}" if doi else ""),
                "source": "semantic_scholar",
                "ss_paper_id": paper.get("paperId"),
                "month_certain": True,
            })

        return publications

    except Exception as e:
        print(f"  SS tarama hatası {name}: {e}")
        return []


def _map_ss_type(pub_types: list) -> str:
    if not pub_types:
        return "other"
    types_str = " ".join(pub_types).lower()
    if "journalarticle" in types_str or "journal" in types_str:
        return "article"
    if "conference" in types_str:
        return "conference"
    if "book" in types_str and "chapter" in types_str:
        return "book-chapter"
    if "book" in types_str:
        return "book"
    if "preprint" in types_str or "arxiv" in types_str:
        return "preprint"
    if "review" in types_str:
        return "article"
    return "other"


def scan_academician(academician: dict, year: int, month: int) -> dict:
    """Tek bir akademisyen için tüm kaynaklardan tara."""
    import acad_helpers as ah
    name = ah.name(academician)
    orcid = ah.orcid(academician)

    print(f"  Taranan: {name}")
    publications = []
    found_dois = set()

    # 1. ORCID taraması
    if orcid:
        orcid_pubs = scan_orcid(orcid, year, month)
        for pub in orcid_pubs:
            if pub.get("doi"):
                found_dois.add(pub["doi"])
        publications.extend(orcid_pubs)
        time.sleep(0.5)

    # 2. Semantic Scholar taraması (farklı yayınlar için)
    ss_pubs = scan_semantic_scholar(name, year, month, existing_dois=found_dois)
    publications.extend(ss_pubs)

    return {
        "academician": academician,
        "publications": publications,
        "scanned_at": datetime.now().isoformat(),
    }


def scan_all(
    academicians: list,
    year: int,
    month: int,
    progress_callback=None,
) -> list:
    """Tüm akademisyenleri tara."""
    all_results = []
    total = len(academicians)

    for i, acad in enumerate(academicians):
        if progress_callback:
            progress_callback(i, total, acad.get("isim") or acad.get("name", ""))
        result = scan_academician(acad, year, month)
        all_results.append(result)
        time.sleep(0.3)

    if progress_callback:
        progress_callback(total, total, "Tamamlandı")

    return all_results
