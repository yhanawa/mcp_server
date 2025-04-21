from typing import Any, Dict, List, Optional
import json
import os
import re
from mcp.server.fastmcp import FastMCP

# リポジトリクラスの実装
class DocsRepository:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.docs_data = []
        self.load_data()
    
    def load_data(self) -> None:
        """JSONファイルからドキュメントデータを読み込む"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as file:
                self.docs_data = json.load(file)
            print(f"Loaded {len(self.docs_data)} documents from {self.file_path}")
        except Exception as e:
            print(f"Error loading JSON data: {e}")
            self.docs_data = []
    
    def search(self, query: str) -> List[Dict[str, Any]]:
        """キーワードでドキュメントを検索"""
        if not self.docs_data:
            return []
        
        results = []
        query = query.lower()
        
        for doc in self.docs_data:
            title = doc.get("title", "")
            content = doc.get("content", "")
            url = doc.get("url", "")
            
            if query in title.lower() or query in content.lower():
                results.append({
                    "title": title,
                    "url": url,
                    "preview": content[:200] + "..." if len(content) > 200 else content
                })
        
        return results
    
    def get_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """URLによるドキュメント取得"""
        for doc in self.docs_data:
            if doc.get("url") == url:
                return doc
        return None
    
    def get_all_docs(self) -> List[Dict[str, Any]]:
        """全ドキュメント取得"""
        return self.docs_data
    
    def extract_model_info(self) -> Dict[str, str]:
        """ドキュメントからモデル情報を抽出"""
        models_info = {}
        model_pattern = r"([\d\.]+\s+\w+)(?:\s+\w+)?\s*\n\s*\n([^\[]+)"
        
        for doc in self.docs_data:
            content = doc.get("content", "")
            matches = re.findall(model_pattern, content)
            for model_name_part, description in matches:
                model_key = "gemini-" + model_name_part.lower().replace(" ", "-")
                models_info[model_key] = description.strip()
        
        return models_info
    
    def get_code_examples(self) -> Dict[str, List[str]]:
        """ドキュメントからコード例を抽出"""
        code_block_pattern = r"###\s*(\w+)\s+```(\w+)\s+(.*?)```"
        examples = {}

        for doc in self.docs_data:
            content = doc.get("content", "")
            matches = re.findall(code_block_pattern, content, re.DOTALL)
            for heading_lang, code_lang, code in matches:
                lang_key = heading_lang.lower()
                if lang_key not in examples:
                    examples[lang_key] = []
                examples[lang_key].append(code.strip())

        return examples

# MCPサーバー初期化
mcp = FastMCP(
    "gemini_docs",
    server_info={
        "name": "Gemini Docs Server",
        "version": "1.0.0"
    }
)

# 環境変数からJSONファイルパスを取得
json_file_path = os.environ.get("GEMINI_DOCS_PATH", "/Users/hanawayuki/Documents/funrepeat/mcp/gemini_docs_all.json")
docs_repository = DocsRepository(json_file_path)

# ツール実装
@mcp.tool()
async def search_docs(query: str) -> dict:
    """Gemini APIドキュメント内のキーワードを検索します。

    Args:
        query: 検索キーワード
    """
    if not query or len(query.strip()) == 0:
        return {
            "isError": True,
            "content": [{"type": "text", "text": "検索キーワードを入力してください。"}]
        }
    
    if not docs_repository.docs_data:
        return {
            "isError": True,
            "content": [{"type": "text", "text": "ドキュメントデータが読み込まれていません。"}]
        }
    
    results = docs_repository.search(query)
    
    if not results:
        return {
            "content": [{"type": "text", "text": "該当する情報は見つかりませんでした。"}]
        }
    
    # 結果をフォーマット
    formatted_results = []
    for i, result in enumerate(results, 1):
        formatted_results.append(f"""
結果 {i}:
タイトル: {result['title']}
URL: {result['url']}
プレビュー: {result['preview']}
""")
    
    return {
        "content": [{"type": "text", "text": "\n---\n".join(formatted_results)}]
    }

@mcp.tool()
async def get_doc_by_url(url: str) -> dict:
    """指定したURLのドキュメント全文を取得します。

    Args:
        url: ドキュメントのURL
    """
    if not url or len(url.strip()) == 0:
        return {
            "isError": True,
            "content": [{"type": "text", "text": "URLを入力してください。"}]
        }
    
    if not docs_repository.docs_data:
        return {
            "isError": True,
            "content": [{"type": "text", "text": "ドキュメントデータが読み込まれていません。"}]
        }
    
    doc = docs_repository.get_by_url(url)
    
    if not doc:
        return {
            "isError": True,
            "content": [{"type": "text", "text": "指定されたURLのドキュメントは見つかりませんでした。"}]
        }
    
    content = f"""
