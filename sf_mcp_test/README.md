# Salesforce MCP Server（読み取り専用）

SalesforceのデータをSOQLクエリで読み取るためのMCP（Model Context Protocol）サーバーです。
データの安全性のため、読み取り専用機能のみを提供します。

## セットアップ手順

### 1. 環境変数の設定

`.env.example`を`.env`にコピーして、Salesforceの認証情報を設定してください：

```bash
cp .env.example .env
```

`.env`ファイルを編集：
```
SALESFORCE_USERNAME=your_username@example.com
SALESFORCE_PASSWORD=your_password
SALESFORCE_SECURITY_TOKEN=your_security_token
SALESFORCE_LOGIN_URL=https://login.salesforce.com
PORT=3000
```

### 2. Salesforce認証情報の取得方法

#### セキュリティトークンの取得：
1. Salesforceにログイン
2. 右上のプロフィールアイコン → 設定
3. 左メニュー「私の個人情報」→「私のセキュリティトークンのリセット」
4. 「セキュリティトークンのリセット」をクリック
5. メールで送信されたトークンを使用

### 3. 開発環境での実行

```bash
# 依存関係のインストール
npm install

# 開発モードで実行
npm run dev

# ビルドして実行
npm run build
npm start
```

## 利用可能なツール

- `query_salesforce`: SOQL クエリの実行（読み取り専用）

### 使用例

```
SELECT Id, Name, Email FROM Contact LIMIT 10
SELECT Id, Name, Industry FROM Account WHERE Industry = 'Technology'
SELECT Id, Subject, Status FROM Case WHERE Status = 'New'
```

## 無料デプロイ方法

### Railway でのデプロイ

1. [Railway](https://railway.app) にサインアップ
2. 「New Project」→「Deploy from GitHub repo」
3. このリポジトリを選択
4. 環境変数を設定：
   - `SALESFORCE_USERNAME`
   - `SALESFORCE_PASSWORD` 
   - `SALESFORCE_SECURITY_TOKEN`
   - `SALESFORCE_LOGIN_URL`

### Render でのデプロイ

1. [Render](https://render.com) にサインアップ
2. 「New」→「Web Service」
3. GitHubリポジトリを接続
4. 設定：
   - Build Command: `npm install && npm run build`
   - Start Command: `npm start`
5. 環境変数を追加

### Heroku でのデプロイ

1. [Heroku](https://heroku.com) にサインアップ（無料プランは制限あり）
2. Heroku CLI をインストール
3. デプロイ：

```bash
heroku create your-app-name
heroku config:set SALESFORCE_USERNAME=your_username
heroku config:set SALESFORCE_PASSWORD=your_password  
heroku config:set SALESFORCE_SECURITY_TOKEN=your_token
heroku config:set SALESFORCE_LOGIN_URL=https://login.salesforce.com
git push heroku main
```

## MCPクライアントでの使用

Claude Desktop などの MCP クライアントで使用する場合、設定ファイルに以下を追加：

```json
{
  "mcpServers": {
    "salesforce": {
      "command": "node",
      "args": ["/path/to/your/dist/index.js"]
    }
  }
}
```

## 注意事項

- このサーバーは**読み取り専用**です。データの作成・更新・削除はできません
- セキュリティトークンは信頼できるIPアドレスからのアクセス時は不要な場合があります
- 本番環境では適切なセキュリティ設定を行ってください
- APIコール制限にご注意ください
- 機密データを含むクエリを実行する際は十分注意してください