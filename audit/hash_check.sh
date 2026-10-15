for f in 2025_H2 2026_H1; do
  a=$(shasum -a 256 "/Volumes/T9/nq data/raw/trades/$f.parquet" | cut -d' ' -f1)
  b=$(shasum -a 256 "/Volumes/T9/nq data/NQ_HOLDOUT/$f.parquet" | cut -d' ' -f1)
  echo "$f raw=$a holdout=$b same=$([ "$a" = "$b" ] && echo YES || echo NO)"
done
