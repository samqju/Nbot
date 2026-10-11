"""Approved, frozen V4 Champion recommendations for LIVE/PAPER Execution only."""
from __future__ import annotations

import json
import math
from pathlib import Path
import sqlite3

from nbot.communication.authorities import LIVE_PAPER_LEARNED_AUTHORITY
from nbot.communication.contracts import ExecutionProposal
from nbot.config.profiles import get_profile
from .features import CANONICAL_FEATURE_VERSION
from .learned_recommendation import _execution_compatible_quotes
from .recommendation import RecommendationSnapshot
from .v4_promotion import connect, digest
from .v4_research import V4CandidateScanner


class V4ChampionSource:
    authority = LIVE_PAPER_LEARNED_AUTHORITY

    def __init__(self, database, *, release_sha: str, repo_root: Path, profile_name='live-paper'):
        if profile_name != 'live-paper':
            raise ValueError('V4_RECOMMENDATIONS_PAPER_ONLY')
        self.profile = get_profile(profile_name)
        self.database = database
        self.release_sha = release_sha
        self.base = Path(repo_root)/'data/observation/v4'
        self.scanner = V4CandidateScanner(database)
        self._model = None
        self._model_identity = None
        # Separate proposal receipts; neither research nor contest paths are written.
        with database.connection() as c:
            c.execute('CREATE TABLE IF NOT EXISTS v4_execution_decisions(event_open_ms INTEGER PRIMARY KEY,payload_json TEXT NOT NULL,payload_digest TEXT NOT NULL)')

    def _champion(self):
        try:
            with connect((self.base/'generations.db').resolve().as_uri()+'?mode=ro', uri=True) as c:
                c.execute('PRAGMA query_only=ON')
                c.execute('BEGIN')
                state = dict(c.execute('SELECT key,value FROM state'))
                if state.get('champion_generation') is None:
                    return None
                generation = int(state['champion_generation'])
                row = c.execute('SELECT artifact_json,artifact_digest,qualification_status FROM generations WHERE generation=?', (generation,)).fetchone()
                review = c.execute("SELECT contest_id,report_json FROM paper_review_outbox WHERE decision='PROMOTE' AND champion_generation=? AND applied=1 ORDER BY reviewed_at_ms DESC LIMIT 1", (generation,)).fetchone()
                if row is None or review is None:
                    raise ValueError('V4_CHAMPION_APPROVAL_MISSING')
                artifact = json.loads(row[0])
                report = json.loads(review[1])
                if digest(artifact) != row[1] or digest({k:v for k,v in artifact.items() if k != 'model_digest'}) != artifact['model_digest']:
                    raise ValueError('V4_CHAMPION_ARTIFACT_CORRUPT')
                if not report.get('eligible') or report['evidence'][str(generation)]['artifact_digest'] != row[1]:
                    raise ValueError('V4_CHAMPION_APPROVAL_ARTIFACT_MISMATCH')
                return generation, {'artifact': artifact, 'artifact_digest': row[1], 'qualification_status': row[2]}, int(review[0])
        except sqlite3.OperationalError:
            return None

    def refresh(self, *, now_ms: int, ttl_ms: int):
        champion = self._champion()
        if champion is None:
            return RecommendationSnapshot('NOT_READY', 'V4_WAIT_FOR_APPROVED_PAPER_CHAMPION', None, now_ms)
        generation, record, review_id = champion
        artifact = record['artifact']
        with self.database.connection() as c:
            event = c.execute("SELECT e.event_open_ms,e.event_close_ms,e.captured_at_ms FROM market_events e JOIN event_provenance p USING(event_open_ms) WHERE e.status='COMPLETE' AND p.evidence_mode='LIVE_POINT_IN_TIME' AND p.context_complete=1 AND p.membership_quality='POINT_IN_TIME' ORDER BY e.event_open_ms DESC LIMIT 1").fetchone()
            saved = c.execute('SELECT payload_json,payload_digest FROM v4_execution_decisions WHERE event_open_ms=?', (event[0],)).fetchone() if event else None
        if event is None:
            return RecommendationSnapshot('NOT_READY', 'V4_WAIT_FOR_LIVE_EVENT', None, now_ms)
        event_ms, close_ms, captured = map(int, event)
        if not close_ms <= captured <= now_ms or now_ms-captured > ttl_ms or close_ms <= int(artifact['trained_at_ms']):
            return RecommendationSnapshot('NOT_READY', 'V4_EVENT_STALE_OR_PRETRAINING', None, now_ms)
        if saved:
            body = json.loads(saved[0])
            if digest(body) != saved[1]:
                raise ValueError('V4_PROPOSAL_RECEIPT_CORRUPT')
            if body['generation'] != generation or body['model_digest'] != artifact['model_digest']:
                return RecommendationSnapshot('NOT_READY', 'V4_MODEL_CHANGED_WAIT_NEXT_EVENT', None, now_ms)
            proposal = ExecutionProposal.from_dict(body['proposal']) if body['proposal'] else None
            return RecommendationSnapshot(body['status'], body['reason'], proposal, body['refreshed_at_ms'])
        identity = (generation, record['artifact_digest'])
        if self._model_identity != identity:
            from .v4_paper_contest import FrozenGenerationModel
            self._model = FrozenGenerationModel(generation, record)
            self._model_identity = identity
        candidates = self.scanner.scan(event_open_ms=event_ms, now_ms=now_ms)
        scored = [(self._model.score(candidate), candidate) for candidate in candidates]
        scored.sort(key=lambda row: (-row[0], row[1].symbol, row[1].side))
        proposal = None
        reason = 'V4_NO_POSITIVE_CANDIDATE'
        if scored and math.isfinite(scored[0][0]) and scored[0][0] > 0:
            score, candidate = scored[0]
            with self.database.connection() as c:
                raw = c.execute('SELECT symbol,bid_price,ask_price,captured_at_ms FROM market_snapshots WHERE event_open_ms=? AND symbol=?', (event_ms, candidate.symbol)).fetchall()
            quotes = _execution_compatible_quotes(raw, close_ms=close_ms, now_ms=now_ms, ttl_ms=ttl_ms)
            if candidate.symbol in quotes:
                _, bid, ask, quote_ms = quotes[candidate.symbol]
                source_digest = digest({'event':event_ms, 'vector':candidate.vector, 'quote':quotes[candidate.symbol], 'model_digest':artifact['model_digest'], 'approved_contest':review_id})
                generated = min(captured, int(quote_ms))
                proposal = ExecutionProposal.create(
                    proposal_id='PROP-'+digest({'source':source_digest, 'generation':generation})[:40],
                    generated_at_ms=generated, expires_at_ms=generated+ttl_ms,
                    profile=self.profile.name, market_environment=self.profile.market_environment,
                    evidence_lineage=self.profile.evidence_lineage, symbol=candidate.symbol, side=candidate.side,
                    market_event_id=f'ME-{event_ms}', data_generation_id=f'V4-GEN-{generation}-{event_ms}',
                    feature_version=CANONICAL_FEATURE_VERSION, selector_version='NBOT_V4_CHAMPION_TOP1_V1',
                    entry_authority=self.authority, exit_policy_version='INTEGER_R_STEP_CONTROL',
                    reference_price=(float(bid)+float(ask))/2, selection_score=score, selection_rank=1,
                    expected_after_cost_net_r=score, source_digest=source_digest, model_digest=artifact['model_digest'],
                    experiment_context={'authority_class':self.authority, 'economic_claim':False,
                        'research_evidence':False, 'selection_method':'V4_APPROVED_CHAMPION_TOP1',
                        'model_version':f'V4_MODEL_GEN_{generation:03d}', 'v4_generation':generation,
                        'approved_paper_contest_id':review_id, 'training_environment':'LIVE',
                        'inference_environment':'LIVE', 'execution_environment':'LIVE',
                        'reference_quote_environment':'LIVE', 'live_market_event_ms':event_ms,
                        'prediction_target':'V4_AGGTRADE_INTEGER_R_PAPER_OUTCOME', 'order_authority':'NONE'})
                reason = None
            else:
                reason = 'V4_FRESH_QUOTE_UNAVAILABLE'
        snapshot = RecommendationSnapshot('READY', reason, proposal, now_ms)
        body = {'generation':generation, 'model_digest':artifact['model_digest'], 'status':snapshot.status,
                'reason':reason, 'proposal':proposal.to_dict() if proposal else None, 'refreshed_at_ms':now_ms}
        with self.database.connection() as c:
            c.execute('INSERT OR IGNORE INTO v4_execution_decisions VALUES(?,?,?)', (event_ms,json.dumps(body,sort_keys=True,allow_nan=False),digest(body)))
        # The supervisor is the sole refresh writer. Requests consume its saved snapshot.
        return snapshot
