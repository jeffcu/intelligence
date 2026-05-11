# Intelligence — Install Without Docker

These instructions replace the Docker setup. You get the same result: the app runs at **http://localhost:8001**, the news scheduler runs automatically, and you control it with two commands.

---

## Before you start — what you need

- **Python 3.11 or newer** — check with `python3 --version`
  - macOS: `brew install python@3.11`
  - Linux: `sudo apt install python3.11 python3.11-venv`
- **Node.js 18 or newer** — check with `node --version`
  - macOS: `brew install node`
  - Linux: `sudo apt install nodejs npm`
- **Git** — check with `git --version`
  - macOS: `brew install git` (or it prompts you automatically)
  - Linux: `sudo apt install git`
- **A free Gemini API key** — get one at https://aistudio.google.com/apikey (30 seconds, no credit card)

---

## Step 1 — Open Terminal in the right place

You probably have a folder called **`intelligence-main`** or **`intelligence-main-2`** from when you downloaded the zip. That folder came from GitHub's "Download ZIP" button — it is **not** a proper git repository, so you can't update it with `git pull`. You can leave it where it is or delete it.

You need a fresh clone. Here is where to put it:

**Mac — open Terminal:**
- Press `⌘ Space`, type **Terminal**, press Enter
- Terminal opens in your home folder (`/Users/yourname`) by default

**Linux — open Terminal:**
- `Ctrl + Alt + T`, or find Terminal in your applications

Once Terminal is open, decide where to keep the project. Your home folder is fine:

```
cd ~
```

Or if you have a Projects folder:

```
cd ~/Projects
```

---

## Step 2 — Clone the repository

This creates a folder called `intelligence` in whatever directory you're in:

```
git clone https://github.com/jeffcu/intelligence.git
cd intelligence
```

You are now inside the project folder. All commands from here on run from inside this folder.

---

## Step 3 — Install everything

```
bash install.sh
```

This will:
1. Check Python and Node versions
2. Create a Python virtual environment inside the project folder (`venv/`)
3. Install all Python dependencies (~2–4 minutes — one package called chromadb is large)
4. Ask you to paste your Gemini API key and save it to `.env`
5. Install npm packages and build the web UI

You only run `install.sh` once. After that, use `start.sh` and `stop.sh`.

---

## Step 4 — Start Intelligence

```
bash start.sh
```

When you see `http://localhost:8001` printed, open that address in your browser. The full UI will be there.

The news scheduler starts automatically in the background. On first start it immediately runs a news fetch — this can take a few minutes while it initialises. The scheduler then runs on its own at **7am, noon, and 3pm** every day.

---

## Step 5 — Stop Intelligence

```
bash stop.sh
```

This stops the API and the scheduler cleanly.

---

## Daily use

Every time you want to run Intelligence:

```
cd ~/intelligence
bash start.sh
```

To stop it:

```
bash stop.sh
```

If you put the folder somewhere other than your home directory, replace `~/intelligence` with the actual path.

---

## Getting updates

When a new version is released, update your copy with:

```
cd ~/intelligence
bash stop.sh
git pull
bash install.sh
bash start.sh
```

`git pull` downloads the latest code. `install.sh` picks up any new dependencies and rebuilds the UI. Then start as normal.

---

## Troubleshooting

**"python3 not found" or wrong version**
Install Python 3.11 from https://python.org or via your package manager, then run `install.sh` again.

**"node not found" or wrong version**
Install Node.js 18+ from https://nodejs.org or via `brew install node`, then run `install.sh` again.

**API didn't start / browser shows nothing**
Check what went wrong:
```
tail -30 api.log
```

**Scheduler not fetching news**
Check the scheduler log:
```
tail -30 scheduler.log
```

**Start over cleanly**
```
bash stop.sh
rm -rf venv dist node_modules
bash install.sh
bash start.sh
```

This wipes the Python environment and built UI and rebuilds from scratch. Your API key in `.env` and any existing data in `intelligence.db` are kept.

**Check if it's running**
```
curl http://localhost:8001/health
```
Should return something like `{"status":"ok","api_key":"configured","db":"exists"}`.
