from app import database
from app.services import case_store as cs
from app.services import deduplication as dd


def test_delete_duplicates_keeps_case_candidates(tmp_path, monkeypatch):
    db = tmp_path / "d.db"
    database.init_db(db)
    real = database.get_db
    monkeypatch.setattr(dd, "get_db", lambda p=db: real(p))
    with real(db) as conn:
        ids = [conn.execute("INSERT INTO emails (message_id, subject) VALUES (?, 's')", (f"m{n}",)).lastrowid
               for n in range(3)]
        gid = conn.execute("INSERT INTO duplicate_groups (canonical_email_id, duplicate_count) VALUES (?, 2)",
                           (ids[0],)).lastrowid
        for eid in ids[1:]:
            conn.execute("INSERT INTO duplicate_emails (group_id, email_id) VALUES (?, ?)", (gid, eid))
        cid = cs.create_case(conn, "c", "i", None, None)
        conn.execute("INSERT INTO case_candidates (case_id, email_id) VALUES (?, ?)", (cid, ids[1]))

    assert dd.delete_duplicates(group_ids=[gid]) == {"deleted": 1, "kept_in_cases": 1}
    with real(db) as conn:
        left = [r[0] for r in conn.execute("SELECT id FROM emails ORDER BY id")]
        group = dd.get_duplicate_groups()["groups"]
    assert left == ids[:2]
    assert [d["id"] for g in group for d in g["duplicates"]] == [ids[1]]  # still shown as a duplicate
