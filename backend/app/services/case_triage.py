"""Cancellable background triage of a case's untriaged candidates."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.config import DB_PATH
from app.database import get_connection
from app.services.case_ai import triage_email
from app.services.case_store import _TRIAGE_RANK

# Mutated in place (never reassigned), like routers/topics._task_status.
TRIAGE_STATUS = {
    "running": False, "case_id": None, "done": 0, "total": 0,
    "cancelled": False, "error": None,
}
_executor = ThreadPoolExecutor(max_workers=1)


def request_cancel() -> None:
    TRIAGE_STATUS["cancelled"] = True


def start_triage(case_id: int, db_path: Path = DB_PATH) -> bool:
    if TRIAGE_STATUS["running"]:
        return False
    # Set before submit so a second call can't slip in before the worker starts.
    TRIAGE_STATUS.update(running=True, case_id=case_id, done=0, total=0,
                         cancelled=False, error=None)
    _executor.submit(run_triage_sync, case_id, db_path)
    return True


def run_triage_sync(case_id: int, db_path: Path) -> None:
    TRIAGE_STATUS.update(running=True, case_id=case_id, done=0, total=0, error=None)
    conn = get_connection(db_path)
    try:
        case = conn.execute("SELECT issue FROM cases WHERE id = ?", (case_id,)).fetchone()
        if case is None:
            TRIAGE_STATUS["error"] = "Case not found"
            return
        rows = conn.execute(
            f"""SELECT e.* FROM case_candidates cc JOIN emails e ON e.id = cc.email_id
                WHERE cc.case_id = ? AND cc.triage = 'untriaged'
                ORDER BY cc.semantic_only ASC, {_TRIAGE_RANK},
                         e.date_timestamp IS NULL, e.date_timestamp DESC""",
            (case_id,),
        ).fetchall()
        TRIAGE_STATUS["total"] = len(rows)
        for row in rows:
            if TRIAGE_STATUS["cancelled"]:
                break
            email = dict(row)
            try:
                r = triage_email(case["issue"], email)
            except Exception as e:  # llm.complete can raise on a malformed body
                r = {"triage": "untriaged", "reason": "", "quote": None,
                     "quote_ok": False, "partial": False,
                     "error": f"{type(e).__name__}: {e}"[:200]}
            conn.execute(
                """UPDATE case_candidates SET triage = ?, triage_reason = ?, model_quote = ?,
                          model_quote_ok = ?, partial_text = ?, triage_error = ?
                   WHERE case_id = ? AND email_id = ?""",
                (r["triage"], r["reason"], r["quote"], int(r["quote_ok"]),
                 int(r["partial"]), r["error"], case_id, email["id"]),
            )
            conn.commit()
            TRIAGE_STATUS["done"] += 1
    except Exception as e:
        TRIAGE_STATUS["error"] = f"{type(e).__name__}: {e}"[:200]
    finally:
        conn.close()
        TRIAGE_STATUS["running"] = False
