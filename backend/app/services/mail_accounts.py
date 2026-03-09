"""IMAP/SMTP account management and live sync services for native client."""
import email
import imaplib
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from typing import Optional

import requests

from app.database import get_db
from app.logging_config import get_logger

log = get_logger("mail-accounts")


@dataclass
class MailAccount:
    id: int
    display_name: str
    email_address: str
    imap_host: str
    imap_port: int
    imap_security: str
    imap_username: str
    imap_password: Optional[str]
    smtp_host: str
    smtp_port: int
    smtp_security: str
    smtp_username: str
    smtp_password: Optional[str]
    oauth_provider: Optional[str]
    oauth_client_id: Optional[str]
    oauth_client_secret: Optional[str]
    oauth_refresh_token: Optional[str]
    oauth_access_token: Optional[str]
    oauth_token_url: Optional[str]
    oauth_expires_at: Optional[str]
    enabled: bool


def _to_account(row) -> MailAccount:
    return MailAccount(**dict(row))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def list_accounts() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM mail_accounts
            ORDER BY created_at DESC
            """
        ).fetchall()
    return [public_account(_to_account(r)) for r in rows]


def get_account(account_id: int) -> Optional[MailAccount]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM mail_accounts WHERE id = ?", (account_id,)).fetchone()
    return _to_account(row) if row else None


def create_account(payload: dict) -> dict:
    required = [
        "display_name",
        "email_address",
        "imap_host",
        "imap_username",
        "smtp_host",
        "smtp_username",
    ]
    missing = [k for k in required if not payload.get(k)]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    imap_port = int(payload.get("imap_port") or 993)
    smtp_port = int(payload.get("smtp_port") or 587)

    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO mail_accounts (
                display_name, email_address,
                imap_host, imap_port, imap_security, imap_username, imap_password,
                smtp_host, smtp_port, smtp_security, smtp_username, smtp_password,
                oauth_provider, oauth_client_id, oauth_client_secret,
                oauth_refresh_token, oauth_access_token, oauth_token_url, oauth_expires_at,
                enabled, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                payload["display_name"],
                payload["email_address"],
                payload["imap_host"],
                imap_port,
                payload.get("imap_security", "ssl"),
                payload["imap_username"],
                payload.get("imap_password"),
                payload["smtp_host"],
                smtp_port,
                payload.get("smtp_security", "starttls"),
                payload["smtp_username"],
                payload.get("smtp_password"),
                payload.get("oauth_provider"),
                payload.get("oauth_client_id"),
                payload.get("oauth_client_secret"),
                payload.get("oauth_refresh_token"),
                payload.get("oauth_access_token"),
                payload.get("oauth_token_url"),
                payload.get("oauth_expires_at"),
                1 if payload.get("enabled", True) else 0,
            ),
        )
        account_id = cur.lastrowid
    account = get_account(account_id)
    return public_account(account)


def update_account(account_id: int, payload: dict) -> dict:
    existing = get_account(account_id)
    if not existing:
        raise LookupError("Account not found")

    allowed = {
        "display_name", "email_address", "imap_host", "imap_port", "imap_security", "imap_username",
        "imap_password", "smtp_host", "smtp_port", "smtp_security", "smtp_username", "smtp_password",
        "oauth_provider", "oauth_client_id", "oauth_client_secret", "oauth_refresh_token",
        "oauth_access_token", "oauth_token_url", "oauth_expires_at", "enabled"
    }
    updates = {k: v for k, v in payload.items() if k in allowed}
    if not updates:
        return public_account(existing)

    cols = []
    params = []
    for key, value in updates.items():
        cols.append(f"{key} = ?")
        params.append(value)
    cols.append("updated_at = datetime('now')")
    params.append(account_id)

    with get_db() as conn:
        conn.execute(f"UPDATE mail_accounts SET {', '.join(cols)} WHERE id = ?", params)

    updated = get_account(account_id)
    return public_account(updated)


def delete_account(account_id: int) -> bool:
    with get_db() as conn:
        cur = conn.execute("DELETE FROM mail_accounts WHERE id = ?", (account_id,))
    return cur.rowcount > 0


def public_account(account: Optional[MailAccount]) -> dict:
    if not account:
        return {}
    imap_host = account.imap_host or ""
    smtp_host = account.smtp_host or ""
    imap_username = account.imap_username or ""
    smtp_username = account.smtp_username or ""
    return {
        "id": account.id,
        "display_name": account.display_name,
        "email_address": account.email_address,
        "imap": {
            "host": imap_host,
            "port": int(account.imap_port or 993),
            "security": account.imap_security or "ssl",
            "username": imap_username,
        },
        "smtp": {
            "host": smtp_host,
            "port": int(account.smtp_port or 587),
            "security": account.smtp_security or "starttls",
            "username": smtp_username,
        },
        "oauth_provider": account.oauth_provider,
        "enabled": bool(account.enabled),
    }


def _xoauth2_string(username: str, access_token: str) -> bytes:
    # https://developers.google.com/gmail/imap/xoauth2-protocol
    return f"user={username}\x01auth=Bearer {access_token}\x01\x01".encode("utf-8")


def _refresh_oauth_token(account: MailAccount) -> Optional[str]:
    if not account.oauth_refresh_token or not account.oauth_token_url or not account.oauth_client_id:
        return account.oauth_access_token

    # Refresh only when missing/expired.
    expires_at = _parse_iso(account.oauth_expires_at)
    if account.oauth_access_token and expires_at and expires_at > datetime.now(timezone.utc):
        return account.oauth_access_token

    payload = {
        "grant_type": "refresh_token",
        "refresh_token": account.oauth_refresh_token,
        "client_id": account.oauth_client_id,
    }
    if account.oauth_client_secret:
        payload["client_secret"] = account.oauth_client_secret

    resp = requests.post(account.oauth_token_url, data=payload, timeout=20)
    if not resp.ok:
        raise RuntimeError(f"OAuth refresh failed: {resp.status_code}")
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError("OAuth refresh response missing access_token")

    expires_in = int(data.get("expires_in", 3500))
    expires_at_dt = datetime.now(timezone.utc).timestamp() + max(60, expires_in - 60)
    expires_at_iso = datetime.fromtimestamp(expires_at_dt, tz=timezone.utc).isoformat()

    with get_db() as conn:
        conn.execute(
            "UPDATE mail_accounts SET oauth_access_token = ?, oauth_expires_at = ?, updated_at = datetime('now') WHERE id = ?",
            (token, expires_at_iso, account.id),
        )

    return token


def _imap_connect(account: MailAccount):
    security = (account.imap_security or "ssl").lower()
    if security == "ssl":
        client = imaplib.IMAP4_SSL(account.imap_host, account.imap_port)
    else:
        client = imaplib.IMAP4(account.imap_host, account.imap_port)
        if security == "starttls":
            client.starttls(ssl_context=ssl.create_default_context())

    access_token = _refresh_oauth_token(account)
    if access_token:
        client.authenticate("XOAUTH2", lambda _: _xoauth2_string(account.imap_username, access_token))
    elif account.imap_password:
        client.login(account.imap_username, account.imap_password)
    else:
        raise RuntimeError("Missing IMAP credentials (password or OAuth token)")

    return client


def _smtp_connect(account: MailAccount):
    security = (account.smtp_security or "starttls").lower()
    if security == "ssl":
        smtp = smtplib.SMTP_SSL(account.smtp_host, account.smtp_port, timeout=20)
    else:
        smtp = smtplib.SMTP(account.smtp_host, account.smtp_port, timeout=20)
        smtp.ehlo()
        if security == "starttls":
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()

    access_token = _refresh_oauth_token(account)
    if access_token:
        auth_string = _xoauth2_string(account.smtp_username, access_token)
        if hasattr(smtp, "auth"):
            smtp.auth("XOAUTH2", lambda _: auth_string)
        else:
            raise RuntimeError("SMTP XOAUTH2 not supported in this Python runtime")
    elif account.smtp_password:
        smtp.login(account.smtp_username, account.smtp_password)
    else:
        raise RuntimeError("Missing SMTP credentials (password or OAuth token)")

    return smtp


def _extract_plain_text(msg: email.message.Message) -> tuple[str, bool, list[str]]:
    has_attachments = False
    attachment_names: list[str] = []

    if msg.is_multipart():
        text_parts = []
        for part in msg.walk():
            content_disposition = (part.get("Content-Disposition") or "").lower()
            content_type = (part.get_content_type() or "").lower()
            filename = part.get_filename()
            if filename:
                attachment_names.append(filename)
                has_attachments = True
            if "attachment" in content_disposition:
                has_attachments = True
                continue
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                charset = part.get_content_charset() or "utf-8"
                try:
                    text_parts.append(payload.decode(charset, errors="replace"))
                except Exception:
                    text_parts.append(payload.decode("utf-8", errors="replace"))
        return "\n\n".join(text_parts).strip(), has_attachments, attachment_names

    payload = msg.get_payload(decode=True)
    if not payload:
        return "", has_attachments, attachment_names
    charset = msg.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace"), has_attachments, attachment_names
    except Exception:
        return payload.decode("utf-8", errors="replace"), has_attachments, attachment_names


def _as_date_fields(raw_date: Optional[str]) -> tuple[Optional[str], Optional[float]]:
    if not raw_date:
        return None, None
    try:
        dt = parsedate_to_datetime(raw_date)
        if dt is None:
            return None, None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat(), dt.timestamp()
    except Exception:
        return None, None


def _recipients_header(msg: email.message.Message) -> str:
    values = []
    for header, kind in (("To", "to"), ("Cc", "cc"), ("Bcc", "bcc")):
        raw = msg.get(header)
        if not raw:
            continue
        for name, address in getaddresses([raw]):
            if not address:
                continue
            values.append({"name": name or None, "email": address, "type": kind})
    import json
    return json.dumps(values)


def list_rules(account_id: Optional[int] = None) -> list[dict]:
    with get_db() as conn:
        if account_id is None:
            rows = conn.execute(
                "SELECT * FROM mail_rules ORDER BY account_id ASC, id ASC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM mail_rules WHERE account_id IS NULL OR account_id = ? ORDER BY account_id ASC, id ASC",
                (account_id,),
            ).fetchall()
    return [dict(r) for r in rows]


def replace_global_rules(rules: list[dict]) -> dict:
    with get_db() as conn:
        conn.execute("DELETE FROM mail_rules WHERE account_id IS NULL")
        for rule in rules:
            if not rule.get("contains"):
                continue
            conn.execute(
                """
                INSERT INTO mail_rules (account_id, enabled, name, field, contains, action, continue_evaluating, updated_at)
                VALUES (NULL, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    1 if rule.get("enabled", True) else 0,
                    rule.get("name") or "Rule",
                    rule.get("field") or "subject",
                    rule.get("contains") or "",
                    rule.get("action") or "mark_junk",
                    1 if rule.get("continue_evaluating", False) else 0,
                ),
            )
        count = conn.execute("SELECT COUNT(*) FROM mail_rules WHERE account_id IS NULL").fetchone()[0]
    return {"ok": True, "count": int(count)}


