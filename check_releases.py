"""
新刊トラッカー - 月次自動チェックスクリプト
毎月1日にGitHub Actionsから実行されます。
books.json を読み込み、Claude APIで新刊情報を検索して
GitHubのIssueとして投稿します。
"""
import json
import os
import urllib.request
from datetime import datetime

import anthropic

# ── books.json 読み込み ──────────────────────────────
with open("books.json", "r", encoding="utf-8") as f:
    data = json.load(f)

works = data.get("works", [])
if not works:
    print("作品が登録されていません。Issueの作成をスキップします。")
    exit(0)

print(f"登録作品数: {len(works)}")

# ── プロンプト生成 ───────────────────────────────────
TYPE_LABEL = {"manga": "漫画", "novel": "小説", "ln": "ライトノベル", "other": "その他"}

work_lines = []
for w in works:
    line = f"・{w['title']}"
    if w.get("pub"):
        line += f"（{w['pub']}）"
    if w.get("type"):
        line += f"［{TYPE_LABEL.get(w['type'], w['type'])}］"
    if w.get("note"):
        line += f" ※{w['note']}"
    work_lines.append(line)

today = datetime.now().strftime("%Y年%m月%d日")
this_month = datetime.now().strftime("%Y年%m月")
works_str = "\n".join(work_lines)

prompt = f"""今日は{today}です。
以下の作品について、{this_month}〜翌月に発売予定の新刊情報をWeb検索で調べてください。

{works_str}

## 出力形式
各作品について以下の情報をまとめてください：
- **作品名**
  - 最新刊: ○巻（発売日: ○月○日、出版社）
  - 次巻予定: ○巻（発売日: ○月○日）※未定の場合は「未定」
  - 電子版: 同日発売 or 別日（違いがあれば記載）

情報がない・発売なしの場合は「今月・来月の発売予定なし」と記載してください。
"""

# ── Claude API 呼び出し ──────────────────────────────
print("Claude APIに問い合わせ中...")
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=4096,
    system="あなたは漫画・小説・ライトノベルの新刊情報に詳しいアシスタントです。Web検索を使って最新の発売日情報を調べてください。",
    tools=[
        {
            "type": "web_search_20250305",
            "name": "web_search",
        }
    ],
    messages=[{"role": "user", "content": prompt}],
)

# レスポンスからテキストを抽出
result_parts = []
for block in response.content:
    if hasattr(block, "text") and block.text:
        result_parts.append(block.text)

result = "\n\n".join(result_parts)
print("Claude APIの応答を取得しました。")

# ── GitHub Issue 作成 ─────────────────────────────────
repo       = os.environ["GITHUB_REPOSITORY"]
token      = os.environ["GITHUB_TOKEN"]
issue_month = datetime.now().strftime("%Y年%m月")

issue_title = f"📚 新刊情報チェック {issue_month}"
issue_body  = f"""## {issue_month} 新刊情報

{result}

---
*🤖 自動生成: {today}*
*登録作品数: {len(works)} 作品*
"""

payload = json.dumps({"title": issue_title, "body": issue_body}).encode("utf-8")
req = urllib.request.Request(
    f"https://api.github.com/repos/{repo}/issues",
    data=payload,
    headers={
        "Authorization": f"Bearer {token}",
        "Accept":        "application/vnd.github.v3+json",
        "Content-Type":  "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
    },
    method="POST",
)

with urllib.request.urlopen(req) as resp:
    result_data = json.loads(resp.read().decode())
    print(f"✅ Issue作成完了: {result_data.get('html_url')}")
