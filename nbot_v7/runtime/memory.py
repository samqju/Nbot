"""Durable event/outcome memory and atomic state transitions with hash-chain audit."""
from hashlib import sha256
import json
import sqlite3


class Memory:
    def __init__(self,path,initial_equity=10000):
        self.conn=sqlite3.connect(str(path),timeout=30,isolation_level=None)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=FULL")
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY CHECK(id=1),body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS event(seq INTEGER PRIMARY KEY,kind TEXT,body TEXT,previous TEXT,digest TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS outcome(id TEXT PRIMARY KEY,available_ms INTEGER NOT NULL,body TEXT NOT NULL);
        """)
        state={"equity":initial_equity,"peak":initial_equity,"daily_net":0,"day":None,
               "kill":False,"position":None,"pending":None,"last_decision":-1,
               "watch":[],"watch_expires":0}
        self.conn.execute("INSERT OR IGNORE INTO state VALUES(1,?)",(json.dumps(state,sort_keys=True),))
        self.verify()

    def read(self):
        return json.loads(self.conn.execute("SELECT body FROM state WHERE id=1").fetchone()[0])

    def transition(self,kind,mutate,payload=None,outcome=None):
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            state=self.read()
            mutate(state)
            body=json.dumps({"payload":payload,"state":state},sort_keys=True,separators=(",",":"),allow_nan=False)
            last=self.conn.execute("SELECT seq,digest FROM event ORDER BY seq DESC LIMIT 1").fetchone()
            seq,previous=(last[0]+1,last[1]) if last else (0,"0"*64)
            digest=sha256((previous+kind+body).encode()).hexdigest()
            self.conn.execute("INSERT INTO event VALUES(?,?,?,?,?)",(seq,kind,body,previous,digest))
            self.conn.execute("UPDATE state SET body=? WHERE id=1",(json.dumps(state,sort_keys=True),))
            if outcome is not None:
                self.record_outcome(*outcome)
            self.conn.execute("COMMIT")
            return state
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise

    def verify(self):
        previous="0"*64
        last=None
        expected_seq=0
        for seq,kind,body,parent,digest in self.conn.execute("SELECT * FROM event ORDER BY seq"):
            if seq!=expected_seq or parent!=previous or sha256((parent+kind+body).encode()).hexdigest()!=digest:
                raise ValueError("CORRUPT_RECOVERY_JOURNAL_HOLD")
            previous=digest
            expected_seq+=1
            last=json.loads(body)["state"]
        if last is not None and last!=self.read():
            raise ValueError("STATE_JOURNAL_MISMATCH_HOLD")

    def record_outcome(self,identity,available_ms,body):
        content=json.dumps(body,sort_keys=True,allow_nan=False)
        existing=self.conn.execute("SELECT available_ms,body FROM outcome WHERE id=?",(identity,)).fetchone()
        if existing is not None and existing!=(available_ms,content):
            raise ValueError("IMMUTABLE_OUTCOME_CONFLICT")
        self.conn.execute("INSERT OR IGNORE INTO outcome VALUES(?,?,?)",(identity,available_ms,content))

    def matured(self,cutoff_ms):
        return [json.loads(row[0]) for row in self.conn.execute("SELECT body FROM outcome WHERE available_ms<? ORDER BY available_ms,id",(cutoff_ms,))]

    def close(self):
        self.conn.close()
