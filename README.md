# Hermes Google Workspace Skill

让 Hermes Agent 原生接入 Google Workspace（Gmail、Calendar、Tasks、Sheets、Docs、Drive），通过 OAuth2 无缝认证，支持完整的增删改查操作。

**适用于**：需要 AI 助手直接操作 Google 文档、日历、邮件、任务表的用户

---

## 功能一览

| 服务 | 支持操作 |
|------|---------|
| **Gmail** | 搜索、读取、发送、回复、管理标签 |
| **Google Calendar** | 列出事件、创建事件、删除事件 |
| **Google Tasks** | 列出任务列表、列出任务、创建任务（两步：insert + patch） |
| **Google Sheets** | 读取范围、写入、追加行 |
| **Google Docs** | 读取文档内容（纯文本） |
| **Google Drive** | 搜索文件、按 MIME 类型筛选 |
| **Google Contacts** | 读取联系人 |

---

## 快速安装

### 前置要求

- Hermes Agent 已安装（任何平台：CLI / Telegram / Slack / Discord）
- Python 3.8+
- Google 账号

### Step 1：安装 Skill

```bash
hermes skills install google-workspace
```

或者手动安装：

```bash
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
SKILL_DIR="$HERMES_HOME/skills/productivity/google-workspace"
mkdir -p "$SKILL_DIR/scripts" "$SKILL_DIR/references"

# 复制脚本
cp scripts/setup.py "$SKILL_DIR/scripts/"
cp scripts/google_api.py "$SKILL_DIR/scripts/"
cp references/gmail-search-syntax.md "$SKILL_DIR/references/"
```

### Step 2：配置 shorthand（每次会话）

```bash
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
GWORKSPACE_SKILL_DIR="$HERMES_HOME/skills/productivity/google-workspace"
PYTHON_BIN="${HERMES_PYTHON:-python3}"
if [ -x "$HERMES_HOME/hermes-agent/venv/bin/python" ]; then
  PYTHON_BIN="$HERMES_HOME/hermes-agent/venv/bin/python"
fi
GSETUP="$PYTHON_BIN $GWORKSPACE_SKILL_DIR/scripts/setup.py"
GAPI="$PYTHON_BIN $GWORKSPACE_SKILL_DIR/scripts/google_api.py"
```

### Step 3：检查是否已认证

```bash
$GSETUP --check
# 输出 AUTHENTICATED → 跳过 Step 4，直接看使用
```

---

## OAuth 配置（Step 4）

如果你有现成的 OAuth 客户端 JSON 文件，跳过 Step A 直接到 Step B。

### Step A：创建 Google Cloud OAuth 客户端（一次性，~5 分钟）

