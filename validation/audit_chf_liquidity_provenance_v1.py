#!/usr/bin/env python3
import json
import re
import subprocess

REPO_PATTERNS = [
    '400255.9803935034', '400255.98', 'bakredinausbm', 'Credito bancario',
    'sight deposits', 'SNB', 'NATIVE_LIQ_DATA'
]


def sh(*args, check=True):
    p = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed: {p.stderr[-2000:]}")
    return p.stdout


def git_log_pickaxe(term):
    out = sh('git','log','--all','--date=iso-strict','--format=%H\t%ad\t%s',f'-S{term}','--', check=False)
    return [x for x in out.splitlines() if x.strip()][:100]


def commits_for_path(path):
    out = sh('git','log','--all','--follow','--date=iso-strict','--format=%H\t%ad\t%s','--',path, check=False)
    return [x for x in out.splitlines() if x.strip()][:100]


def grep_commits(term, max_commits=800):
    hits=[]
    commits=sh('git','rev-list','--all').splitlines()[:max_commits]
    rx=re.compile(re.escape(term), re.I)
    for c in commits:
        names=sh('git','ls-tree','-r','--name-only',c, check=False).splitlines()
        likely=[n for n in names if n.endswith(('.py','.js','.html','.json','.txt','.md','.yml','.yaml','.csv')) and ('liqu' in n.lower() or 'runtime' in n.lower() or 'dashboard' in n.lower() or 'payload' in n.lower() or 'index' in n.lower() or 'validation' in n.lower())]
        for n in likely:
            txt=sh('git','show',f'{c}:{n}',check=False)
            if txt and rx.search(txt):
                snippets=[]
                for m in list(rx.finditer(txt))[:3]:
                    a=max(0,m.start()-180); b=min(len(txt),m.end()+260)
                    snippets.append(txt[a:b].replace('\n',' ')[:700])
                hits.append({'commit':c,'path':n,'snippets':snippets})
                if len(hits)>=40:return hits
    return hits


def main():
    result={
        'schema':'GMFQ_CHF_LIQUIDITY_PROVENANCE_AUDIT_V1',
        'head':sh('git','rev-parse','HEAD').strip(),
        'native_liq_history':commits_for_path('live_data/sections/NATIVE_LIQ_DATA.json'),
        'pickaxe':{p:git_log_pickaxe(p) for p in REPO_PATTERNS},
        'deep_grep':{}
    }
    # Expensive scan only for source-defining tokens/value, not generic SNB/NATIVE_LIQ.
    for p in ('400255.9803935034','400255.98','bakredinausbm','Credito bancario','sight deposits'):
        result['deep_grep'][p]=grep_commits(p)
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
