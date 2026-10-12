#!/usr/bin/env python3
import re, urllib.request

URL='https://www.ecb.europa.eu/press/govcdec/mopo/html/index.en.html'
req=urllib.request.Request(URL,headers={'User-Agent':'GMFQ-research/1.0 result-blind-ecb-transport-diagnostic'})
with urllib.request.urlopen(req,timeout=60) as r:
    body=r.read().decode('utf-8','ignore')
print('bytes',len(body))
patterns={
 'literal_ecb_mp':r'ecb\.mp',
 'decision_title':r'Monetary policy decisions',
 'press_pr_date':r'/press/pr/date/',
 'escaped_press_pr_date':r'\\/press\\/pr\\/date\\/',
 'unicode_slash':r'\\u002[fF]press',
 'six_digit_mp':r'ecb\.mp\d{6}',
 'data_url':r'data-[A-Za-z0-9_-]*url',
 'json_script':r'application/(?:ld\+)?json',
}
for k,p in patterns.items(): print(k,len(re.findall(p,body,re.I)))
for needle in ('ecb.mp','Monetary policy decisions','/press/pr/date/','\\/press\\/pr\\/date\\/'):
    print('\nNEEDLE',needle)
    starts=[m.start() for m in re.finditer(re.escape(needle),body,re.I)][:5]
    for s in starts:
        x=body[max(0,s-250):s+500].replace('\n',' ')
        print(repr(x[:800]))
