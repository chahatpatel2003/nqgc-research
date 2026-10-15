"""Split / holdout guard.

Every data load goes through an `Access` object. The guard is expressed on the CME TRADE DATE
(not the UTC calendar date), so the 22:00/23:00 UTC tail of the last development day — which
belongs to the next trade date — is excluded as well.

Phases
------
development : free access within the development window.
validation   : requires a frozen spec id; each access is appended to runs/ACCESS_LOG.jsonl.
holdout      : requires a frozen spec id AND the unlock phrase; appended to runs/HOLDOUT_LEDGER.md.
infrastructure : calendar / front-contract-map builders only (aggregate metadata, no strategy P&L);
                 every use is logged. Never use it from a strategy.
"""
from __future__ import annotations
import datetime as dt
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .paths import CONFIG_DIR, RUNS_DIR, assert_writable_target

UNLOCK_PHRASE = "I_AM_DELIBERATELY_OPENING_THE_FINAL_HOLDOUT"
INFRA = "infrastructure"


def _phase_cfg(splits: dict, instrument: str, phase: str) -> dict:
    """Split entries are {window: [a, b], locked: bool, label: str}; legacy [a, b] lists are accepted."""
    v = splits[instrument][phase]
    if isinstance(v, dict):
        return {"window": v["window"], "locked": bool(v.get("locked", False)), "label": v.get("label", phase)}
    return {"window": list(v), "locked": phase == "holdout", "label": phase}


class HoldoutViolation(RuntimeError):
    pass


def load_splits() -> dict:
    with open(CONFIG_DIR / "splits.yaml") as f:
        return yaml.safe_load(f)


def _d(s: str | dt.date) -> dt.date:
    return s if isinstance(s, dt.date) else dt.date.fromisoformat(str(s))


@dataclass(frozen=True)
class Access:
    phase: str
    instrument: str
    spec_id: str | None = None
    unlock: str | None = None
    purpose: str = ""
    splits: dict = field(default_factory=load_splits, repr=False, compare=False)

    def __post_init__(self):
        if self.instrument not in self.splits:
            raise ValueError(f"no split defined for instrument {self.instrument!r}")
        phases = tuple(k for k in self.splits[self.instrument].keys())
        if self.phase != INFRA and self.phase not in phases:
            raise ValueError(f"unknown phase {self.phase!r} for {self.instrument}; expected one of {phases + (INFRA,)}")
        if self.phase != INFRA:
            cfg = _phase_cfg(self.splits, self.instrument, self.phase)
            if self.phase != "development" and not self.spec_id:
                raise HoldoutViolation(f"{self.phase} access requires a frozen spec_id")
            if cfg["locked"]:
                if self.unlock != UNLOCK_PHRASE:
                    raise HoldoutViolation(f"{self.phase} for {self.instrument} is LOCKED ({cfg['label']}); explicit unlock phrase required")
                self._ledger(f"LOCKED-PHASE ACCESS [{cfg['label']}]")
        if self.phase == INFRA and not self.purpose:
            raise ValueError("infrastructure access must state a purpose")
        self._log()

    @property
    def locked(self) -> bool:
        return self.phase != INFRA and _phase_cfg(self.splits, self.instrument, self.phase)["locked"]

    # ---- window --------------------------------------------------------------------------
    def window(self) -> tuple[dt.date, dt.date]:
        if self.phase == INFRA:
            # infrastructure (calendar / front map) spans every UNLOCKED phase only
            wins = [_phase_cfg(self.splits, self.instrument, k)["window"] for k in self.splits[self.instrument]
                    if not _phase_cfg(self.splits, self.instrument, k)["locked"]]
            return min(_d(w[0]) for w in wins), max(_d(w[1]) for w in wins)
        a, b = _phase_cfg(self.splits, self.instrument, self.phase)["window"]
        return _d(a), _d(b)

    def check_range(self, start: dt.date | str, end: dt.date | str) -> tuple[dt.date, dt.date]:
        """Raise unless [start, end] (trade dates, inclusive) lies inside this phase's window."""
        s, e = _d(start), _d(end)
        lo, hi = self.window()
        if s < lo or e > hi:
            raise HoldoutViolation(
                f"{self.instrument} {self.phase} window is {lo}..{hi}; requested {s}..{e}")
        return s, e

    def clip(self, start, end) -> tuple[dt.date, dt.date]:
        """Clip a requested range to the phase window (used by loaders to add SQL predicates)."""
        s, e = _d(start), _d(end)
        lo, hi = self.window()
        return max(s, lo), min(e, hi)

    # ---- logging -------------------------------------------------------------------------
    def _log(self):
        assert_writable_target(RUNS_DIR)
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        rec = dict(ts=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), phase=self.phase,
                   instrument=self.instrument, spec_id=self.spec_id, purpose=self.purpose, pid=os.getpid())
        with open(RUNS_DIR / "ACCESS_LOG.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")

    def _ledger(self, what: str):
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        p = RUNS_DIR / "HOLDOUT_LEDGER.md"
        new = not p.exists()
        with open(p, "a") as f:
            if new:
                f.write("# HOLDOUT LEDGER — every holdout access, permanent record\n\n")
            f.write(f"- {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')} | {what} | "
                    f"instrument={self.instrument} | spec={self.spec_id} | purpose={self.purpose}\n")


def trade_date_predicate_sql(col_expr: str) -> str:
    """DuckDB expression for CME trade date from a UTC timestamp column expression.
    17:00 CT open belongs to the next calendar date -> shift the CT clock by +7h and take the date."""
    # timezone(zone, TIMESTAMPTZ) -> naive local wall-clock timestamp in that zone (DuckDB ICU semantics)
    return f"CAST(timezone('America/Chicago', ({col_expr})) + INTERVAL 7 HOUR AS DATE)"
