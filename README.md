# Google Workspace × AI Agent

[English README →](README.en.md)

让 **任意能在终端里执行命令**的 AI（Hermes、OpenClaw、Claude Code、Cursor Agent等）通过 **同一套 OAuth2 + CLI** 读写你的 Google Workspace：Gmail、Calendar、Tasks、Sheets、Docs（读）、Drive（读）、Contacts。

设计理念：**Agent 只负责编排**（把 URL 发给用户、收集重定向 URL、确认写操作），**凭证与 API 调用落在本仓库的 Python 脚本上**，因此不绑定某一款聊天产品。

---

## 功能一览

| 服务 | 支持操作 |
|------|---------|
| **Gmail** | 搜索、读取、发送、回复、标签 |
| **Calendar** | 列出 / 创建 / 删除事件 |
| **Tasks** | 任务列表、列出任务、添加（含 due）、标记完成 |
| **Sheets** | 读范围、写入、追加行 |
| **Docs** | 读取正文（纯文本） |
| **Drive** | 搜索（只读） |
| **Contacts** | 列出联系人（People API） |

写入类操作建议由 Agent **先展示草稿再执行**（策略层；本仓库 CLI 会直接调用 Google API）。

---

## 架构要点（审阅结论摘要）

| 项目 | 说明 |
|------|------|
| **OAuth scope单一来源** |所有 scope 只在 `scripts/scopes.py` 定义，`setup.py` 与 `google_api.py` 统一导入，避免「授权了 A、CLI 却要 B」的隐性故障。 |
| **Profile 目录** | 由 `scripts/_gws_env.py` 解析：可选 `GOOGLE_WORKSPACE_STATE_DIR`，否则 Hermes 内用 `hermes_constants`，再否则 `HERMES_HOME` / `OPENCLAW_HOME`，默认 `~/.hermes`（兼容旧版）。 |
| **独立仓库可运行** | 旧版在找不到 `hermes_constants` 时用错误的 `Path.parents[4]` 回退，会在独立 clone 下 **IndexError**；已改为不依赖该回退。 |
| **Calendar list时区** | 已修复「在 for 循环里改局部变量但未写回 `time_min` / `time_max`」导致 RFC3339 未补 `Z` 的问题。 |
| **Gmail / Contacts** | 旧版文档宣称支持，但 OAuth 列表未包含对应 scope；已在 `scopes.py` 中补齐（升级后需 **重新授权**）。 |
| **Tasks** | 已提供 `google_api.py tasks …` 子命令，无需再手写 Python 片段。 |

---

## 环境要求

