import unittest
from datetime import datetime,timezone
from validation.macro.prepare_us_quarterly_cfna_revised_v1 import CONFIG,prepare_row,prepare
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
def fixture(ident):
    code,title,f,unit,lo,hi,*_=CONFIG[ident]
    step=3 if f=="Q" else 1
    ds=[f"{2017+i*step//12}-{i*step%12+1:02d}-01" for i in range(36)]
    vs=[(lo+hi)/2+i*.001 for i in range(len(ds))]
    row=dict(id=ident,unit=unit,frequency=f,dates=ds[:-2],values=vs[:-2],last_date=ds[-3],last_value=vs[-3])
    heading=title+" "+("Nonfarm Business" if code in ("ULCNFB","OPHNFB") else "Large and Middle-Market" if code=="DRTSCILM" else "")+" ("+code+")"
    units="Index, Seasonally Adjusted" if code!="DRTSCILM" else "Percent, Not Seasonally Adjusted"
    meta=f"<html><title>{heading}</title><body>Units: {units} Frequency: {'Quarterly' if f=='Q' else 'Monthly'}</body></html>".encode()
    raw=("observation_date,"+code+"\n"+"\n".join(f"{d},{v}" for d,v in zip(ds,vs))).encode()
    def fetch(url):return (meta if "/series/" in url else raw),url
    return row,fetch
class Tests(unittest.TestCase):
    def test_four_sources(self):
        for ident in CONFIG:
            row,fetch=fixture(ident)
            self.assertEqual(prepare_row(row,ident,NOW,fetch)["status"],"READY")
            self.assertEqual(prepare_row(row,ident,NOW,fetch)["status"],"NO_CHANGE")
    def test_sloos_mixed_columns_require_unique_match(self):
        ident="US_SLOOS_CI_LARGE_MIDDLE_history_value"
        row,fetch=fixture(ident)
        row["dates"]+=row["dates"][:]
        row["values"] += [v+10 for v in row["values"]]
        row["last_value"]=row["values"][-1]
        self.assertEqual(prepare_row(row,ident,NOW,fetch)["status"],"READY")
        self.assertEqual(len(row["dates"]),len(set(row["dates"])))
        self.assertTrue(row["current_vintage_provenance"]["legacy_duplicate_column_repair"])
    def test_bad_metadata(self):
        ident=next(iter(CONFIG));row,_=fixture(ident)
        with self.assertRaises(ValueError):prepare_row(row,ident,NOW,lambda url:(b"<html></html>",url))
if __name__=="__main__":unittest.main()