def _normalize_action(value: str) -> str:
    normalized = (value or "").strip().lower().replace("-", "_")
    mapping = {
        "markread": "mark_read",
        "mark_read": "mark_read",
        "markunread": "mark_unread",
        "mark_unread": "mark_unread",
        "markjunk": "mark_junk",
        "mark_junk": "mark_junk",
        "archive": "archive",
    }
    return mapping.get(normalized, normalized)


def _rule_haystack(field: str, subject: Optional[str], sender_name: Optional[str], sender_email: Optional[str], body_text: Optional[str]) -> str:
    f = (field or "subject").lower()
    if f == "sender":
        return f"{sender_name or ''} {sender_email or ''}".lower()
    if f == "snippet":
        return (body_text or "").lower()
    return (subject or "").lower()


def _evaluate_server_rules(account_id: int, subject: Optional[str], sender_name: Optional[str], sender_email: Optional[str], body_text: Optional[str]) -> dict:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT enabled, field, contains, action, continue_evaluating
            FROM mail_rules
            WHERE enabled = 1 AND (account_id IS NULL OR account_id = ?)
            ORDER BY account_id ASC, id ASC
            """,
            (account_id,),
        ).fetchall()

    actions = {"is_read": 0, "is_junk": 0, "is_archived": 0}
    for row in rows:
        needle = (row["contains"] or "").strip().lower()
        if not needle:
            continue
        haystack = _rule_haystack(row["field"], subject, sender_name, sender_email, body_text)
        if needle not in haystack:
            continue

        action = _normalize_action(row["action"])
        if action == "archive":
            actions["is_archived"] = 1
        elif action == "mark_read":
            actions["is_read"] = 1
        elif action == "mark_unread":
            actions["is_read"] = 0
        elif action == "mark_junk":
            actions["is_junk"] = 1

        if not bool(row["continue_evaluating"]):
            break

    return actions


def sync_account(account_id: int, folder_name: str = "INBOX", limit: int = 200) -> dict:
    account = get_account(account_id)
    if not account:
        raise LookupError("Account not found")
    if not account.enabled:
        raise RuntimeError("Account is disabled")

    folder = folder_name.strip() or "INBOX"
    with get_db() as conn:
        run_cur = conn.execute(
            "INSERT INTO mail_sync_runs (account_id, folder_name, status) VALUES (?, ?, 'running')",
            (account_id, folder),
        )
        run_id = run_cur.lastrowid

    fetched_count = 0
    inserted_count = 0
    skipped_count = 0
    max_uid_seen = 0

    try:
        with get_db() as conn:
            state_row = conn.execute(
                "SELECT last_uid FROM mail_sync_state WHERE account_id = ? AND folder_name = ?",
                (account_id, folder),
            ).fetchone()
            last_uid = int(state_row["last_uid"] if state_row else 0)

        client = _imap_connect(account)
        try:
            status, _ = client.select(folder, readonly=True)
            if status != "OK":
                raise RuntimeError(f"Cannot select folder '{folder}'")

            status, data = client.uid("search", None, f"UID {last_uid + 1}:*")
            if status != "OK":
                raise RuntimeError("IMAP UID search failed")

            all_uids = [int(v) for v in (data[0] or b"").split() if v]
            all_uids = sorted(all_uids)
            selected_uids = all_uids[-limit:]

            fetched_count = len(selected_uids)
            for uid in selected_uids:
                max_uid_seen = max(max_uid_seen, uid)
                status, msg_data = client.uid("fetch", str(uid), "(RFC822)")
                if status != "OK" or not msg_data:
                    skipped_count += 1
                    continue

                raw_bytes = None
                for part in msg_data:
                    if isinstance(part, tuple) and len(part) >= 2:
                        raw_bytes = part[1]
                        break
                if not raw_bytes:
                    skipped_count += 1
                    continue

                parsed = BytesParser(policy=policy.default).parsebytes(raw_bytes)

                message_id = (parsed.get("Message-ID") or "").strip()
                if not message_id:
                    message_id = f"<imap-{account_id}-{folder}-{uid}@quackbox.local>"

                subject = parsed.get("Subject")
                sender = getaddresses([parsed.get("From", "")])
                sender_name = sender[0][0] if sender else None
                sender_email = sender[0][1] if sender else None

                body_text, has_attachments, attachment_names = _extract_plain_text(parsed)
                date_sent, date_timestamp = _as_date_fields(parsed.get("Date"))

                import json
                headers = json.dumps({k: v for (k, v) in parsed.items()})
                recipients_json = _recipients_header(parsed)
                attachment_names_json = json.dumps(attachment_names)
                thread_id = parsed.get("In-Reply-To")
                source = f"imap:{account.email_address}:{folder}"
                rule_actions = _evaluate_server_rules(
                    account_id=account.id,
                    subject=subject,
                    sender_name=sender_name,
                    sender_email=sender_email,
                    body_text=body_text,
                )
                if rule_actions["is_junk"]:
                    source = f"imap:{account.email_address}:Junk"
                elif rule_actions["is_archived"]:
                    source = f"imap:{account.email_address}:Archive"

                try:
                    with get_db() as conn:
                        conn.execute(
                            """
                            INSERT INTO emails (
                                message_id, subject, sender_name, sender_email, recipients,
                                date_sent, date_timestamp, body_text, body_html, headers,
                                mbox_source, thread_id, has_attachments, attachment_names
                                , is_read, is_junk, is_archived
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                message_id,
                                subject,
                                sender_name,
                                sender_email,
                                recipients_json,
                                date_sent,
                                date_timestamp,
                                body_text,
                                None,
                                headers,
                                source,
                                thread_id,
                                1 if has_attachments else 0,
                                attachment_names_json,
                                rule_actions["is_read"],
                                rule_actions["is_junk"],
                                rule_actions["is_archived"],
                            ),
                        )
                    inserted_count += 1
                except Exception:
                    skipped_count += 1
        finally:
            try:
                client.logout()
            except Exception:
                pass

        new_last_uid = max_uid_seen if max_uid_seen else last_uid
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO mail_sync_state (account_id, folder_name, last_uid, last_sync_at, last_error)
                VALUES (?, ?, ?, datetime('now'), NULL)
                ON CONFLICT(account_id, folder_name)
                DO UPDATE SET
                    last_uid = excluded.last_uid,
                    last_sync_at = excluded.last_sync_at,
                    last_error = NULL
                """,
                (account_id, folder, new_last_uid),
            )

            conn.execute(
                """
                UPDATE mail_sync_runs
                SET completed_at = datetime('now'), fetched_count = ?, inserted_count = ?, skipped_count = ?, status = 'success'
                WHERE id = ?
                """,
                (fetched_count, inserted_count, skipped_count, run_id),
            )

        # Opportunistically retry queued outbound messages whenever sync succeeds.
        try:
            process_outbox(max_items=10)
        except Exception as exc:
            log.warning("Outbox flush after sync failed: %s", exc)

        return {
            "account_id": account_id,
            "folder": folder,
            "fetched_count": fetched_count,
            "inserted_count": inserted_count,
            "skipped_count": skipped_count,
            "last_uid": new_last_uid,
        }
    except Exception as exc:
        err = str(exc)
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO mail_sync_state (account_id, folder_name, last_uid, last_sync_at, last_error)
                VALUES (?, ?, 0, datetime('now'), ?)
                ON CONFLICT(account_id, folder_name)
                DO UPDATE SET
                    last_sync_at = excluded.last_sync_at,
                    last_error = excluded.last_error
                """,
                (account_id, folder, err),
            )
            conn.execute(
                """
                UPDATE mail_sync_runs
                SET completed_at = datetime('now'), fetched_count = ?, inserted_count = ?, skipped_count = ?, status = 'error', error = ?
                WHERE id = ?
                """,
                (fetched_count, inserted_count, skipped_count, err, run_id),
            )
        raise


