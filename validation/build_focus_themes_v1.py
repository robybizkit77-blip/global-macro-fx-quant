import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CC=ROOT/'CURRENCY_COMPACT_PAYLOAD_V1_2026-10-07.json'
PA=ROOT/'PAIR_ATTENTION_BUCKETS_V1_2026-10-07.json'
OUT=ROOT/'FOCUS_THEMES_V1_2026-10-07.json'

cc=json.loads(CC.read_text())
pa=json.loads(PA.read_text())

curr=cc['currencies']
clean=[x['pair'] for x in pa['buckets']['CLEAN_ROBUST']]

themes=[]
if clean:
    themes.append({
        'type':'CLEAN_CROSSES',
        'label_it':'CROSS PIÙ COERENTI',
        'subjects':clean,
        'read_it':'Macro relativo, banca centrale, front-end/rates e prezzo sono allineati.',
        'meaning_it':'Sono i cross con la catena causale più pulita oggi; non è una previsione di rendimento.',
        'action_it':'Osservare per primi, poi verificare timing e rischio.',
    })

coherent=[]
for c,d in curr.items():
    m=d['macro_relative']; t=d['transmission']; r=d['robustness']
    if m['favored']>=5 and t['divergent']==0 and r['robust']==7:
        coherent.append(c)
if coherent:
    themes.append({
        'type':'CURRENCY_BROAD_COHERENCE',
        'label_it':'COERENZA RELATIVA G8',
        'subjects':sorted(coherent),
        'read_it':'La valuta è favorita nella maggioranza dei cross e non presenta divergenze di trasmissione nei confronti direzionali.',
        'meaning_it':'Il quadro relativo è più coerente del resto del G8, senza trasformarlo in uno score assoluto.',
        'action_it':'Usare come contesto per selezionare i cross, non come segnale standalone.',
    })

disconnect=[]
for c,d in curr.items():
    m=d['macro_relative']; t=d['transmission']
    directional=max(m['favored'],m['opposed'])>=5
    if directional and t['divergent']>=4:
        disconnect.append(c)
if disconnect:
    themes.append({
        'type':'MACRO_TRANSMISSION_DISCONNECT',
        'label_it':'MACRO E TRASMISSIONE NON COINCIDONO',
        'subjects':sorted(disconnect),
        'read_it':'Il quadro macro relativo è direzionale, ma molti cross mostrano trasmissione divergente.',
        'meaning_it':'È un’area da diagnosticare: può esserci ritardo, repricing o una view macro non ancora accettata dal mercato.',
        'action_it':'Capire quale layer diverge prima di usare la view operativamente.',
    })

changed=[]
for c,d in curr.items():
    if d.get('what_changed') not in (None,'BASELINE','STABILE'):
        changed.append({'currency':c,'state':d['what_changed']})
if changed:
    themes.append({
        'type':'NEW_CHANGE',
        'label_it':'COSA È CAMBIATO',
        'subjects':changed,
        'read_it':'Una o più valute hanno cambiato stato rispetto allo snapshot precedente.',
        'meaning_it':'È informazione nuova, non una conferma automatica.',
        'action_it':'Dare priorità al confronto con lo snapshot precedente.',
    })

# Fixed category priority; never score/rank subjects inside a theme.
priority=['NEW_CHANGE','CLEAN_CROSSES','CURRENCY_BROAD_COHERENCE','MACRO_TRANSMISSION_DISCONNECT']
themes=sorted(themes,key=lambda x:priority.index(x['type']))[:4]

out={
  'schema':'GMFQ_FOCUS_THEMES_V1',
  'status':'RESEARCH_ONLY_DESCRIPTIVE_NOT_PROMOTED',
  'purpose':'Maximum four compact themes for future dashboard focus. No numeric ranking, no trade signal, no predictive claim.',
  'theme_count':len(themes),
  'max_themes':4,
  'themes':themes,
  'guards':{
    'numeric_ranking':False,
    'trade_signal':False,
    'predictive_claim':False,
    'changes_engine_rules':False,
    'changes_live_data':False,
    'production_promotion':False,
  }
}
OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'theme_count':len(themes),'types':[x['type'] for x in themes]},ensure_ascii=False))
