#!/usr/bin/env python3
import json,re,math,sys
from datetime import date,datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from collect_official_news_rss_v1 import collect as collect_official_releases
from news_reaction_evidence_v1 import annotate as annotate_reaction_proof


ROOT=Path(__file__).resolve().parents[1]
# This builder is invoked as `python validation/build_news_pulse_operational_v1.py`
# by multiple existing jobs; its script directory, not repository root, is
# initially on sys.path. Resolve the existing validation package explicitly.
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from validation.macro.build_macro_event_market_context_v1 import run as macro_event_market_context_run
OIS=ROOT/'live_data/sections/OIS_OPERATIONAL_VIEW.json'
MACRO=ROOT/'live_data/sections/MACRO_THERMOMETER_DATA.json'
OUT=ROOT/'live_data/sections/NEWS_PULSE_OPERATIONAL.json'
ORDER=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']

def parse_asof(raw):
    s=str(raw or '')
    m=re.search(r'(20\d{2})-(\d{2})-(\d{2})',s)
    if m:return date(int(m.group(1)),int(m.group(2)),int(m.group(3)))
    m=re.search(r'(20\d{2})-(\d{2})',s)
    if m:return date(int(m.group(1)),int(m.group(2)),1)
    return None

def iso(d): return d.isoformat() if d else None

def finite_number(value):
    # bool, NaN, infinity and strings must not become market signals.
    return type(value) in (int, float) and math.isfinite(value)


def ois_items(data, today=None):
    today = today or datetime.now(timezone.utc).date()
    out = []
    for ccy, row in (data.get('currencies') or {}).items():
        if ccy not in ORDER or not isinstance(row, dict):
            continue
        status = row.get('operational_status')
        quality = row.get('quality')
        # WITHHELD/uncertified feeds must not become headlines even if a
        # future source accidentally contains non-null 1D changes.
        if not ((status == 'GREEN_OFFICIAL' and quality == 'OFFICIAL_CERTIFIED') or
                (status == 'GREEN_ESTIMATED' and quality == 'ESTIMATED_INFORMATIONAL')):
            continue
        as_of = row.get('as_of')
        source = row.get('source')
        try:
            vintage = date.fromisoformat(as_of) if isinstance(as_of, str) else None
        except ValueError:
            vintage = None
        if not vintage or vintage > today or not isinstance(source, str) or not source.strip():
            continue
        moves = []
        for h in ('3m', '6m', '12m'):
            v = ((row.get('horizons') or {}).get(h) or {}).get('change_1d_bp')
            if finite_number(v):
                moves.append((abs(v), h, float(v)))
        if not moves:
            continue
        _, h, v = max(moves)
        hrow = (row.get('horizons') or {}).get(h) or {}
        weekly = hrow.get('change_1w_bp')
        tone = 'più hawkish' if v > 0 else 'più dovish' if v < 0 else 'invariato'
        indicative = status == 'GREEN_ESTIMATED'
        futures_based = 'futures' in source.lower()
        if futures_based:
            prefix = ('repricing indicativo da futures' if indicative
                      else 'repricing implicito da futures')
            category = 'FUTURES_IMPLIED_REPRICING'
        else:
            prefix = 'repricing OIS stimato' if indicative else 'repricing OIS'
            category = 'OIS_PROXY_REPRICING' if indicative else 'OIS_REPRICING'
        detail = f"Movimento 1D {v:+.1f} bp sul bucket {h.upper()}"
        detail += (f"; variazione 1W {float(weekly):+.1f} bp."
                   if finite_number(weekly) else '; riferimento 1W non disponibile.')
        if futures_based:
            detail += ' Indicazione tratta da futures: non equivale a una curva OIS osservata.'
        elif indicative:
            detail += ' Stima informativa: non è una curva OIS ufficiale.'
        out.append({
            'category': category,
            'ccy': ccy, 'as_of': as_of,
            'title': f'{ccy}: {prefix} {tone} ({v:+.1f} bp {h.upper()} in 1D)',
            'detail': detail, 'quality': quality, 'confidence': row.get('confidence'),
            'source': source, 'importance': 'HIGH' if abs(v) >= 2 else 'MEDIUM',
            '_date': vintage,
        })
    return out


