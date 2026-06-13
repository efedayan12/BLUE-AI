"""
BLUE_AI — Web Arama Modulu

DuckDuckGo HTML uzerinden arama yapar (API key gerektirmez).
BeautifulSoup ile sonuclari parse eder.
Opsiyonel: URL icerigini indir ve ozetle.
"""

import re
import requests
from typing import Optional
from urllib.parse import quote_plus

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def search_web(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo HTML araması yaparak sonuçları döndürür.
    
    Returns:
        list[dict]: Her sonuç {"title", "url", "snippet"} içerir.
    """
    if not BS4_AVAILABLE:
        return [{"title": "Hata", "url": "", "snippet": "beautifulsoup4 yuklu degil. pip install beautifulsoup4"}]

    try:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        for item in soup.select(".result"):
            title_el = item.select_one(".result__title a, .result__a")
            snippet_el = item.select_one(".result__snippet")

            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""

            # DuckDuckGo redirect URL'sinden gerçek URL'yi çıkar
            if "uddg=" in href:
                import urllib.parse
                parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                href = parsed.get("uddg", [href])[0]

            if title and href:
                results.append({
                    "title": title,
                    "url": href,
                    "snippet": snippet[:200],
                })

            if len(results) >= max_results:
                break

        return results

    except requests.Timeout:
        return [{"title": "Hata", "url": "", "snippet": "Arama zaman asimina ugradi."}]
    except requests.ConnectionError:
        return [{"title": "Hata", "url": "", "snippet": "Internet baglantisi yok."}]
    except Exception as e:
        return [{"title": "Hata", "url": "", "snippet": f"Arama hatasi: {str(e)}"}]


def fetch_url_text(url: str, max_chars: int = 3000) -> str:
    """URL icerigini indir ve temiz metin olarak dondur."""
    if not BS4_AVAILABLE:
        return "beautifulsoup4 yuklu degil."

    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Gereksiz elementleri kaldır
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        # Çoklu boşlukları temizle
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)

        return text[:max_chars]

    except Exception as e:
        return f"URL okunamadi: {str(e)}"


def summarize_search(query: str, max_results: int = 3) -> str:
    """Arama yap ve sonuclari ozetlenebilir formatta dondur."""
    results = search_web(query, max_results)
    if not results:
        return f"'{query}' icin sonuc bulunamadi."

    lines = [f"'{query}' arama sonuclari:\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}")
        if r["url"]:
            lines.append(f"   {r['url']}")
        if r["snippet"]:
            lines.append(f"   {r['snippet']}")
        lines.append("")

    return "\n".join(lines)
