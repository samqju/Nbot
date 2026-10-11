"""Read-only, bounded journald diagnosis; safe while paper paths remain open."""
import html
import json
import re
import subprocess


UNITS = ('nbot-observation-live.service', 'nbot-v4-research.service', 'nbot-v4-paper-contest.service')


def summarize(messages):
    streams = {}
    reasons = {}
    latest = None
    reconnects = gaps = overflows = 0
    for message in messages:
        if 'WSS_MARKET_DATA_GAP' in message:
            gaps += 1
        if 'WSS_RUNNER_RECONNECT' not in message:
            continue
        reconnects += 1
        stream = re.search(r'\bstream=(aggTrade|bookTicker|mixed|unknown)\b', message)
        key = stream.group(1) if stream else 'unlabelled'
        streams[key] = streams.get(key, 0)+1
        reason = ('backpressure' if 'WSS_BACKPRESSURE_OVERFLOW' in message else
                  'keepalive_timeout' if 'keepalive ping timeout' in message else
                  'abnormal_close' if 'no close frame' in message else 'other')
        reasons[reason] = reasons.get(reason, 0)+1
        overflows += reason == 'backpressure'
        # Only diagnostic scalars cross the control/Telegram boundary.
        fields = re.findall(r'\b(connected_seconds|messages|last_message_age_seconds|queue_depth|dropped_total|close_code|retry_seconds)=([0-9.]+|None)\b', message)
        latest = {'stream':key, 'category':reason, **dict(fields)}
    return {'reconnects':reconnects, 'stream_counts':streams, 'categories':reasons,
            'symbol_gap_events':gaps, 'backpressure_events':overflows, 'latest':latest}


def wss_status():
    result = {}
    for unit in UNITS:
        proc = subprocess.run(['journalctl','-u',unit,'--since','30 minutes ago','-n','2000','-o','json','--no-pager'],
            capture_output=True,text=True,timeout=5,check=False)
        if proc.returncode:
            result[unit] = {'status':'JOURNAL_UNAVAILABLE'}
            continue
        messages = []
        for line in proc.stdout.splitlines():
            try:
                item = json.loads(line)
                if isinstance(item.get('MESSAGE'),str): messages.append(item['MESSAGE'])
            except (ValueError,TypeError):
                continue
        result[unit] = {'status':'OK','records_read':len(messages), **summarize(messages)}
    body = ['WSS diagnosis: last 30 minutes, at most 2000 journal records per service.']
    for unit, data in result.items():
        body.append(unit.removeprefix('nbot-').removesuffix('.service'))
        if data['status'] != 'OK':
            body.append('Journal unavailable')
            continue
        body.append(f"Reconnects: {data['reconnects']} | symbol gaps: {data['symbol_gap_events']}")
        body.append('Streams: '+json.dumps(data['stream_counts'],sort_keys=True))
        body.append('Reasons: '+json.dumps(data['categories'],sort_keys=True))
        if data['latest']: body.append('Latest: '+json.dumps(data['latest'],sort_keys=True))
    body.append('Unlabelled = older running process. Counts describe symptoms; root cause is unconfirmed. No services or paper paths were changed.')
    return {'status':'OK','view':'wss','order_authority':'NONE', 'document':result,
            'telegram_body':html.escape('\n'.join(body))[:3500]}
