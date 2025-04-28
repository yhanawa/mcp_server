# プロジェクトディレクトリ概要

このプロジェクトは、MCP サーバーを使用して API ドキュメントを参照する方法を提供します。`reference` の機能を使用して実装されています。

## ディレクトリ構成

- `README.md`: このファイル。プロジェクトの概要と使用方法を記載しています。
- `crawl_all.py`: 特定のウェブページをクロールするスクリプト。（使用方法は後述）
- `document/`: クローリングした結果が保存されるディレクトリ。
- `gemini_docs.py`: `gemini_docs.json` の内容を MCP サーバー経由で提供するメインプログラム。
- `anthropic_docs.py`: `anthropic_docs.json` の内容を MCP サーバー経由で提供するメインプログラム。
- `openapi_docs.py`: `openapi.yaml` の内容を MCP サーバー経由で提供するメインプログラム。

## 使用方法

詳細なセットアップ手順については、[公式クイックスタートガイド](https://modelcontextprotocol.io/quickstart/server#set-up-your-environment)を参照してください。事前に本リポジトリをクローンしてください。

1. **uv のインストール**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. **仮想環境の有効化**

```bash
uv venv
source .venv/bin/activate
```

3. **依存関係のインストール**

```bash
uv add "mcp[cli]" PyYAML
```

4. **プログラムの動作確認**

例として、`gemini_docs.py` を実行します。

```bash
uv run gemini_docs.py
```

5. **`claude_desktop_config.json` の更新**

以下の設定を追加または更新してください。

```json
{
  "mcpServers": {
    "gemini_docs_resource": {
      "command": "uv",
      "args": [
        "--directory",
        "mcp_server ディレクトリへのパス",
        "run",
        "gemini_docs.py"
      ]
    }
  }
}
```

**注:** 実行がうまくいかない場合は、`uv` を絶対パスに変更してください。また、必要に応じて `gemini_docs.py` を `anthropic_docs.py` または `openapi_docs.py` に変更してください。

6. **Claude の再起動**

設定を反映させるために Claude を再起動してください。

## 各 MCP サーバーについて

- **gemini_docs.py**: クローリング結果が JSON ファイルとして保存され、その内容を利用します。
- **anthropic_docs.py**: クローリング結果が JSON ファイルとして保存され、その内容を利用します。
- **openapi_docs.py**: OpenAPI ドキュメントはクローリングできないため、[GitHub リポジトリ](https://github.com/openai/openai-openapi/tree/master)からダウンロードしたファイルを参照します。このプログラムは YAML 形式のファイルを読み取るように設計されています。

## クローリング

`crawl_all.py` を使用して、プリセットに基づき gemini と anthropic のドキュメントをクロールできます。

```bash
python crawl_all.py --preset gemini
python crawl_all.py --preset anthropic
```

また、プリセットを使用せず、任意の設定でクロールすることも可能です。

```bash
python crawl_all.py \
  --base-url "https://example.com" \
  --start-path "/docs" \
  --output_file "document/example_docs.json" \
  --selector "main" \
  --path-pattern "^/docs/.*" \
  --delay 0.5 \
  --max-pages 100
```

### 主なコマンドラインオプション

| オプション           | 説明                                                                             |
| -------------------- | -------------------------------------------------------------------------------- |
| `--preset`           | gemini または anthropic を指定すると、事前定義された設定でクロールを開始します。 |
| `--base-url`         | クロール対象サイトのベース URL（例: https://example.com）。                      |
| `--start-path`       | クロール開始パス（例: /docs）。                                                  |
| `--output_file`      | クロール結果の保存先ファイルパス（例: document/example_docs.json）。             |
| `--selector`         | ページ内でコンテンツを取得するための CSS セレクタ（デフォルト: main）。          |
| `--delay`            | 各リクエスト間の待機時間（秒）（デフォルト: 0.5 秒）。                           |
| `--use-selenium`     | 動的ページ対応のため Selenium を使用する場合に指定します。                       |
| `--wait-time`        | Selenium 使用時のページ読み込み待機時間（秒）（デフォルト: 5 秒）。              |
| `--additional-paths` | クロール対象に追加するパスのリスト。                                             |
| `--path-pattern`     | クロール対象とする URL パスの正規表現パターン。                                  |
| `--max-pages`        | 最大クロールページ数（例: 200 ページまで）。                                     |
| `--debug`            | デバッグモードを有効にして詳細なログを出力します。                               |