def macro_items(data, today=None):
    today = today or datetime.now(timezone.utc).date()
    out = []
    for ccy, row in (data.get('currencies') or {}).items():
        if ccy not in ORDER or not isinstance(row, dict):
            continue
        candidates = []
        for layer in ('inflation', 'labour'):
            x = row.get(layer) or {}
            if not isinstance(x, dict):
                continue
            # as_of is the OBSERVED REFERENCE PERIOD, not the release date.
            # Only a separately certified release timestamp makes it news.
            if x.get('release_date_verified') is not True:
                continue
            release = x.get('release_date')
            try:
                published = date.fromisoformat(release) if isinstance(release, str) else None
            except ValueError:
                published = None
            period = parse_asof(x.get('as_of'))
            if (not period or not published or published < period or
                    published > today or (today - published).days > 45 or
                    not finite_number(x.get('latest_value')) or
                    not isinstance(x.get('source'), str) or not x['source'].strip()):
                continue
            candidates.append((published, layer, x))
        if not candidates:
            continue
        published, layer, x = max(candidates, key=lambda z: z[0])
        label = x.get('label') or layer.title()
        val = x['latest_value']
        direction = x.get('direction') or 'N/D'
        acceleration = x.get('acceleration') or 'N/D'
        out.append({
            'category': 'MACRO_UPDATE', 'ccy': ccy, 'as_of': published.isoformat(),
            'reference_period': x.get('as_of'),
            'title': f'{ccy}: {label} {direction.lower()} · {acceleration.lower()}',
            'detail': f"Pubblicato il {published.isoformat()} (periodo {x.get('as_of')}). Ultimo valore {val}; percentile storico {x.get('percentile')}%; stato {x.get('temperature_label')}.",
            'quality': 'VERIFIED_RELEASE_DATE_MACRO_OBSERVATION', 'confidence': 'A',
            'source': x['source'],
            'importance': 'HIGH' if x.get('temperature_label') in ('MOLTO_CALDO','MOLTO_FREDDO') else 'MEDIUM',
            '_date': published,
        })
    return out


def stable_write(core, now=None):
    """Preserve content vintage while recording a separate successful daily check.

    The check stamp is refreshed at most once per Rome calendar date if the
    source content is identical, avoiding repeated commits and publication
    churn. No unchanged market signal is presented as newly generated.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware UTC check instant required")
    now = now.astimezone(timezone.utc)
    now_str = now.isoformat().replace('+00:00', 'Z')
    prior = None
    if OUT.exists():
        try:
            prior = json.loads(OUT.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            prior = None
    prior_core = dict(prior or {})
    prior_core.pop('generated_at_utc', None)
    prior_core.pop('last_checked_at_utc', None)
    content_changed = prior_core != core or not (prior or {}).get('generated_at_utc')
    generated = now_str if content_changed else prior['generated_at_utc']
    prev_check = (prior or {}).get('last_checked_at_utc')
    try:
        parsed = datetime.fromisoformat(prev_check.replace('Z', '+00:00'))
        prior_checked_today = (
            parsed.tzinfo is not None
            and parsed.astimezone(ZoneInfo('Europe/Rome')).date()
            == now.astimezone(ZoneInfo('Europe/Rome')).date()
            and parsed <= now
        )
    except (AttributeError, TypeError, ValueError):
        prior_checked_today = False
    checked = prev_check if (not content_changed and prior_checked_today) else now_str
    out = dict(core)
    out['generated_at_utc'] = generated
    out['last_checked_at_utc'] = checked
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return content_changed

def main():
    ois=json.loads(OIS.read_text(encoding='utf-8'));macro=json.loads(MACRO.read_text(encoding='utf-8'))
    items=ois_items(ois)+macro_items(macro)
    items.sort(key=lambda x:(x['_date'] or date.min,x['importance']=='HIGH',-ORDER.index(x['ccy']) if x['ccy'] in ORDER else 0),reverse=True)
    for x in items:x.pop('_date',None)
    items=items[:12]
    latest=max((parse_asof(x.get('as_of')) for x in items if parse_asof(x.get('as_of'))),default=None)
    now=datetime.now(timezone.utc)
    official=annotate_reaction_proof(
        collect_official_releases(now), ois,
        json.loads((ROOT/'live_data/sections/NATIVE_RATES_DATA.json').read_text(encoding='utf-8')),
        now=now,
    )
    # Keep the established deterministic market signal vintage independent of
    # external official statements. Never backfill a failed RSS feed or claim
    # that a press announcement proves a market move.
    # Published as an additional explicit evidence lane; unchanged classic
    # news headline items remain independent of macro-event attribution.
    # Anchor journal is written by the preceding Calendar/News workflow step.
    _, macro_context = macro_event_market_context_run(now=now,freeze=False)
    core={'schema':'GMFQ_NEWS_PULSE_OPERATIONAL_V1','status':'ACTIVE_DETERMINISTIC_LAYERS','content_as_of':iso(latest),'scope':{'external_news_feed':'OFFICIAL_G8_CB_EIA_RSS_SEPARATE_HEADLINE_ONLY','inputs':['OIS_OPERATIONAL_VIEW','MACRO_THERMOMETER_DATA'],'claim':'LATEST_VALIDATED_SIGNALS_NOT_GENERIC_HEADLINES'},'items':items,'official_releases':official,'macro_event_market_context':macro_context}
    changed=stable_write(core, now=now)
    print(json.dumps({'status':'PASS','changed':changed,'items':len(items),'content_as_of':iso(latest),'official_headlines':len(official['headlines']),'boj_selected_headlines':[{'title':h['title'],'at':h['published_at_utc']} for h in official['headlines'] if h.get('source_id')=='BOJ_NEWS'],'official_source_status':[{'id':x['source_id'],'status':x['status'],'count':x['accepted_items']} for x in official['sources']],'output':str(OUT.relative_to(ROOT))}))

if __name__=='__main__':main()
