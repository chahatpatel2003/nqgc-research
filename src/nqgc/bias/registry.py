"""Append-only experiment registry (runs/phase5/registry.jsonl). Every experiment, hypothesis batch and audit is
recorded — successes and failures alike — with the hashes of the inputs it used."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
from pathlib import Path

from .splits import OUT

REGISTRY = OUT / "registry.jsonl"


def file_hash(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, float):
        return None if o != o or o in (float("inf"), float("-inf")) else o
    if hasattr(o, "item"):
        return _clean(o.item())
    if isinstance(o, (dt.date, dt.datetime)):
        return o.isoformat()
    return o


def record(experiment: str, payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rec = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "experiment": experiment} | _clean(payload)
    with open(REGISTRY, "a") as f:
        f.write(json.dumps(rec) + "\n")
