"""Position sizing and prop-firm account rules (all parameters from configs/propfirm_*.yaml)."""
from __future__ import annotations
import datetime as dt
import math
from dataclasses import dataclass, field

import yaml

from .paths import CONFIG_DIR


def size_fixed(contracts: int, **_) -> int:
    return int(contracts)


def size_fixed_dollar_risk(risk_usd: float, stop_points: float, point_value: float, max_contracts: int | None = None, **_) -> int:
    if stop_points is None or stop_points <= 0:
        return 0
    n = math.floor(risk_usd / (stop_points * point_value))
    if max_contracts is not None:
        n = min(n, max_contracts)
    return max(n, 0)


def size_pct_account(account_equity: float, pct: float, stop_points: float, point_value: float, max_contracts: int | None = None, **_) -> int:
    return size_fixed_dollar_risk(account_equity * pct, stop_points, point_value, max_contracts)


@dataclass
class PropFirmRules:
    account_size: float = 50000
    profit_target: float | None = None
    daily_loss_limit: float | None = None
    daily_loss_limit_basis: str = "intraday"
    trailing_drawdown: float | None = None
    trailing_drawdown_basis: str = "eod"
    trailing_stops_at_initial_plus: float | None = None
    max_contracts: dict = field(default_factory=dict)
    consistency_rule: float | None = None
    min_trading_days: int = 0
    flatten_by: str | None = None
    no_trading_window: list | None = None
    allowed_instruments: list = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path=None) -> "PropFirmRules":
        with open(path or CONFIG_DIR / "propfirm_default.yaml") as f:
            d = yaml.safe_load(f)
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class AccountState:
    """Tracks balance, high-water mark and rule breaches. Fed by the engine bar by bar."""
    rules: PropFirmRules
    balance: float = 0.0
    hwm: float = 0.0
    day: dt.date | None = None
    day_start_balance: float = 0.0
    day_realised: float = 0.0
    breached: str | None = None
    breach_ts: object = None
    trades_today: int = 0
    daily_pnl: dict = field(default_factory=dict)

    def __post_init__(self):
        self.balance = float(self.rules.account_size)
        self.hwm = self.balance
        self.day_start_balance = self.balance

    @property
    def trailing_floor(self) -> float | None:
        r = self.rules
        if r.trailing_drawdown is None:
            return None
        floor = self.hwm - r.trailing_drawdown
        if r.trailing_stops_at_initial_plus is not None:
            floor = min(floor, r.account_size + r.trailing_stops_at_initial_plus)
        return floor

    def new_day(self, day: dt.date):
        if self.day is not None:
            self.daily_pnl[self.day] = self.day_realised
            if self.rules.trailing_drawdown_basis == "eod":
                self.hwm = max(self.hwm, self.balance)
        self.day = day
        self.day_start_balance = self.balance
        self.day_realised = 0.0
        self.trades_today = 0

    def on_realised(self, pnl: float, ts):
        self.balance += pnl
        self.day_realised += pnl
        self.trades_today += 1
        if self.rules.trailing_drawdown_basis == "intraday":
            self.hwm = max(self.hwm, self.balance)
        self._check(ts, unrealised=0.0)

    def on_mark(self, unrealised: float, ts):
        if self.rules.trailing_drawdown_basis == "intraday":
            self.hwm = max(self.hwm, self.balance + unrealised)
        self._check(ts, unrealised)

    def _check(self, ts, unrealised: float):
        if self.breached:
            return
        r = self.rules
        eq = self.balance + (unrealised if r.daily_loss_limit_basis == "intraday" else 0.0)
        if r.daily_loss_limit is not None and (eq - self.day_start_balance) <= -r.daily_loss_limit:
            self.breached, self.breach_ts = "daily_loss_limit", ts
            return
        floor = self.trailing_floor
        if floor is not None and (self.balance + unrealised) <= floor:
            self.breached, self.breach_ts = "trailing_drawdown", ts

    def can_trade(self, max_trades_per_day: int | None = None) -> bool:
        if self.breached:
            return False
        if max_trades_per_day is not None and self.trades_today >= max_trades_per_day:
            return False
        return True
