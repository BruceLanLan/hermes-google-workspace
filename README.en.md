# Google Workspace × AI Agent

[← 中文说明](README.md)

Give **any AI that can run terminal commands** (Hermes, OpenClaw, Claude Code, Cursor agents, etc.) a **single OAuth2 + CLI layer** for Google Workspace: Gmail, Calendar, Tasks, Sheets, Docs (read), Drive (read), and Contacts.

**Design:** the **agent orchestrates** (sends the OAuth URL, collects the redirect URL, confirms writes). **Credentials and API calls live in this repo’s Python scripts**, so the integration is not tied to a specific chat product.

---

## Capabilities

| Service | Operations |
|---------|------------|
| **Gmail** | Search, read, send, reply, labels |
| **Calendar** | List / create / delete events |
| **Tasks** | Task lists, list tasks, add (with due), complete |
| **Sheets** | Read range, update, append |
| **Docs** | Read plain text |
| **Drive** | Search (read-only) |
| **Contacts** | List connections (People API) |

For mutating actions, have the agent **show a draft and ask for confirmation** (policy layer; the CLI here calls Google APIs directly).

---

## Design notes (review summary)

| Topic | Detail |
|-------|--------|
| **Single scope source** | All OAuth scopes live in `scripts/scopes.py` and are imported by both `setup.py` and `google_api.py`, so consent and CLI validation cannot drift. |
| **Profile directory** | Resolved in `scripts/_gws_env.py`: optional `GOOGLE_WORKSPACE_STATE_DIR`, else `hermes_constants` inside Hermes, else `HERMES_HOME` / `OPENCLAW_HOME`, default `~/.hermes` (backward compatible). |
| **Standalone clone** | Older code used an invalid `Path.parents[4]` fallback when `hermes_constants` was missing, which could **IndexError** outside a full Hermes tree. That path is removed. |
| **Calendar list / RFC3339** | Fixed a bug where timezone normalization modified a loop variable but never updated `time_min` / `time_max`. |
| **Gmail / Contacts** | Docs claimed support, but OAuth scopes were incomplete; `scopes.py` now includes the right scopes (**re-consent after upgrade**). |
| **Tasks** | Native `google_api.py tasks …` subcommands replace ad-hoc Python snippets. |

---

## Requirements

- Python **3.8+** (3.11+ recommended)
- Google account / Workspace
- A **Desktop** OAuth client in [Google Cloud Console](https://console.cloud.google.com/apis/credentials) and APIs enabled (including **People API** for Contacts)

---

## Installation

### A. Hermes marketplace (if your distribution ships it)

```bash
hermes skills install google-workspace
```

### B. Clone (most portable)

```bash
git clone https://github.com/BruceLanLan/hermes-google-workspace.git
cd hermes-google-workspace
```

Dependencies install on first `setup.py` run, or manually:

```bash
python3 -m pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
```

### C. npm / npx (optional, requires Node)

Bins `gws` / `gws-setup` wrap the Python CLIs. After publish:

```bash
npx -y -p hermes-google-workspace gws-setup --check
npx -y -p hermes-google-workspace gws gmail search "is:unread" --max 5
```

Before npm publish, use a local path or GitHub (depending on npm support):

```bash
npx -y -p github:BruceLanLan/hermes-google-workspace gws-setup --help
```

Global install:

```bash
npm install -g github:BruceLanLan/hermes-google-workspace
gws-setup --check
```

Custom Python: `GWS_PYTHON=/usr/bin/python3 gws calendar list`

---

## Shell aliases for agents

Point `GWORKSPACE_SKILL_DIR` at your clone (or `$HERMES_HOME/skills/productivity/google-workspace` inside Hermes).

```bash
GWORKSPACE_SKILL_DIR="$HOME/src/hermes-google-workspace"
PYTHON_BIN="${HERMES_PYTHON:-python3}"
if [ -x "${HERMES_HOME:-}/hermes-agent/venv/bin/python" ]; then
  PYTHON_BIN="$HERMES_HOME/hermes-agent/venv/bin/python"
fi
GSETUP="$PYTHON_BIN $GWORKSPACE_SKILL_DIR/scripts/setup.py"
GAPI="$PYTHON_BIN $GWORKSPACE_SKILL_DIR/scripts/google_api.py"
```

For non-Hermes CLIs, pin tokens to a dedicated directory:

```bash
export GOOGLE_WORKSPACE_STATE_DIR="$HOME/.config/google-workspace-cli"
```

---

## OAuth flow

1. `$GSETUP --check` — exit 0 means you can skip setup.
2. `$GSETUP --client-secret /path/to/client_secret.json`
3. (Advanced) Trim scopes in **`scripts/scopes.py`**, then re-authorize.
4. `$GSETUP --auth-url` — send the printed URL to the user’s browser.
5. After consent, the browser lands on `http://localhost:1/?...` — paste the **full URL** (or code) back.
6. `$GSETUP --auth-code '…'`
7. `$GSETUP --check` — expect `AUTHENTICATED`.

Revoke: `$GSETUP --revoke`

---

## CLI examples

### Gmail

```bash
$GAPI gmail search "is:unread newer_than:1d" --max 10
$GAPI gmail get MESSAGE_ID
$GAPI gmail send --to user@example.com --subject "Hello" --body "Message" --html
$GAPI gmail reply MESSAGE_ID --body "Thanks!"
```

See `references/gmail-search-syntax.md` for search operators.

### Calendar

```bash
$GAPI calendar list
$GAPI calendar create \
  --summary "Standup" \
  --start 2026-04-20T09:00:00-05:00 \
  --end 2026-04-20T09:30:00-05:00
$GAPI calendar delete EVENT_ID
```

### Tasks

```bash
$GAPI tasks tasklists
$GAPI tasks list --tasklist TASKLIST_ID
$GAPI tasks add --tasklist TASKLIST_ID --title "Buy milk" --due "2026-04-20T00:00:00.000Z"
$GAPI tasks complete --tasklist TASKLIST_ID --task TASK_ID
```

### Sheets, Docs, Drive, Contacts

```bash
$GAPI sheets get "SHEET_ID" "Sheet1!A1:D10"
$GAPI docs get DOC_ID
$GAPI drive search "report" --max 10
$GAPI contacts list --max 20
```

---

## Slack, Discord, Telegram, WeChat, etc.

Those apps **do not implement Google APIs**. Any agent runtime that can execute your `$GSETUP` / `$GAPI` (or `gws` / `gws-setup`) works the same as local CLI: share OAuth URL → user signs in → paste redirect URL → subsequent calls reuse the token profile.

If a channel cannot run commands on the host that holds tokens, complete OAuth on a machine that can, and point `GOOGLE_WORKSPACE_STATE_DIR` at that token directory.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `NOT_AUTHENTICATED` | Finish OAuth |
| `AUTH_SCOPE_MISMATCH` / `Insufficient Permission` | Edit `scripts/scopes.py`, re-authorize |
| `ModuleNotFoundError` | `$GSETUP --install-deps` or pip install |
| `Access Not Configured` | Enable API in Cloud Console |
| Gmail/Contacts 403 after upgrading from pre-2.1 | New scopes require a fresh `--auth-url` / `--auth-code` |

---

## Layout

```
hermes-google-workspace/
├── README.md / README.en.md
├── SKILL.md
├── package.json
├── bin/gws.cjs / gws-setup.cjs
├── scripts/
│   ├── scopes.py
│   ├── _gws_env.py
│   ├── setup.py
│   └── google_api.py
└── references/
    └── gmail-search-syntax.md
```

---

## License

MIT
