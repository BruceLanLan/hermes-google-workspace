# Google Workspace × AI Agent

[English README →](README.en.md)

让 **任意能在终端里执行命令**的 AI（Hermes、OpenClaw、Claude Code、Cursor Agent等）通过 **同一套 OAuth2 + CLI** 读写你的 Google Workspace：Gmail、Calendar、Tasks、Sheets、Docs（读）、Drive（读）、Contacts。

设计理念：**Agent 只负责编排**（把 URL 发给用户、收集重定向 URL、确认写操作），**凭证与 API 调用落在本仓库的 Python 脚本上**，因此不绑定某一款聊天产品。

---

## 功能一览

| 服务 | 支持操作 |
|------|---------|
| **Gmail** | 搜索 (`--format ids` 管道化)、读取 (`--format json/text/markdown`)、发送 / 回复（支持多附件 & HTML）、标签管理 |
| **Calendar** | 列出、创建（`--duration 1h30m`）、**更新**、删除（`--notify`） |
| **Tasks** | 任务列表、列出任务、添加（含 due）、标记完成 |
| **Sheets** | 读范围、写入、追加行 |
| **Docs** | 读取正文（纯文本） |
| **Drive** | 搜索（只读） |
| **Contacts** | 列出 & 按姓名过滤（People API） |

写入类操作建议由 Agent **先展示草稿再执行**（策略层；本仓库 CLI 会直接调用 Google API）。

---

## 架构要点（审阅结论摘要）

| 项目 | 说明 |
|------|------|
| **OAuth scope 单一来源** | 所有 scope 只在 `scripts/scopes.py` 定义；`setup.py`、`google_api.py` 统一导入，CI 强制 grep 保证。 |
| **共享模块** | `scripts/_gws_common.py` 提供 `@api_call` 装饰器（HttpError → 结构化 JSON 到 stderr、exit 2）、scope 比对、`print_json`，避免重复。 |
| **Profile 目录** | `scripts/_gws_env.py` 解析顺序：`GOOGLE_WORKSPACE_STATE_DIR` → Hermes `hermes_constants` → `HERMES_HOME` / `OPENCLAW_HOME` → `~/.hermes`。 |
| **独立仓库可运行** | 去掉错误的 `Path.parents[4]` 回退，单独 clone 也能工作。 |
| **Calendar list 时区** | 修复「写回 time_min / time_max」bug，RFC3339 `Z` 补齐逻辑有单测覆盖。 |
| **Gmail / Contacts scope 补齐** | 新增 `gmail.modify` / `contacts.readonly` / `drive.readonly`，升级后需 **重新授权**。 |
| **Tasks CLI 子命令** | `tasks tasklists / list / add / complete`，不再需要手写 Python。 |
| **打包** | 支持 `pip install` 后得到 `gws` / `gws-setup`（`pyproject.toml`），也支持 `npx` 与直接脚本调用。 |
| **测试** | `tests/test_pure_helpers.py` 覆盖纯逻辑：时区归一化、duration 解析、Gmail body 抽取、scope 比对。 |

---

## 环境要求

