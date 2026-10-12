"""Prospective V4 cadence; audit windows remain 1,000 scored outcomes."""
OUTCOME_WINDOW = 1000
BASELINE_TRADES = 100
HEAD_TO_HEAD_TRADES = 50


def training_schedule(last_generation=0, last_batch=0, *, resolved=0):
    generation = int(last_generation)+1
    interval = OUTCOME_WINDOW if generation <= 3 else 5000
    previous_cutoff = int(last_batch)*OUTCOME_WINDOW
    target = previous_cutoff+interval
    return {'next_generation':generation, 'previous_training_cutoff':previous_cutoff,
            'training_interval_outcomes':interval, 'next_training_at':target,
            'target_batch':target//OUTCOME_WINDOW,
            'new_scored_outcomes':max(0, int(resolved)-previous_cutoff),
            'remaining_outcomes':max(0, target-int(resolved)),
            'training_progress_pct':round(min(1.,max(0.,(int(resolved)-previous_cutoff)/interval))*100,1)}


def contest_checkpoint(contest):
    # Pre-policy contests have a frozen legacy checkpoint of 100.
    value = int(contest.get('checkpoint_trades', BASELINE_TRADES))
    if value not in {BASELINE_TRADES, HEAD_TO_HEAD_TRADES} or (contest['mode']=='BASELINE_EXAM' and value != BASELINE_TRADES):
        raise ValueError('V4_PAPER_CHECKPOINT_INVALID')
    return value
