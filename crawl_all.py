import requests
from bs4 import BeautifulSoup
import html2text
import json
import time
import argparse
import re
import logging
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class APIDocCrawler:
    def __init__(self, base_url, start_path, output_file, selector="main", delay=0.5, 
                 use_selenium=False, wait_time=5, additional_paths=None, path_pattern=None,
                 max_pages=None, headers=None):
        """
        汎用APIドキュメントクローラー
        
        Args:
            base_url (str): ベースURL (例: "https://ai.google.dev")
            start_path (str): クロール開始パス (例: "/gemini-api/docs/")
            output_file (str): 出力JSONファイル名
            selector (str): コンテンツを含む主要HTML要素のセレクタ
            delay (float): リクエスト間の遅延（秒）
            use_selenium (bool): Seleniumを使用して動的コンテンツを取得するか
            wait_time (int): Seleniumでページロード待機する秒数
            additional_paths (list): クロールする追加パスのリスト
            path_pattern (str): 対象とするパスの正規表現パターン
            max_pages (int): クロールする最大ページ数（Noneの場合は無制限）
            headers (dict): リクエストヘッダー
        """
        self.base_url = base_url
        self.start_path = start_path
        self.start_url = urljoin(base_url, start_path)
        self.output_file = output_file
        self.content_selector = selector
        self.delay = delay
        self.use_selenium = use_selenium
        self.wait_time = wait_time
        self.additional_paths = additional_paths or []
        self.path_pattern = path_pattern
        self.max_pages = max_pages
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        self.visited = set()
        self.docs = []
        self.driver = None
        
        # パスパターンをコンパイル
        self.path_regex = re.compile(self.path_pattern) if self.path_pattern else None
        
        # HTML → Markdown 変換器
        self.converter = html2text.HTML2Text()
        self.converter.ignore_links = False
        self.converter.ignore_images = True
        self.converter.body_width = 0
        
        # ページカウンター
        self.page_count = 0

    def setup_selenium(self):
        """Seleniumドライバーの設定"""
        if not self.use_selenium:
            return
            
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        logger.info("Seleniumドライバーを初期化しました")

    def is_valid_link(self, href):
        """リンクが有効かつクロール対象かを判定"""
        if not href:
            return False
        if href.startswith("#"):
            return False
        if "mailto:" in href or "javascript:" in href:
            return False
            
        full_url = urljoin(self.base_url, href)
        parsed = urlparse(full_url)
        
        # 同じドメイン内かを確認
        if parsed.netloc != urlparse(self.base_url).netloc:
            return False
            
        # パスが開始パスで始まるか、または追加パスのいずれかで始まるかを確認
        starts_with_valid_path = parsed.path.startswith(self.start_path) or any(
            parsed.path.startswith(path) for path in self.additional_paths
        )
        
        # 正規表現パターンがある場合はそれにもマッチするか確認
        if self.path_regex:
            return starts_with_valid_path and self.path_regex.match(parsed.path)
        
        return starts_with_valid_path

    def get_page_content(self, url):
        """URLからページコンテンツを取得する（通常リクエストかSeleniumを使用）"""
        if self.use_selenium:
            try:
                logger.info(f"🌐 Seleniumでフェッチ中: {url}")
                self.driver.get(url)
                
                # 特定のセレクタが表示されるまで待機
                selectors = self.content_selector.split(',')
                for selector in selectors:
                    selector = selector.strip()
                    try:
                        WebDriverWait(self.driver, self.wait_time).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        logger.debug(f"セレクタ '{selector}' の表示を確認: {url}")
                        break
                    except Exception:
                        logger.debug(f"セレクタ '{selector}' が見つかりませんでした、次を試します")
                        continue
                
                # SPAの場合、JavaScriptの実行完了を待つために少し待機
                time.sleep(1)
                
                # スクロールして全コンテンツをロード（SPAの場合に有効）
                self.scroll_to_bottom()
                
                html = self.driver.page_source
                return html
            except Exception as e:
                logger.error(f"❌ Seleniumでの取得に失敗 {url}: {e}")
                # 通常のリクエストにフォールバック
                logger.info("通常のリクエストへフォールバックします")
                
        # 通常のリクエスト
        try:
            logger.info(f"📥 通常HTTPでフェッチ中: {url}")
            res = requests.get(url, headers=self.headers, timeout=30)
            res.raise_for_status()
            return res.text
        except Exception as e:
            logger.error(f"❌ Failed to fetch {url}: {e}")
            return None
            
    def scroll_to_bottom(self):
        """ページを下までスクロールしてコンテンツをロード（SPAサイト用）"""
        if not self.driver:
            return
            
        try:
            # 最初の高さを取得
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            
            for _ in range(3):  # 最大3回スクロール試行
                # 下までスクロール
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                # 読み込みを待つ
                time.sleep(2)
                
                # 新しい高さを計算
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                
                # 高さが変わらなければ読み込み完了
                if new_height == last_height:
                    break
                    
                last_height = new_height
                
            # ページトップに戻る
            self.driver.execute_script("window.scrollTo(0, 0);")
        except Exception as e:
            logger.warning(f"スクロール中にエラーが発生しました: {e}")
            
    def extract_links(self, soup, base_url):
        """HTMLからリンクを抽出"""
        links = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if self.is_valid_link(href):
                full_url = urljoin(base_url, href)
                # 重複していなければ追加
                if full_url not in links and full_url not in self.visited:
                    links.append(full_url)
                    
        logger.debug(f"抽出したリンク数: {len(links)}")
        return links

    def crawl(self, url):
        """指定URLとそのリンク先を再帰的にクロール"""
        if url in self.visited:
            return
            
        # 最大ページ数チェック
        if self.max_pages is not None and self.page_count >= self.max_pages:
            logger.info(f"最大ページ数 {self.max_pages} に達しました。クロールを停止します。")
            return
            
        self.visited.add(url)
        self.page_count += 1

        html_content = self.get_page_content(url)
        if not html_content:
            return

        soup = BeautifulSoup(html_content, "html.parser")
        
        # コンテンツ部分を取得（指定セレクタかbody）
        content = None
        for selector in self.content_selector.split(','):
            selector = selector.strip()
            found_content = soup.select_one(selector)
            if found_content:
                content = found_content
                logger.debug(f"セレクタ '{selector}' でコンテンツを見つけました: {url}")
                break
                
        if not content:
            content = soup.body
            logger.warning(f"指定セレクタ '{self.content_selector}' が見つかりません: {url}")

        # 空のコンテンツをスキップ
        if not content or len(str(content).strip()) < 100:
            logger.warning(f"コンテンツが空または短すぎます: {url}")
            return

        markdown = self.converter.handle(str(content))
        title = soup.title.string.strip() if soup.title else url

        # メタデータを取得
        description = ""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and "content" in meta_desc.attrs:
            description = meta_desc["content"]

        self.docs.append({
            "url": url,
            "title": title,
            "description": description,
            "content": markdown
        })
        
        logger.info(f"✓ 保存: {title} ({url}) - {self.page_count}ページ目")

        # 新しいリンクを発見して再帰的にクロール
        links = self.extract_links(soup, url)
        for link in links:
            if self.max_pages is not None and self.page_count >= self.max_pages:
                logger.info(f"最大ページ数 {self.max_pages} に達しました。クロールを停止します。")
                break
                
            time.sleep(self.delay)  # サーバーに優しく
            self.crawl(link)

    def run(self):
        """クロールを実行し結果を保存"""
        if self.use_selenium:
            self.setup_selenium()
            
        try:
            # メイン開始URL
            self.crawl(self.start_url)
            
            # 追加パスがある場合はそれもクロール
            for path in self.additional_paths:
                additional_url = urljoin(self.base_url, path)
                if additional_url not in self.visited:
                    self.crawl(additional_url)
                    
            # 結果を保存
            with open(self.output_file, "w", encoding="utf-8") as f:
                json.dump(self.docs, f, indent=2, ensure_ascii=False)

            logger.info(f"✅ 全 {len(self.docs)} ページを保存完了: {self.output_file}")
            return len(self.docs)
        finally:
            # Seleniumを使用した場合はクリーンアップ
            if self.driver:
                self.driver.quit()
                logger.info("Seleniumドライバーを終了しました")



