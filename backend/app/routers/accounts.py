"""Mail account + sync/send endpoints for native clients."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

from app.services import mail_accounts

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


class AccountCreateRequest(BaseModel):
    display_name: str
    email_address: EmailStr
    imap_host: str
    imap_port: int = 993
    imap_security: str = Field("ssl", pattern="^(ssl|starttls|plain)$")
    imap_username: str
    imap_password: Optional[str] = None
    smtp_host: str
    smtp_port: int = 587
    smtp_security: str = Field("starttls", pattern="^(ssl|starttls|plain)$")
    smtp_username: str
    smtp_password: Optional[str] = None
    oauth_provider: Optional[str] = None
    oauth_client_id: Optional[str] = None
    oauth_client_secret: Optional[str] = None
    oauth_refresh_token: Optional[str] = None
    oauth_access_token: Optional[str] = None
    oauth_token_url: Optional[str] = None
    oauth_expires_at: Optional[str] = None
    enabled: bool = True


class AccountPatchRequest(BaseModel):
    display_name: Optional[str] = None
    email_address: Optional[EmailStr] = None
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    imap_security: Optional[str] = Field(None, pattern="^(ssl|starttls|plain)$")
    imap_username: Optional[str] = None
    imap_password: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_security: Optional[str] = Field(None, pattern="^(ssl|starttls|plain)$")
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    oauth_provider: Optional[str] = None
    oauth_client_id: Optional[str] = None
    oauth_client_secret: Optional[str] = None
    oauth_refresh_token: Optional[str] = None
    oauth_access_token: Optional[str] = None
    oauth_token_url: Optional[str] = None
    oauth_expires_at: Optional[str] = None
    enabled: Optional[bool] = None


class SendEmailRequest(BaseModel):
    to: list[EmailStr]
    cc: list[EmailStr] = []
    bcc: list[EmailStr] = []
    subject: str = ""
    body_text: str = ""
    body_html: Optional[str] = None


@router.get("")
async def list_mail_accounts():
    return {"items": mail_accounts.list_accounts()}


@router.post("")
async def create_mail_account(payload: AccountCreateRequest):
    try:
        item = mail_accounts.create_account(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return item


@router.patch("/{account_id}")
async def patch_mail_account(account_id: int, payload: AccountPatchRequest):
    try:
        item = mail_accounts.update_account(account_id, payload.model_dump(exclude_unset=True))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return item


@router.delete("/{account_id}")
async def remove_mail_account(account_id: int):
    ok = mail_accounts.delete_account(account_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"ok": True}


@router.post("/{account_id}/sync")
async def sync_mail_account(account_id: int, folder: str = Query("INBOX"), limit: int = Query(200, ge=1, le=1000)):
    try:
        return mail_accounts.sync_account(account_id, folder_name=folder, limit=limit)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{account_id}/sync-status")
async def sync_status(account_id: int):
    try:
        return mail_accounts.get_sync_status(account_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{account_id}/send")
async def send_from_account(account_id: int, payload: SendEmailRequest):
    try:
        return mail_accounts.send_email(
            account_id=account_id,
            to=[str(v) for v in payload.to],
            cc=[str(v) for v in payload.cc],
            bcc=[str(v) for v in payload.bcc],
            subject=payload.subject,
            body_text=payload.body_text,
            body_html=payload.body_html,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
