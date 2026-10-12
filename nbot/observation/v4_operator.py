"""Bounded paper review interface for the authenticated Execution Telegram proxy."""
from __future__ import annotations

import html
from pathlib import Path
import time

from .v4_promotion import connect, promotion_report, rows


class V4PaperOperator:
    def __init__(self, root: Path):
        self.base = Path(root) / 'data/observation/v4'

    def status(self, _view='v4-review'):
        # Reading a status must never initialize or migrate a live database.
        now = int(time.time()*1000)
        with connect((self.base/'paper_contest.db').resolve().as_uri()+'?mode=ro', uri=True) as c, \
             connect((self.base/'generations.db').resolve().as_uri()+'?mode=ro', uri=True) as g, \
             connect((self.base/'paper_ledger.db').resolve().as_uri()+'?mode=ro', uri=True) as ledger:
            for conn in (c, g, ledger):
                conn.execute('PRAGMA query_only=ON')
                conn.execute('BEGIN')
            report = promotion_report(c, g, ledger, now_ms=now)
            contests = rows(c, "SELECT * FROM contests WHERE status IN ('ACTIVE','REVIEW_REQUIRED') ORDER BY contest_id DESC LIMIT 1")
            contest = contests[0] if contests else None
            models = rows(c, 'SELECT generation,role,completed_trades,realized_r FROM contest_models WHERE contest_id=?', (contest['contest_id'],)) if contest else []
            state = dict(g.execute('SELECT key,value FROM state'))
        lines = ['V4 paper Champion review', f"Champion: {state.get('champion_generation') or 'none'}"]
        ready = bool(contest and contest['status'] == 'REVIEW_REQUIRED')
        if contest:
            lines.append(f"Contest {contest['contest_id']}: {contest['status']}")
            for model in models:
                from .v4_policy import contest_checkpoint
                lines.append(f"Gen-{model['generation']} {model['role']}: {model['completed_trades']}/{contest_checkpoint(contest)} scored, {model['realized_r']:.3f}R")
        lines.append('Promotion gates: '+('PASS' if report['eligible'] else 'BLOCKED'))
        lines.extend(report.get('failed_checks', [])[:12])
        if ready:
            ident = f"{contest['contest_id']} {contest['challenger_generation']}"
            if report['eligible']:
                lines.append('To approve paper Champion: /champion approve '+ident)
            lines.append('To reject and advance the queue: /champion reject '+ident)
        lines.append('Paper only. Approval never enables entries or real-money trading.')
        return {'status': 'OK', 'view': 'v4-review', 'order_authority': 'NONE',
                'telegram_body': html.escape('\n'.join(lines)),
                'document': {'contest': contest, 'models': models, 'promotion_review': report,
                             'review_ready': ready, 'order_authority': 'NONE'}}

    def review(self, payload):
        if set(payload) != {'action', 'contest_id', 'generation'}:
            raise ValueError('V4_REVIEW_REQUEST_INVALID')
        action = payload['action']
        if action not in {'approve', 'reject'} or any(type(payload[k]) is not int or payload[k] <= 0 for k in ('contest_id', 'generation')):
            raise ValueError('V4_REVIEW_REQUEST_INVALID')
        from .v4_paper_contest import V4PaperReviewAdmin
        admin = V4PaperReviewAdmin(generation_path=self.base/'generations.db',
            contest_path=self.base/'paper_contest.db', ledger_path=self.base/'paper_ledger.db')
        # Identity comparison and gates happen under the authoritative writer locks.
        return admin._review('PROMOTE' if action == 'approve' else 'REJECT',
            now_ms=int(time.time()*1000), expected=(payload['contest_id'], payload['generation']))
