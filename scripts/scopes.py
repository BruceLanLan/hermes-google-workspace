"""Single source of truth for Google OAuth scopes.

setup.py and google_api.py must import SCOPES only from this module so consent,
token refresh, and scope validation never drift apart.
"""

# Docs: read-only in this skill (no Docs write helpers yet).
# Gmail: modify covers read, send, reply, labels for a personal assistant use case.
# People: contacts.readonly for People API connections list.
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/contacts.readonly",
]
