#!/usr/bin/env python3
"""Diagnostic-only interpretation; never changes canonical score or trade entries."""
import json
from pathlib import Path
SRC=Path(__file__).resolve().parents[2]/'live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json'
STRUCT={'CONTRASTO STRUTTURALE FORTE':'FORTE','VANTAGGIO RELATIVO PARZIALE':'PARZIALE','SEPARAZIONE RATES MATERIALE':'PARZIALE','PILASTRI DIVISI':'DIVISA','NESSUN CONTRASTO':'DEBOLE'}
def assess(row):
 s=row.get('setup') or {}
 if s.get('quality')=='NON VALUTABILE' or not s.get('structuralFav'):return dict(thesis='NON VALUTABILE',trade='NON VALUTABILE',reason='Dati insufficienti',entry_signal=False)
 thesis=STRUCT.get((s.get('structural') or {}).get('quality'),'NON VALUTABILE')
 price=(s.get('price') or {}).get('state')
 timing=(s.get('timing') or {}).get('state')
 extension=(s.get('extension') or {}).get('state')
 cot=(s.get('cot') or {}).get('state')
 if thesis in ('NON VALUTABILE','DEBOLE','DIVISA'):trade,reason='ATTENDERE','Struttura non sufficientemente definita'
 elif price=='BAD' or timing=='ADVERSE':trade,reason='ATTENDERE','Prezzo o dinamica contrari'
 elif extension=='ADVANCED':trade,reason='NON INSEGUIRE','Movimento già esteso'
 elif price=='GOOD' and timing not in ('ADVERSE','UNCERTAIN','MIXED') and cot!='DIVERGENT':trade,reason='DA STUDIARE','Verificare condizioni di ingresso sul grafico'
 else:trade,reason='CERCA CONFERMA','Mancano conferme operative'
 return dict(thesis=thesis,trade=trade,reason=reason,entry_signal=False)
def main():
 raw=json.loads(SRC.read_text())
 assert raw['schema']=='GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1' and raw['pair_count']==28 and len(raw['pairs'])==28 and raw['thesis_is_not_entry'] is True
 rows={pair:assess(row) for pair,row in raw['pairs'].items()}
 assert all(not x['entry_signal'] for x in rows.values())
 assert all(rows[pair]['thesis']==rows[pair]['trade']=='NON VALUTABILE' for pair,row in raw['pairs'].items() if row['setup']['quality']=='NON VALUTABILE')
 result={'schema':'PAIR_THESIS_TRADE_DIAGNOSTIC_V0','as_of':raw['price_asof'],'diagnostic_only':True,'rows':rows}
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
