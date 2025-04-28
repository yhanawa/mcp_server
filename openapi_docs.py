from typing import Any, Dict, List, Optional
import json
import os
import re
import yaml
from mcp.server.fastmcp import FastMCP
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("api_docs_server")

# MCPサーバー初期化
mcp = FastMCP(
    "openapi_docs",
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
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.docs_data = []
        self.load_data()
    
    def load_data(self) -> None:
        try:
            ext = os.path.splitext(self.file_path)[1].lower()
            with open(self.file_path, 'r', encoding='utf-8') as file:
                if ext == '.json':
                    data = json.load(file)
                elif ext in ['.yaml', '.yml']:
                    data = yaml.safe_load(file)
                elif ext == '.txt':
                    # txt形式の場合、1ドキュメント = 1行 として仮定
                    self.docs_data = [
                        {"title": f"Line {i+1}", "content": line.strip(), "url": f"txt://line/{i+1}"}
                        for i, line in enumerate(file.readlines())
                        if line.strip()
                    ]
                    print(f"Loaded {len(self.docs_data)} documents from {self.file_path}")
                    return
                else:
                    raise ValueError(f"Unsupported file extension: {ext}")
                
                # OpenAPI形式のドキュメントを処理
                if isinstance(data, dict) and ('openapi' in data or 'swagger' in data):
                    # 各パスをドキュメントとして処理
                    docs = []
                    api_title = data.get('info', {}).get('title', 'API Documentation')
                    api_version = data.get('info', {}).get('version', 'unknown')
                    
                    # APIの概要ドキュメント
                    docs.append({
                        "title": f"{api_title} v{api_version}",
                        "content": str(data.get('info', {}).get('description', 'No description')),
                        "url": "api://info"
                    })
                    
                    # 各パスをドキュメント化
                    for path, path_item in data.get('paths', {}).items():
                        for method, operation in path_item.items():
                            if method in ['get', 'post', 'put', 'delete', 'patch']:
                                operation_id = operation.get('operationId', f"{method.upper()} {path}")
                                summary = operation.get('summary', 'No summary')
                                description = operation.get('description', 'No description')
                                
                                content = f"""Method: {method.upper()}
Path: {path}
Summary: {summary}
Description: {description}
Parameters: {str(operation.get('parameters', []))}
Responses: {str(operation.get('responses', {}))}
"""
                                docs.append({
                                    "title": f"{operation_id}",
                                    "content": content,
                                    "url": f"api://{method}{path.replace('/', '_')}"
                                })
                    
                    self.docs_data = docs
                else:
                    # 通常のJSONまたはYAMLとして処理
                    if isinstance(data, list):
                        self.docs_data = data
                    else:
                        # オブジェクトを1つの文書として扱う
                        self.docs_data = [{
                            "title": "Document",
                            "content": json.dumps(data, indent=2) if ext == '.json' else yaml.dump(data),
                            "url": "api://document"
                        }]
                
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
docs_repository = DocsRepository("document/openapi.yaml")

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
@mcp.tool("getDocument_openapi")
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
@mcp.tool("getDocumentByIndex_openapi")
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
@mcp.tool("searchDocuments_openapi")
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