def anthropic_crawl():
    """Anthropic APIドキュメントのクロール用設定"""
    return {
        "base_url": "https://docs.anthropic.com",
        "start_path": "/en/api/getting-started",
        "additional_paths": [
            "/en/api/messages",
            "/en/api/rate-limits",
            "/en/api/system-prompts",
            "/en/api/human-in-the-loop"
        ],
        "output_file": "document/anthropic_docs.json",
        "selector": ".docs-content, main, article, .content-wrapper, .content",
        "use_selenium": True,
        "path_pattern": r"^/en/api/.*",
        "max_pages": 200,
        "wait_time": 8,
        "delay": 1.0
    }

def gemini_crawl():
    """Google Gemini APIドキュメントのクロール用設定"""
    return {
        "base_url": "https://ai.google.dev",
        "start_path": "/gemini-api/docs/",
        "additional_paths": [
            "/gemini-api/docs/models",
            "/gemini-api/docs/quickstart"
        ],
        "output_file": "document/gemini_docs.json",
        "selector": "main, article, .devsite-article-body, .devsite-article-inner",
        "use_selenium": False,
        "path_pattern": r"^/gemini-api/docs/.*",
        "max_pages": 200,
        "delay": 0.5
    }

# プリセット設定
PRESETS = {
    "anthropic": anthropic_crawl,
    "gemini": gemini_crawl
}

