#!/usr/bin/env python3
"""Fail-closed validation of a proposed OIS operational view. Read only."""
import argparse, datetime as dt, json, pathlib, sys
def check(obj,today):
    problems=[]
    for c,row in (obj.get('currencies') or {}).items():
        status=str(row.get('operational_status',''))
        if not status.startswith('GREEN'): continue
        try: age=(today-dt.date.fromisoformat(row['as_of'])).days
        except (KeyError,ValueError,TypeError): age=None
        h=row.get('horizons') or {}
        official=status=='GREEN_OFFICIAL'
        complete=all(isinstance(h.get(k),dict)
          and isinstance(h[k].get('rate'),(int,float)) and not isinstance(h[k].get('rate'),bool)
          and (h[k].get('quote_as_of')==row.get('as_of') or (official and not h[k].get('quote_as_of')))
          for k in ('3m','6m','12m'))
        if age is None or not 0<=age<=5 or not complete:
            problems.append({'currency':c,'age_days':age,'complete':complete,'status':status})
    return problems
def main():
    p=argparse.ArgumentParser();p.add_argument('candidate');p.add_argument('--today');a=p.parse_args()
    today=dt.date.fromisoformat(a.today) if a.today else dt.datetime.now(dt.timezone.utc).date()
    obj=json.loads(pathlib.Path(a.candidate).read_text())
    problems=check(obj,today)
    print(json.dumps({'status':'REJECTED' if problems else 'PASS','issues':problems}))
    return 1 if problems else 0
if __name__=='__main__':sys.exit(main())