タイトル: {doc.get('title', 'タイトルなし')}
URL: {url}
---
{doc.get('content', 'コンテンツなし')}
"""
    
    return {
        "content": [{"type": "text", "text": content}]
    }

@mcp.tool()
async def list_all_docs() -> dict:
    """利用可能なすべてのドキュメントの一覧を表示します。"""
    # 最新データを読み込み直す
    docs_repository.load_data()
    
    if not docs_repository.docs_data:
        return {
            "isError": True,
            "content": [{"type": "text", "text": "ドキュメントデータが読み込まれていません。"}]
        }
    
    doc_list = []
    for i, doc in enumerate(docs_repository.docs_data, 1):
        doc_list.append(f"{i}. {doc.get('title', 'タイトルなし')} - {doc.get('url', 'URLなし')}")
    
    return {
        "content": [{"type": "text", "text": "\n".join(doc_list)}]
    }

@mcp.tool()
async def get_gemini_model_info(model_name: Optional[str] = None) -> dict:
    """Geminiモデルの情報を取得します。

    Args:
        model_name: モデル名（例: gemini-2.0-flash）。省略すると全モデルの情報を返します。
    """
    if not docs_repository.docs_data:
        return {
            "isError": True,
            "content": [{"type": "text", "text": "ドキュメントデータが読み込まれていません。"}]
        }
    
    models_info = docs_repository.extract_model_info()
    
    if not models_info:
        return {
            "isError": True,
            "content": [{"type": "text", "text": "ドキュメント内にモデル情報が見つかりませんでした。"}]
        }
    
    if model_name:
        # 特定のモデル情報を返す
        for model_key in models_info:
            if model_name.lower() in model_key:
                return {
                    "content": [{"type": "text", "text": f"モデル: {model_key}\n説明: {models_info[model_key]}"}]
                }
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"指定されたモデル {model_name} の情報はドキュメント内に見つかりませんでした。"}]
        }
    
    # すべてのモデル情報を返す
    result = []
    for model, description in models_info.items():
        result.append(f"モデル: {model}\n説明: {description}")
    
    return {
        "content": [{"type": "text", "text": "\n---\n".join(result)}]
    }

@mcp.tool()
async def get_api_usage_examples(language: str = "python") -> dict:
    """指定した言語でのGemini API使用例を取得します。"""
    if not docs_repository.docs_data:
        return {
            "isError": True,
            "content": [{"type": "text", "text": "ドキュメントデータが読み込まれていません。"}]
        }
    
    examples = docs_repository.get_code_examples()
    language = language.lower()
    
    if language not in examples or not examples[language]:
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"指定された言語 {language} の使用例はドキュメント内に見つかりませんでした。"}]
        }
    
    return {
        "content": [{"type": "text", "text": f"{language.capitalize()}での使用例:\n```{language}\n{examples[language][0]}\n```"}]
    }

# リソース実装（修正版）
@mcp.resource("gemini-docs://info")
async def get_docs_info() -> str:
    """Geminiドキュメントの基本情報を返します"""
    return f"Gemini APIドキュメント ({len(docs_repository.docs_data)}件)"

@mcp.resource("gemini-doc://{url}")
async def get_doc_resource(url: str) -> Optional[dict]:
    """特定URLのドキュメントをリソースとして提供"""
    if not docs_repository.docs_data:
        return None
    
    doc = docs_repository.get_by_url(url)
    if not doc:
        return None
    
    return {
        "mimeType": "text/plain",
        "text": f"タイトル: {doc.get('title', 'タイトルなし')}\nURL: {doc.get('url', '')}\n---\n{doc.get('content', 'コンテンツなし')}"
    }

# プロンプト実装
@mcp.prompt("api_quickstart")
async def api_quickstart_prompt(language: str = "python") -> dict:
    """Gemini APIのクイックスタートプロンプト"""
    if not docs_repository.docs_data:
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": {
                        "type": "text",
                        "text": "ドキュメントデータが読み込まれていないため、情報を提供できません。"
                    }
                }
            ]
        }
    
    examples = docs_repository.get_code_examples()
    language = language.lower()
    
    example_code = ""
    if language in examples and examples[language]:
        example_code = f"```{language}\n{examples[language][0]}\n```"
    
    return {
        "messages": [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": f"Gemini APIについての基本的な使い方を教えてください。特に{language}での実装例が知りたいです。"
                }
            },
            {
                "role": "assistant",
                "content": {
                    "type": "text",
                    "text": f"Gemini APIの基本的な使い方を説明します。以下は{language}での実装例です：\n\n{example_code}"
                }
            }
        ]
    }

if __name__ == "__main__":
    # サーバーを実行
    mcp.run(transport='stdio')