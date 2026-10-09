

#!/usr/bin/env python3
"""
Export user queries to an Excel workbook (read-only).

Both sheets only include users whose username starts with the company prefix
(case-insensitive, default: MMA), e.g. MMA001, MMA002 -> MMA.

Sheet 1 - "<PREFIX> User Query Summary":
    S.No | Username | Date | No. of Queries
    Query count per user per date, summed across all of that user's chats.

Sheet 2 - "All User Queries":
    S.No | Username | Email | Date | Query
    Every query asked by the prefix's users, one row per query.

Default date range is the latest week: today and the 6 days before it.
--from / --to override it.

Queries are read from chat_sessions.messages (JSONB) joined to users. The SQL
only fetches sessions of the prefix's users updated on/after --from, so the
whole table is not transferred on every run.
The database is opened in a READ ONLY transaction - nothing is written.

After the workbook is written it is emailed as an attachment via SMTP.
Recipients come from --email-to, else REPORT_EMAIL_TO in .env (comma-separated).
SMTP credentials come from REPORT_SMTP_* in .env. Use --no-email to skip.

Usage:
    python scripts/export_user_queries.py
    python scripts/export_user_queries.py --from 2026-09-01 --to 2026-09-30
    python scripts/export_user_queries.py --output reports/queries.xlsx
    python scripts/export_user_queries.py --prefix DOL
    python scripts/export_user_queries.py --email-to "a@example.com,b@example.com"
    python scripts/export_user_queries.py --no-email
"""

import argparse
import asyncio
import json
import re
import smtplib
import ssl
import sys
from email.message import EmailMessage
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path so config.py (and .env settings) can be loaded
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
import pandas as pd
from openpyxl.styles import Alignment, Font

from config import settings


DEFAULT_PREFIX = "MMA"
DEFAULT_RANGE_DAYS = 7
DETAIL_SHEET = "All User Queries"
EXCEL_CELL_LIMIT = 32767
XLSX_MIME = ("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet")
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024  # Gmail attachment limit
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s.]+(?:\.[^@\s.]+)+$")

QUERY_SQL = """
    SELECT
        u.user_name,
        u.name,
        u.email,
        cs.session_id,
        cs.created_at,
        cs.messages
    FROM public.chat_sessions cs
    INNER JOIN public.users u
        ON u.id = cs.user_id
    WHERE BTRIM(COALESCE(NULLIF(u.user_name, ''), u.name, '')) ILIKE $1
      AND cs.updated_at >= $2::date
"""


