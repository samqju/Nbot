"""Private append-only integration journal and immutable ML candidate registry.

No source DB migration, no promotion side effect, no order capabilities.
"""
import json
from pathlib import Path
import sqlite3
from nbot.v5.science import canonical, digest, sha, verify_review


class ResearchStore:
    def __init__(self, path, *, paper=False):
        path = Path(path)
        if path.is_symlink() or path.name != ("guarded_paper.sqlite" if paper else "continuous_research.sqlite"):
            raise ValueError("RESEARCH_PATH_NOT_ISOLATED")
        self.db = sqlite3.connect(path, timeout=10, isolation_level=None)
        names = {r[0] for r in self.db.execute("select name from sqlite_master where type='table'")}
        if names - {"research_journal", "sqlite_sequence"}:
            self.db.close()
            raise ValueError("RESEARCH_MIXED_DB_FORBIDDEN")
        self.db.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=FULL;
        CREATE TABLE IF NOT EXISTS research_journal(
          seq INTEGER PRIMARY KEY AUTOINCREMENT, identity TEXT UNIQUE NOT NULL,
          kind TEXT NOT NULL, at_ms INTEGER NOT NULL, body TEXT NOT NULL,
          body_sha TEXT NOT NULL, previous_sha TEXT NOT NULL, chain_sha TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS research_no_update BEFORE UPDATE ON research_journal
          BEGIN SELECT RAISE(ABORT,'RESEARCH_IMMUTABLE'); END;
        CREATE TRIGGER IF NOT EXISTS research_no_delete BEFORE DELETE ON research_journal
          BEGIN SELECT RAISE(ABORT,'RESEARCH_IMMUTABLE'); END;
        """)
        try:
            self.audit()
        except BaseException:
            self.db.close()
            raise

    def append(self, identity, kind, at_ms, body):
        if not isinstance(identity, str) or not identity or type(at_ms) is not int or at_ms < 0:
            raise ValueError("RESEARCH_RECORD_INVALID")
        raw, body_sha = canonical(body), digest(body)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            old = self.db.execute("SELECT kind,body_sha,body FROM research_journal WHERE identity=?", (identity,)).fetchone()
            if old:
                if old != (kind, body_sha, raw):
                    raise ValueError("RESEARCH_IDENTITY_CONFLICT")
                self.db.execute("COMMIT")
                return False
            tail = self.db.execute("SELECT chain_sha FROM research_journal ORDER BY seq DESC LIMIT 1").fetchone()
            previous = tail[0] if tail else "0"*64
            chain = digest([identity, kind, at_ms, body_sha, previous])
            self.db.execute("INSERT INTO research_journal(identity,kind,at_ms,body,body_sha,previous_sha,chain_sha) VALUES(?,?,?,?,?,?,?)",
                            (identity, kind, at_ms, raw, body_sha, previous, chain))
            self.db.execute("COMMIT")
            return True
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def audit(self):
        if self.db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("RESEARCH_SQLITE_CORRUPT")
        previous, count = "0"*64, 0
        for seq, identity, kind, at, raw, body_sha, prior, chain in self.db.execute("SELECT * FROM research_journal ORDER BY seq"):
            count += 1
            if (seq != count or digest(json.loads(raw)) != body_sha or prior != previous
                    or digest([identity, kind, at, body_sha, prior]) != chain):
                raise ValueError("RESEARCH_CHAIN_CORRUPT")
            previous = chain
        return {"records": count, "head_sha256": previous, "integrity": "PASS"}

    def register_candidate(self, artifact, at_ms):
        model_sha = artifact.get("model_sha256")
        if not sha(model_sha) or digest({k: v for k, v in artifact.items() if k != "model_sha256"}) != model_sha:
            raise ValueError("G6_MODEL_ARTIFACT_TAMPER")
        return self.append("model:"+model_sha, "MODEL_CANDIDATE", at_ms, artifact)

    def record_disposition(self, model_sha, disposition, at_ms, *, envelope=None, reviewer_key=None, prior_model=None):
        if disposition not in ("REJECT", "RETIRE", "PROMOTE", "ROLLBACK"):
            raise ValueError("G6_DISPOSITION_INVALID")
        row = self.db.execute("SELECT body FROM research_journal WHERE identity=?", ("model:"+model_sha,)).fetchone()
        if not row:
            raise ValueError("G6_UNKNOWN_MODEL")
        artifact = json.loads(row[0])
        if disposition in ("PROMOTE", "ROLLBACK"):
            if artifact["grade"] != "ORIGINAL":
                raise ValueError("G6_SYNTHETIC_MODEL_NEVER_ELIGIBLE")
            # Separate authorization must explicitly attest extra disjoint
            # Challenger labels and accepted G5/G6 proof, not a count alone.
            review = verify_review(envelope, key=reviewer_key, subject_sha256=model_sha, purpose="G6_"+disposition, now_ms=at_ms)
            if (review.get("g5_accepted") is not True or review.get("g6_accepted") is not True
                    or review.get("qualified_training_outcomes", 0) < 2000
                    or review.get("role") not in ("CHAMPION", "CHALLENGER")
                    or (review.get("role") == "CHALLENGER" and review.get("additional_nonoverlapping_outcomes", 0) < 2000)
                    or review.get("holdout_source_audit_accepted") is not True):
                raise ValueError("G6_QUALIFICATION_HOLD")
        return self.append("disposition:"+digest([model_sha, disposition, at_ms]), "MODEL_"+disposition, at_ms,
                           {"model_sha256": model_sha, "prior_model": prior_model, "review": envelope,
                            "disposition": disposition, "paper_authority": "NONE"})

    def close(self):
        self.db.close()
