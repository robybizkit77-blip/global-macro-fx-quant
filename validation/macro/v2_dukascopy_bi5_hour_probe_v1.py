#!/usr/bin/env python3
"""OFFLINE ONLY Dukascopy BI5 EUR/USD one-hour decoder; network blocked pending written consent.

This is not a feed, scheduler or production importer. It decodes one chosen
hour and keeps transport evidence separate from a licence or market claim.
"""
import argparse,hashlib,json,lzma,math,re,struct
from datetime import datetime,timezone,timedelta
from pathlib import Path
URL="https://datafeed.dukascopy.com/datafeed/EURUSD/2026/09/02/12h_ticks.bi5"
FMT=struct.Struct(">IIIff")
MAX_SOURCE_BYTES=10_000_000
URL_RE=re.compile(r"^https://datafeed\.dukascopy\.com/datafeed/EURUSD/(?P<year>\d{4})/(?P<month0>\d{2})/(?P<day>\d{2})/(?P<hour>\d{2})h_ticks\.bi5$")
def source_clock(source_url):
    """Parse the canonical BI5 path, whose month is zero-based."""
    m=URL_RE.fullmatch(source_url)
    if not m:raise ValueError("expected canonical HTTPS Dukascopy EURUSD BI5 hour URL")
    p={k:int(v) for k,v in m.groupdict().items()}
    if not 0<=p["month0"]<=11 or not 0<=p["hour"]<=23:raise ValueError("invalid zero-based month or hour in BI5 URL")
    try:base=datetime(p["year"],p["month0"]+1,p["day"],p["hour"],tzinfo=timezone.utc)
    except ValueError as e:raise ValueError("invalid calendar date in BI5 URL") from e
    return base,p
def fetch(sourcdef fetch(source_url,timeout_s):
    """Do NOT automate Dukascopy access without prior express written consent.

    Dukascopy website terms prohibit scraping, robots and automated acquisition
    absent prior express written consent. This entrypoint intentionally has no
    network implementation or self-attestation override.
    """
    source_clock(source_url)
    raise PermissionError(
        "DUKASCOPY_AUTOMATED_ACCESS_BLOCKED: prior express written consent "
        "has not been independently verified; offline fixtures only"
    )
ata,*,source_url=URL,transport_receipt=None):
    BASE,parts=source_clock(source_url)
    if not data or len(data)>MAX_SOURCE_BYTES: raise ValueError("empty/oversized source")
    if transport_receipt and transport_receipt.get("content_length")!=len(data):raise ValueError("transport receipt content length does not match source bytes")
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
        return {"observed_at_utc":(BASE+timedelta(milliseconds=ms)).isoformat(),
          "bid":bid,"ask":ask,"mid":round((bid+ask)/2,7),
          "spread_pips":round((ask-bid)*10000,3),"age_s":round((target-ms)/1000,3)}
    p,q=pick(25),pick(35)
    return {"schema":"GMFQ_DUKASCOPY_EURUSD_BI5_ONE_HOUR_PROBE_V2",
     "source_declared":"Dukascopy public datafeed BI5 binary","source_url":source_url,
     "source_path_calendar_utc":BASE.isoformat(),"bi5_month_index_zero_based":parts["month0"],
     "source_sha256":hashlib.sha256(data).hexdigest(),"source_bytes_n":len(data),
     "transport_receipt":transport_receipt,"source_bytes_externally_retrieved":transport_receipt is not None,"tick_count":len(ticks),
     "release_at":"2026-10-02T12:30:00+00:00",
     "pre_0825_new_york":p,"post_0835_new_york":q,
     "fx_window_complete":p is not None and q is not None,
     "mid_move_pips":round((q["mid"]-p["mid"])*10000,3) if p and q else None,
     "source_license_independently_certified":False,"usage_authorization_not_established":True,"causal_attribution":False,
     "ois_window_available":False,"treasury_window_available":False,
     "pre_release_consensus_available":False,"eligible_for_backtest":False,
     "safe_to_publish_new_D":False,"safe_to_update_pair_theses":False,
     "writes_live_data":False}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--offline-bi5",type=Path)
    ap.add_argument("--source-url",default=URL)
    ap.add_argument("--timeout-s",type=int,default=45)
    ap.add_argument("--out",type=Path)
    args=ap.parse_args()
    if not args.offline_bi5:
        ap.error("Automated BI5 network download disabled pending independent written permission; use --offline-bi5 with authorized local bytes")
    if args.out and not args.out.resolve().is_relative_to(Path("/tmp")):raise ValueError("only /tmp allowed")
    if not 1<=args.timeout_s<=60:raise ValueError("timeout must be between 1 and 60 seconds")
    if args.offline_bi5:
        buf=args.offline_bi5.read_bytes();receipt=None
    else:
        buf,receipt=fetch(args.source_url,args.timeout_s)
    r=summarize(buf,source_url=args.source_url,transport_receipt=receipt)
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(r,indent=2)+"\n")
    print(json.dumps(r))
if __name__=="__main__":main()