def _parse_date_arg(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date '{value}'. Use YYYY-MM-DD.")


def _load_messages(raw: Any) -> List[Dict[str, Any]]:
    """Normalize chat_sessions.messages into a list of dicts (handles JSON strings)."""
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []

    messages: List[Dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            try:
                item = json.loads(item)
            except json.JSONDecodeError:
                continue
        if isinstance(item, dict):
            messages.append(item)
    return messages


def _extract_query_text(msg: Dict[str, Any]) -> Optional[str]:
    """Return the user's question text, or None if this message is not a user query."""
    if msg.get("role") == "user":
        text = msg.get("content")
    elif "question" in msg and "role" not in msg:
        # Legacy message format: {"question": ..., "response": ...}
        text = msg.get("question")
    else:
        return None

    if text is None:
        return None
    text = str(text).strip()
    return text or None


def _message_date(msg: Dict[str, Any], session_created_at: Optional[datetime]) -> Optional[date]:
    """Date exactly as stored: YYYY-MM-DD part of the message timestamp, else session created_at."""
    ts = msg.get("timestamp")
    if ts:
        try:
            return date.fromisoformat(str(ts)[:10])
        except ValueError:
            pass
    if session_created_at is not None:
        return session_created_at.date()
    return None


def _like_prefix_pattern(prefix: str) -> str:
    """ILIKE pattern matching usernames that start with prefix (LIKE wildcards escaped)."""
    return re.sub(r"([\\%_])", r"\\\1", prefix) + "%"


async def fetch_query_records(prefix: str, date_from: date) -> List[Dict[str, Any]]:
    """
    Read only sessions of the prefix's users that were updated on/after date_from.

    updated_at is never earlier than the newest message's date, so sessions last
    updated before date_from cannot hold queries in range. Exact per-message date
    and prefix filtering is still done afterwards in Python.
    """
    conn = await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
    )
    try:
        async with conn.transaction(readonly=True):
            rows = await conn.fetch(QUERY_SQL, _like_prefix_pattern(prefix), date_from)
    finally:
        await conn.close()

    records: List[Dict[str, Any]] = []
    for row in rows:
        username = (row["user_name"] or row["name"] or "").strip()
        email = row["email"] or ""
        created_at = row["created_at"]

        for msg in _load_messages(row["messages"]):
            query = _extract_query_text(msg)
            if query is None:
                continue
            msg_date = _message_date(msg, created_at)
            records.append(
                {
                    "username": username,
                    "email": email,
                    "date": msg_date,
                    "sort_ts": str(msg.get("timestamp") or created_at or ""),
                    "query": query[:EXCEL_CELL_LIMIT],
                }
            )
    return records


def filter_by_date(
    records: List[Dict[str, Any]], date_from: Optional[date], date_to: Optional[date]
) -> List[Dict[str, Any]]:
    if not date_from and not date_to:
        return records
    filtered = []
    for r in records:
        d = r["date"]
        if d is None:
            continue
        if date_from and d < date_from:
            continue
        if date_to and d > date_to:
            continue
        filtered.append(r)
    return filtered


def filter_by_prefix(records: List[Dict[str, Any]], prefix: str) -> List[Dict[str, Any]]:
    """Keep only records whose username starts with the company prefix (case-insensitive)."""
    prefix_upper = prefix.upper()
    return [r for r in records if r["username"].upper().startswith(prefix_upper)]


def summary_sheet_name(prefix: str) -> str:
    # Excel sheet names are limited to 31 characters
    return f"{prefix} User Query Summary"[:31]


def build_summary_df(records: List[Dict[str, Any]]) -> pd.DataFrame:
    columns = ["S.No", "Username", "Date", "No. of Queries"]
    matched = [r for r in records if r["date"] is not None]
    if not matched:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(matched)
    summary = (
        df.groupby(["username", "date"])
        .size()
        .reset_index(name="No. of Queries")
        .sort_values(["username", "date"])
        .reset_index(drop=True)
    )
    summary.insert(0, "S.No", range(1, len(summary) + 1))
    summary = summary.rename(columns={"username": "Username", "date": "Date"})
    return summary[columns]


def build_detail_df(records: List[Dict[str, Any]]) -> pd.DataFrame:
    columns = ["S.No", "Username", "Email", "Date", "Query"]
    if not records:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(records).sort_values(["username", "sort_ts"]).reset_index(drop=True)
    df.insert(0, "S.No", range(1, len(df) + 1))
    df = df.rename(
        columns={"username": "Username", "email": "Email", "date": "Date", "query": "Query"}
    )
    return df[columns]


def _format_sheet(worksheet, column_widths: Dict[str, int], wrap_columns: List[str]) -> None:
    worksheet.freeze_panes = "A2"
    for cell in worksheet[1]:
        cell.font = Font(bold=True)

    for col_letter, width in column_widths.items():
        worksheet.column_dimensions[col_letter].width = width

    for col_letter in wrap_columns:
        for cell in worksheet[col_letter][1:]:
            cell.alignment = Alignment(wrap_text=True, vertical="top")


def write_excel(
    summary_df: pd.DataFrame, detail_df: pd.DataFrame, output_path: Path, summary_sheet: str
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl", date_format="YYYY-MM-DD") as writer:
        summary_df.to_excel(writer, sheet_name=summary_sheet, index=False)
        detail_df.to_excel(writer, sheet_name=DETAIL_SHEET, index=False)

        _format_sheet(
            writer.sheets[summary_sheet],
            {"A": 8, "B": 28, "C": 14, "D": 16},
            wrap_columns=[],
        )
        _format_sheet(
            writer.sheets[DETAIL_SHEET],
            {"A": 8, "B": 28, "C": 34, "D": 14, "E": 90},
            wrap_columns=["E"],
        )


def parse_recipients(value: str) -> List[str]:
    """Split a comma/semicolon-separated recipient string into a de-duplicated list."""
    recipients: List[str] = []
    for part in re.split(r"[,;]", value or ""):
        addr = part.strip()
        if addr and addr.lower() not in (r.lower() for r in recipients):
            recipients.append(addr)
    return recipients


def send_report_email(attachment: Path, recipients: List[str], subject: str, body: str) -> None:
    """Email the report as an attachment using the REPORT_SMTP_* settings. Raises on failure."""
    invalid = [r for r in recipients if not EMAIL_PATTERN.match(r)]
    if invalid:
        raise ValueError(f"invalid recipient address(es): {', '.join(invalid)}")

    username = settings.report_smtp_username
    password = settings.report_smtp_password
    if not username or not password:
        raise ValueError("REPORT_SMTP_USERNAME and REPORT_SMTP_PASSWORD must be set in .env")

    size = attachment.stat().st_size
    if size > MAX_ATTACHMENT_BYTES:
        raise ValueError(
            f"attachment is {size / 1024 / 1024:.1f} MB, over the "
            f"{MAX_ATTACHMENT_BYTES // 1024 // 1024} MB limit; narrow the date range"
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.report_email_from or username
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)
    msg.add_attachment(
        attachment.read_bytes(),
        maintype=XLSX_MIME[0],
        subtype=XLSX_MIME[1],
        filename=attachment.name,
    )

    host, port = settings.report_smtp_host, settings.report_smtp_port
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=60) as server:
            server.login(username, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=60) as server:
            server.starttls(context=context)
            server.login(username, password)
            server.send_message(msg)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export user queries (prefix summary + all queries) to Excel. Read-only."
    )
    parser.add_argument(
        "--prefix", default=DEFAULT_PREFIX,
        help=f"Username prefix for the summary sheet, case-insensitive. Default: {DEFAULT_PREFIX}.",
    )
    parser.add_argument(
        "--from", dest="date_from", type=_parse_date_arg, default=None,
        help="Start date, inclusive (YYYY-MM-DD). Default: 6 days before --to.",
    )
    parser.add_argument(
        "--to", dest="date_to", type=_parse_date_arg, default=None,
        help="End date, inclusive (YYYY-MM-DD). Default: today.",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Output .xlsx path. Default: user_queries_report_<timestamp>.xlsx in the current directory.",
    )
    parser.add_argument(
        "--email-to", default=None,
        help="Comma-separated recipient emails. Default: REPORT_EMAIL_TO from .env.",
    )
    parser.add_argument(
        "--no-email", action="store_true",
        help="Generate the Excel file only; do not send an email.",
    )
    args = parser.parse_args()

    # Default reporting period is the latest week; --from / --to override either end.
    if args.date_to is None:
        args.date_to = date.today()
    if args.date_from is None:
        args.date_from = args.date_to - timedelta(days=DEFAULT_RANGE_DAYS - 1)
    if args.date_from > args.date_to:
        parser.error(f"--from ({args.date_from}) must be on or before --to ({args.date_to})")
    if args.no_email and args.email_to:
        parser.error("--email-to cannot be used with --no-email")
    if args.output is None:
        args.output = Path(f"user_queries_report_{datetime.now():%Y%m%d_%H%M%S}.xlsx")
    return args


