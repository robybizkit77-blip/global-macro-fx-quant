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
FX_HISTORY=ROOT/'live_data/sections/ECB_G8_PRICE_HISTORY.json'
SOVEREIGN=ROOT/'live_data/sections/NATIVE_RATES_DATA.json'
CROSS_ASSET=ROOT/'site/fx-quant-v2/cross-asset-live-data.json'


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


def _source_day(s, today, max_age_days=7):
    """Strict market close with explicit date and bounded historical age."""
    try:
        d = date.fromisoformat(s)
        return d if d <= today and 0 <= (today-d).days <= max_age_days else None
    except (TypeError, ValueError):
        return None


def cross_asset_items(data, today):
    """Research-only closing data, not issuer news or intraday impact."""
    streams = (data or {}).get('streams') or {}
    if (data or {}).get('eligible_for_fx_core') is not False:
        return []
    specs = (
        ('SP500', 'S&P 500', 'MARKET_EQUITY_CLOSE'),
        ('NASDAQCOM', 'Nasdaq Composite', 'MARKET_EQUITY_CLOSE'),
        ('VIX', 'VIX', 'MARKET_VOLATILITY_CLOSE'),
        ('HY_OAS', 'Credito HY OAS', 'MARKET_CREDIT_OAS'),
        ('IG_OAS', 'Credito IG OAS', 'MARKET_CREDIT_OAS'),
    )
    result = []
    for key, label, category in specs:
        r = streams.get(key) or {}
        vintage = _source_day(r.get('date'), today)
        prev = _source_day(r.get('previous_date'), today, max_age_days=14)
        source = r.get('publisher')
        if (not vintage or not prev or prev >= vintage or
                r.get('quality') != 'PUBLISHED_SOURCE_RESEARCH_ONLY' or
                not isinstance(source, str) or not source.strip()):
            continue
        history = r.get('history') or []
        if (len(history) < 2 or not isinstance(history[-1], list) or
                not isinstance(history[-2], list) or
                history[-1][0] != vintage.isoformat() or
                history[-2][0] != prev.isoformat()):
            continue
        current, prior = r.get('value'), r.get('previous')
        if (not all(finite_number(z) and z > 0 for z in (current, prior)) or
                not all(finite_number(z) for z in (history[-1][1], history[-2][1])) or
                abs(current-history[-1][1]) > 1e-6 or
                abs(prior-history[-2][1]) > 1e-6):
            continue
        if key.endswith('_OAS'):
            change = (current-prior)*100
            delta = f'{change:+.1f} pb'
            base = f'{current:.2f}%'
            importance = 'HIGH' if abs(change) >= 10 else 'MEDIUM'
        elif key == 'VIX':
            change = current-prior
            delta = f'{change:+.2f} punti'
            base = f'{current:.2f}'
            importance = 'HIGH' if abs(change) >= 3 else 'MEDIUM'
        else:
            change = (current/prior-1)*100
            delta = f'{change:+.2f}%'
            base = f'{current:.2f}'
            importance = 'HIGH' if abs(change) >= 1.5 else 'MEDIUM'
        result.append({
            'category': category, 'ccy': '',
            'as_of': vintage.isoformat(), 'reference_previous_date': prev.isoformat(),
            'title': f'{label}: {delta} nella chiusura del {vintage.isoformat()}',
            'detail': f'Livello {base}; confronto con chiusura {prev.isoformat()}. '
                      'Dato di mercato storico, non prova di un evento causale o di flussi.',
            'quality': 'PUBLISHED_SOURCE_RESEARCH_ONLY', 'confidence': 'B',
            'source': source, 'source_url': r.get('source_url'),
            'importance': importance, '_date': vintage,
        })
    return result


def fx_fixing_items(data, today):
    """Only ECB same-fixing cross rates; no FX direction from mixed calendars."""
    if (data or {}).get('source') != 'ECB euro foreign exchange reference rates':
        return []
    rows = (data or {}).get('rows') or []
    if len(rows) < 2:
        return []
    last, prior = rows[-1], rows[-2]
    vintage = _source_day(last.get('Date'), today)
    earlier = _source_day(prior.get('Date'), today, max_age_days=14)
    if (not vintage or not earlier or earlier >= vintage or
            (data or {}).get('last_as_of') != last.get('Date')):
        return []
    pairs = (
        ('EURUSD', 'EUR/USD', 'EUR', 'USD'),
        ('USDJPY', 'USD/JPY', 'USD', 'JPY'),
        ('AUDCAD', 'AUD/CAD', 'AUD', 'CAD'),
    )
    result=[]
    for key, label, base, quote in pairs:
        x0, x1 = prior.get(base), prior.get(quote)
        y0, y1 = last.get(base), last.get(quote)
        if not all(finite_number(n) and n > 0 for n in (x0, x1, y0, y1)):
            continue
        before, after = x1/x0, y1/y0  # ECB: units of currency per EUR
        change = (after/before-1)*100
        result.append({
            'category': 'MARKET_FX_ECB_FIXING', 'ccy': base, 'pair': key,
            'as_of': vintage.isoformat(), 'reference_previous_date': earlier.isoformat(),
            'title': f'{label}: {change:+.2f}% fra due fixing BCE',
            'detail': f'1 {base} = {after:.5f} {quote} al fixing {vintage.isoformat()}; '
                      f'variazione vs {earlier.isoformat()}. Non è una quotazione intraday '
                      'e non prova quale economia o flusso abbia causato il movimento.',
            'quality': 'OFFICIAL_ECB_REFERENCE_FIXING', 'confidence': 'A',
            'source': 'BCE · cambi di riferimento euro (cross derivato da due fixing)',
            'source_url': data.get('source_url'), 'importance': 'MEDIUM',
            '_date': vintage,
        })
    return result


