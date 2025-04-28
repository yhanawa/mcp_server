from typing import Any, Dict, List, Optional
import json
import os
import re
import yaml
from mcp.server.fastmcp import FastMCP
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("api_docs_server")

# MCPサーバー初期化 - ツール機能を有効化
mcp = FastMCP(
    "gemini_docs",
    server_info={
        "name": "API Docs Server",
        "version": "1.0.0",
        "description": "API documentation server with search capability"
    }
)

# JSONデータ管理クラス
class DocsRepository:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.docs_data = []
        self.last_modified_time = 0
        self.load_data()
    
    def load_data(self) -> bool:
        """データを読み込みます。更新があった場合はTrueを返します。"""
        try:
            # Check if file exists
            if not self.file_path.exists():
                logger.error(f"File not found: {self.file_path}")
                return False
                
            # Check if file was modified
            current_mtime = os.path.getmtime(self.file_path)
            if current_mtime <= self.last_modified_time and self.docs_data:
                logger.info(f"File {self.file_path} hasn't been modified, skipping reload")
                return False
                
            self.last_modified_time = current_mtime
            ext = self.file_path.suffix.lower()
            
            with open(self.file_path, 'r', encoding='utf-8') as file:
                if ext == '.json':
                    self.docs_data = json.load(file)
                elif ext in ['.yaml', '.yml']:
                    self.docs_data = yaml.safe_load(file)
                elif ext == '.txt':
                    # txt形式の場合、1ドキュメント = 1行 として仮定
                    self.docs_data = [
                        {"title": f"Line {i+1}", "content": line.strip(), "url": f"txt://line/{i+1}"}
                        for i, line in enumerate(file.readlines())
                        if line.strip()
                    ]
                else:
                    raise ValueError(f"Unsupported file extension: {ext}")
                    
                logger.info(f"Loaded {len(self.docs_data)} documents from {self.file_path}")
                return True
                
        except Exception as e:
            logger.error(f"Error loading data from {self.file_path}: {e}", exc_info=True)
            return False
    
    def search(self, query: str) -> List[Dict[str, Any]]:
        """キーワードでドキュメントを検索"""
        results = []
        query = query.lower()
        
        for doc in self.docs_data:
            title = doc.get("title", "")
            content = doc.get("content", "")
            url = doc.get("url", "")
            
            if query in title.lower() or query in content.lower():
                # Create better context-aware preview
                preview = self._generate_preview(content, query)
                
                results.append({
                    "title": title,
                    "url": url,
                    "preview": preview
                })
        
        return results
    
    def _generate_preview(self, content: str, query: str, max_length: int = 200) -> str:
        """検索キーワードの前後のコンテキストを含むプレビューを生成"""
        content_lower = content.lower()
        if query not in content_lower:
            return content[:max_length] + "..." if len(content) > max_length else content
            
        # Find position of query
        pos = content_lower.find(query)
        # Get context around the match
        start = max(0, pos - max_length // 2)
        end = min(len(content), pos + len(query) + max_length // 2)
        
        preview = content[start:end]
        if start > 0:
            preview = "..." + preview
        if end < len(content):
            preview = preview + "..."
            
        return preview
    
    def get_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """URLによるドキュメント取得"""
        for doc in self.docs_data:
            if doc.get("url") == url:
                return doc
        return None

# リポジトリの初期化
docs_repository = DocsRepository("document/gemini_docs.json")

# 静的リソース: ドキュメント一覧
@mcp.resource("docs://list")
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

# 静的リソース: データ再読み込み
@mcp.resource("docs://reload")
async def reload_data() -> dict:
    """データを再読み込みします"""
    was_updated = docs_repository.load_data()
    status_message = f"データを再読み込みしました。{len(docs_repository.docs_data)}件のドキュメントがロードされました。" if was_updated else "ファイルに変更がないため、再読み込みは行いませんでした。"
    
    return {
        "mimeType": "text/plain",
        "text": status_message
    }

# 静的リソース: サーバー状態
@mcp.resource("docs://status")
async def get_status() -> dict:
    """サーバーの状態を返します"""
    return {
        "mimeType": "application/json",
        "text": json.dumps({
            "status": "running",
            "documentCount": len(docs_repository.docs_data),
            "sourceFile": str(docs_repository.file_path),
            "lastModified": docs_repository.last_modified_time
        }, indent=2)
    }

# ツール: ドキュメント取得（URLパラメータを使用）
@mcp.tool("getDocument_gemini")
async def get_document_by_url(url: str) -> dict:
    """
    指定されたURLに基づいてドキュメントを取得します。
    
    Args:
        url: ドキュメントのURL
        
    Returns:
        ドキュメントの内容
    """
    if not docs_repository.docs_data:
        return {
            "success": False,
            "message": "ドキュメントデータが読み込まれていません。"
        }
    
    doc = docs_repository.get_by_url(url)
    if not doc:
        return {
            "success": False,
            "message": f"指定されたURL '{url}' のドキュメントは見つかりませんでした。"
        }
    
    # レスポンスの作成
    return {
        "success": True,
        "document": {
            "title": doc.get('title', 'タイトルなし'),
            "url": url,
            "content": doc.get('content', 'コンテンツなし')
        }
    }

# ツール: インデックスでドキュメント取得
@mcp.tool("getDocumentByIndex_gemini")
async def get_document_by_index(index: int) -> dict:
    """
    指定されたインデックス番号のドキュメントを取得します。
    
    Args:
        index: ドキュメントのインデックス（1から始まる）
        
    Returns:
        ドキュメントの内容
    """
    if not docs_repository.docs_data:
        return {
            "success": False,
            "message": "ドキュメントデータが読み込まれていません。"
        }
    
    # インデックスの検証
    idx = index - 1  # 1-based から 0-based へ変換
    if idx < 0 or idx >= len(docs_repository.docs_data):
        return {
            "success": False,
            "message": f"インデックス {index} は範囲外です。有効な範囲: 1-{len(docs_repository.docs_data)}"
        }
    
    doc = docs_repository.docs_data[idx]
    return {
        "success": True,
        "document": {
            "title": doc.get('title', 'タイトルなし'),
            "url": doc.get('url', 'URLなし'),
            "content": doc.get('content', 'コンテンツなし')
        }
    }

# ツール: ドキュメント検索
@mcp.tool("searchDocuments_gemini")
async def search_documents(query: str) -> dict:
    """
    指定されたクエリでドキュメントを検索します。
    
    Args:
        query: 検索クエリ
        
    Returns:
        検索結果のリスト
    """
    if not docs_repository.docs_data:
        return {
            "success": False,
            "message": "ドキュメントデータが読み込まれていません。"
        }
    
    results = docs_repository.search(query)
    
    if not results:
        return {
            "success": False,
            "message": f"検索クエリ '{query}' に一致するドキュメントは見つかりませんでした。"
        }
    
    return {
        "success": True,
        "query": query,
        "count": len(results),
        "results": results
    }

if __name__ == "__main__":
    # サーバーを実行
    logger.info("Starting API Docs Server with MCP tools")
    mcp.run(transport='stdio')