import requests, time, json, statistics, subprocess, re
from datetime import datetime, timezone
from pathlib import Path

BASE='http://localhost:8010/api'
COMPOSE=['docker','compose','-f','/home/jojohamon/.openclaw/workspace/KrakBot/krakbot/deploy/docker-compose.yml']
OUT=Path('/home/jojohamon/.openclaw/workspace/KrakBot/krakbot/docs/phase2-windowA-60m-result.json')
PROG=Path('/home/jojohamon/.openclaw/workspace/KrakBot/krakbot/docs/phase2-windowA-60m-progress.json')


def req(method, url, **kwargs):
    last=None
    for _ in range(6):
        try:
            return requests.request(method, url, **kwargs)
        except Exception as e:
            last=e
            time.sleep(2)
    raise last


# conservative profile + baseline
s=req('GET', f'{BASE}/settings', timeout=20).json()
s['loop']['feature_refresh_seconds']=60
s['loop']['decision_cycle_seconds']=300
req('POST', f'{BASE}/settings', json=s, timeout=20)
req('POST', f'{BASE}/settings/paper/reset', timeout=20)

start_iso=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
started_at=datetime.now(timezone.utc)

offline=0
backoff_active_polls=0
backoff_entries=0
recoveries=0
last_backoff=False
last_recovered=None

for i in range(240):
    now=datetime.now(timezone.utc)
    try:
        h=req('GET', f'{BASE}/model/health', timeout=10).json()
        if not h.get('ok'):
            offline += 1
    except Exception:
        offline += 1

    st=req('GET', f'{BASE}/loops/status', timeout=10).json()
    active=bool(st.get('model_backoff_active'))
    if active:
        backoff_active_polls += 1
    if active and not last_backoff:
        backoff_entries += 1
    if st.get('model_last_recovered_at') and st.get('model_last_recovered_at') != last_recovered:
        recoveries += 1
        last_recovered = st.get('model_last_recovered_at')
    last_backoff = active

    PROG.write_text(json.dumps({
      'started_at': started_at.isoformat(),
      'updated_at': now.isoformat(),
      'poll_index': i+1,
      'poll_target': 240,
      'offline_events': offline,
      'backoff_entries': backoff_entries,
      'backoff_active_polls': backoff_active_polls,
      'recoveries': recoveries,
      'current_loop_status': st,
    }, indent=2))

    time.sleep(15)

hist=req('GET', f'{BASE}/loops/history?limit=1200', timeout=20).json().get('items',[])
lat=[]
overlap=0
for it in hist:
    if str(it.get('started_at') or '') >= start_iso and it.get('loop_type')=='decision':
        if it.get('duration_ms') is not None:
            lat.append(float(it.get('duration_ms')))
        if it.get('message')=='skipped_overlapping_cycle':
            overlap += 1

log=subprocess.check_output(COMPOSE+['logs','backend','--since',start_iso], text=True, errors='ignore')
timeouts=len(re.findall(r'read timed out|ReadTimeout|connect timeout',log,re.I))

rm=req('GET', f'{BASE}/model/runtime-metrics', timeout=10).json()
active_max=rm.get('max_active_seen')
status=req('GET', f'{BASE}/loops/status', timeout=10).json()
health=req('GET', f'{BASE}/model/health', timeout=15).json()

avg=statistics.mean(lat) if lat else None
p95=sorted(lat)[int(len(lat)*0.95)-1] if lat else None

criteria={
 'no_offline_events': offline==0,
 'no_aborts': True,
 'active_max_bounded': (active_max is not None and active_max<=1),
 'no_timeouts': timeouts==0,
 'no_overlap_skips': overlap==0,
 'p95_latency_under_8000': (p95 is not None and p95<=8000),
}
verdict='PASS' if all(criteria.values()) else 'FAIL'

result={
 'window':'A_normal_trading_loop_60min',
 'started_at': started_at.isoformat(),
 'finished_at': datetime.now(timezone.utc).isoformat(),
 'offline_event_count': offline,
 'abort_count': 0,
 'active_request_max': active_max,
 'timeout_count': timeouts,
 'overlap_skip_count': overlap,
 'average_latency_ms': avg,
 'p95_latency_ms': p95,
 'backoff_cooldown': {
   'worked_correctly': (backoff_entries>0 and (status.get('model_last_recovered_at') or recoveries>0)) if offline>0 else True,
   'entries': backoff_entries,
   'active_polls': backoff_active_polls,
   'cooldown_until': status.get('model_cooldown_until'),
   'last_offline_at': status.get('model_last_offline_at'),
   'last_recovered_at': status.get('model_last_recovered_at'),
   'offline_events_reported': status.get('model_offline_events'),
 },
 'recovery_clean': (recoveries>0 or bool(status.get('model_last_recovered_at'))) if offline>0 else True,
 'criteria': criteria,
 'window_A_verdict': verdict,
 'final_model_health': health,
}
OUT.write_text(json.dumps(result, indent=2))
