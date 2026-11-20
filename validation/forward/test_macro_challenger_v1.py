from datetime import date, datetime, timedelta
from itertools import combinations
from pathlib import Path
import unittest

from validation.forward import macro_challenger_v1 as m

DAY = date(2026, 11, 20)
NOW = datetime.fromisoformat("2026-11-20T11:00:00+00:00")


def country(*, growth=0.4, prior=None, jobs=0.3, period="2026-10"):
    g = {"reference_quarter": "2026Q3", "publisher_release_day": "2026-10-30",
         "nonannualized_qoq_descriptive_pct": growth, "is_growth_strength_score": False}
    if prior is not None:
        g["prior_documented_quarter"] = {
            "reference_quarter": "2026Q2", "publisher_release_day": "2026-08-30",
            "nonannualized_qoq_descriptive_pct": prior, "is_growth_strength_score": False,
        }
    return {"growth": g, "labour": {"observation_period": period,
                                   "change_over_three_observation_intervals_pp": jobs},
            "inflation": {"observation_period": period, "change_direction": "UP"}}


def curve(yield_2y, change, start="2026-11-12", end="2026-11-19"):
    return {"date": end, "2Y": yield_2y, "source": "official 2Y example",
            "freshness_status": "CURRENT_OFFICIAL_SAME_BASIS",
            "weekly2_validation": {"start_date": start, "end_date": end,
                                   "source": "official 2Y example", "change_bp": change,
                                   "start_value": yield_2y - change / 100, "end_value": yield_2y}}


def fx(as_of):
    days = [date(2026, 11, 1) + timedelta(days=i) for i in range(45)]
    currencies = sorted(m.G8 - {"EUR"})
    rows = []
    for n, day in enumerate(d for d in days if d <= as_of and d.weekday() < 5):
        rows.append({"Date": day.isoformat(), "EUR": 1,
                     **{c: (i + 2) + n / 100 for i, c in enumerate(currencies)}})
    return {"schema": "GMFQ_ECB_G8_PRICE_HISTORY_V1", "status": "CURRENT_OFFICIAL_HISTORY",
            "base": "EUR", "source_url": m.SOURCE_URL, "last_as_of": rows[-1]["Date"], "rows": rows}


def fixture():
    canon = list(combinations(sorted(m.G8), 2))
    context = {"schema": "GMFQ_MACRO_V3_G8_28PAIR_PUBLIC_OBSERVED_CONTEXT_V1", "safe_to_republish_D": False,
               "generated_europe_rome_day": DAY.isoformat(),
               "countries": {c: country(jobs=-0.3 if c == "EUR" else 0.3) for c in m.G8}}
    return {"macro": context, "rates": {"EUR": curve(3.0, 10), "USD": curve(4.5, 0)},
            "core": {"asOf": m.FROZEN_MACRO_ASOF, "pairs": [{"pair": f"{a}/{b}"} for a, b in canon],
                     "pairStates": {f"{a}/{b}": {"convergence_winner": a} for a, b in canon}},
            "prices": fx(DAY - timedelta(days=1))}


class MacroChallengerTests(unittest.TestCase):
    def test_direction_disagreement_veto_and_unmatched_rate_windows(self):
        macro = {"EUR": country(jobs=-0.3), "USD": country(jobs=0.4)}
        result = m.compare_pair("EUR", "USD", macro, {"EUR": curve(3, -10), "USD": curve(4, 0)}, DAY)
        self.assertEqual((result["candidate"], result["rates_contradicted"]), (0, True))
        unmatched = {"EUR": curve(3, -10, start="2026-11-11"), "USD": curve(4, 0)}
        result = m.compare_pair("EUR", "USD", macro, unmatched, DAY)
        self.assertIsNone(result["yield_spread_week_change_bp"])
        self.assertEqual((result["candidate"], result["rates_confirmed"]), (1, False))

    def test_gdp_acceleration_on_same_quarter_and_independent_labour_cadence(self):
        macro = {"EUR": country(growth=0.6, prior=0.3), "NZD": country(growth=0.6, prior=0.9, period="2026Q3")}
        result = m.compare_pair("EUR", "NZD", macro, {}, DAY)
        self.assertEqual(result["growth_basis"], "GDP_ACCELERATION_2026Q3")
        self.assertEqual(result["growth"], 1)
        self.assertIsNone(result["labour"])
        self.assertEqual(result["candidate"], 1)
        self.assertEqual(m.compare_pair("EUR", "NZD", macro, {}, DAY)["candidate"],
                         -m.compare_pair("NZD", "EUR", macro, {}, DAY)["candidate"])

    def test_prices_never_change_challenger_direction(self):
        a = fixture()
        b = fixture()
        b["prices"]["rows"][-1]["USD"] *= 0.5
        one = m.build(a, {}, NOW, "c" * 40)
        two = m.build(b, {}, NOW, "d" * 40)
        self.assertEqual(len(one["pairs"]), 28)
        self.assertTrue(one["pairs"]["EUR/USD"]["rates_confirmed"])
        self.assertNotEqual(one["pairs"]["EUR/USD"]["momentum"], two["pairs"]["EUR/USD"]["momentum"])
        self.assertEqual({p: x["candidate"] for p, x in one["pairs"].items()},
                         {p: x["candidate"] for p, x in two["pairs"].items()})
        self.assertFalse(one["safe_to_publish_new_core"])

    def test_weekly_observation_waits_and_uses_later_archival_date(self):
        row = m.build(fixture(), {}, NOW, "c" * 40)
        file = Path("2026-11-20.json")
        entries = [(file, row, "2026-11-23T08:00:00+00:00")]
        early = datetime.fromisoformat("2026-11-30T22:00:00+01:00")
        result = m.evaluate(entries, fx(early.date()), early)
        self.assertEqual(result["windows"][0]["status"], "WAITING_FOR_WEEKLY_ECB_OUTCOME")
        late = datetime.fromisoformat("2026-12-01T22:00:00+01:00")
        result = m.evaluate(entries, fx(late.date()), late)
        window, = result["windows"]
        self.assertEqual((window["start_fixing"], window["end_fixing"]), ("2026-11-24", "2026-12-01"))
        self.assertEqual(result["nonoverlapping_by_formula"][row["formula_sha256"]]["windows"], 1)
        self.assertFalse(result["predictive_validation_established"])
        row["pairs"]["EUR/USD"]["candidate"] = -1
        with self.assertRaisesRegex(ValueError, "frozen contract"):
            m.evaluate(entries, fx(late.date()), late)


if __name__ == "__main__":
    unittest.main()
