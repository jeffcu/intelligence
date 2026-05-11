# Intelligence — Install on Mac (No Docker)

These instructions are for Mac only. When you're done, the app runs at **http://localhost:8001**, the news scheduler runs automatically, and you control everything with two commands.

---

## What you need before starting

You need four tools. The install script will offer to install any that are missing — but it's helpful to know what they are first.

| Tool | What it does |
|------|-------------|
| **Homebrew** | A Mac package manager — it installs software the easy way |
| **Python 3.11+** | Runs the Intelligence server and AI engine |
| **Node.js 18+** | Builds the web interface |
| **Git** | Downloads the code and keeps it up to date |

**You also need a free Gemini API key** — the install script will ask for it and tell you where to get one (30 seconds, no credit card).

---

## Step 1 — Install Homebrew (if you don't have it)

Homebrew is a free tool that lets you install software on a Mac from the Terminal with a single command. Think of it as an App Store for developer tools.

**Check if you already have it:** open Terminal (press ⌘ Space, type **Terminal**, press Enter) and run:

```
brew --version
```

If you see a version number, you already have Homebrew — skip to Step 2.

If you see "command not found", install it by pasting this into Terminal and pressing Enter:

```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

This will:
- Ask for your Mac password (normal — it needs permission to install software)
- Download and install Homebrew (a few minutes)
- Print "Installation successful!" when done

After it finishes, close Terminal and open it again so the new commands are available.

---

## Step 2 — Get the code

You probably have a folder called **`intelligence-main`** or **`intelligence-main-2`** from when you downloaded the ZIP from GitHub. That folder is a snapshot — it cannot receive updates with `git pull`. You can leave it where it is; it won't interfere with anything.

You need a fresh copy from git. Open Terminal and run:

```
cd ~
git clone https://github.com/jeffcu/intelligence.git
cd intelligence
```

This creates a folder called `intelligence` in your home folder. All commands from here on run from inside that folder.

> If Terminal says "git: command not found", run `brew install git` first, then retry.

---

## Step 3 — Run the installer

```
bash install.sh
```

The installer will automatically check for Python, Node.js, and Git. If any are missing, it will ask if you want to install them — just press **Enter** or type **y** to say yes.

What the installer does:
1. Checks Python, Node.js, and Git — offers to install anything missing via Homebrew
2. Creates a Python virtual environment inside the project folder (`venv/`)
3. Installs all Python packages (2–4 minutes — one package called chromadb is large)
4. Asks you for your Gemini API key and saves it
5. Installs npm packages and builds the web interface

**Getting your Gemini API key:** when the installer asks, go to **https://aistudio.google.com/apikey**, click "Create API Key", copy it, and paste it into Terminal. You only do this once.

You only run `install.sh` once. After that, use `start.sh` and `stop.sh`.

---

## Step 4 — Start Intelligence

```
bash start.sh
```

When you see `http://localhost:8001` printed, open that address in your browser. The full interface will be there.

The news scheduler starts automatically in the background. On first start it immediately runs a news fetch — this takes a few minutes while it initialises. After that, the scheduler runs on its own at **7am, noon, and 3pm** every day.

---

## Step 5 — Stop Intelligence

```
bash stop.sh
```

This stops the server and the scheduler cleanly.

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

---

## Getting updates

When a new version is released:

```
cd ~/intelligence
bash stop.sh
git pull
bash install.sh
bash start.sh
```

`git pull` downloads the latest code. `install.sh` picks up any new packages and rebuilds the interface.

---

## Troubleshooting

**"zsh: command not found: brew"**
Homebrew isn't installed or your Terminal needs to be restarted. See Step 1.

**API didn't start / browser shows nothing**
```
tail -30 api.log
```

**Scheduler not fetching news**
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
This wipes and rebuilds everything. Your API key in `.env` and your data in `intelligence.db` are kept.

**Check if it's running**
```
curl http://localhost:8001/health
```
Should return something like `{"status":"ok","api_key":"configured","db":"exists"}`.
