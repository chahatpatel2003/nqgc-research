"""E0 — eligibility, the seven labels, base rates, label agreement and tradability. DEVELOPMENT ONLY."""
import datetime as dt, json, sys
sys.path.insert(0, "src")
import numpy as np, polars as pl
from nqgc.bias.daily import build_daily, TARGETS
from nqgc.bias.splits import OUT
from nqgc.bias.registry import record, file_hash
from nqgc.bias.report import _pct

E0 = OUT / "E0"; E0.mkdir(parents=True, exist_ok=True)
print("building daily table (development 2021-01-04 .. 2023-12-31) ...", flush=True)
daily, seq, seq_dates = build_daily("development", purpose="E0 daily table / labels (development only)")
assert daily["date"].max() <= dt.date(2023, 12, 31)
daily.write_parquet(E0 / "daily_development.parquet")
np.save(E0 / "seq1m_development.npy", seq)
pl.DataFrame({"date": seq_dates}).write_parquet(E0 / "seq1m_dates_development.parquet")
# targets file: date + labels + descriptive excursions only (no features)
tg = daily.select(["date", "year", "eligible", "elig_reason", "R20", "post_am_ret_pts", "post_mfe", "post_mae", "post_am_rng", "post_open"] + TARGETS)
tg.write_parquet(E0 / "targets_development.parquet")

lines = ["# E0 — eligibility, labels, base rates (DEVELOPMENT 2021–2023 only)", ""]
# eligibility
el = daily.group_by("year").agg(pl.len().alias("trade_dates"), pl.col("is_rth").sum().alias("rth_sessions"), pl.col("eligible").sum().alias("eligible")).sort("year")
reasons = daily.group_by(["year", "elig_reason"]).len().sort(["year", "elig_reason"])
lines += ["## Eligibility", "", "| Year | Trade dates | RTH sessions | Eligible |", "|---|---|---|---|"]
lines += [f"| {r['year']} | {r['trade_dates']} | {r['rth_sessions']} | {r['eligible']} |" for r in el.to_dicts()]
lines += [f"| all | {daily.height} | {int(daily['is_rth'].sum())} | {int(daily['eligible'].sum())} |", "", "Exclusion reasons by year: " + "; ".join(f"{r['year']} {r['elig_reason']}={r['len']}" for r in reasons.to_dicts() if r["elig_reason"] != "ok"), ""]
e = daily.filter(pl.col("eligible"))
# base rates
lines += ["## Label base rates on eligible days (share of +1 / −1 / FLAT)", ""]
hdr = "| Year | n | " + " | ".join(t[2:] for t in TARGETS) + " |"
lines += [hdr, "|" + "---|" * (2 + len(TARGETS))]
base = {}
for yr in sorted(e["year"].unique().to_list()) + ["all"]:
    s = e if yr == "all" else e.filter(pl.col("year") == yr)
    cells = []
    for t in TARGETS:
        v = s[t].drop_nulls().to_numpy()
        up, dn, fl = (v == 1).mean(), (v == -1).mean(), (v == 0).mean()
        base[(str(yr), t)] = dict(n=int(v.size), up=float(up), down=float(dn), flat=float(fl))
        cells.append(f"{100*up:.1f}/{100*dn:.1f}/{100*fl:.1f}")
    lines.append(f"| {yr} | {s.height} | " + " | ".join(cells) + " |")
lines += ["", "Read: up-share / down-share / FLAT-share in %. Always-BUY accuracy on decisive days = up / (up + down).", ""]
# agreement matrix
lines += ["## Label agreement (share of days where both labels are decisive and equal; diagonal = decisive share)", ""]
lines += ["| | " + " | ".join(t[2:] for t in TARGETS) + " |", "|" + "---|" * (1 + len(TARGETS))]
agree = {}
for a in TARGETS:
    row = []
    for b in TARGETS:
        va, vb = e[a].to_numpy().astype(float), e[b].to_numpy().astype(float)
        m = ~np.isnan(va) & ~np.isnan(vb) & (va != 0) & (vb != 0)
        val = float((va[m] == vb[m]).mean()) if m.any() else np.nan
        if a == b:
            val = float(((va != 0) & ~np.isnan(va)).mean())
        agree[(a, b)] = val
        row.append(f"{100*val:.1f}")
    lines.append(f"| {a[2:]} | " + " | ".join(row) + " |")
lines.append("")
# tradability: excursion in the labelled direction
lines += ["## Tradability — was the labelled direction the better bias? (eligible days, R20 units)", "",
          "| Target | label | n | median favourable excursion | median adverse excursion | share fav ≥ 0.5·R20 | share net move agrees (T1) |", "|---|---|---|---|---|---|---|"]
trad = {}
mfe, mae, ret, R = e["post_mfe"].to_numpy(), e["post_mae"].to_numpy(), e["post_am_ret_pts"].to_numpy(), e["R20"].to_numpy()
for t in TARGETS:
    v = e[t].to_numpy().astype(float)
    for lab in (1, -1):
        m = v == lab
        fav = np.where(lab > 0, mfe, mae)[m] / R[m]
        adv = np.where(lab > 0, mae, mfe)[m] / R[m]
        agree_t1 = float((np.sign(ret[m]) == lab).mean()) if m.any() else np.nan
        trad[(t, lab)] = dict(n=int(m.sum()), fav_med=float(np.median(fav)) if m.any() else np.nan, adv_med=float(np.median(adv)) if m.any() else np.nan,
                              fav_ge_half=float((fav >= 0.5).mean()) if m.any() else np.nan, t1_agree=agree_t1)
        x = trad[(t, lab)]
        lines.append(f"| {t[2:]} | {'BUY' if lab > 0 else 'SELL'} | {x['n']} | {x['fav_med']:.2f} | {x['adv_med']:.2f} | {_pct(x['fav_ge_half'])} | {_pct(x['t1_agree'])} |")
lines += ["", "Favourable excursion = move from the 09:30 open in the labelled direction to the 09:30–12:00 extreme; adverse = the opposite extreme.",
          f"R20 (median of the prior 20 sessions' 09:30–12:00 ranges) on eligible days: median {np.median(R):.0f} pts, {100*np.median(R/e['post_open'].to_numpy()):.2f}% of price.", ""]
(E0 / "REPORT.md").write_text("\n".join(lines))
json.dump({"base": {f"{k[0]}|{k[1]}": v for k, v in base.items()}, "agree": {f"{k[0]}|{k[1]}": v for k, v in agree.items()},
           "tradability": {f"{k[0]}|{k[1]}": v for k, v in trad.items()}}, open(E0 / "summary.json", "w"), indent=1, default=float)
record("E0", {"phase": "development", "rows": daily.height, "eligible": int(daily["eligible"].sum()), "daily_hash": file_hash(E0 / "daily_development.parquet"),
              "targets_hash": file_hash(E0 / "targets_development.parquet"), "base_rates_all": {t: base[("all", t)] for t in TARGETS}})
print("\n".join(lines))
