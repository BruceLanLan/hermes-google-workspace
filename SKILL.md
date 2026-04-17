---
name: google-workspace
description: Gmail, Calendar, Tasks, Sheets, Docs, Drive, Contacts — OAuth2 with auto-refresh; works with Hermes, OpenClaw, and any terminal agent/CLI.
version: 2.1.0
author: Hermes Agent Community
license: MIT
tags: [Google, Gmail, Calendar, Tasks, Sheets, Docs, Drive, Contacts, OAuth]
required_credential_files:
  - path: google_token.json
    description: Google OAuth2 access token（自动刷新，setup.py 管理）
  - path: google_client_secret.json
    description: Google OAuth2 客户端凭证（从 Google Cloud Console 下载）
optional_credential_files:
  - path: google_oauth_pending.json
    description: OAuth 流程中间状态（授权完成后自动删除）
metadata:
  hermes:
    homepage: https://github.com/BruceLanLan/hermes-google-workspace
    platform: [cli, telegram, slack, discord, whatsapp, openclaw, cursor]
    profile_scoped: true
---

# Google Workspace Skill

Gmail、Calendar、Tasks、Sheets、Docs、Drive、Contacts — 通过 Google OAuth2 集成到任意能跑终端命令的 Agent（Hermes、OpenClaw、Claude Code、Cursor 等）。Token 存放在可配置的 profile 目录，支持自动刷新。

## 功能覆盖

| 服务 | 读取 | 写入 | 备注 |
|------|------|------|------|
| Gmail | ✅ search, get, labels | ✅ send, reply, modify | 支持 HTML；发送前确认 |
| Calendar | ✅ list | ✅ create, delete | ISO 8601 带时区 |
| Tasks | ✅ tasklists, list | ✅ add（insert+patch）, complete | `google_api.py tasks …` |
| Sheets | ✅ get | ✅ update, append | 需先查 tab 名 |
| Docs | ✅ get（纯文本） | ❌ | 只读 |
| Drive | ✅ search | ❌ | 只读 |
| Contacts | ✅ list | ❌ | 只读 |

## 文件索引

- `scripts/setup.py` — OAuth 配置（check / client-secret / auth-url / auth-code / revoke）
- `scripts/google_api.py` — Google API 的 CLI 封装
- `scripts/scopes.py` — **唯一**的 OAuth scope 列表（`setup.py` 与 `google_api.py` 均从这里导入）
- `scripts/_gws_env.py` — 解析 token 存放目录（Hermes / OpenClaw / 自定义）
- `references/gmail-search-syntax.md` — Gmail 搜索操作符完整参考

## 快速安装

```bash
hermes skills install google-workspace
```

手动安装：

```bash
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
mkdir -p "$HERMES_HOME/skills/productivity/google-workspace"/{scripts,references}
# 复制 scripts 和 references 目录内容到上述路径
```

配置 shorthand（按需把 `GWORKSPACE_SKILL_DIR` 换成你克隆本仓库的路径）：

```bash
GWORKSPACE_SKILL_DIR="$HOME/src/hermes-google-workspace"
PYTHON_BIN="${HERMES_PYTHON:-python3}"
GSETUP="$PYTHON_BIN $GWORKSPACE_SKILL_DIR/scripts/setup.py"
GAPI="$PYTHON_BIN $GWORKSPACE_SKILL_DIR/scripts/google_api.py"
```

可选：用 npm 提供的入口（需本仓库在本地或已通过 `npm install -g` / `npx` 解析到含 `scripts/` 的包目录）：

```bash
# 已发布到 npm 时（或先用本地路径调试：`npx -y -p /path/to/hermes-google-workspace …`）
GSETUP="npx -y -p hermes-google-workspace gws-setup"
GAPI="npx -y -p hermes-google-workspace gws"
# 从 GitHub 安装：`npx -y -p github:BruceLanLan/hermes-google-workspace gws-setup`
```

Token 目录解析顺序见 `scripts/_gws_env.py`。常用覆盖：

- `GOOGLE_WORKSPACE_STATE_DIR` — 显式指定目录（推荐用于非 Hermes 的 CLI）
- `HERMES_HOME` / `OPENCLAW_HOME` — 与对应 Agent 的 profile 对齐

## 首次 OAuth 配置

### Step 0：检查

```bash
$GSETUP --check
# AUTHENTICATED → 已完成，跳过本节
```

### Step 1：创建 Google Cloud OAuth 客户端

1. 访问 https://console.cloud.google.com/apis/credentials
2. 创建项目 → Enable APIs（Gmail / Calendar / Tasks / Sheets / Docs / Drive / **People API**（通讯录）按需启用）
3. Credentials → Create Credentials → OAuth 2.0 Client ID → Desktop app
4. Download JSON → 把文件路径交给 Agent / 你自己用于 `--client-secret`

### Step 2：存储客户端凭证

```bash
$GSETUP --client-secret /path/to/client_secret.json
```

### Step 3：按需裁剪 SCOPES（高级）

