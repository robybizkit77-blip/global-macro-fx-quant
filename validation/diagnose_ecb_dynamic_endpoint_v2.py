#!/usr/bin/env python3
import re, urllib.parse, urllib.request
BASE='https://www.ecb.europa.eu/press/govcdec/mopo/html/index.en.html'
UA='GMFQ-research/1.0 result-blind-ecb-endpoint-diagnostic'
def get(u):
    q=urllib.request.Request(u,headers={'User-Agent':UA})
    with urllib.request.urlopen(q,timeout=60) as r:return r.read().decode('utf-8','ignore')
body=get(BASE)
scripts=[]
for s in re.findall(r'<script[^>]+src=["\']([^"\']+)',body,re.I):
    u=urllib.parse.urljoin(BASE,s)
    if 'ecb.europa.eu' in urllib.parse.urlparse(u).netloc.lower():scripts.append(u)
print('scripts',len(scripts))
for u in scripts: print('SCRIPT',u)
need=('govcdec','mopo','publication','filter','ajax','api/','loadmore','load-more','press/')
for u in scripts:
    try:t=get(u)
    except Exception as e:
        print('FETCH_FAIL',u,repr(e));continue
    low=t.lower()
    hits=[x for x in need if x in low]
    if not hits:continue
    print('\nMATCH_SCRIPT',u,'bytes',len(t),'hits',hits)
    # Print compact snippets around high-value tokens only; transport diagnostics, not content labels.
    for token in ('govcdec','mopo','loadmore','load-more','ajax','api/'):
        for m in list(re.finditer(re.escape(token),low))[:5]:
            a=max(0,m.start()-300);b=min(len(t),m.start()+700)
            print('TOKEN',token,repr(t[a:b].replace('\n',' ')[:1000]))
# Also inspect form/action/data attributes from page shell.
for pat in (r'<form[^>]*>',r'data-[\w-]+=["\'][^"\']+["\']',r'action=["\'][^"\']+["\']'):
    vals=re.findall(pat,body,re.I)
    print('\nPATTERN',pat,'count',len(vals))
    for x in vals[:30]:print(x[:800])
