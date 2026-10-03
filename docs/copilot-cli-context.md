# Copilot CLI Project Context

Repository: `Peta01/election-monitor`

## Project goal
Build a Python app that polls Czech municipal election open data, stores snapshots in SQLite, and shows a web UI with a time series of results.

## Current decisions
- Stack: Python, SQLite, web UI.
- Development happens locally in VS Code.
- One app instance = one municipality.
- Polling is on-demand.
- Shared SQLite DB is fine.
- It is acceptable to download the full dataset if needed, then filter locally.
- The UI should later show a “virtual council composition” computed from current election results.
- The legal basis for council seat allocation is Czech law 491/2001 Coll.

## Repository status
A scaffold already exists with:
- `src/election_monitor/app.py`
- `src/election_monitor/config.py`
- `src/election_monitor/downloader.py`
- `src/election_monitor/parser.py`
- `src/election_monitor/db.py`
- `src/election_monitor/models.py`
- `src/election_monitor/web.py`

The current parser is only a placeholder.

## Next task
Implement the real parser for the election open data source:
- Source page: `https://volby.gov.cz/opendata/kv2026/kv2026_opendata.htm`
- Determine actual file format and structure.
- Support ZIP/CSV/XML if necessary.
- Parse results for one selected municipality only.
- Normalize data into:
  - municipality reference
  - snapshot metadata
  - party/list results
  - turnout/progress metadata
- Store snapshots in SQLite.

## Additional goals
- Keep the parser modular.
- Make it easy to add a polling loop later.
- Make it easy to compute virtual council seat allocation in a separate module.
- Prefer clean, testable code.

## Important implementation constraints
- Do not hardcode assumptions about file names until the real format is verified.
- Use a robust detection layer for input format.
- Preserve the architecture so the web UI can later query historical snapshots.

## Suggested immediate steps
1. Inspect the open data source.
2. Implement a parser abstraction.
3. Add format-specific parsers.
4. Wire parsing into SQLite persistence.
5. Add basic tests.

## Helpful URL
- Open data source: https://volby.gov.cz/opendata/kv2026/kv2026_opendata.htm
