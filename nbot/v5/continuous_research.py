"""G1-G6 observation bridge with isolated durable G4 population tracking.

Uses read-only original source, immutable policy and independent quote replay.
No online training or order worker is reachable. Original cost/source verdicts
must arrive through separately independently verified evidence exports.
"""
import argparse
from collections import Counter
from contextlib import closing, ExitStack
from dataclasses import asdict
import json
import os
from pathlib import Path
import sqlite3
import time

from nbot.v5.g4_forward_entry_quote import IndependentSourceAudit
from nbot.v5.g4_segment_replay import verified_ram_vault
from nbot.v5.g4_real_entry_admission import admit_research_entry
from nbot.v5.g4_source_binding import bind_from_frozen_observation_copy
from nbot.v5.g4_live_outcomes import follow_original_path
from nbot.v5.g4_research_ledger import init_offline_ledger, freeze_label_intent, maturity_calendar,append_terminal
from nbot.v5.research_store import ResearchStore
from nbot.v5.science import Protocol, dataset, evaluate, digest, canonical, causal_features, verify_review


def ro(path):
    p=Path(path)
    if p.is_symlink() or not p.is_file():raise ValueError("SOURCE_NOT_REGULAR")
    return closing(sqlite3.connect(p.resolve().as_uri()+"?mode=ro",uri=True,timeout=10))


