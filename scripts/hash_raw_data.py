"""One-time sha256 manifest of the raw files (trades, GC, DBN; MBP-1 is size/mtime only — 222 GB)."""
import hashlib, json, sys
sys.path.insert(0, "src")
from nqgc.paths import nq_trades_files, gc_bar_files, nq_dbn_files, nq_mbp1_files, PROJECT_ROOT, assert_writable_target
out = {}
for p in nq_trades_files() + gc_bar_files() + nq_dbn_files():
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    out[str(p)] = dict(sha256=h.hexdigest(), size=p.stat().st_size)
    print(p.name, out[str(p)]["sha256"][:16], flush=True)
for p in nq_mbp1_files():
    out[str(p)] = dict(sha256=None, size=p.stat().st_size, mtime=int(p.stat().st_mtime))
assert_writable_target(PROJECT_ROOT / "audit" / "RAW_DATA_MANIFEST.json").write_text(json.dumps(out, indent=1))
print("DONE")
