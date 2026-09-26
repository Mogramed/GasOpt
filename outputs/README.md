# Reproducible outputs

`empirical/` was generated on 2026-09-24 from verified Dune Ethereum extracts.
It contains separate TRAIN and TEST tables, all frozen schedules, held-out daily
costs, metadata, the readable report and ten figures in both PNG and PDF.

Run `python -m gasopt.empirical_study run` to reproduce these outputs offline
from the validated Parquet files. Synthetic validation figures used during
development remain under the ignored `tmp/` directory and are explicitly
labelled as fixtures.
