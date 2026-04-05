"""
Akademisyen sözlüğünden alan okuma yardımcıları.
Yeni format (isim, alan1, kurum_veya_profil_url) ve
eski format (name, field, institution) ile uyumludur.
"""


def name(acad: dict) -> str:
    return acad.get("isim") or acad.get("name", "")


def orcid(acad: dict) -> str:
    return acad.get("orcid") or ""


def institution(acad: dict) -> str:
    """Kurum adını döndür. URL ise boş string."""
    v = acad.get("kurum_veya_profil_url") or acad.get("institution", "") or ""
    return v if v and not v.startswith("http") else ""


def profile_url(acad: dict) -> str:
    """En uygun profil URL'ini döndür."""
    kp = acad.get("kurum_veya_profil_url") or ""
    if kp.startswith("http"):
        return kp.split("&")[0].strip()  # "url1 & url2" durumunda ilkini al
    return acad.get("academia_url") or acad.get("profileUrl", "") or ""


def field(acad: dict) -> str:
    a1 = acad.get("alan1") or acad.get("field", "") or ""
    a2 = acad.get("alan2", "") or ""
    if a1 and a2:
        return f"{a1} / {a2}"
    return a1 or a2
