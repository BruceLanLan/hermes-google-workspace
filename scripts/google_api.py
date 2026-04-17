#!/usr/bin/env python3
"""Google Workspace API CLI (Hermes, OpenClaw, Claude Code, or any terminal agent).

A thin CLI wrapper around Google's Python client libraries.
Authenticates using the token stored by setup.py.

Usage:
  python google_api.py gmail search "is:unread" [--max 10]
  python google_api.py gmail get MESSAGE_ID
  python google_api.py gmail send --to user@example.com --subject "Hi" --body "Hello"
  python google_api.py gmail reply MESSAGE_ID --body "Thanks"
  python google_api.py calendar list [--from DATE] [--to DATE] [--calendar primary]
  python google_api.py calendar create --summary "Meeting" --start DATETIME --end DATETIME
  python google_api.py drive search "budget report" [--max 10]
  python google_api.py contacts list [--max 20]
  python google_api.py sheets get SHEET_ID RANGE
  python google_api.py sheets update SHEET_ID RANGE --values '[[...]]'
  python google_api.py sheets append SHEET_ID RANGE --values '[[...]]'
  python google_api.py docs get DOC_ID
  python google_api.py tasks tasklists
  python google_api.py tasks list --tasklist TASKLIST_ID
  python google_api.py tasks add --tasklist TASKLIST_ID --title "Buy milk" [--due RFC3339]
  python google_api.py tasks complete --tasklist TASKLIST_ID --task TASK_ID
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path

try:
    from ._gws_common import api_call, format_missing_scopes, missing_scopes_from_payload, print_json
    from ._gws_env import display_state_dir, get_state_dir
    from .scopes import SCOPES
except ImportError:
    _SCRIPT_DIR = Path(__file__).resolve().parent
    if str(_SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPT_DIR))
    from _gws_common import api_call, format_missing_scopes, missing_scopes_from_payload, print_json  # type: ignore
    from _gws_env import display_state_dir, get_state_dir  # type: ignore
    from scopes import SCOPES  # type: ignore

TOKEN_PATH = get_state_dir() / "google_token.json"


def _load_token_payload() -> dict:
    try:
        return json.loads(TOKEN_PATH.read_text())
    except Exception:
        return {}


def _missing_scopes() -> list:
    return missing_scopes_from_payload(_load_token_payload())


def get_credentials():
    """Load and refresh credentials from token file."""
    if not TOKEN_PATH.exists():
        print("Not authenticated. Run the setup script first:", file=sys.stderr)
        print(f"  python {Path(__file__).parent / 'setup.py'}", file=sys.stderr)
        sys.exit(1)

    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
    if not creds.valid:
        print("Token is invalid. Re-run setup.", file=sys.stderr)
        sys.exit(1)

    missing_scopes = _missing_scopes()
    if missing_scopes:
        print(
            "Token is valid but missing Google Workspace scopes required by this skill.",
            file=sys.stderr,
        )
        for scope in missing_scopes:
            print(f"  - {scope}", file=sys.stderr)
        print(
            f"Re-run setup.py for profile directory {display_state_dir()} to restore full access.",
            file=sys.stderr,
        )
        sys.exit(1)
    return creds


def build_service(api, version):
    from googleapiclient.discovery import build
    return build(api, version, credentials=get_credentials())


# =========================================================================
# Gmail
# =========================================================================

def _extract_gmail_body(payload: dict) -> str:
    """Return the best-effort text body from a Gmail message payload."""
    if payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    parts = payload.get("parts") or []
    # Prefer text/plain, fall back to text/html, then recurse into multiparts.
    for mt in ("text/plain", "text/html"):
        for part in parts:
            if part.get("mimeType") == mt and part.get("body", {}).get("data"):
                return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
    for part in parts:
        if part.get("mimeType", "").startswith("multipart/"):
            nested = _extract_gmail_body(part)
            if nested:
                return nested
    return ""


def _build_mime_message(
    *,
    to: str,
    subject: str,
    body: str,
    html: bool,
    cc: str = "",
    bcc: str = "",
    attachments=None,
    extra_headers=None,
):
    attachments = attachments or []
    extra_headers = extra_headers or {}
    subtype = "html" if html else "plain"

    if attachments:
        root = MIMEMultipart()
        root.attach(MIMEText(body, subtype, "utf-8"))
        for path_str in attachments:
            path = Path(path_str).expanduser().resolve()
            if not path.exists():
                raise FileNotFoundError(f"Attachment not found: {path}")
            ctype, _ = mimetypes.guess_type(str(path))
            maintype, subt = (ctype or "application/octet-stream").split("/", 1)
            with open(path, "rb") as fh:
                part = MIMEBase(maintype, subt)
                part.set_payload(fh.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=path.name)
            root.attach(part)
        message = root
    else:
        message = MIMEText(body, subtype, "utf-8")

    message["to"] = to
    message["subject"] = subject
    if cc:
        message["cc"] = cc
    if bcc:
        message["bcc"] = bcc
    for k, v in extra_headers.items():
        message[k] = v
    return message


@api_call
def gmail_search(args):
    service = build_service("gmail", "v1")
    results = service.users().messages().list(
        userId="me", q=args.query, maxResults=args.max
    ).execute()
    messages = results.get("messages", [])
    if not messages:
        print_json([])
        return

    if args.format == "ids":
        print("\n".join(m["id"] for m in messages))
        return

    output = []
    for msg_meta in messages:
        msg = service.users().messages().get(
            userId="me", id=msg_meta["id"], format="metadata",
            metadataHeaders=["From", "To", "Subject", "Date"],
        ).execute()
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        output.append({
            "id": msg["id"],
            "threadId": msg["threadId"],
            "from": headers.get("From", ""),
            "to": headers.get("To", ""),
            "subject": headers.get("Subject", ""),
            "date": headers.get("Date", ""),
            "snippet": msg.get("snippet", ""),
            "labels": msg.get("labelIds", []),
        })
    print_json(output)


@api_call
def gmail_get(args):
    service = build_service("gmail", "v1")
    msg = service.users().messages().get(
        userId="me", id=args.message_id, format="full"
    ).execute()

    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
    body = _extract_gmail_body(msg.get("payload", {}))

    result = {
        "id": msg["id"],
        "threadId": msg["threadId"],
        "from": headers.get("From", ""),
        "to": headers.get("To", ""),
        "cc": headers.get("Cc", ""),
        "subject": headers.get("Subject", ""),
        "date": headers.get("Date", ""),
        "labels": msg.get("labelIds", []),
        "body": body,
    }

    if args.format == "text":
        print(f"From: {result['from']}\nTo: {result['to']}\nDate: {result['date']}\nSubject: {result['subject']}\n\n{body}")
    elif args.format == "markdown":
        print(
            f"# {result['subject']}\n\n"
            f"- **From:** {result['from']}\n"
            f"- **To:** {result['to']}\n"
            f"- **Date:** {result['date']}\n"
            f"- **Labels:** {', '.join(result['labels'])}\n\n"
            f"---\n\n{body}"
        )
    else:
        print_json(result)


@api_call
def gmail_send(args):
    service = build_service("gmail", "v1")
    message = _build_mime_message(
        to=args.to,
        subject=args.subject,
        body=args.body,
        html=args.html,
        cc=args.cc,
        bcc=args.bcc,
        attachments=args.attachment or [],
    )
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body = {"raw": raw}
    if args.thread_id:
        body["threadId"] = args.thread_id
    result = service.users().messages().send(userId="me", body=body).execute()
    print_json({"status": "sent", "id": result["id"], "threadId": result.get("threadId", "")})


@api_call
def gmail_reply(args):
    service = build_service("gmail", "v1")
    original = service.users().messages().get(
        userId="me", id=args.message_id, format="metadata",
        metadataHeaders=["From", "Subject", "Message-ID"],
    ).execute()
    headers = {h["name"]: h["value"] for h in original.get("payload", {}).get("headers", [])}

    subject = headers.get("Subject", "")
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    extra = {}
    if headers.get("Message-ID"):
        extra["In-Reply-To"] = headers["Message-ID"]
        extra["References"] = headers["Message-ID"]

    message = _build_mime_message(
        to=headers.get("From", ""),
        subject=subject,
        body=args.body,
        html=args.html,
        attachments=args.attachment or [],
        extra_headers=extra,
    )
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body = {"raw": raw, "threadId": original["threadId"]}
    result = service.users().messages().send(userId="me", body=body).execute()
    print_json({"status": "sent", "id": result["id"], "threadId": result.get("threadId", "")})


@api_call
def gmail_labels(args):
    service = build_service("gmail", "v1")
    results = service.users().labels().list(userId="me").execute()
    labels = [{"id": l["id"], "name": l["name"], "type": l.get("type", "")} for l in results.get("labels", [])]
    print_json(labels)


@api_call
def gmail_modify(args):
    service = build_service("gmail", "v1")
    body = {}
    if args.add_labels:
        body["addLabelIds"] = args.add_labels.split(",")
    if args.remove_labels:
        body["removeLabelIds"] = args.remove_labels.split(",")
    result = service.users().messages().modify(userId="me", id=args.message_id, body=body).execute()
    print_json({"id": result["id"], "labels": result.get("labelIds", [])})


# =========================================================================
# Calendar
# =========================================================================

def _ensure_rfc3339_z_if_naive(iso: str) -> str:
    """Append Z for datetimes that omit a timezone (Calendar API expects RFC3339)."""
    if "T" not in iso:
        return iso
    if "Z" in iso:
        return iso
    t_idx = iso.index("T")
    tail = iso[t_idx + 1 :]
    if "+" in tail or "-" in tail:
        return iso
    return iso + "Z"


_DURATION_RE = re.compile(r"^(?:(\d+)h)?(?:(\d+)m)?$")


def _parse_duration(text: str) -> timedelta:
    """Parse '1h', '30m', '1h30m' (case-insensitive) into a timedelta."""
    if not text:
        raise ValueError("empty duration")
    m = _DURATION_RE.fullmatch(text.strip().lower())
    if not m or (not m.group(1) and not m.group(2)):
        raise ValueError(f"Invalid duration {text!r}; expected '<H>h', '<M>m' or '<H>h<M>m'")
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    return timedelta(hours=hours, minutes=minutes)


def _add_to_iso(start_iso: str, delta: timedelta) -> str:
    """Add a timedelta to an ISO-8601 datetime string while preserving tz info."""
    # Python <3.11 doesn't accept trailing Z in fromisoformat.
    text = start_iso.replace("Z", "+00:00") if start_iso.endswith("Z") else start_iso
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as e:
        raise ValueError(f"--start is not a valid ISO 8601 datetime: {start_iso!r}") from e
    end = dt + delta
    iso = end.isoformat()
    return iso.replace("+00:00", "Z") if start_iso.endswith("Z") else iso


@api_call
def calendar_list(args):
    service = build_service("calendar", "v3")
    now = datetime.now(timezone.utc)
    time_min = _ensure_rfc3339_z_if_naive(args.start or now.isoformat())
    time_max = _ensure_rfc3339_z_if_naive(args.end or (now + timedelta(days=7)).isoformat())

    results = service.events().list(
        calendarId=args.calendar, timeMin=time_min, timeMax=time_max,
        maxResults=args.max, singleEvents=True, orderBy="startTime",
    ).execute()

    events = []
    for e in results.get("items", []):
        events.append({
            "id": e["id"],
            "summary": e.get("summary", "(no title)"),
            "start": e.get("start", {}).get("dateTime", e.get("start", {}).get("date", "")),
            "end": e.get("end", {}).get("dateTime", e.get("end", {}).get("date", "")),
            "location": e.get("location", ""),
            "description": e.get("description", ""),
            "status": e.get("status", ""),
            "htmlLink": e.get("htmlLink", ""),
        })
    print_json(events)


@api_call
def calendar_create(args):
    service = build_service("calendar", "v3")
    if not args.end and not args.duration:
        raise SystemExit("calendar create requires --end or --duration")
    end = args.end or _add_to_iso(args.start, _parse_duration(args.duration))
    event = {
        "summary": args.summary,
        "start": {"dateTime": args.start},
        "end": {"dateTime": end},
    }
    if args.location:
        event["location"] = args.location
    if args.description:
        event["description"] = args.description
    if args.attendees:
        event["attendees"] = [{"email": e.strip()} for e in args.attendees.split(",")]

    result = service.events().insert(
        calendarId=args.calendar,
        body=event,
        sendUpdates="all" if args.attendees else "none",
    ).execute()
    print_json({
        "status": "created",
        "id": result["id"],
        "summary": result.get("summary", ""),
        "start": event["start"]["dateTime"],
        "end": event["end"]["dateTime"],
        "htmlLink": result.get("htmlLink", ""),
    })


@api_call
def calendar_update(args):
    service = build_service("calendar", "v3")
    patch: dict = {}
    if args.summary:
        patch["summary"] = args.summary
    if args.location:
        patch["location"] = args.location
    if args.description:
        patch["description"] = args.description
    if args.start:
        patch["start"] = {"dateTime": args.start}
    if args.end:
        patch["end"] = {"dateTime": args.end}
    elif args.duration:
        if not args.start:
            existing = service.events().get(calendarId=args.calendar, eventId=args.event_id).execute()
            start_iso = existing.get("start", {}).get("dateTime") or existing.get("start", {}).get("date", "")
        else:
            start_iso = args.start
        patch["end"] = {"dateTime": _add_to_iso(start_iso, _parse_duration(args.duration))}
    if args.attendees is not None:
        patch["attendees"] = (
            [{"email": e.strip()} for e in args.attendees.split(",") if e.strip()]
            if args.attendees else []
        )

    if not patch:
        raise SystemExit("calendar update requires at least one field to change")

    result = service.events().patch(
        calendarId=args.calendar,
        eventId=args.event_id,
        body=patch,
        sendUpdates="all" if "attendees" in patch else "none",
    ).execute()
    print_json({
        "status": "updated",
        "id": result["id"],
        "summary": result.get("summary", ""),
        "htmlLink": result.get("htmlLink", ""),
    })


@api_call
def calendar_delete(args):
    service = build_service("calendar", "v3")
    service.events().delete(
        calendarId=args.calendar,
        eventId=args.event_id,
        sendUpdates="all" if args.notify else "none",
    ).execute()
    print_json({"status": "deleted", "eventId": args.event_id})


# =========================================================================
# Tasks
# =========================================================================

@api_call
def tasks_tasklists(args):
    service = build_service("tasks", "v1")
    items = service.tasklists().list().execute().get("items", [])
    out = [{"id": x["id"], "title": x.get("title", ""), "updated": x.get("updated", "")} for x in items]
    print_json(out)


@api_call
def tasks_list(args):
    service = build_service("tasks", "v1")
    results = service.tasks().list(
        tasklist=args.tasklist,
        maxResults=args.max,
        showCompleted=args.show_completed,
    ).execute()
    items = results.get("items", [])
    out = []
    for t in items:
        out.append({
            "id": t.get("id", ""),
            "title": t.get("title", ""),
            "notes": t.get("notes", ""),
            "status": t.get("status", ""),
            "due": t.get("due", ""),
            "updated": t.get("updated", ""),
        })
    print_json(out)


@api_call
def tasks_add(args):
    service = build_service("tasks", "v1")
    body = {"title": args.title}
    if args.notes:
        body["notes"] = args.notes
    task = service.tasks().insert(tasklist=args.tasklist, body=body).execute()
    if args.due:
        task = service.tasks().patch(
            tasklist=args.tasklist,
            task=task["id"],
            body={"due": args.due},
        ).execute()
    print_json(task)


@api_call
def tasks_complete(args):
    service = build_service("tasks", "v1")
    task = service.tasks().patch(
        tasklist=args.tasklist,
        task=args.task,
        body={"status": "completed"},
    ).execute()
    print_json({"status": "completed", "id": task.get("id"), "title": task.get("title")})


# =========================================================================
# Drive
# =========================================================================

@api_call
def drive_search(args):
    service = build_service("drive", "v3")
    query = f"fullText contains '{args.query}'" if not args.raw_query else args.query
    results = service.files().list(
        q=query, pageSize=args.max, fields="files(id, name, mimeType, modifiedTime, webViewLink)",
    ).execute()
    print_json(results.get("files", []))


# =========================================================================
# Contacts
# =========================================================================

@api_call
def contacts_list(args):
    service = build_service("people", "v1")
    results = service.people().connections().list(
        resourceName="people/me",
        pageSize=args.max,
        personFields="names,emailAddresses,phoneNumbers",
    ).execute()
    contacts = []
    for person in results.get("connections", []):
        names = person.get("names", [{}])
        emails = person.get("emailAddresses", [])
        phones = person.get("phoneNumbers", [])
        name = names[0].get("displayName", "") if names else ""
        if args.name and args.name.lower() not in name.lower():
            continue
        contacts.append({
            "name": name,
            "emails": [e.get("value", "") for e in emails],
            "phones": [p.get("value", "") for p in phones],
        })
    print_json(contacts)


# =========================================================================
# Sheets
# =========================================================================

@api_call
def sheets_get(args):
    service = build_service("sheets", "v4")
    result = service.spreadsheets().values().get(
        spreadsheetId=args.sheet_id, range=args.range,
    ).execute()
    print_json(result.get("values", []))


@api_call
def sheets_update(args):
    service = build_service("sheets", "v4")
    values = json.loads(args.values)
    body = {"values": values}
    result = service.spreadsheets().values().update(
        spreadsheetId=args.sheet_id, range=args.range,
        valueInputOption="USER_ENTERED", body=body,
    ).execute()
    print_json({
        "updatedCells": result.get("updatedCells", 0),
        "updatedRange": result.get("updatedRange", ""),
    })


@api_call
def sheets_append(args):
    service = build_service("sheets", "v4")
    values = json.loads(args.values)
    body = {"values": values}
    result = service.spreadsheets().values().append(
        spreadsheetId=args.sheet_id, range=args.range,
        valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS", body=body,
    ).execute()
    print_json({"updatedCells": result.get("updates", {}).get("updatedCells", 0)})


# =========================================================================
# Docs
# =========================================================================

@api_call
def docs_get(args):
    service = build_service("docs", "v1")
    doc = service.documents().get(documentId=args.doc_id).execute()
    text_parts = []
    for element in doc.get("body", {}).get("content", []):
        paragraph = element.get("paragraph", {})
        for pe in paragraph.get("elements", []):
            text_run = pe.get("textRun", {})
            if text_run.get("content"):
                text_parts.append(text_run["content"])
    print_json({
        "title": doc.get("title", ""),
        "documentId": doc.get("documentId", ""),
        "body": "".join(text_parts),
    })


# =========================================================================
# CLI parser
# =========================================================================

def main():
    parser = argparse.ArgumentParser(
        prog="gws",
        description="Google Workspace API CLI (Gmail, Calendar, Tasks, Sheets, Docs, Drive, Contacts)",
    )
    try:
        from . import __version__ as pkg_version  # type: ignore
    except ImportError:
        pkg_version = "dev"
    parser.add_argument("--version", action="version", version=f"gws {pkg_version}")
    sub = parser.add_subparsers(dest="service", required=True)

    # --- Gmail ---
    gmail = sub.add_parser("gmail")
    gmail_sub = gmail.add_subparsers(dest="action", required=True)

    p = gmail_sub.add_parser("search")
    p.add_argument("query", help="Gmail search query (e.g. 'is:unread')")
    p.add_argument("--max", type=int, default=10)
    p.add_argument(
        "--format",
        choices=["json", "ids"],
        default="json",
        help="json (default) returns message metadata; ids returns newline-separated message IDs",
    )
    p.set_defaults(func=gmail_search)

    p = gmail_sub.add_parser("get")
    p.add_argument("message_id")
    p.add_argument(
        "--format",
        choices=["json", "text", "markdown"],
        default="json",
        help="Output format (default json; markdown is easy for agents to summarize)",
    )
    p.set_defaults(func=gmail_get)

    p = gmail_sub.add_parser("send")
    p.add_argument("--to", required=True)
    p.add_argument("--subject", required=True)
    p.add_argument("--body", required=True)
    p.add_argument("--cc", default="")
    p.add_argument("--bcc", default="")
    p.add_argument("--html", action="store_true", help="Send body as HTML")
    p.add_argument("--thread-id", default="", help="Thread ID for threading")
    p.add_argument(
        "--attachment",
        action="append",
        default=[],
        help="Path to a file to attach (repeatable)",
    )
    p.set_defaults(func=gmail_send)

    p = gmail_sub.add_parser("reply")
    p.add_argument("message_id", help="Message ID to reply to")
    p.add_argument("--body", required=True)
    p.add_argument("--html", action="store_true")
    p.add_argument("--attachment", action="append", default=[])
    p.set_defaults(func=gmail_reply)

    p = gmail_sub.add_parser("labels")
    p.set_defaults(func=gmail_labels)

    p = gmail_sub.add_parser("modify")
    p.add_argument("message_id")
    p.add_argument("--add-labels", default="", help="Comma-separated label IDs to add")
    p.add_argument("--remove-labels", default="", help="Comma-separated label IDs to remove")
    p.set_defaults(func=gmail_modify)

    # --- Calendar ---
    cal = sub.add_parser("calendar")
    cal_sub = cal.add_subparsers(dest="action", required=True)

    p = cal_sub.add_parser("list")
    p.add_argument("--start", default="", help="Start time (ISO 8601)")
    p.add_argument("--end", default="", help="End time (ISO 8601)")
    p.add_argument("--max", type=int, default=25)
    p.add_argument("--calendar", default="primary")
    p.set_defaults(func=calendar_list)

    p = cal_sub.add_parser("create")
    p.add_argument("--summary", required=True)
    p.add_argument("--start", required=True, help="Start (ISO 8601 with timezone)")
    p.add_argument("--end", default="", help="End (ISO 8601 with timezone); or pass --duration")
    p.add_argument("--duration", default="", help="Friendly length: 30m, 1h, 1h30m")
    p.add_argument("--location", default="")
    p.add_argument("--description", default="")
    p.add_argument("--attendees", default="", help="Comma-separated email addresses")
    p.add_argument("--calendar", default="primary")
    p.set_defaults(func=calendar_create)

    p = cal_sub.add_parser("update")
    p.add_argument("event_id")
    p.add_argument("--summary", default="")
    p.add_argument("--start", default="")
    p.add_argument("--end", default="")
    p.add_argument("--duration", default="")
    p.add_argument("--location", default="")
    p.add_argument("--description", default="")
    p.add_argument(
        "--attendees",
        default=None,
        help="Comma-separated emails; pass empty string to clear",
    )
    p.add_argument("--calendar", default="primary")
    p.set_defaults(func=calendar_update)

    p = cal_sub.add_parser("delete")
    p.add_argument("event_id")
    p.add_argument("--calendar", default="primary")
    p.add_argument("--notify", action="store_true", help="Notify attendees of cancellation")
    p.set_defaults(func=calendar_delete)

    # --- Tasks ---
    tsk = sub.add_parser("tasks")
    tsk_sub = tsk.add_subparsers(dest="action", required=True)

    p = tsk_sub.add_parser("tasklists")
    p.set_defaults(func=tasks_tasklists)

    p = tsk_sub.add_parser("list")
    p.add_argument("--tasklist", required=True, help="Task list id (from tasks tasklists)")
    p.add_argument("--max", type=int, default=100)
    p.add_argument(
        "--show-completed",
        action="store_true",
        help="Include completed tasks (default: incomplete only)",
    )
    p.set_defaults(func=tasks_list)

    p = tsk_sub.add_parser("add")
    p.add_argument("--tasklist", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--notes", default="")
    p.add_argument(
        "--due",
        default="",
        help="RFC3339 due datetime, e.g. 2026-04-20T00:00:00.000Z (uses insert+patch)",
    )
    p.set_defaults(func=tasks_add)

    p = tsk_sub.add_parser("complete")
    p.add_argument("--tasklist", required=True)
    p.add_argument("--task", required=True, help="Task id from tasks list")
    p.set_defaults(func=tasks_complete)

    # --- Drive ---
    drv = sub.add_parser("drive")
    drv_sub = drv.add_subparsers(dest="action", required=True)

    p = drv_sub.add_parser("search")
    p.add_argument("query")
    p.add_argument("--max", type=int, default=10)
    p.add_argument("--raw-query", action="store_true", help="Use query as raw Drive API query")
    p.set_defaults(func=drive_search)

    # --- Contacts ---
    con = sub.add_parser("contacts")
    con_sub = con.add_subparsers(dest="action", required=True)

    p = con_sub.add_parser("list")
    p.add_argument("--max", type=int, default=50)
    p.add_argument("--name", default="", help="Case-insensitive substring filter on display name")
    p.set_defaults(func=contacts_list)

    # --- Sheets ---
    sh = sub.add_parser("sheets")
    sh_sub = sh.add_subparsers(dest="action", required=True)

    p = sh_sub.add_parser("get")
    p.add_argument("sheet_id")
    p.add_argument("range")
    p.set_defaults(func=sheets_get)

    p = sh_sub.add_parser("update")
    p.add_argument("sheet_id")
    p.add_argument("range")
    p.add_argument("--values", required=True, help="JSON array of arrays")
    p.set_defaults(func=sheets_update)

    p = sh_sub.add_parser("append")
    p.add_argument("sheet_id")
    p.add_argument("range")
    p.add_argument("--values", required=True, help="JSON array of arrays")
    p.set_defaults(func=sheets_append)

    # --- Docs ---
    docs = sub.add_parser("docs")
    docs_sub = docs.add_subparsers(dest="action", required=True)

    p = docs_sub.add_parser("get")
    p.add_argument("doc_id")
    p.set_defaults(func=docs_get)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
