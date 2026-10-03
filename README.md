# election-monitor

Python app for polling Czech municipal election open data, storing snapshots in SQLite, and showing a time-series web UI.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m election_monitor.app
```

## Project goals

- Poll election open data for a single municipality
- Store snapshots in SQLite
- Compute and display time-series results
- Later: virtual council seat allocation
