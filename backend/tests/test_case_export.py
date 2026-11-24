import csv
import io
import json
import zipfile

from app.services import case_store as cs
from app.services.case_export import build_case_zip

RAW = b"From: a@example.com\r\nSubject: hi\r\n\r\nbody \xff\r\n"


def _email(conn, n, ts=1700000000, date="2023-11-14", subject="s", raw=RAW):
    cur = conn.execute(
        "INSERT INTO emails (message_id, subject, sender_name, sender_email, date_sent,"
        " date_timestamp, recipients, body_text, raw_message, mbox_source)"
        " VALUES (?, ?, 'Al', 'al@example.com', ?, ?, ?, 'b', ?, 'box.mbox')",
        (f"m{n}", subject, date, ts,
         json.dumps([{"name": "Bo", "email": "bo@example.com", "type": "to"},
                     {"name": "", "email": "cc@example.com", "type": "cc"}]), raw),
    )
    return cur.lastrowid


def _cand(conn, cid, eid, review="evidence", **kw):
    cols = {"review": review, "semantic_only": 0, **kw}
    conn.execute(
        f"INSERT INTO case_candidates (case_id, email_id, {', '.join(cols)})"
        f" VALUES (?, ?, {', '.join('?' * len(cols))})", (cid, eid, *cols.values()))


def _open(conn, cid):
    z = zipfile.ZipFile(io.BytesIO(build_case_zip(conn, cid)))
    return z, lambda n: z.read(n).decode()


def _rows(text):
    return list(csv.DictReader(io.StringIO(text)))


def _case(conn):
    return cs.create_case(conn, "Case A", "an issue", None, None)


def test_only_evidence_exported(fresh_db):
    cid = _case(fresh_db)
    a, b = _email(fresh_db, 1), _email(fresh_db, 2)
    _cand(fresh_db, cid, a)
    _cand(fresh_db, cid, b, review="not_relevant")
    z, rd = _open(fresh_db, cid)
    rows = _rows(rd("evidence.csv"))
    assert [r["email_id"] for r in rows] == [str(a)]
    assert list(rows[0]) == ["date", "from", "to_cc", "subject", "quote", "quote_source", "note",
                             "found_by_terms", "mailbox", "email_id", "eml_file"]
    assert rows[0]["to_cc"] == "Bo <bo@example.com> (To); cc@example.com (Cc)"
    assert rows[0]["mailbox"] == "box.mbox"
    assert len([n for n in z.namelist() if n.startswith("eml/")]) == 1


def test_eml_bytes_identical(fresh_db):
    cid = _case(fresh_db)
    a = _email(fresh_db, 1)
    _cand(fresh_db, cid, a)
    z, rd = _open(fresh_db, cid)
    name = f"eml/2023-11-14_{a}.eml"
    assert z.read(name) == RAW
    assert _rows(rd("evidence.csv"))[0]["eml_file"] == name


def test_failed_model_quote_not_exported(fresh_db):
    cid = _case(fresh_db)
    a = _email(fresh_db, 1)
    _cand(fresh_db, cid, a, model_quote="made up", model_quote_ok=0)
    r = _rows(_open(fresh_db, cid)[1]("evidence.csv"))[0]
    assert (r["quote"], r["quote_source"]) == ("", "")


def test_verified_model_quote_used(fresh_db):
    cid = _case(fresh_db)
    a = _email(fresh_db, 1)
    _cand(fresh_db, cid, a, model_quote="real", model_quote_ok=1)
    r = _rows(_open(fresh_db, cid)[1]("evidence.csv"))[0]
    assert (r["quote"], r["quote_source"]) == ("real", "model")


def test_owner_quote_wins(fresh_db):
    cid = _case(fresh_db)
    a = _email(fresh_db, 1)
    _cand(fresh_db, cid, a, owner_quote="mine", model_quote="real", model_quote_ok=1)
    r = _rows(_open(fresh_db, cid)[1]("evidence.csv"))[0]
    assert (r["quote"], r["quote_source"]) == ("mine", "owner")


def test_undated_last_in_timeline(fresh_db):
    cid = _case(fresh_db)
    und = _email(fresh_db, 1, ts=None, date=None, subject="UNDATED-SUBJ")
    early = _email(fresh_db, 2, ts=100, date="1970-01-01", subject="EARLY-SUBJ")
    late = _email(fresh_db, 3, ts=200, date="1970-01-02", subject="LATE-SUBJ")
    for e in (und, late, early):
        _cand(fresh_db, cid, e)
    z, rd = _open(fresh_db, cid)
    html = rd("timeline.html")
    assert html.index("EARLY-SUBJ") < html.index("LATE-SUBJ") < html.index("Undated") < html.index("UNDATED-SUBJ")
    assert f"eml/undated_{und}.eml" in z.namelist()
    assert 'href="eml/undated_' in html
    assert "http://" not in html and "https://" not in html


