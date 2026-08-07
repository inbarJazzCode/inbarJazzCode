# RUN INSTRUCTIONS

## Install

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt      # add -r requirements-dev.txt for tests/packaging
```

Python 3.11+ recommended (built and verified on CPython 3.11).

## Run the application

```bash
python main.py streamlit     # Streamlit UI on http://localhost:8501
python main.py desktop       # Tkinter desktop UI (needs a display; degrades gracefully)
```

## Run the checks

```bash
python main.py smoke                 # -> SMOKE PASS ✅   (fully offline)
pytest                               # 68 offline tests
pytest -m network                    # optional live-Yahoo integration test
python main.py integrity             # database integrity check
python main.py backup                # verified timestamped DB backup
python -m compileall statinvest main.py smoke_test.py
```

## Data location

SQLite database: `~/.local/share/statistics-investment-eco-system/statinvest.db`
Override with `STATINVEST_DATA_DIR=/some/path`.

## Restore / rollback a database

```bash
python main.py backup                                 # creates backups/statinvest.<UTC>.bak
# To restore: stop the app, copy the chosen .bak over statinvest.db.
```

## Package a desktop binary (optional)

```bash
pip install pyinstaller
pyinstaller statinvest.spec          # output in dist/
```
