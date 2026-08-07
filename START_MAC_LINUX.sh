#!/usr/bin/env bash
# ===================================================================
#  Invest-System  -  OLS, Logistic & Poisson  --  one-click start (Mac/Linux)
#
#  Mac:   right-click this file -> Open With -> Terminal
#         (first time only: run  chmod +x START_MAC_LINUX.sh )
#  Linux: ./START_MAC_LINUX.sh
# ===================================================================
set -u
cd "$(dirname "$0")"

echo
echo " ============================================================"
echo "  Invest-System  -  OLS, Logistic & Poisson"
echo "  Starting up. The first run takes 2-3 minutes."
echo " ============================================================"
echo

# --- 1. Python present? --------------------------------------------
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo " [X] Python 3 is not installed."
  echo "     Mac:   brew install python   (or https://www.python.org/downloads/)"
  echo "     Linux: sudo apt install python3 python3-venv"
  exit 1
fi
echo " [OK] $($PY --version) found."

# --- 2. Environment (first run only) --------------------------------
if [ ! -x ".venv/bin/python" ]; then
  echo " [..] Creating a private environment (first run only)..."
  "$PY" -m venv .venv || { echo " [X] Could not create the environment."; exit 1; }
fi
echo " [OK] Environment ready."

# --- 3. Dependencies (first run only) -------------------------------
if [ ! -f ".venv/.installed" ]; then
  echo " [..] Installing required packages. This is the slow part, once."
  .venv/bin/python -m pip install --upgrade pip --quiet
  .venv/bin/python -m pip install -r requirements.txt --quiet \
    || { echo " [X] Installation failed. Check your internet connection."; exit 1; }
  touch .venv/.installed
fi
echo " [OK] Packages installed."

# --- 4. Self-check ---------------------------------------------------
echo " [..] Running the built-in self-check..."
.venv/bin/python main.py smoke || echo " [!] Self-check reported a problem; the app may still run."

# --- 5. Launch -------------------------------------------------------
echo
echo " ============================================================"
echo "  Opening the app at  http://localhost:8501"
echo "  Leave THIS WINDOW OPEN while you use the app."
echo "  To stop: press Ctrl+C."
echo " ============================================================"
echo
( sleep 4; (command -v open >/dev/null && open http://localhost:8501) \
        || (command -v xdg-open >/dev/null && xdg-open http://localhost:8501) ) >/dev/null 2>&1 &
exec .venv/bin/python main.py streamlit
