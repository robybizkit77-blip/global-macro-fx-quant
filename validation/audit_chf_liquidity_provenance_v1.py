#!/usr/bin/env python3
import json
import re
import subprocess

TERMS = [
    '400255.9803935034', '400255.98', 'bakredinausbm', 'Credito bancario',
    'sight deposits', 'NATIVE_LIQ_DATA'
]


def sh(*args, check=True):
    p=subprocess.run(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if check and p.returncode!=0:
        raise RuntimeError(f"{' '.join(args)} failed: {p.stderr[-2000:]}")
    return p.stdout


def log_search(flag, term):
    out=sh('git','log','--all','--date=iso-strict','--format=%H\t%ad\t%s',f'{flag}{term}','--',check=False)
    return [x for x in out.splitlines() if x.strip()][:60]


def path_history(path):
    out=sh('git','log','--all','--follow','--date=iso-strict','--format=%H\t%ad\t%s','--',path,check=False)
    return [x for x in out.splitlines() if x.strip()][:60]


def candidate_commits(searches):
    seen=[]
    for rows in searches.values():
        for row in rows:
            c=row.split('\t',1)[0]
            if c not in seen: seen.append(c)
    return seen[:80]


def snippets_for_commit(commit, terms):
    hits=[]
    names=sh('git','diff-tree','--no-commit-id','--name-only','-r',commit,check=False).splitlines()
    if not names:
        names=sh('git','ls-tree','-r','--name-only',commit,check=False).splitlines()
    likely=[n for n in names if n.endswith(('.py','.js','.html','.json','.txt','.md','.yml','.yaml','.csv'))]
    for n in likely:
        txt=sh('git','show',f'{commit}:{n}',check=False)
        if not txt: continue
        for term in terms:
            m=re.search(re.escape(term),txt,re.I)
            if not m: continue
            a=max(0,m.start()-240); b=min(len(txt),m.end()+420)
            hits.append({'path':n,'term':term,'snippet':txt[a:b].replace('\n',' ')[:900]})
            if len(hits)>=30:return hits
    return hits


def main():
    pickaxe={t:log_search('-S',t) for t in TERMS}
    regex={t:log_search('-G',t) for t in ('bakredinausbm','Credito bancario','sight deposits','400255\\.98')}
    combined={**{f'S:{k}':v for k,v in pickaxe.items()},**{f'G:{k}':v for k,v in regex.items()}}
    commits=candidate_commits(combined)
    details={c:snippets_for_commit(c,TERMS) for c in commits}
    print(json.dumps({
        'schema':'GMFQ_CHF_LIQUIDITY_PROVENANCE_AUDIT_V2',
        'head':sh('git','rev-parse','HEAD').strip(),
        'native_liq_history':path_history('live_data/sections/NATIVE_LIQ_DATA.json'),
        'pickaxe':pickaxe,
        'regex_log':regex,
        'candidate_commit_details':details
    },indent=2,ensure_ascii=False))

if __name__=='__main__':main()