def get_sync_status(account_id: int) -> dict:
    with get_db() as conn:
        account = conn.execute(
            "SELECT id, display_name, email_address, enabled FROM mail_accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
        if not account:
            raise LookupError("Account not found")

        states = conn.execute(
            "SELECT folder_name, last_uid, last_sync_at, last_error FROM mail_sync_state WHERE account_id = ? ORDER BY folder_name",
            (account_id,),
        ).fetchall()
        runs = conn.execute(
            """
            SELECT id, folder_name, started_at, completed_at, fetched_count, inserted_count, skipped_count, status, error
            FROM mail_sync_runs WHERE account_id = ? ORDER BY id DESC LIMIT 20
            """,
            (account_id,),
        ).fetchall()

    return {
        "account": dict(account),
        "folders": [dict(r) for r in states],
        "recent_runs": [dict(r) for r in runs],
    }


def send_email(
    account_id: int,
    to: list[str],
    subject: str,
    body_text: str,
    cc: Optional[list[str]] = None,
    bcc: Optional[list[str]] = None,
    body_html: Optional[str] = None,
    queue_on_failure: bool = True,
) -> dict:
    account = get_account(account_id)
    if not account:
        raise LookupError("Account not found")
    if not account.enabled:
        raise RuntimeError("Account is disabled")
    if not to:
        raise ValueError("Recipient list cannot be empty")

    return _send_or_queue(
        account=account,
        to=to,
        cc=cc or [],
        bcc=bcc or [],
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        queue_on_failure=queue_on_failure,
    )


def _build_message(account: MailAccount, to: list[str], cc: list[str], subject: str, body_text: str, body_html: Optional[str]) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = f"{account.display_name} <{account.email_address}>"
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject or "(No Subject)"
    msg.set_content(body_text or "")
    if body_html:
        msg.add_alternative(body_html, subtype="html")
    return msg


def _send_via_smtp(account: MailAccount, to: list[str], cc: list[str], bcc: list[str], subject: str, body_text: str, body_html: Optional[str]) -> dict:
    msg = _build_message(account, to, cc, subject, body_text, body_html)
    recipients = list(to) + cc + bcc
    smtp = _smtp_connect(account)
    try:
        smtp.send_message(msg, from_addr=account.email_address, to_addrs=recipients)
    finally:
        try:
            smtp.quit()
        except Exception:
            pass
    return {
        "ok": True,
        "queued": False,
        "status": "sent",
        "sent_at": _now_iso(),
        "account_id": account.id,
        "recipient_count": len(recipients),
        "subject": msg["Subject"],
        "outbox_id": None,
    }


def enqueue_outbox(account_id: int, to: list[str], cc: Optional[list[str]], bcc: Optional[list[str]], subject: str, body_text: str, body_html: Optional[str]) -> dict:
    import json
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO mail_outbox (
                account_id, to_json, cc_json, bcc_json,
                subject, body_text, body_html,
                status, attempt_count, next_attempt_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', 0, datetime('now'), datetime('now'))
            """,
            (
                account_id,
                json.dumps(to or []),
                json.dumps(cc or []),
                json.dumps(bcc or []),
                subject or "",
                body_text or "",
                body_html,
            ),
        )
        outbox_id = cur.lastrowid
    return {"outbox_id": outbox_id, "status": "pending"}


def _send_or_queue(account: MailAccount, to: list[str], cc: list[str], bcc: list[str], subject: str, body_text: str, body_html: Optional[str], queue_on_failure: bool) -> dict:
    try:
        return _send_via_smtp(
            account=account,
            to=to,
            cc=cc,
            bcc=bcc,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )
    except Exception as exc:
        if not queue_on_failure:
            raise
        queued = enqueue_outbox(
            account_id=account.id,
            to=to,
            cc=cc,
            bcc=bcc,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )
        return {
            "ok": True,
            "queued": True,
            "status": "queued",
            "sent_at": _now_iso(),
            "account_id": account.id,
            "recipient_count": len(list(to) + cc + bcc),
            "subject": subject or "(No Subject)",
            "outbox_id": queued["outbox_id"],
            "message": f"SMTP unavailable, queued for retry: {exc}",
        }


def list_outbox(status: Optional[str] = None, limit: int = 200) -> list[dict]:
    import json
    sql = "SELECT * FROM mail_outbox"
    params: list = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY created_at ASC LIMIT ?"
    params.append(limit)
    with get_db() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        item["to"] = json.loads(item.pop("to_json") or "[]")
        item["cc"] = json.loads(item.pop("cc_json") or "[]")
        item["bcc"] = json.loads(item.pop("bcc_json") or "[]")
        out.append(item)
    return out


def _retry_delay_minutes(attempt_count: int) -> int:
    # Exponential backoff from 1m, capped at 60m.
    return max(1, min(60, 2 ** max(0, attempt_count - 1)))


def process_outbox(max_items: int = 25) -> dict:
    import json
    attempted = 0
    sent = 0
    failed = 0
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM mail_outbox
            WHERE status IN ('pending', 'failed')
              AND (next_attempt_at IS NULL OR next_attempt_at <= datetime('now'))
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (max_items,),
        ).fetchall()

    for row in rows:
        attempted += 1
        item = dict(row)
        outbox_id = int(item["id"])
        with get_db() as conn:
            conn.execute(
                "UPDATE mail_outbox SET status = 'sending', updated_at = datetime('now') WHERE id = ?",
                (outbox_id,),
            )

        account = get_account(int(item["account_id"]))
        if not account or not account.enabled:
            failed += 1
            with get_db() as conn:
                conn.execute(
                    """
                    UPDATE mail_outbox
                    SET status = 'failed',
                        attempt_count = attempt_count + 1,
                        last_error = ?,
                        next_attempt_at = datetime('now', '+15 minutes'),
                        updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    ("Account missing or disabled", outbox_id),
                )
            continue

        to = json.loads(item.get("to_json") or "[]")
        cc = json.loads(item.get("cc_json") or "[]")
        bcc = json.loads(item.get("bcc_json") or "[]")
        subject = item.get("subject") or ""
        body_text = item.get("body_text") or ""
        body_html = item.get("body_html")

        try:
            _send_via_smtp(
                account=account,
                to=to,
                cc=cc,
                bcc=bcc,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
            )
            sent += 1
            with get_db() as conn:
                conn.execute(
                    """
                    UPDATE mail_outbox
                    SET status = 'sent',
                        sent_at = datetime('now'),
                        last_error = NULL,
                        updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (outbox_id,),
                )
        except Exception as exc:
            failed += 1
            next_attempt = _retry_delay_minutes(int(item.get("attempt_count") or 0) + 1)
            with get_db() as conn:
                conn.execute(
                    """
                    UPDATE mail_outbox
                    SET status = 'failed',
                        attempt_count = attempt_count + 1,
                        last_error = ?,
                        next_attempt_at = datetime('now', ?),
                        updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (str(exc), f"+{next_attempt} minutes", outbox_id),
                )

    return {"attempted": attempted, "sent": sent, "failed": failed}


def retry_outbox_item(outbox_id: int) -> dict:
    with get_db() as conn:
        row = conn.execute("SELECT id FROM mail_outbox WHERE id = ?", (outbox_id,)).fetchone()
        if not row:
            raise LookupError("Outbox item not found")
        conn.execute(
            "UPDATE mail_outbox SET status = 'pending', next_attempt_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
            (outbox_id,),
        )
    return process_outbox(max_items=1)


def delete_outbox_item(outbox_id: int) -> bool:
    with get_db() as conn:
        cur = conn.execute("DELETE FROM mail_outbox WHERE id = ?", (outbox_id,))
    return cur.rowcount > 0
