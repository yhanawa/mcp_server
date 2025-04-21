from typing import Any, Dict, List, Optional
import json
import os
import re
import yaml
from mcp.server.fastmcp import FastMCP

# MCPサーバー初期化
mcp = FastMCP(
    "gemini_docs",
    server_info={
        "name": "API Docs Server",
        "version": "1.0.0"
    }
)

# JSONデータ管理クラス
class DocsRepository:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.docs_data = []
        self.load_data()
    
    # def load_data(self) -> None:
    #     """JSONファイルからドキュメントデータを読み込む"""
    #     try:
    #         with open(self.file_path, 'r', encoding='utf-8') as file:
    #             self.docs_data = json.load(file)
    #         print(f"Loaded {len(self.docs_data)} documents from {self.file_path}")
    #     except Exception as e:
    #         print(f"Error loading JSON data: {e}")
    #         self.docs_data = []
    def load_data(self) -> None:
        try:
            ext = os.path.splitext(self.file_path)[1].lower()
            with open(self.file_path, 'r', encoding='utf-8') as file:
                if ext == '.json':
                    self.docs_data = json.load(file)
                elif ext in ['.yaml', '.yml']:
                    self.docs_data = yaml.safe_load(file)
                elif ext == '.txt':
                    # txt形式の場合、1ドキュメント = 1行 として仮定（適宜変更可）
                    self.docs_data = [
                        {"title": f"Line {i+1}", "content": line.strip(), "url": f"txt://line/{i+1}"}
                        for i, line in enumerate(file.readlines())
                        if line.strip()
                    ]
                else:
                    raise ValueError(f"Unsupported file extension: {ext}")
                print(f"Loaded {len(self.docs_data)} documents from {self.file_path}")
        except Exception as e:
            print(f"Error loading data from {self.file_path}: {e}")
            self.docs_data = []

    
    def search(self, query: str) -> List[Dict[str, Any]]:
        """キーワードでドキュメントを検索"""
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

# リポジトリの初期化
docs_repository = DocsRepository("document/gemini_docs.json")

# ドキュメント一覧リソース
@mcp.resource("gemini-docs://all")
async def list_all_documents() -> dict:
    """すべてのドキュメント一覧を返します"""
    if not docs_repository.docs_data:
        return {
            "mimeType": "text/plain",
            "text": "ドキュメントデータが読み込まれていません。"
        }
    
    doc_list = []
    for i, doc in enumerate(docs_repository.docs_data, 1):
        doc_list.append(f"{i}. {doc.get('title', 'タイトルなし')} - {doc.get('url', 'URLなし')}")
    
    return {
        "mimeType": "text/plain",
        "text": "\n".join(doc_list)
    }

# 特定のドキュメントリソース
@mcp.resource("api-doc://{url}")
async def get_doc_by_url(url: str) -> dict:
    """指定URLのドキュメントを返します"""
    if not docs_repository.docs_data:
        return {
            "mimeType": "text/plain",
            "text": "ドキュメントデータが読み込まれていません。"
        }
    
    doc = docs_repository.get_by_url(url)
    if not doc:
        return {
            "mimeType": "text/plain",
            "text": "指定されたURLのドキュメントは見つかりませんでした。"
        }
    
    content = f"""
タイトル: {doc.get('title', 'タイトルなし')}
URL: {url}
---
{doc.get('content', 'コンテンツなし')}
"""
    
    return {
        "mimeType": "text/plain",
        "text": content
    }

# 検索結果リソース
@mcp.resource("api-search://{query}")
async def search_docs(query: str) -> dict:
    """キーワードでドキュメントを検索します"""
    if not docs_repository.docs_data:
        return {
            "mimeType": "text/plain",
            "text": "ドキュメントデータが読み込まれていません。"
        }
    
    results = docs_repository.search(query)
    
    if not results:
        return {
            "mimeType": "text/plain",
            "text": "該当する情報は見つかりませんでした。"
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
        "mimeType": "text/plain",
        "text": "\n---\n".join(formatted_results)
    }

# データ再読み込みリソース
@mcp.resource("api-docs://reload")
async def reload_data() -> dict:
    """データを再読み込みします"""
    docs_repository.load_data()
    return {
        "mimeType": "text/plain",
        "text": f"データを再読み込みしました。{len(docs_repository.docs_data)}件のドキュメントがロードされました。"
    }

if __name__ == "__main__":
    # サーバーを実行
    mcp.run(transport='stdio')