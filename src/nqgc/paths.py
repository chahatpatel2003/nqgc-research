"""Dataset locations on the external T9 drive (READ-ONLY) and project directories.

Nothing in this package ever writes under T9_ROOT. `assert_writable_target` is called by every
writer in the project and raises if a path resolves onto the drive.
"""
from __future__ import annotations
import os
from pathlib import Path

T9_ROOT = Path("/Volumes/T9")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "configs"
CACHE_DIR = PROJECT_ROOT / "data_cache"
RUNS_DIR = PROJECT_ROOT / "runs"
SPECS_DIR = PROJECT_ROOT / "specs"
DOCS_DIR = PROJECT_ROOT / "docs"

# Raw datasets (discovered by the 2026-09-02 inventory; see docs/DATA_INVENTORY.md)
NQ_TRADES_DIR = T9_ROOT / "nq data" / "raw" / "trades"          # 2021_H1 .. 2026_H1 parquet
NQ_MBP1_DIR = T9_ROOT / "nq data" / "raw" / "mbp1"              # 2021_H1 .. 2025_H1 parquet
NQ_DBN_DIR = T9_ROOT / "nq data" / "NQ_HOLDOUT" / "GLBX-20260815-69WTYRKTDB"   # 2026-06-17 .. 2026-08-14 dbn.zst
GC_BARS_DIR = T9_ROOT / "Gc:Xauusd" / "gc"                       # gc_2016..2023 + Holdout/gc_2024, gc_2025


def t9_mounted() -> bool:
    return T9_ROOT.exists() and NQ_TRADES_DIR.exists()


def require_t9() -> None:
    if not t9_mounted():
        raise RuntimeError(f"T9 drive not mounted at {T9_ROOT} (expected {NQ_TRADES_DIR})")


def is_on_t9(path: os.PathLike | str) -> bool:
    try:
        return Path(path).resolve().is_relative_to(T9_ROOT.resolve())
    except (OSError, ValueError):
        return str(path).startswith(str(T9_ROOT))


def assert_writable_target(path: os.PathLike | str) -> Path:
    """Every writer calls this. Raises if the target lives on the raw-data drive."""
    p = Path(path)
    if is_on_t9(p):
        raise PermissionError(f"Refusing to write onto the read-only raw-data drive: {p}")
    return p


def nq_trades_files() -> list[Path]:
    require_t9()
    return sorted(NQ_TRADES_DIR.glob("20??_H?.parquet"))


def nq_mbp1_files() -> list[Path]:
    require_t9()
    return sorted(NQ_MBP1_DIR.glob("20??_H?.parquet"))


def nq_dbn_files() -> list[Path]:
    require_t9()
    return sorted(NQ_DBN_DIR.glob("glbx-mdp3-*.trades.dbn.zst"))


def gc_bar_files() -> list[Path]:
    require_t9()
    files = sorted(GC_BARS_DIR.glob("gc_20??.parquet")) + sorted((GC_BARS_DIR / "Holdout").glob("gc_20??.parquet"))
    # gc_2024_jan.parquet is a verified byte-identical subset of gc_2024.parquet; deliberately excluded.
    return files