1. 打开 [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. 创建项目（或使用已有项目）
3. 点击 **Enable APIs**，启用你需要的 API：
   - Gmail API
   - Google Calendar API
   - Google Tasks API
   - Google Sheets API
   - Google Docs API
   - Google Drive API
   - Google People API（通讯录）
4. 进入 **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
5. Application type 选 **Desktop app** → 创建
6. 点击 **Download JSON**，把文件路径告诉 Hermes

### Step B：告知 Hermes 客户端文件路径

```bash
$GSETUP --client-secret /path/to/client_secret.json
```

### Step C：确认 SCOPES（在两个文件中必须完全一致）

编辑这两个文件，保留你需要的 SCOPES：

**`scripts/setup.py`**（约第 43 行）：
```python
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.readonly",
]
```

**`scripts/google_api.py`**（约第 41 行）：
```python
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
```

> ⚠️ **两个文件的 SCOPES 必须完全一致**，否则 OAuth exchange 会失败（"Scope has changed"）。

### Step D：获取授权 URL

```bash
$GSETUP --auth-url
```

把输出的 URL **发送给用户**，让用户在浏览器中打开并授权。

### Step E：用户授权后，交换 Token

用户授权后，浏览器会跳转到 `http://localhost:1/?state=...&code=...`。
让用户**复制浏览器地址栏的完整 URL** 粘贴给 Hermes：

```bash
$GSETUP --auth-code "用户粘贴的URL"
```

> ⚠️ 每个 auth code 只能使用一次。如果中途修改了 SCOPES，必须重新执行 Step D 获取新 URL。

### Step F：验证

```bash
$GSETUP --check
# 输出 AUTHENTICATED → 安装完成
```

---

## 使用示例

> **注意**：发送邮件、创建/删除事件等写入操作，Agent 会先展示草稿内容并征得用户确认后再执行。

### Gmail

```bash
# 搜索邮件
$GAPI gmail search "is:unread newer_than:1d" --max 10

# 读取邮件正文
$GAPI gmail get MESSAGE_ID

# 发送邮件（发送前会确认草稿）
$GAPI gmail send --to user@example.com --subject "Hello" --body "Message" --html

# 回复邮件（自动 threading）
$GAPI gmail reply MESSAGE_ID --body "Thanks for your reply!"

# 管理标签
$GAPI gmail labels
$GAPI gmail modify MESSAGE_ID --add-labels STARRED --remove-labels UNREAD
```

> Gmail 搜索语法参考：`skill_view("google-workspace", file_path="references/gmail-search-syntax.md")`

### Google Calendar

```bash
# 列出未来7天事件
$GAPI calendar list

# 列出指定时间段
$GAPI calendar list --start 2026-04-20T00:00:00Z --end 2026-04-25T23:59:59Z

# 创建事件（时间必须带时区）
$GAPI calendar create \
  --summary "Team Standup" \
  --start 2026-04-20T09:00:00-05:00 \
  --end 2026-04-20T09:30:00-05:00 \
  --location "Zoom" \
  --attendees "alice@co.com,bob@co.com"

# 删除事件
$GAPI calendar delete EVENT_ID
```

### Google Tasks（需要直接 Python 调用）

Tasks API 通过 `google_api.py` 暴露为子命令方式不可用（CLI 只支持 Gmail/Calendar/Drive/Contacts/Sheets/Docs），但可以通过 Python 脚本直接调用：

```python
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta, timezone

hermes_home = "/root/.hermes"
TOKEN_PATH = f"{hermes_home}/google_token.json"
SCOPES = [
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
tasks = build("tasks", "v1", credentials=creds)

# 列出任务列表
tasklists = tasks.tasklists().list().execute().get("items", [])
for tl in tasklists:
    print(f"List: {tl['title']} — id: {tl['id']}")

# 列出任务（在指定列表中）
TASKLIST_ID = "MDM0NzU4Njk2MzQ1NTg1ODI4MDk6MDow"
tasks_in_list = tasks.tasks().list(tasklist=TASKLIST_ID).execute().get("items", [])
for t in tasks_in_list:
    print(f"  - {t.get('title')} (due: {t.get('due', 'none')})")

# 创建任务（注意：due date 需要分两步设置）
task = tasks.tasks().insert(
    tasklist=TASKLIST_ID,
    body={"title": "Review Q4 Report", "notes": "Check numbers before sending"}
).execute()
# 再 patch 添加 due date
tasks.tasks().patch(
    tasklist=TASKLIST_ID, task=task["id"],
    body={"due": (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")}
).execute()
```

### Google Sheets

```bash
# 读取范围数据
$GAPI sheets get "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms" "Sheet1!A1:D10"

# 写入数据
$GAPI sheets update "SHEET_ID" "Sheet1!A1:B2" --values '[["Name","Score"],["Alice","95"]]'

# 追加行
$GAPI sheets append "SHEET_ID" "Sheet1!A:C" --values '[["Bob","92"]]'
```

### Google Docs

```bash
# 读取文档（返回纯文本）
$GAPI docs get DOC_ID
```

### Google Drive

```bash
# 全文搜索
$GAPI drive search "quarterly report" --max 10

# 按文件类型搜索
$GAPI drive search "mimeType='application/vnd.google-apps.spreadsheet'" --raw-query --max 5
```

---

## 扩展现有认证（添加新 Scope）

如果已经认证了部分服务，想添加新的 Scope（如从 Calendar 扩展到 Gmail）：

1. 在 `scripts/setup.py` 和 `scripts/google_api.py` 的 SCOPES 中添加新 scope
2. 重新获取授权 URL：`$GSETUP --auth-url`
3. 用户重新授权：`$GSETUP --auth-code "URL"`
4. 验证：`$GSETUP --check`

> ⚠️ auth code 只能使用一次，且修改 SCOPES 后必须重新授权。

---

## 卸载 / 撤销权限

```bash
$GSETUP --revoke
```

---

## 故障排除

| 问题 | 原因 | 解决方法 |
|------|------|---------|
| `NOT_AUTHENTICATED` | 未完成 OAuth | 按 Step 4 完成配置 |
| `REFRESH_FAILED` | Token 被撤销 | 重新授权 |
| `HttpError 403: Insufficient Permission` | Scope 不包含该 API | 重新授权，添加对应 scope |
| `HttpError 403: Access Not Configured` | Google Cloud Console 未启用该 API | 用户去 https://console.cloud.google.com/apis/library 启用 |
| `HttpError 403: The caller does not have permission` (Sheets) | 文件未与 OAuth 客户端共享 | 让文件所有者分享给你 |
| `ModuleNotFoundError` | 未安装依赖 | `$GSETUP --install-deps` |
| Advanced Protection 阻止授权 | 账号启用了高级保护 | Workspace 管理员需要将 OAuth 客户端 ID 加入白名单 |

---

## 项目结构

```
hermes-google-workspace/
├── README.md                          # 本文件
├── SKILL.md                           # Hermes Skill 定义文件
├── scripts/
│   ├── setup.py                       # OAuth 配置脚本
│   └── google_api.py                  # Google API CLI 封装
└── references/
    └── gmail-search-syntax.md        # Gmail 搜索语法参考
```

---

## License

MIT