- Python **3.9+**（推荐 3.11+）
- Google 账号 / Workspace
- 在 [Google Cloud Console](https://console.cloud.google.com/apis/credentials) 创建 **Desktop OAuth 客户端**，并启用所需 API（含 **People API** 若要用通讯录）

---

## 安装方式

### A. Hermes 内置（若你的发行版提供）

```bash
hermes skills install google-workspace
```

### B. `pip install`（推荐，得到 `gws` / `gws-setup`）

```bash
pip install --user git+https://github.com/BruceLanLan/hermes-google-workspace.git
gws --version        # gws 2.2.0
gws-setup --check
```

或本地开发：

```bash
git clone https://github.com/BruceLanLan/hermes-google-workspace.git
cd hermes-google-workspace
pip install -e ".[test]" && pytest -q
```

### C. 直接运行脚本

```bash
git clone https://github.com/BruceLanLan/hermes-google-workspace.git
python3 -m pip install -r hermes-google-workspace/requirements.txt
python3 hermes-google-workspace/scripts/google_api.py --help
```

### D. npm / npx（需 Node）

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

安装为包后，Agent 直接使用即可：

```bash
GSETUP="gws-setup"
GAPI="gws"
```

若用脚本模式，把 `GWORKSPACE_SKILL_DIR` 换成你的克隆路径（Hermes skill 目录即 `$HERMES_HOME/skills/productivity/google-workspace`）：

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
$GAPI gmail search "from:boss is:unread" --format ids        # 可管道化
$GAPI gmail get MESSAGE_ID --format markdown                  # 便于 Agent 总结
$GAPI gmail send --to user@example.com --subject "Hello" \
  --body "<h1>Hi</h1>" --html \
  --attachment ~/slides.pdf --attachment ~/notes.txt
$GAPI gmail reply MESSAGE_ID --body "Thanks!"
$GAPI gmail labels
$GAPI gmail modify MESSAGE_ID --add-labels STARRED --remove-labels UNREAD
```

Gmail 搜索语法见 `references/gmail-search-syntax.md`。

### Calendar

```bash
$GAPI calendar list
$GAPI calendar list --start 2026-04-20T00:00:00Z --end 2026-04-25T23:59:59Z

# 创建：--end 或 --duration 二选一
$GAPI calendar create \
  --summary "Team Standup" \
  --start 2026-04-20T09:00:00-05:00 \
  --duration 30m \
  --attendees "alice@co.com,bob@co.com"

# 更新（可以只改 summary / 时间 / 参会人）
$GAPI calendar update EVENT_ID --start 2026-04-20T10:00:00-05:00 --duration 45m

# 删除；--notify 会给参会人发取消邮件
$GAPI calendar delete EVENT_ID --notify
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

## 错误契约（agents 友好）

成功返回 **exit 0** + stdout 的 JSON。失败时 `@api_call` 装饰器写结构化 JSON 到 **stderr** 并以 **exit 2** 退出，形如：

```json
{
  "ok": false,
  "error": "HttpError",
  "message": "...",
  "http_status": 403,
  "google": { "error": { "message": "Insufficient Permission", "status": "PERMISSION_DENIED" } }
}
```

---

## 故障排除

| 现象 | 处理 |
|------|------|
| `NOT_AUTHENTICATED` | 完成 OAuth 流程 |
| `AUTH_SCOPE_MISMATCH` / `Insufficient Permission` | 检查 `scripts/scopes.py`，修改后重新授权 |
| `ModuleNotFoundError` | `gws-setup --install-deps` 或 `pip install -r requirements.txt` |
| `Access Not Configured` | Cloud Console 启用对应 API |
| 从 2.1 之前的版本升级后出现 Gmail/通讯录 403 | 新 scope 需重新走 `--auth-url` / `--auth-code` |
| CLI 出错 | 所有 handler 都会把 `HttpError` 转成 stderr 的结构化 JSON，并以 exit code **2** 退出，便于 Agent 分析 |

---

## 仓库结构

```
hermes-google-workspace/
├── README.md / README.en.md
├── SKILL.md                 # Hermes skill 元数据 + 说明
├── LICENSE                  # MIT
├── pyproject.toml           # pip install → gws / gws-setup
├── requirements.txt
├── package.json             # npx / npm 全局安装
├── bin/gws.cjs / gws-setup.cjs
├── scripts/
│   ├── __init__.py          # 安装后包名 gws_cli
│   ├── scopes.py            # 唯一 OAuth scope 列表
│   ├── _gws_env.py          # token 目录解析
│   ├── _gws_common.py       # @api_call 装饰器 / JSON 输出
│   ├── setup.py             # OAuth
│   └── google_api.py        # CLI
├── tests/
│   └── test_pure_helpers.py # pytest（纯逻辑）
├── .github/workflows/test.yml
└── references/
    └── gmail-search-syntax.md
```

---

## Star History

<a href="https://www.star-history.com/?repos=brucelanlan%2Fhermes-google-workspace&type=timeline&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=brucelanlan/hermes-google-workspace&type=timeline&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=brucelanlan/hermes-google-workspace&type=timeline&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=brucelanlan/hermes-google-workspace&type=timeline&legend=top-left" />
 </picture>
</a>


## License

MIT
