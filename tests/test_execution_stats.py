import datetime as dt
import polars as pl
import pytest
from nqgc.execution import CostModel, InstrumentSpec
from nqgc.stats import summary, breakdown
from nqgc.risk import size_fixed_dollar_risk, AccountState, PropFirmRules


def test_cost_model_from_config_all_instruments():
    for ins in ("NQ", "MNQ", "GC", "MGC"):
        c = CostModel.from_config(ins)
        assert c.fee_per_side > 0 and c.spec.tick_size > 0
    c = CostModel.from_config("NQ")
    assert c.fill_market(17000.0, 1) == 17000.25 and c.fill_market(17000.0, -1) == 16999.75
    assert c.fill_stop(17000.0, 17010.0, 1) == 17010.25          # gap through the stop -> open + slip
    assert c.fill_limit(17000.0, 16990.0, 1) == 16990.0          # opened below the limit -> better price
    assert c.limit_fillable(17000.0, 17020.0, 17000.0, 1) is False
    assert c.limit_fillable(17000.0, 17020.0, 16999.75, 1) is True
    assert c.fees(2) == 2 * 2 * c.fee_per_side


def test_sizing_and_account_rules():
    assert size_fixed_dollar_risk(500, 10, 20.0) == 2
    assert size_fixed_dollar_risk(500, 10, 20.0, max_contracts=1) == 1
    assert size_fixed_dollar_risk(500, 0, 20.0) == 0
    a = AccountState(PropFirmRules(account_size=50000, trailing_drawdown=2000, trailing_drawdown_basis="eod", daily_loss_limit=1000))
    a.new_day(dt.date(2024, 1, 2))
    a.on_realised(1500, None); a.new_day(dt.date(2024, 1, 3))
    assert a.hwm == 51500 and a.trailing_floor == 49500
    a.on_realised(-999, None); assert a.breached is None
    a.on_realised(-2, None); assert a.breached == "daily_loss_limit"


def test_summary_and_breakdowns():
    ts = [dt.datetime(2024, 1, 2, 15, 0, tzinfo=dt.timezone.utc) + dt.timedelta(days=i) for i in range(6)]
    tr = pl.DataFrame({"net_usd": [100.0, -50.0, 200.0, -50.0, 0.0, 300.0], "gross_usd": [104.0, -46.0, 204.0, -46.0, 4.0, 304.0],
                       "r_multiple": [1.0, -0.5, 2.0, -0.5, 0.0, 3.0], "fees_usd": [4.0] * 6, "slippage_usd": [5.0] * 6,
                       "mae_pts": [1.0] * 6, "mfe_pts": [2.0] * 6, "hold_minutes": [10.0] * 6, "side": [1, -1, 1, -1, 1, 1],
                       "ambiguous": [False] * 6, "tick_resolved": [False] * 6, "session": ["RTH"] * 6,
                       "trade_date": [t.date() for t in ts], "entry_ts": ts, "exit_ts": ts, "exit_reason": ["target", "stop", "target", "stop", "flatten", "target"]})
    s = summary(tr, 50000)
    assert s["trades"] == 6 and s["win_rate"] == 0.5 and s["net_pnl"] == 500 and s["gross_pnl"] == 524
    assert s["profit_factor"] == 600 / 100 and s["consecutive_losses"] == 1 and s["max_drawdown_usd"] == 50
    assert breakdown(tr, "side").height == 2 and breakdown(tr, "dow").height >= 1
