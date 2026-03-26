"""
DergiPark Scraper
https://dergipark.org.tr — Türkiye'nin ulusal akademik dergi platformu

Arama URL: https://dergipark.org.tr/tr/search?q={sorgu}&section=article
ORCID ara: https://dergipark.org.tr/tr/search?q={orcid}&section=article
"""
import time
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE      = "https://dergipark.org.tr"
SEARCH_URL = f"{BASE}/tr/search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Referer": "https://dergipark.org.tr/tr",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def _get(url, params=None, retries=2) -> requests.Response | None:
    for attempt in range(retries):
        try:
            r = SESSION.get(url, params=params, timeout=30)
            if r.status_code == 429:
                wait = 15 * (attempt + 1)
                print(f"    DergiPark rate-limit, {wait}s bekleniyor...")
                time.sleep(wait)
                continue
            return r
        except Exception as e:
            if attempt == retries - 1:
                print(f"    DergiPark bağlantı hatası: {e}")
    return None


def _parse_year(text: str) -> int | None:
    """Metin içindeki 4 haneli yılı bul."""
    m = re.search(r"\b(20\d{2}|19\d{2})\b", text or "")
    return int(m.group(1)) if m else None


def _parse_results(soup: BeautifulSoup) -> list[dict]:
    """
    DergiPark arama sonuçlarını parse et.
    Sayfa yapısı: her makale .search-result-item içinde.
    """
    items = []

    # ── Strateji 1: .search-result-item ──────────────────────────────────────
    cards = soup.select("div.search-result-item, li.search-result-item")

    # ── Strateji 2: article-search sayfasındaki kt-widget4 yapısı ────────────
    if not cards:
        cards = soup.select(".kt-widget4__item")

    # ── Strateji 3: genel makale listesi ─────────────────────────────────────
    if not cards:
        cards = soup.select("article, .article-item, [data-article-id]")

    for card in cards:
        # Başlık
        title_el = (
            card.select_one("h3 a, h4 a, .article-title a, .search-item-title a, a[href*='/pub/']")
        )
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        href  = title_el.get("href", "")
        url   = urljoin(BASE, href) if href else ""

        # Yazarlar
        authors_el = card.select_one(
            ".article-authors, .authors, [class*='author'], .search-item-authors"
        )
        authors = authors_el.get_text(strip=True) if authors_el else ""

        # Dergi adı
        journal_el = card.select_one(
            ".journal-name, .journal-title, [class*='journal'], a[href*='/pub/'][href*='/issue/']"
        )
        journal = ""
        if journal_el:
            journal = journal_el.get_text(strip=True)
        # Alternatif: üst breadcrumb veya küçük metin
        if not journal:
            small = card.select_one("small, .text-muted")
            if small:
                journal = small.get_text(strip=True)

        # Yıl — kart metninde veya meta alanda
        card_text = card.get_text(" ", strip=True)
        year = _parse_year(card_text)

        # DOI
        doi = None
        doi_el = card.select_one("a[href*='doi.org'], [class*='doi']")
        if doi_el:
            doi_href = doi_el.get("href", "") or doi_el.get_text(strip=True)
            doi_m = re.search(r"10\.\d{4,}/\S+", doi_href)
            if doi_m:
                doi = doi_m.group(0).rstrip(".,;)")

        items.append({
            "title":   title,
            "authors": authors,
            "journal": journal,
            "year":    year,
            "doi":     doi,
            "url":     url,
        })

    return items


def _search(query: str) -> list[dict]:
    """Tek sorgu ile DergiPark'ta ara, tüm sayfalardaki sonuçları getir."""
    all_items = []
    page = 1

    while True:
        params = {"q": query, "section": "article", "page": page}
        r = _get(SEARCH_URL, params=params)
        if not r or r.status_code != 200:
            break

        soup  = BeautifulSoup(r.text, "html.parser")
        items = _parse_results(soup)

        if not items:
            break

        all_items.extend(items)

        # Sonraki sayfa var mı?
        next_btn = soup.select_one("a[rel='next'], .pagination .next:not(.disabled)")
        if not next_btn:
            break
        if page >= 5:          # güvenlik sınırı
            break
        page += 1
        time.sleep(1)

    return all_items


def scan_dergipark(
    name: str,
    orcid: str = "",
    year: int = None,
    months: set = None,
    all_time: bool = False,
) -> list[dict]:
    """
    DergiPark'ta akademisyeni tara.
    Hem isimle hem ORCID ile arar, sonuçları birleştirir.

    Döndürülen yayınlar scan.py formatında: title, type, year, month,
    journal, doi, url, source, month_certain
    """
    raw = []
    seen_titles: set[str] = set()

    def _collect(query: str):
        results = _search(query)
        for item in results:
            t = (item["title"] or "").lower().strip()
            if t and t in seen_titles:
                continue
            if t:
                seen_titles.add(t)
            raw.append(item)

    # İsimle ara
    _collect(name)
    time.sleep(1.2)

    # ORCID ile de ara (ek yayınlar çıkabilir)
    if orcid:
        _collect(orcid)
        time.sleep(1.0)

    # Yıl ve ay filtresi uygula, çıktı formatını dönüştür
    pubs = []
    for item in raw:
        py = item.get("year")

        if not all_time:
            if year and py != year:
                continue
            # DergiPark genelde ay bilgisi vermez → months filtresi atlanır

        pubs.append({
            "title":         item["title"],
            "type":          "article",   # DergiPark yalnızca dergi makaleleri
            "year":          py,
            "month":         None,        # DergiPark ay bilgisi vermiyor
            "journal":       item.get("journal", ""),
            "doi":           item.get("doi"),
            "url":           item.get("url", ""),
            "authors":       item.get("authors", ""),
            "source":        "dergipark",
            "month_certain": False,
        })

    return pubs