if __name__ == "__main__":
    # Anthropic APIドキュメント用の設定を更新
    anthropic_config = anthropic_crawl()
    anthropic_config.update({
        "selector": ".docs-content, main, article, .content-wrapper",
        "use_selenium": True,
        "delay": 1.0
    })
    
    # コマンドライン引数の解析
    parser = argparse.ArgumentParser(description="API Documentation Crawler")
    
    # プリセット設定か詳細設定かのグループ
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preset", choices=PRESETS.keys(), help="事前定義された設定を使用 (anthropic, gemini)")
    group.add_argument("--base-url", help="ベースURL (例: https://ai.google.dev)")
    
    # その他の引数
    parser.add_argument("--start-path", help="開始パス (例: /gemini-api/docs/)")
    parser.add_argument("--output_file", help="出力JSONファイル名")
    parser.add_argument("--selector", default="main", help="コンテンツを含む要素のCSSセレクタ (デフォルト: main)")
    parser.add_argument("--delay", type=float, default=0.5, help="リクエスト間の遅延（秒）(デフォルト: 0.5)")
    parser.add_argument("--use-selenium", action="store_true", help="動的コンテンツにSeleniumを使用する")
    parser.add_argument("--wait-time", type=int, default=5, help="Seleniumの待機時間（秒）(デフォルト: 5)")
    parser.add_argument("--additional-paths", nargs="+", help="クロール対象の追加パス")
    parser.add_argument("--path-pattern", help="クロール対象のパス正規表現パターン")
    parser.add_argument("--debug", action="store_true", help="デバッグモードを有効化")
    parser.add_argument("--max-pages", type=int, default=None, help="クロールする最大ページ数")
    
    args = parser.parse_args()
    
    # デバッグモードの設定
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 設定を決定
    if args.preset:
        config = PRESETS[args.preset]()
    else:
        if not args.base_url or not args.start_path or not args.output_file:
            parser.error("--preset を使用しない場合は --base-url, --start-path, --output が必須です")
            
        config = {
            "base_url": args.base_url,
            "start_path": args.start_path,
            "output_file": args.output_file,
            "selector": args.selector,
            "delay": args.delay,
            "use_selenium": args.use_selenium,
            "wait_time": args.wait_time,
            "additional_paths": args.additional_paths,
            "path_pattern": args.path_pattern,
            "max_pages": args.max_pages
        }
    
    # コマンドライン引数で上書き
    for key, value in vars(args).items():
        if key not in ["preset", "debug"] and value is not None:
            snake_key = key.replace("-", "_")
            config[snake_key] = value
    
    logger.info(f"設定: {config}")
    
    # クローラーの作成と実行
    crawler = APIDocCrawler(**config)
    crawler.run()