class ContinuousResearch:
    def __init__(self, *, source, vault, registry, root, protocol, start_event_ms):
        root=Path(root)
        if root.is_symlink() or not root.is_dir() or root.stat().st_mode & 0o077:
            raise ValueError("RESEARCH_ROOT_NOT_PRIVATE")
        if Path(source).resolve().parent == root.resolve() or Path(vault).resolve().parent == root.resolve():
            raise ValueError("RESEARCH_SOURCE_MIXED_ROOT")
        protocol.validate()
        self.source,self.vault,self.registry=source,vault,registry
        self.protocol,self.start_event_ms=protocol,start_event_ms
        self.store=ResearchStore(root/"continuous_research.sqlite")
        self.labels=sqlite3.connect(root/"g4_outcomes.sqlite",timeout=10)
        self.labels.execute("PRAGMA journal_mode=WAL")
        self.labels.execute("PRAGMA synchronous=FULL")
        init_offline_ledger(self.labels)
        self.store.append("research-protocol","PROTOCOL",protocol.declared_ms,
                          {"protocol":asdict(protocol),"start_event_ms":start_event_ms})

    def tick(self, now_ms, *, max_events=1):
        """For compressed sources, use only a bounded, independently verified
        RAM-backed replay view. Missing evidence is never promoted to outcomes.
        """
        vault_path=Path(self.vault)
        if vault_path.is_dir() and not vault_path.is_symlink():
            with ExitStack() as stack:
                view=vault_path
                try:
                    with ro(self.source) as db:
                        cohort=db.execute(
                            "SELECT symbols_json FROM g1f_universe_snapshots LIMIT 1").fetchone()
                    if cohort is None:
                        raise ValueError("G4_G1_FROZEN_COHORT_MISSING")
                    view,_=stack.enter_context(verified_ram_vault(
                        vault_path,symbols=json.loads(cohort[0]),
                        max_frames=100000,max_view_mib=128))
                except (ValueError,OSError,sqlite3.DatabaseError):
                    # Only archive mounting failures become source HOLD;
                    # internal scientific processing bugs must never be swallowed.
                    view=vault_path
                return self._tick_from_source(
                    now_ms,max_events=max_events,vault_path=view)
        return self._tick_from_source(
            now_ms,max_events=max_events,vault_path=self.vault)

    def _tick_from_source(self, now_ms, *, max_events, vault_path):
        if type(max_events) is not int or not 1<=max_events<=3:
            raise ValueError("RESEARCH_BATCH_BOUNDS")
        with ro(self.source) as db:
            events=[r[0] for r in db.execute("SELECT event_open_ms FROM g1f_event_manifest WHERE event_open_ms>=? ORDER BY event_open_ms",(self.start_event_ms,))]
        done={json.loads(r[0])["event_ms"] for r in self.store.db.execute("SELECT body FROM research_journal WHERE kind='EVENT_COMPLETE'")}
        selected=[e for e in events if e not in done][:max_events]
        audit=None
        if selected:
            try:
                audit=IndependentSourceAudit(vault_path)
            except (OSError,ValueError,sqlite3.DatabaseError):
                # An absent, malformed or tampered independent forward vault
                # cannot qualify a single G4 price. Still enumerate all 100
                # original source candidates as explicit HOLD, not a crash.
                audit=None
        for event in selected:
            with ro(self.source) as db:
                candidates=db.execute("SELECT record_json FROM g1f_candidate_events WHERE event_open_ms=? ORDER BY symbol,direction",(event,)).fetchall()
                g3_raw=db.execute("SELECT payload_json FROM g3_event_context WHERE event_open_ms=?",(event,)).fetchone()
            if len(candidates)!=100 or g3_raw is None:
                raise ValueError("G4_FULL_DIRECTIONAL_DENOMINATOR_MISSING")
            g3=json.loads(g3_raw[0])
            # G3 HOLD has no feature evidence; never invent a BTC regime.
            g3_features=g3.get("feature_evidence")
            btc_features=(g3_features.get("btc",{})
                          if isinstance(g3_features,dict) else {})
            regime=(btc_features.get("regime","UNKNOWN")
                    if isinstance(btc_features,dict) else "UNKNOWN")
            for raw, in candidates:
                c=json.loads(raw)
                identity="candidate:"+c["decision_id"]
                if self.store.db.execute("SELECT 1 FROM research_journal WHERE identity=?",(identity,)).fetchone():continue
                admission=admit_research_entry(g1_snapshot=self.source,raw_source_vault=vault_path,
                                               registry_file=self.registry,event_open_ms=event,symbol=c["symbol"],side=c["side"],audit_cache=audit)
                features=None;feature_reasons=[]
                try:features=causal_features(c,g3)
                except (KeyError,TypeError,ValueError) as exc:feature_reasons=[type(exc).__name__+":CAUSAL_FEATURES_UNAVAILABLE"]
                if admission.state=="REFERENCE_GEOMETRY_RECORDED":
                    # Immutable declared decision, no fill or economic score.
                    c["source_digest"]=admission.original_candidate_sha256
                    label=freeze_label_intent(self.labels,c,admission.policy_geometry)
                else:label=None
                payload={"candidate":c,"admission":asdict(admission),"label_id":label,
                         "features":features,"feature_reasons":feature_reasons,
                         "regime":regime,
                         "g3_feature_known_ms":g3.get("valid_from_ms"),"order_authority":"NONE"}
                self.store.append(identity,"CANDIDATE",now_ms,payload)
            self.store.append("event:"+str(event),"EVENT_COMPLETE",now_ms,{"event_ms":event,"candidate_population":100})
        path_ids={r[0][5:] for r in self.store.db.execute("SELECT identity FROM research_journal WHERE kind='ORIGINAL_PRICE_PATH'")}
        pending=[r for r in self.labels.execute("SELECT i.label_id,i.intent_json FROM g4_label_intents i LEFT JOIN g4_label_terminals t ON i.label_id=t.label_id WHERE t.label_id IS NULL ORDER BY i.decision_at_ms") if r[0] not in path_ids][:3000]
        if pending and audit is None:
            try:
                audit=IndependentSourceAudit(vault_path)
            except (OSError,ValueError,sqlite3.DatabaseError):
                audit=None
        for label_id,raw in pending:
            if self.store.db.execute("SELECT 1 FROM research_journal WHERE identity=?",("path:"+label_id,)).fetchone():continue
            intent=json.loads(raw)
            stored=self.store.db.execute("SELECT body FROM research_journal WHERE identity=?",("candidate:"+intent["decision_id"],)).fetchone()
            if stored is None:continue
            candidate=json.loads(stored[0])["candidate"]
            path=(follow_original_path(
                vault=vault_path,audit=audit,candidate=candidate,
                policy=intent["frozen_policy"],now_ms=now_ms)
                if audit is not None else
                {"state":"HOLD","reasons":["G4_ORIGINAL_VAULT_NOT_INDEPENDENTLY_AUDITED"]})
            if path["state"]=='PATH_REPLAYED':
                self.store.append("path:"+label_id,"ORIGINAL_PRICE_PATH",now_ms,
                                  {"label_id":label_id,"path":path,"economic_state":"HELD_PENDING_INDEPENDENT_EXIT_QUOTE_FEE_SLIPPAGE_SETTLED_FUNDING"})
            elif now_ms>=intent["maturity_at_ms"] and not self.store.db.execute("SELECT 1 FROM research_journal WHERE identity=?",("expired-path:"+label_id,)).fetchone():
                self.store.append("expired-path:"+label_id,"PATH_DEFICIENCY",now_ms,
                                  {"label_id":label_id,"path":path,"loss_label_inferred":False})
                append_terminal(self.labels,label_id,{"status":"CENSORED","source_grade":"NONE","settled_at_ms":now_ms,
                                                      "reason_codes":path.get("reasons",["G4_ORIGINAL_PATH_INCOMPLETE"]),
                                                      "net_r":None,"gross_r":None,"order_authority":"NONE"})
        rows=self.verified_rows()
        d=dataset(rows,cutoff_ms=now_ms,grade="ORIGINAL")
        report=evaluate(d,self.protocol)
        self.store.append("g5:"+report["report_sha256"],"G5_REPORT",now_ms,report)
        telemetry=self.telemetry(now_ms)
        telemetry["g5"]=report
        return telemetry

    def accept_verified_export(self, export, review, reviewer_key, now_ms):
        """Only independent source reviewers may make rows eligible for G5.

        They must bind original hashes to G1-G4 receipts and recompute costs.
        Producer booleans or raw source counts cannot authorize this import.
        """
        verify_review(review,key=reviewer_key,subject_sha256=digest(export),purpose="G4_OUTCOME_EXPORT",now_ms=now_ms)
        checked=dataset(export["rows"],cutoff_ms=now_ms,grade="ORIGINAL")
        for row in checked["rows"]:
            intent=self.labels.execute("SELECT intent_json FROM g4_label_intents WHERE label_id=?",(row["label_id"],)).fetchone()
            if intent is None:raise ValueError("G4_EXPORT_UNREGISTERED_INTENT")
            intent=json.loads(intent[0])
            if (intent["decision_at_ms"]!=row["decision_ms"] or intent["symbol"]!=row["symbol"]
                    or intent["side"]!=row["side"] or intent["policy_sha256"]!=row["lineage"]["policy"]):
                raise ValueError("G4_EXPORT_INTENT_MISMATCH")
            record=self.store.db.execute("SELECT body FROM research_journal WHERE identity=?",("candidate:"+intent["decision_id"],)).fetchone()
            if record is None or json.loads(record[0])["features"]!=row["features"]:
                raise ValueError("G4_EXPORT_HINDSIGHT_FEATURES")
            population=json.loads(record[0])
            path_record=self.store.db.execute("SELECT body FROM research_journal WHERE identity=?",("path:"+row["label_id"],)).fetchone()
            if path_record is None:raise ValueError("G4_EXPORT_ORIGINAL_PATH_MISSING")
            path=json.loads(path_record[0])["path"]
            if (row["exit_ms"]!=path["exit_at_ms"] or row["lineage"]["path"]!=digest(path)
                    or row["regime"]!=population["regime"] or row["feature_known_ms"]!=population["g3_feature_known_ms"]
                    or row["patterns"]!=sorted(k for k,v in population["candidate"]["patterns"].items() if v=="MATCH")
                    or row["lineage"]["candidate"]!=population["admission"]["original_candidate_sha256"]
                    or row["lineage"]["g3"]!=population["admission"]["original_g3_feature_sha256"]):
                raise ValueError("G4_EXPORT_SOURCE_OR_PATH_MISMATCH")
            terminal={"status":"SCORED","source_grade":"QUOTE_CONSTRAINED_SIMULATION",
                      "settled_at_ms":row["settled_ms"],"exit_at_ms":row["exit_ms"],"exit_reason":path["exit_reason"],
                      "early_exit_source_proof_sha256":row["lineage"]["path"],
                      "original_sources_independently_verified":True,"path_sha256":row["lineage"]["path"],
                      "quote_cost_sha256":row["lineage"]["cost"],"label_sha256":row["row_sha256"],
                      "net_r":repr(row["net_r"]),"gross_r":repr(row["gross_r"]),"order_authority":"NONE"}
            append_terminal(self.labels,row["label_id"],terminal)
            self.store.append("qualified:"+row["label_id"],"QUALIFIED_OUTCOME",now_ms,{"row":row,"independent_review":review})

    def verified_rows(self):
        return [json.loads(r[0])["row"] for r in self.store.db.execute("SELECT body FROM research_journal WHERE kind='QUALIFIED_OUTCOME'")]

    def telemetry(self,now_ms):
        candidates=[json.loads(r[0]) for r in self.store.db.execute("SELECT body FROM research_journal WHERE kind='CANDIDATE'")]
        states=Counter(p["admission"]["state"] for p in candidates)
        reasons=Counter(r for p in candidates for r in p["admission"]["reasons"])
        return {"candidate_population":len(candidates),"admission_states":dict(states),"hold_reasons":dict(reasons),
                "g4_maturity":maturity_calendar(self.labels,asof_ms=now_ms),
                "qualified_independently_reviewed_outcomes":len(self.verified_rows()),
                "original_price_paths":self.store.db.execute("SELECT count(*) FROM research_journal WHERE kind='ORIGINAL_PRICE_PATH'").fetchone()[0],
                "economic_state":"REQUIRES_ORIGINAL_VERIFIED_COST_EXPORT_NOT_ZERO_DEFAULTS",
                "research_chain":self.store.audit(),"g6_training_state":"LOCKED_PENDING_G5_INDEPENDENT_RELEASE",
                "g7_paper_state":"LOCKED","real_money_authority":"NONE"}

    def close(self):self.labels.close();self.store.close()


def main():
    p=argparse.ArgumentParser()
    for name in ("source","vault","registry","root","protocol"):p.add_argument("--"+name,required=True)
    p.add_argument("--start-event-ms",type=int,required=True)
    p.add_argument("--interval-seconds",type=int,default=300)
    p.add_argument("--once",action="store_true")
    a=p.parse_args()
    if not 60<=a.interval_seconds<=600:raise ValueError("RESEARCH_INTERVAL_BOUNDS")
    os.umask(0o077)
    engine=ContinuousResearch(source=a.source,vault=a.vault,registry=a.registry,root=a.root,
                              protocol=Protocol(**json.loads(Path(a.protocol).read_text())),start_event_ms=a.start_event_ms)
    try:
        while True:
            started=time.monotonic()
            result=engine.tick(time.time_ns()//1000000)
            print(canonical(result),flush=True)
            if a.once:break
            time.sleep(max(1,a.interval_seconds-(time.monotonic()-started)))
    finally:engine.close()


if __name__=="__main__":main()
