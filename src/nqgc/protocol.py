"""Research protocol: versioned strategy specs, freezing with code hashes, run manifests.

Rules (docs/RESEARCH_PROTOCOL.md): a spec is frozen BEFORE validation; the validation run happens
once; a frozen spec file is immutable (refused overwrite); holdout requires a frozen spec and is
recorded in the ledger; every run stores its full configuration and data fingerprint.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

import yaml

from .paths import CONFIG_DIR, PROJECT_ROOT, RUNS_DIR, SPECS_DIR, assert_writable_target, nq_trades_files, gc_bar_files, nq_dbn_files


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def code_hash(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(p.name.encode()); h.update(p.read_bytes())
    return h.hexdigest()[:16]


def package_hash() -> str:
    return code_hash(sorted((PROJECT_ROOT / "src" / "nqgc").glob("*.py")))


def config_snapshot() -> dict:
    return {p.name: yaml.safe_load(open(p)) for p in sorted(CONFIG_DIR.glob("*.yaml"))}


def data_fingerprint() -> dict:
    """Cheap fingerprint (size + mtime) of every raw file — full hashing of 240 GB is not practical per run.
    The full sha256 manifest is produced once by scripts/hash_raw_data.py."""
    files = []
    try:
        files = nq_trades_files() + gc_bar_files() + nq_dbn_files()
    except RuntimeError:
        pass
    return {str(p): dict(size=p.stat().st_size, mtime=int(p.stat().st_mtime)) for p in files}


@dataclass
class StrategySpec:
    strategy_name: str
    version: str
    instrument: str
    timeframe_s: int
    rules: str                       # plain-language mechanical rules
    parameters: dict
    dataset_split: dict              # copy of the split boundaries used
    hypothesis_id: str = ""
    entry_type: str = "market"
    exit_rules: str = ""
    date_frozen: str = ""
    code_hash: str = ""
    strategy_file_hash: str = ""
    spec_id: str = ""
    notes: str = ""

    def canonical(self) -> str:
        d = asdict(self)
        for k in ("spec_id", "date_frozen"):
            d.pop(k, None)
        return json.dumps(d, sort_keys=True, default=str)


def freeze(spec: StrategySpec, strategy_file: Path) -> Path:
    spec.code_hash = package_hash()
    spec.strategy_file_hash = code_hash([Path(strategy_file)])
    spec.spec_id = hashlib.sha256(spec.canonical().encode()).hexdigest()[:12]
    spec.date_frozen = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    SPECS_DIR.mkdir(exist_ok=True)
    out = assert_writable_target(SPECS_DIR / f"{spec.strategy_name}_v{spec.version}_{spec.spec_id}.json")
    if out.exists():
        raise FileExistsError(f"frozen spec already exists and is immutable: {out}")
    out.write_text(json.dumps(asdict(spec), indent=1, default=str))
    return out


def load_spec(spec_id: str) -> StrategySpec:
    for p in SPECS_DIR.glob(f"*_{spec_id}.json"):
        return StrategySpec(**json.loads(p.read_text()))
    raise FileNotFoundError(spec_id)


def verify_spec_matches_code(spec: StrategySpec, strategy_file: Path) -> None:
    if spec.code_hash != package_hash() or spec.strategy_file_hash != code_hash([Path(strategy_file)]):
        raise RuntimeError("code changed since the spec was frozen — freeze a new version")


@dataclass
class RunManifest:
    run_id: str
    phase: str
    instrument: str
    spec_id: str | None
    seed: int
    engine_config: dict
    cost_config: dict
    propfirm_config: dict
    configs: dict = field(default_factory=config_snapshot)
    code_hash: str = field(default_factory=package_hash)
    data_fingerprint: dict = field(default_factory=data_fingerprint)
    python: str = field(default_factory=lambda: sys.version)
    platform: str = field(default_factory=platform.platform)
    packages: dict = field(default_factory=dict)
    created: str = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))

    def save(self, trades, stats: dict) -> Path:
        d = assert_writable_target(RUNS_DIR / self.run_id)
        d.mkdir(parents=True, exist_ok=True)
        import polars, numpy, duckdb, pyarrow
        self.packages = dict(polars=polars.__version__, numpy=numpy.__version__, duckdb=duckdb.__version__, pyarrow=pyarrow.__version__)
        (d / "manifest.json").write_text(json.dumps(asdict(self), indent=1, default=str))
        if trades is not None and not trades.is_empty():
            trades.write_parquet(d / "trades.parquet")
        (d / "stats.json").write_text(json.dumps(stats, indent=1, default=str))
        return d


def new_run_id(prefix: str) -> str:
    return f"{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{prefix}"