- Python **3.8+**（推荐3.11+）
- Google 账号 / Workspace- 在 [Google Cloud Console](https://console.cloud.google.com/apis/credentials) 创建 **Desktop OAuth客户端**，并启用所需 API（含 **People API** 若要用通讯录）

---

## 安装方式

### A. Hermes 内置（若你的发行版提供）

```bash
hermes skills install google-workspace
```

### B. 克隆本仓库（最通用）

```bash
git clone https://github.com/BruceLanLan/hermes-google-workspace.git
cd hermes-google-workspace
```

依赖可在首次 `setup.py` 时自动安装，或手动：

```bash
python3 -m pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
```

### C. npm / npx（可选，需 Node）

本仓库提供 `gws` / `gws-setup` 两个 bin，实质是调用上面的 Python 脚本。发布至 npm 后可用：

```bash
npx -y -p hermes-google-workspace gws-setup --check
npx -y -p hermes-google-workspace gws gmail search "is:unread" --max 5
```

在包未上架前，可用本地路径或 GitHub 源（视 npm 版本支持情况而定）：

```bash
npx -y -p github:BruceLanLan/hermes-google-workspace gws-setup --help
```

也可全局安装后直接使用 `gws` / `gws-setup`：

```bash
npm install -g github:BruceLanLan/hermes-google-workspace
gws-setup --check
```

指定 Python：`GWS_PYTHON=/usr/bin/python3 gws calendar list`

---

## 命令别名（推荐给 Agent 的 shell 片段）

把 `GWORKSPACE_SKILL_DIR` 换成你的克隆路径；若在 Hermes skill 目录，则换成 `$HERMES_HOME/skills/productivity/google-workspace`。

```bash
GWORKSPACE_SKILL_DIR="$HOME/src/hermes-google-workspace"
PYTHON_BIN="${HERMES_PYTHON:-python3}"
if [ -x "${HERMES_HOME:-}/hermes-agent/venv/bin/python" ]; then
  PYTHON_BIN="$HERMES_HOME/hermes-agent/venv/bin/python"
fi
GSETUP="$PYTHON_BIN $GWORKSPACE_SKILL_DIR/scripts/setup.py"
GAPI="$PYTHON_BIN $GWORKSPACE_SKILL_DIR/scripts/google_api.py"
```

非 Hermes 的 CLI 助手建议显式设置状态目录，避免与别的工具混用 token：

```bash
export GOOGLE_WORKSPACE_STATE_DIR="$HOME/.config/google-workspace-cli"
```

---

## OAuth 配置流程

1. **`$GSETUP --check`** — 已认证则退出码 0，可跳过。
2. **`$GSETUP --client-secret /path/to/client_secret.json`** — 保存客户端密钥。
3. （高级）若需减少权限：编辑 **`scripts/scopes.py`**，删去不需要的 scope，再重新授权。
4. **`$GSETUP --auth-url`** — 将打印的 URL 发给最终用户在浏览器打开。
5. 用户授权后，浏览器会跳到 `http://localhost:1/?...`，让用户把 **地址栏完整 URL** 贴回。
6. **`$GSETUP --auth-code '粘贴的 URL 或 code'`**
7. **`$GSETUP --check`** — 应输出 `AUTHENTICATED`。

撤销：`$GSETUP --revoke`

---

## CLI 示例

### Gmail

```bash
$GAPI gmail search "is:unread newer_than:1d" --max 10
$GAPI gmail get MESSAGE_ID
$GAPI gmail send --to user@example.com --subject "Hello" --body "Message" --html
$GAPI gmail reply MESSAGE_ID --body "Thanks!"
$GAPI gmail labels
$GAPI gmail modify MESSAGE_ID --add-labels STARRED --remove-labels UNREAD
```

Gmail 搜索语法见 `references/gmail-search-syntax.md`。

### Calendar

```bash
$GAPI calendar list
$GAPI calendar list --start 2026-04-20T00:00:00Z --end 2026-04-25T23:59:59Z
$GAPI calendar create \
  --summary "Team Standup" \
  --start 2026-04-20T09:00:00-05:00 \
  --end 2026-04-20T09:30:00-05:00 \
  --attendees "alice@co.com,bob@co.com"
$GAPI calendar delete EVENT_ID
```

### Tasks

```bash
$GAPI tasks tasklists
$GAPI tasks list --tasklist TASKLIST_ID
$GAPI tasks add --tasklist TASKLIST_ID --title "Buy milk" --due "2026-04-20T00:00:00.000Z"
$GAPI tasks complete --tasklist TASKLIST_ID --task TASK_ID
```

### Sheets / Docs / Drive / Contacts

```bash
$GAPI sheets get "SHEET_ID" "Sheet1!A1:D10"
$GAPI sheets update "SHEET_ID" "Sheet1!A1:B2" --values '[["Name","Score"],["Alice","95"]]'
$GAPI docs get DOC_ID
$GAPI drive search "quarterly report" --max 10
$GAPI contacts list --max 20
```

---

## 与 Slack / Discord / Telegram / 微信 的关系

这些渠道 **不负责实现 Google API**；只要对应 Agent 运行时能执行你配置的 `$GSETUP` / `$GAPI`（或 `gws` / `gws-setup`），流程与本地 CLI 相同：发授权链接 → 用户浏览器授权 → 粘贴重定向 URL → 之后即可在同一 profile 下调 CLI。

微信若无法直接跑本地命令，需要你在 **能执行脚本的宿主机** 上完成 OAuth，并把 `GOOGLE_WORKSPACE_STATE_DIR` 指到该宿主机上的 token 目录。

---

## 故障排除

| 现象 | 处理 |
|------|------|
| `NOT_AUTHENTICATED` | 完成 OAuth 流程 |
| `AUTH_SCOPE_MISMATCH` / `Insufficient Permission` | 检查 `scripts/scopes.py`，修改后重新授权 |
| `ModuleNotFoundError` | `$GSETUP --install-deps` 或手动 pip安装 |
| `Access Not Configured` | Cloud Console 启用对应 API |
| 从 2.1 之前的版本升级后出现 Gmail/通讯录 403 | 新 scope 需重新走 `--auth-url` / `--auth-code` |

---

## 仓库结构

```
hermes-google-workspace/
├── README.md / README.en.md
├── SKILL.md                 # Hermes skill 元数据 + 说明
├── package.json             # 可选 npx / npm 全局安装
├── bin/gws.cjs / gws-setup.cjs
├── scripts/
│   ├── scopes.py            # 唯一 OAuth scope 列表
│   ├── _gws_env.py          # token 目录解析
│   ├── setup.py             # OAuth
│   └── google_api.py        # CLI
└── references/
    └── gmail-search-syntax.md
```

---

## License

MIT
