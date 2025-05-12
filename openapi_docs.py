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
    "openapi_docs"
)

# JSONデータ管理クラス
class DocsRepository:
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