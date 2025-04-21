# プロジェクトディレクトリ概要

API ドキュメントを参照する MCP サーバーの使用方法について

- `README.md`: このファイル。概要と使用方法を提供します。
- `crawl_all.py`: 特定のウェブページをクロールするスクリプト。（使用方法は後述）
- `document/` : クローリングした結果がこのディレクトリに入る
- `gemini_docs.py`: `gemini_docs.json`の内容を MCP サーバー経由で提供するメインプログラム。
- `anthropic_docs.py`: `anthropic_docs.json`の内容を MCP サーバー経由で提供するメインプログラム。
- `openapi_docs.py`: `openapi.yaml`の内容を MCP サーバー経由で提供するメインプログラム。

## 使用方法（参考 →https://modelcontextprotocol.io/quickstart/server#set-up-your-environment）

1. uv をインストール

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

1. 仮想環境を有効化する:

```bash
uv venv
source .venv/bin/activate
```

2. 依存関係をインストールする:

```bash
uv add "mcp[cli]" PyYAML
```

3. プログラムが正しく動作するか確認する(例：gemini_docs.py):

```bash
uv run gemini_docs.py
```

4. `claude_desktop_config.json`を以下の設定で更新する:

```json
{
  "mcpServers": {
    "gemini_docs_resource": {
      "command": "uv (←実行がうまくいかない場合にはuvまでの絶対パスに変更)",
      "args": [
        "--directory",
        "mcp_server ディレクトリへのパス",
        "run",
        "gemini_docs.py（←適宜ファイル名を変更、anthoropic_docs.py or openapi_docs.py）"
      ]
    }
  }
}
```

5. 変更を適用するために Claude を再起動する。

##　各 mcp サーバーについて

- gemini_docs.py : クローリングした結果が json ファイルのためその結果を利用している
- anthropic_docs.py : クローリングした結果が json ファイルのためその結果を利用している
- openapi_docs.py : openapi はドキュメントがクローリングできない。よって、github(https://github.com/openai/openai-openapi/tree/master)からファイルをダウンロードし、そのファイルを参照。そのため、yml形式のファイルを読み取れるようなプログラムになっている

##　クローリング
crawl_all.py ではプリセットを使用して、gemini と anthropic のドキュメントをクローリングできる

```bash
python crawl_all.py --preset gemini

python crawl_all.py --preset anthropic
```