async def main() -> int:
    args = parse_args()
    prefix = args.prefix.upper()
    # Same period for the Excel report and the email
    from_date, to_date = args.date_from, args.date_to
    range_text = f"{from_date} to {to_date}"

    print(f"Reading user queries from {settings.db_host}:{settings.db_port}/{settings.db_name} (read-only)...")
    try:
        records = await fetch_query_records(prefix, from_date)
    except Exception as e:
        print(f"ERROR: could not read from the database: {e}")
        return 1

    records = filter_by_date(records, from_date, to_date)
    records = filter_by_prefix(records, prefix)
    if not records:
        print(f"No {prefix} user queries found for {range_text}. No file written.")
        return 0

    summary_sheet = summary_sheet_name(prefix)
    summary_df = build_summary_df(records)
    detail_df = build_detail_df(records)
    try:
        write_excel(summary_df, detail_df, args.output, summary_sheet)
    except Exception as e:
        print(f"ERROR: Excel report generation failed: {e}")
        print("Email not sent.")
        return 1

    summary_users = summary_df["Username"].nunique() if not summary_df.empty else 0
    print("SUCCESS: Excel report generated.")
    print(f"Date range  : {range_text}")
    print(f"Prefix      : {prefix} ({summary_users} users)")
    print(f"Sheet 1     : '{summary_sheet}' - {len(summary_df)} rows")
    print(f"Sheet 2     : '{DETAIL_SHEET}' - {len(detail_df)} rows")
    print(f"Saved to    : {args.output.resolve()}")

    if args.no_email:
        print("Email skipped (--no-email).")
        return 0

    recipients = parse_recipients(
        args.email_to if args.email_to is not None else settings.report_email_to
    )
    if not recipients:
        print("ERROR: email not sent: no recipients. Set REPORT_EMAIL_TO in .env or pass --email-to.")
        return 1

    subject = f"{prefix} Weekly User Query Report: {range_text}"
    body = (
        "Hi,\n\n"
        f"Please find attached the *weekly Dolphin usage report for MASSA* for your reference.\n\n"
        f"The report provides a details of Dolphin usage by users during the reporting period{range_text}\n\n"
        "Regards\n"
        "Team Dolphin AI\n"
    )

    print(f"Sending report to {', '.join(recipients)} via {settings.report_smtp_host}:{settings.report_smtp_port}...")
    try:
        send_report_email(args.output, recipients, subject, body)
    except smtplib.SMTPAuthenticationError:
        print(
            "ERROR: email not sent: SMTP authentication failed. For Gmail, set REPORT_SMTP_PASSWORD "
            "to an App Password (requires 2-Step Verification), not your account password."
        )
        return 1
    except Exception as e:
        print(f"ERROR: email not sent: {e}")
        return 1

    print(f"SUCCESS: report emailed to {', '.join(recipients)}.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))