def test_timeline_escapes_html(fresh_db):
    cid = _case(fresh_db)
    a = _email(fresh_db, 1, subject="<script>alert(1)</script>")
    _cand(fresh_db, cid, a, owner_quote="<b>q</b>", note="<i>n</i>")
    html = _open(fresh_db, cid)[1]("timeline.html")
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "<b>q</b>" not in html and "<i>n</i>" not in html


def test_missing_raw_listed_unavailable(fresh_db):
    cid = _case(fresh_db)
    a = _email(fresh_db, 1, raw=None, subject="NO-ORIGINAL")
    _cand(fresh_db, cid, a)
    z, rd = _open(fresh_db, cid)
    assert not [n for n in z.namelist() if n.startswith("eml/")]
    assert _rows(rd("evidence.csv"))[0]["eml_file"] == ""
    readme = rd("README.md")
    assert "Originals unavailable" in readme and "NO-ORIGINAL" in readme and f"{a}" in readme


def test_search_log_includes_retired_terms(fresh_db):
    cid = _case(fresh_db)
    old = cs.add_term(fresh_db, cid, "acme")
    new = cs.edit_term(fresh_db, old, "acme corp")
    counts = json.dumps({"keyword": 3, "recipients": 1, "attachments": 0, "semantic": 2,
                         "semantic_capped": True})
    r1 = fresh_db.execute("INSERT INTO case_runs (case_id, term_id, started_at, status, channel_counts)"
                          " VALUES (?, ?, 't1', 'done', ?)", (cid, old, counts)).lastrowid
    fresh_db.execute("INSERT INTO case_runs (case_id, term_id, started_at, status, error)"
                     " VALUES (?, ?, 't2', 'error', 'boom')", (cid, new))
    a = _email(fresh_db, 1)
    _cand(fresh_db, cid, a)
    fresh_db.execute("INSERT INTO case_candidate_runs VALUES (?, ?, ?, 'keyword')", (cid, a, r1))
    z, rd = _open(fresh_db, cid)
    rows = _rows(rd("search_log.csv"))
    assert [(r["term"], r["term_version"], r["retired"], r["status"]) for r in rows] == [
        ("acme", "1", "1", "done"), ("acme corp", "2", "0", "error")]
    assert rows[0]["keyword"] == "3" and rows[1]["error"] == "boom"
    assert _rows(rd("evidence.csv"))[0]["found_by_terms"] == "acme v1"
    readme = rd("README.md")
    assert "boom" in readme and "capped" in readme.lower()


def test_readme_warns_attachments_unindexed(fresh_db):
    cid = _case(fresh_db)
    _cand(fresh_db, cid, _email(fresh_db, 1))
    readme = _open(fresh_db, cid)[1]("README.md")
    assert "Case A" in readme and "an issue" in readme
    assert "attachment" in readme.lower() and "not indexed" in readme.lower()


def test_readme_method_notes(fresh_db):
    cid = _case(fresh_db)
    _cand(fresh_db, cid, _email(fresh_db, 1))
    readme = _open(fresh_db, cid)[1]("README.md")
    assert "50" in readme and "6,000" in readme and "never filters" in readme


def test_csv_formula_prefixed(fresh_db):
    cid = _case(fresh_db)
    t = cs.add_term(fresh_db, cid, "=cmd")
    fresh_db.execute("INSERT INTO case_runs (case_id, term_id, started_at, status)"
                     " VALUES (?, ?, 't', 'done')", (cid, t))
    _cand(fresh_db, cid, _email(fresh_db, 1, subject="=HYPERLINK(1)"), owner_quote="@x", note="-1")
    z, rd = _open(fresh_db, cid)
    r = _rows(rd("evidence.csv"))[0]
    assert (r["subject"], r["quote"], r["note"]) == ("'=HYPERLINK(1)", "'@x", "'-1")
    assert _rows(rd("search_log.csv"))[0]["term"] == "'=cmd"


def test_semantic_only_marked(fresh_db):
    cid = _case(fresh_db)
    _cand(fresh_db, cid, _email(fresh_db, 1), semantic_only=1)
    z, rd = _open(fresh_db, cid)
    assert _rows(rd("evidence.csv"))[0]["found_by_terms"].endswith("(semantic only)")
    assert "semantic only" in rd("timeline.html")


def test_running_run_listed_unfinished(fresh_db):
    cid = _case(fresh_db)
    fresh_db.execute("INSERT INTO case_runs (case_id, started_at, status) VALUES (?, 't', 'running')", (cid,))
    readme = _open(fresh_db, cid)[1]("README.md")
    assert "did not finish" in readme and "run 1" in readme