def government_curve_items(data, today):
    """2Y/10Y from exactly paired source-history sessions; do not trust orphan deltas."""
    result = []
    for ccy in ('USD','EUR','JPY'):
        r = (data or {}).get(ccy) or {}
        vintage = _source_day(r.get('date'), today)
        if (not vintage or r.get('quality') != 'FULL_CURRENT_OFFICIAL' or
                not isinstance(r.get('source'), str) or not r['source'].strip()):
            continue
        h2,h10=r.get('history2') or {},r.get('history10') or {}
        d2,v2=h2.get('dates') or [],h2.get('values') or []
        d10,v10=h10.get('dates') or [],h10.get('values') or []
        if len(d2)<2 or len(d2)!=len(v2) or len(d10)<2 or len(d10)!=len(v10):
            continue
        m2=dict(zip(d2,v2));m10=dict(zip(d10,v10))
        common=sorted(z for z in m2 if z in m10 and _source_day(z,today,14) and
                      finite_number(m2[z]) and finite_number(m10[z]))
        if len(common)<2 or common[-1]!=vintage.isoformat():
            continue
        old,new=common[-2:]
        if (abs(m2[new]-r.get('2Y',float('inf')))>0.011 or
                abs(m10[new]-r.get('10Y',float('inf')))>0.011):
            continue
        dfront=(m2[new]-m2[old])*100
        dlong=(m10[new]-m10[old])*100
        result.append({
            'category': 'MARKET_GOVERNMENT_RATES', 'ccy': ccy,
            'as_of': new, 'reference_previous_date': old,
            'title': f'{ccy}: governativo 2Y {dfront:+.1f} pb, 10Y {dlong:+.1f} pb',
            'detail': f'Fra {old} e {new}; 2Y {m2[new]:.3f}%, 10Y {m10[new]:.3f}%. '
                      'Rendimenti governativi: non è una curva OIS e non prova di per sé un repricing della banca centrale.',
            'quality': 'FULL_CURRENT_OFFICIAL', 'confidence': 'A',
            'source': r['source'], 'importance': 'MEDIUM', '_date': vintage,
        })
    return result


def load_market_input(path):
    """Missing/corrupt optional research input omits that lane, never fabricates it."""
    try:
        value=json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value,dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


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
    now=datetime.now(timezone.utc)
    today=now.astimezone(ZoneInfo('Europe/Rome')).date()
    items=ois_items(ois,today)+macro_items(macro,today)
    items+=fx_fixing_items(load_market_input(FX_HISTORY),today)
    items+=government_curve_items(load_market_input(SOVEREIGN),today)
    items+=cross_asset_items(load_market_input(CROSS_ASSET),today)
    items.sort(key=lambda x:(x['_date'] or date.min,x['importance']=='HIGH',-ORDER.index(x['ccy']) if x['ccy'] in ORDER else 0),reverse=True)
    for x in items:x.pop('_date',None)
    items=items[:20]
    latest=max((parse_asof(x.get('as_of')) for x in items if parse_asof(x.get('as_of'))),default=None)
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
    core={'schema':'GMFQ_NEWS_PULSE_OPERATIONAL_V1','status':'ACTIVE_DETERMINISTIC_LAYERS','content_as_of':iso(latest),'scope':{'external_news_feed':'OFFICIAL_G8_CB_EIA_RSS_SEPARATE_HEADLINE_ONLY','inputs':['OIS_OPERATIONAL_VIEW','MACRO_THERMOMETER_DATA','ECB_G8_PRICE_HISTORY','NATIVE_RATES_DATA','CROSS_ASSET_LIVE_RESEARCH'],'claim':'LATEST_VALIDATED_SIGNALS_NOT_GENERIC_HEADLINES'},'items':items,'official_releases':official,'macro_event_market_context':macro_context}
    changed=stable_write(core, now=now)
    print(json.dumps({'status':'PASS','changed':changed,'items':len(items),'content_as_of':iso(latest),'official_headlines':len(official['headlines']),'boj_selected_headlines':[{'title':h['title'],'at':h['published_at_utc']} for h in official['headlines'] if h.get('source_id')=='BOJ_NEWS'],'official_source_status':[{'id':x['source_id'],'status':x['status'],'count':x['accepted_items']} for x in official['sources']],'output':str(OUT.relative_to(ROOT))}))

if __name__=='__main__':main()
