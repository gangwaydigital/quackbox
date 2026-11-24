"""Cases API: research workspaces over the email archive."""
import json
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from app.database import get_db
from app.services import case_store, case_triage
from app.services.case_ai import find_more, propose_terms
from app.services.case_export import build_case_zip
from app.services.case_search import person_terms, run_term, to_fts_phrase

router = APIRouter(prefix="/api/cases", tags=["cases"])


class CaseIn(BaseModel):
    name: str
    issue: str
    date_from: Optional[str] = None
    date_to: Optional[str] = None


class PersonIn(BaseModel):
    name: str
    emails: list[str] = []


class TermIn(BaseModel):
    text: str
    source: Literal["owner", "model", "find_more"] = "owner"


class TermEdit(BaseModel):
    text: str


class CandidateIn(BaseModel):
    review: Optional[str] = None
    note: Optional[str] = None
    owner_quote: Optional[str] = None


def _check_text(text: str) -> None:
    try:
        to_fts_phrase(text)
    except ValueError:
        raise HTTPException(400, "Search term can't be empty")


def _case(conn, case_id: int) -> dict:
    case = case_store.get_case(conn, case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    return case


def _term(conn, term_id: int, case_id: Optional[int] = None):
    term = conn.execute("SELECT * FROM case_terms WHERE id = ?", (term_id,)).fetchone()
    if not term or (case_id is not None and term["case_id"] != case_id):
        raise HTTPException(404, "Term not found")
    if term["retired"]:
        raise HTTPException(409, "Term is retired")
    return term


@router.get("")
async def list_cases():
    with get_db() as conn:
        return case_store.list_cases(conn)


@router.post("")
async def create_case(body: CaseIn):
    with get_db() as conn:
        return {"id": case_store.create_case(conn, body.name, body.issue, body.date_from, body.date_to)}


# Static paths before /{id} so "triage" is never parsed as a case id.
@router.get("/triage/status")
async def triage_status():
    return dict(case_triage.TRIAGE_STATUS)


@router.post("/triage/cancel")
async def triage_cancel():
    case_triage.request_cancel()
    return {"ok": True}


@router.put("/terms/{term_id}")
async def edit_term(term_id: int, body: TermEdit):
    with get_db() as conn:
        _term(conn, term_id)
        _check_text(body.text)
        return {"id": case_store.edit_term(conn, term_id, body.text)}


@router.delete("/terms/{term_id}")
async def retire_term(term_id: int):
    with get_db() as conn:
        _term(conn, term_id)
        case_store.retire_term(conn, term_id)
        return {"ok": True}


@router.get("/{case_id}")
async def get_case(case_id: int):
    with get_db() as conn:
        case = _case(conn, case_id)
        case["attachments_indexed"] = conn.execute(
            "SELECT 1 FROM attachment_content LIMIT 1").fetchone() is not None
        return case


@router.post("/{case_id}/people")
async def add_person(case_id: int, body: PersonIn):
    with get_db() as conn:
        _case(conn, case_id)
        pid = case_store.add_person(conn, case_id, body.name, body.emails)
        person = {"name": body.name.strip(), "emails": [e.strip().lower() for e in body.emails]}
        term_ids = [case_store.add_term(conn, case_id, t, "owner")
                    for t in person_terms(person) if t.strip()]
        return {"id": pid, "term_ids": term_ids}


@router.post("/{case_id}/terms")
async def add_term(case_id: int, body: TermIn):
    with get_db() as conn:
        _case(conn, case_id)
        _check_text(body.text)
        return {"id": case_store.add_term(conn, case_id, body.text, body.source)}


@router.post("/{case_id}/propose")
def propose(case_id: int):
    with get_db() as conn:
        case = _case(conn, case_id)
        existing = [t["text"] for t in case["terms"]]
    return propose_terms(case["issue"], case["people"], existing)


@router.post("/{case_id}/terms/{term_id}/run")
def run_one(case_id: int, term_id: int):
    with get_db() as conn:
        _case(conn, case_id)
        _term(conn, term_id, case_id)
        return run_term(conn, case_id, term_id)


@router.post("/{case_id}/run-all")
def run_all(case_id: int):
    with get_db() as conn:
        case = _case(conn, case_id)
        return [run_term(conn, case_id, t["id"]) for t in case["terms"]]


@router.get("/{case_id}/runs")
async def list_runs(case_id: int):
    with get_db() as conn:
        _case(conn, case_id)
        rows = conn.execute("""
            SELECT r.*, t.text AS term_text, t.version AS term_version,
                   t.retired AS term_retired FROM case_runs r
            LEFT JOIN case_terms t ON t.id = r.term_id
            WHERE r.case_id = ? ORDER BY r.id DESC""", (case_id,)).fetchall()
        return [{**dict(r), "channel_counts": json.loads(r["channel_counts"] or "{}")} for r in rows]


@router.get("/{case_id}/candidates")
async def list_candidates(case_id: int, review: Optional[str] = None, triage: Optional[str] = None,
                          page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500)):
    with get_db() as conn:
        _case(conn, case_id)
        return case_store.list_candidates(conn, case_id, review, triage, page, page_size)


@router.put("/{case_id}/candidates/{email_id}")
async def update_candidate(case_id: int, email_id: int, body: CandidateIn):
    with get_db() as conn:
        _case(conn, case_id)
        row = conn.execute("SELECT note FROM case_candidates WHERE case_id = ? AND email_id = ?",
                           (case_id, email_id)).fetchone()
        if not row:
            raise HTTPException(404, "Candidate not found")
        if body.review is not None and body.review not in case_store.REVIEWS:
            raise HTTPException(400, f"review must be one of {case_store.REVIEWS}")
        note = body.note if "note" in body.model_fields_set else row["note"]
        try:
            # Quote first: it is the only check that can fail after review is valid.
            if body.owner_quote is not None:
                case_store.set_owner_quote(conn, case_id, email_id, body.owner_quote)
            if body.review is not None:
                case_store.set_review(conn, case_id, email_id, body.review, note)
            elif "note" in body.model_fields_set:
                conn.execute("UPDATE case_candidates SET note = ? WHERE case_id = ? AND email_id = ?",
                             (note, case_id, email_id))
                conn.commit()
        except ValueError as e:
            raise HTTPException(
                400, "That text isn't in the email." if "quote" in str(e) else str(e))
        return {"ok": True}


@router.post("/{case_id}/triage")
async def start_triage(case_id: int):
    with get_db() as conn:
        _case(conn, case_id)
    if not case_triage.start_triage(case_id):
        raise HTTPException(409, "Triage already running")
    return {"started": True}


@router.post("/{case_id}/find-more")
def find_more_route(case_id: int):
    with get_db() as conn:
        case = _case(conn, case_id)
        evidence = [dict(r) for r in conn.execute(
            """SELECT e.id, e.subject, e.sender_name, e.sender_email, e.date_sent, e.body_text,
                      e.recipients FROM case_candidates cc JOIN emails e ON e.id = cc.email_id
               WHERE cc.case_id = ? AND cc.review = 'evidence'""", (case_id,))]
    return find_more(case["issue"], evidence, [t["text"] for t in case["terms"]], case["people"])


@router.get("/{case_id}/export")
def export_case(case_id: int):
    with get_db() as conn:
        _case(conn, case_id)
        data = build_case_zip(conn, case_id)
    name = f"case-{case_id}-{datetime.now().strftime('%Y%m%d')}.zip"
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