默认列表在 **`scripts/scopes.py`**。`setup.py` 与 `google_api.py` 已强制从该文件导入，避免再出现「授权范围与 CLI 不一致」的问题。若你不需要某项能力，可从列表中删除对应 scope，然后重新走 OAuth。

### Step 4：获取授权 URL

```bash
$GSETUP --auth-url
# 输出一个 URL，发给用户让其在浏览器打开
```

### Step 5：交换 Token

用户授权后浏览器跳转到 `http://localhost:1/?...`，用户粘贴完整 URL：

```bash
$GSETUP --auth-code "用户粘贴的URL"
```

### Step 6：验证

```bash
$GSETUP --check
```

---

## 使用示例

### Gmail

```bash
# 搜索
$GAPI gmail search "is:unread newer_than:1d" --max 10

# 读取
$GAPI gmail get MESSAGE_ID

# 发送（发送前展示草稿并确认）
$GAPI gmail send --to user@example.com --subject "Report" --body "<h1>Q4</h1>" --html

# 回复（自动 threading + In-Reply-To）
$GAPI gmail reply MESSAGE_ID --body "Got it, thanks!"

# 标签管理
$GAPI gmail labels
$GAPI gmail modify MESSAGE_ID --add-labels STARRED --remove-labels UNREAD
```

### Calendar

```bash
# 列表（默认未来7天）
$GAPI calendar list

# 创建（时间必须 ISO 8601 带时区偏移）
$GAPI calendar create \
  --summary "Sprint Planning" \
  --start 2026-04-21T10:00:00-05:00 \
  --end 2026-04-21T11:30:00-05:00 \
  --location "Google Meet" \
  --attendees "team@co.com"

# 删除
$GAPI calendar delete EVENT_ID --calendar primary
```

### Tasks

```bash
$GAPI tasks tasklists
$GAPI tasks list --tasklist TASKLIST_ID
$GAPI tasks add --tasklist TASKLIST_ID --title "Review deck" --notes "Friday" --due "2026-04-20T00:00:00.000Z"
$GAPI tasks complete --tasklist TASKLIST_ID --task TASK_ID
```

### Sheets

```bash
# 读取（注意：先查 tab 名，不要硬写 "Sheet1"）
$GAPI sheets get "SHEET_ID" "Sheet1!A1:D10"

# 写入
$GAPI sheets update "SHEET_ID" "Sheet1!A1:B2" --values '[["Alice","100"],["Bob","95"]]'

# 追加
$GAPI sheets append "SHEET_ID" "Sheet1!A:C" --values '[["Carol","88"]]'
```

### Docs

```bash
$GAPI docs get DOC_ID
```

### Drive

```bash
# 全文搜索
$GAPI drive search "budget report" --max 10

# MIME 类型筛选
$GAPI drive search "mimeType='application/vnd.google-apps.spreadsheet'" --raw-query --max 5
```

---

## 扩展现有认证（添加新 Scope）

1. 编辑 **`scripts/scopes.py`**
2. `$GSETUP --auth-url`（重新获取 URL）
3. `$GSETUP --auth-code "URL"`（用户重新授权）
4. `$GSETUP --check`

---

## API 已知问题

### Docs — body 内容要这样提取

```python
# WRONG: 永远是空的
for block in doc_content.get("content", []):

# CORRECT
for block in doc_content.get("body", {}).get("content", []):
    for elem in block.get("paragraph", {}).get("elements", []):
        if "textRun" in elem:
            text += elem["textRun"].get("content", "")
```

### Sheets — tab 名不是 "Sheet1"

先查 metadata：
```python
meta = sheets.spreadsheets().get(spreadsheetId=ID).execute()
tabs = [s["properties"]["title"] for s in meta.get("sheets", [])]
tab = tabs[0]  # 用第一个 tab 名
```

### Tasks — insert 时不能设 due date

必须分两步：先 insert，再 patch：
```python
# Fails
tasks.tasks().insert(tasklist=ID, body={"title": "x", "due": "2026-04-14T00:00:00Z"})
# Works
t = tasks.tasks().insert(tasklist=ID, body={"title": "x"}).execute()
tasks.tasks().patch(tasklist=ID, task=t["id"], body={"due": "..."}).execute()
```

### Sheets — 403 权限错误

文件所有者没有和你的 OAuth 客户端共享。请求访问权限或换个已共享的文件。

---

## 故障排除

| 问题 | 诊断命令 | 解决方法 |
|------|---------|---------|
| `NOT_AUTHENTICATED` | `$GSETUP --check` | 完成 OAuth Step 4 |
| `REFRESH_FAILED` | — | Token 被 Google 撤销，重新授权 |
| `HttpError 403: Insufficient Permission` | 检查 scopes | 重新授权 |
| `HttpError 403: Access Not Configured` | Google Cloud Console | 启用对应 API |
| `ModuleNotFoundError` | — | `$GSETUP --install-deps` |
| Advanced Protection 阻止 | — | Workspace 管理员白名单 OAuth 客户端 ID |

---

## 撤销权限

```bash
$GSETUP --revoke
```
