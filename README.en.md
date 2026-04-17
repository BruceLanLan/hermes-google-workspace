# Google Workspace × AI Agent

[← 中文说明](README.md)

Give **any AI that can run terminal commands** (Hermes, OpenClaw, Claude Code, Cursor agents, etc.) a **single OAuth2 + CLI layer** for Google Workspace: Gmail, Calendar, Tasks, Sheets, Docs (read), Drive (read), Contacts.

**Design:** the **agent orchestrates** (sends the OAuth URL, collects the redirect URL, confirms writes). **Credentials and API calls live in this repo**, so the integration is not tied to any specific chat product.

---

## Capabilities

| Service | Operations |
|---------|------------|
| **Gmail** | Search (`--format ids` for piping), get (`--format json/text/markdown`), send / reply (multi-attachment + HTML), labels |
| **Calendar** | List, create (`--duration 1h30m`), **update**, delete (`--notify`) |
| **Tasks** | Task lists, list tasks, add (with due), complete |
| **Sheets** | Read range, update, append |
| **Docs** | Read plain text |
| **Drive** | Search (read-only) |
| **Contacts** | List and filter by name (People API) |

Have your agent **show a draft and ask for confirmation** before mutating calls (policy layer; the CLI here calls Google APIs directly).

---

## Design notes

| Topic | Detail |
|-------|--------|
| **Single scope source** | All OAuth scopes live in `scripts/scopes.py` and are imported by both entry points; CI blocks re-introducing `SCOPES` elsewhere. |
| **Shared module** | `scripts/_gws_common.py` provides an `@api_call` decorator (`HttpError` → structured JSON on stderr, exit 2), scope diffing, and `print_json`. |
| **Profile directory** | Resolved in `scripts/_gws_env.py`: `GOOGLE_WORKSPACE_STATE_DIR` → Hermes `hermes_constants` → `HERMES_HOME` / `OPENCLAW_HOME` → `~/.hermes` (backward compatible). |
| **Standalone clone** | Removed the broken `Path.parents[4]` fallback from the original skill. |
| **Calendar RFC3339** | Fixed `time_min` / `time_max` normalization; covered by pytest. |
| **Gmail / Contacts scopes** | Added `gmail.modify` / `contacts.readonly` / `drive.readonly` (**re-consent after upgrade**). |
| **Tasks subcommands** | `tasks tasklists / list / add / complete` replace the earlier Python snippets. |
| **Packaging** | `pip install` exposes `gws` / `gws-setup` via `pyproject.toml`. `npx` and direct-script invocations still work. |
| **Tests** | `tests/test_pure_helpers.py` covers pure helpers without hitting Google. |

---

## Requirements

- Python **3.9+** (3.11+ recommended)
- Google account / Workspace
- **Desktop** OAuth client in [Google Cloud Console](https://console.cloud.google.com/apis/credentials); enable Gmail / Calendar / Tasks / Sheets / Docs / Drive / People API as needed.

---

## Install

### A. Hermes marketplace (if your distribution ships it)

```bash
hermes skills install google-workspace
```

### B. `pip install` (recommended)

```bash
pip install --user git+https://github.com/BruceLanLan/hermes-google-workspace.git
gws --version        # gws 2.2.0
gws-setup --check
```

Or for development:

```bash
git clone https://github.com/BruceLanLan/hermes-google-workspace.git
cd hermes-google-workspace
pip install -e ".[test]" && pytest -q
```

### C. Run scripts directly

```bash
git clone https://github.com/BruceLanLan/hermes-google-workspace.git
python3 -m pip install -r hermes-google-workspace/requirements.txt
python3 hermes-google-workspace/scripts/google_api.py --help
```

### D. npm / npx (requires Node)

Bins `gws` / `gws-setup` wrap the Python CLIs.

```bash
npx -y -p github:BruceLanLan/hermes-google-workspace gws-setup --help
npm install -g github:BruceLanLan/hermes-google-workspace
```

Override interpreter: `GWS_PYTHON=/usr/bin/python3 gws calendar list`

---

## Shell aliases for agents

After `pip install` the agent can use bare commands:

```bash
GSETUP="gws-setup"
GAPI="gws"
```

Script mode:

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
$GAPI gmail search "from:boss is:unread" --format ids
$GAPI gmail get MESSAGE_ID --format markdown
$GAPI gmail send --to user@example.com --subject "Hello" \
  --body "<h1>Hi</h1>" --html \
  --attachment ~/slides.pdf --attachment ~/notes.txt
$GAPI gmail reply MESSAGE_ID --body "Thanks!"
```

### Calendar

```bash
$GAPI calendar list
$GAPI calendar create \
  --summary "Standup" \
  --start 2026-04-20T09:00:00-05:00 \
  --duration 30m \
  --attendees "team@co.com"
$GAPI calendar update EVENT_ID --duration 45m
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
$GAPI docs get DOC_ID
$GAPI drive search "report" --max 10
$GAPI contacts list --name "Alice"
```

---

## Slack, Discord, Telegram, WeChat, etc.

Those apps **do not implement Google APIs**. Any agent runtime that can execute your `$GSETUP` / `$GAPI` (or `gws` / `gws-setup`) works the same as local CLI: share the OAuth URL, user signs in, paste redirect URL, subsequent calls reuse the token profile.

If a channel cannot run commands on the machine that stores tokens, complete OAuth on a machine that can, and point `GOOGLE_WORKSPACE_STATE_DIR` there.

---

## Error contract

Every command returns **exit 0** on success and writes JSON to stdout. On failure the `@api_call` decorator writes a structured JSON object to **stderr** and exits with code **2**:

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

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `NOT_AUTHENTICATED` | Finish OAuth |
| `AUTH_SCOPE_MISMATCH` / `Insufficient Permission` | Edit `scripts/scopes.py`, re-authorize |
| `ModuleNotFoundError` | `gws-setup --install-deps` or `pip install -r requirements.txt` |
| `Access Not Configured` | Enable API in Cloud Console |
| Gmail/Contacts 403 after upgrading from pre-2.1 | New scopes require a fresh `--auth-url` / `--auth-code` |

---

## Layout

```
hermes-google-workspace/
├── README.md / README.en.md
├── SKILL.md
├── LICENSE
├── pyproject.toml
├── requirements.txt
├── package.json
├── bin/gws.cjs / gws-setup.cjs
├── scripts/
│   ├── __init__.py
│   ├── scopes.py
│   ├── _gws_env.py
│   ├── _gws_common.py
│   ├── setup.py
│   └── google_api.py
├── tests/
│   └── test_pure_helpers.py
├── .github/workflows/test.yml
└── references/
    └── gmail-search-syntax.md
```

---

## License

MIT
