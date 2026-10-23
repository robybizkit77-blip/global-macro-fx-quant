#!/usr/bin/env python3
"""One-hour Dukascopy BI5 EURUSD probe; never promotes research to FX scores."""
import argparse,hashlib,json,lzma,math,struct,urllib.request
from datetime import datetime,timezone,timedelta
from pathlib import Path
URL="https://datafeed.dukascopy.com/datafeed/EURUSD/2026/09/02/12h_ticks.bi5"
BASE=datetime(2026,10,2,12,0,tzinfo=timezone.utc)
FMT=struct.Struct(">IIIff")
def summarize(data):
    if not data or len(data)>10000000: raise ValueError("empty/oversized source")
    dec=lzma.LZMADecompressor(format=lzma.FORMAT_AUTO,memlimit=100000000)
    raw=dec.decompress(data,max_length=75000001)
    if not dec.eof or len(raw)>75000000 or len(raw)%20: raise ValueError("incomplete/invalid BI5")
    ticks=[];last=-1
    for ms,ask_i,bid_i,av,bv in FMT.iter_unpack(raw):
        bid=bid_i/100000;ask=ask_i/100000
        if ms<last or ms>=3600000 or not(.5<bid<=ask<2.5) or ask-bid>.02 or not math.isfinite(av+bv):
            raise ValueError("invalid timestamp/quotes/scale/spread")
        ticks.append((ms,bid,ask));last=ms
    if not ticks:raise ValueError("empty decoded hour")
    def pick(minutes):
        target=minutes*60000
        candidates=[t for t in ticks if target-120000<=t[0]<=target]
        if not candidates:return None
        ms,bid,ask=candidates[-1]
        return {"utc":(BASE+timedelta(milliseconds=ms)).isoformat(),
          "bid":bid,"ask":ask,"mid":round((bid+ask)/2,7),
          "spread_pips":round((ask-bid)*10000,3),"age_s":round((target-ms)/1000,3)}
    p,q=pick(25),pick(35)
    return {"schema":"GMFQ_DUKASCOPY_EURUSD_BI5_ONE_HOUR_PROBE_V1",
     "source":URL,"sha256":hashlib.sha256(data).hexdigest(),"tick_count":len(ticks),
     "release_at":"2026-10-02T12:30:00+00:00",
     "pre_0825_new_york":p,"post_0835_new_york":q,
     "fx_window_complete":p is not None and q is not None,
     "mid_move_pips":round((q["mid"]-p["mid"])*10000,3) if p and q else None,
     "source_license_independently_certified":False,"causal_attribution":False,
     "ois_window_available":False,"treasury_window_available":False,
     "pre_release_consensus_available":False,"eligible_for_backtest":False,
     "safe_to_publish_new_D":False,"safe_to_update_pair_theses":False,
     "writes_live_data":False}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--offline-bi5",type=Path)
    ap.add_argument("--out",type=Path)
    args=ap.parse_args()
    if args.out and not args.out.resolve().is_relative_to(Path("/tmp")):raise ValueError("only /tmp allowed")
    if args.offline_bi5:
        buf=args.offline_bi5.read_bytes()
    else:
        req=urllib.request.Request(URL,headers={"User-Agent":"GMFQ-Research-Source-Audit/1.0"})
        with urllib.request.urlopen(req,timeout=12) as response:
            if response.status!=200:raise ValueError("unavailable source status")
            buf=response.read(10000001)
    r=summarize(buf)
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(r,indent=2)+"\n")
    print(json.dumps(r))
if __name__=="__main__":main()
