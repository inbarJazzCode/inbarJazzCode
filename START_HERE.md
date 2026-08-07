# START HERE — getting the app onto your computer

**The app is not on your desktop yet, and it cannot put itself there.**
It was built in a temporary cloud container that has no connection to your
machine. To run it, you download it once. That is the whole story.

Three steps. Ten minutes, most of which is waiting.

---

## Step 1 — Download

Open this link. It downloads a ZIP of the whole project:

**https://github.com/inbarJazzCode/inbarJazzCode/archive/refs/heads/claude/new-session-z4iq3g.zip**

(If your browser asks, save it — it is your own repository.)

## Step 2 — Unzip it to your Desktop

Right-click the downloaded file → **Extract All** (Windows) or double-click it (Mac).
Put the resulting folder on your Desktop. You will end up with something like:

```
Desktop/inbarJazzCode-claude-new-session-z4iq3g/
```

Open that folder. You should see `START_WINDOWS.bat`, `main.py`, `README.md`.

## Step 3 — Double-click the start file

| Your computer | Double-click |
|---|---|
| **Windows** | `START_WINDOWS.bat` |
| **Mac / Linux** | `START_MAC_LINUX.sh` — on Mac, right-click → Open With → Terminal. First time only, run `chmod +x START_MAC_LINUX.sh` |

A black window opens and prints what it is doing. **The first run takes 2–3
minutes** because it installs what it needs. After that it starts in seconds.

When it finishes, your browser opens at **http://localhost:8501** and the app is
running. **Leave the black window open** while you use it — closing it stops the app.

---

## What you need installed first

Only **Python 3.11 or newer**. Check by opening a terminal / Command Prompt and typing:

```
python --version
```

If that errors, install from **https://www.python.org/downloads/** — and on
Windows, **tick "Add Python to PATH"** on the very first installer screen. That
one checkbox causes most of the problems people hit.

---

## If something goes wrong

| What you see | What to do |
|---|---|
| `Python is not installed, or not on your PATH` | Install Python, tick "Add Python to PATH", reboot, try again. |
| `Installation failed` | You need internet for the first run only. Check the connection and re-run. |
| Browser shows "can't connect" | Give it ~15 seconds after the window says it is opening, then refresh. |
| Port 8501 already in use | Something else is using it. Run `python main.py streamlit --port 8600` and open `http://localhost:8600`. |
| Black window flashes and vanishes | Open Command Prompt in the folder and run `START_WINDOWS.bat` from there so you can read the error. |

## Checking it works without the browser

From inside the folder:

```
python main.py smoke        # prints SMOKE PASS if everything is healthy
python main.py integrity    # checks the database
```

---

## Where your data lives

The app creates its own database at:

- **Windows** — `C:\Users\<you>\.local\share\invest-system\`
- **Mac/Linux** — `~/.local/share/invest-system/`

Nothing is uploaded anywhere. No telemetry, no accounts, no network calls except
fetching market prices when you ask for them.

---

## Using live market data

In the app's sidebar, switch **Data provider** from `synthetic` to `yahoo-chart`
for real prices. `synthetic` is offline fake data, clearly labelled, so the app
works with no internet.

> Educational and research use only. Market data may be delayed. This is not
> investment advice.
