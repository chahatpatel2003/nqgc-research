"""nqgc — leak-safe NQ/GC futures research framework (generation 1, 2026-09-02).

Core rule enforced everywhere: at timestamp T a strategy may only use information that
existed at or before T. See docs/LEAKAGE_SAFEGUARDS.md for the full list of safeguards.
"""
__version__ = "0.1.0"
