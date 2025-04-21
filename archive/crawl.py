import requests
from bs4 import BeautifulSoup
import html2text
import json
import time
from urllib.parse import urljoin, urlparse

BASE_URL = "https://ai.google.dev"
START_PATH = "/gemini-api/docs/"
START_URL = urljoin(BASE_URL, START_PATH)

visited = set()
docs = []

# HTML → Markdown 変換器
converter = html2text.HTML2Text()
converter.ignore_links = False
converter.ignore_images = True
converter.body_width = 0

def is_valid_link(href):
    if not href:
        return False
    if href.startswith("#"):
        return False
    if "mailto:" in href or "javascript:" in href:
        return False
    full_url = urljoin(BASE_URL, href)
    parsed = urlparse(full_url)
    return parsed.netloc == "ai.google.dev" and parsed.path.startswith(START_PATH)

def crawl(url):
    if url in visited:
        return
    visited.add(url)

    try:
        print(f"📥 Fetching: {url}")
        res = requests.get(url)
        res.raise_for_status()
    except Exception as e:
        print(f"❌ Failed to fetch {url}: {e}")
        return

    soup = BeautifulSoup(res.text, "html.parser")
    content = soup.find("main")
    if not content:
        content = soup.body

    markdown = converter.handle(str(content))
    title = soup.title.string.strip() if soup.title else url

    docs.append({
        "url": url,
        "title": title,
        "content": markdown
    })

    # 新しいリンクを発見して再帰的にクロール
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if is_valid_link(href):
            full_url = urljoin(BASE_URL, href)
            crawl(full_url)
            time.sleep(0.1)  # 優しめに

# 開始
crawl(START_URL)

# 保存
with open("gemini_docs_all.json", "w", encoding="utf-8") as f:
    json.dump(docs, f, indent=2, ensure_ascii=False)

print(f"✅ 全 {len(docs)} ページを保存完了: gemini_docs_all.json")
