#!/usr/bin/env python3
import json
from pathlib import Path

p=Path('live_data/sections/D.json')
d=json.loads(p.read_text(encoding='utf-8'))
r=d.get('risk')
if not isinstance(r,dict):
    raise SystemExit('D.risk missing')
print(json.dumps({'schema':'GMFQ_RISK_RUNTIME_DIAGNOSTIC_V1','risk':r},indent=2,ensure_ascii=False))
