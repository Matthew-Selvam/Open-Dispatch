# Installing Open-Dispatch

Five ways to get Open-Dispatch running, from fastest to most self-contained.

---

## 1. Docker Compose (recommended — zero Python setup)

```bash
git clone https://github.com/Matthew-Selvam/Open-Dispatch
cd Open-Dispatch
cp .env.example .env    # fill in your platform creds
docker compose up -d
curl http://localhost:8000/healthz   # → {"status":"ok"}
open http://localhost:8000
```

Add Redis: `docker compose --profile redis up -d`

---

## 2. Homebrew (macOS / Linux)

```bash
# Add the tap (formula lives in Formula/ of the main repo)
brew tap matthew-selvam/open-dispatch https://github.com/Matthew-Selvam/Open-Dispatch
brew install open-dispatch

# First-time setup
cp $(brew --prefix)/opt/open-dispatch/.env.example \
   ~/.open-dispatch/.env
$EDITOR ~/.open-dispatch/.env

# Start server
open-dispatch                        # foreground
brew services start open-dispatch    # background (auto-start on login)

# CLI
dispatch send --platforms bluesky,twitter --text "shipped a thing"
```

> The formula installs three binaries: `open-dispatch` (server), `open-dispatch-worker` (queue worker), and `dispatch` (CLI).

---

## 3. One-line installer (macOS + Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/Matthew-Selvam/Open-Dispatch/main/install.sh | bash
```

Or download and inspect before running:

```bash
curl -fsSL https://raw.githubusercontent.com/Matthew-Selvam/Open-Dispatch/main/install.sh -o install.sh
less install.sh
bash install.sh
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--prefix DIR` | `/usr/local` | Where to install binaries |
| `--version TAG` | `v0.4.0` | Release to install |
| `--data-dir DIR` | `~/.open-dispatch` | Where to store queue + .env |
| `--no-service` | — | Skip launchd/systemd unit setup |

After install, start as a background service:

```bash
# macOS
launchctl load ~/Library/LaunchAgents/dev.open-dispatch.plist

# Linux (systemd user session)
systemctl --user enable --now open-dispatch
```

---

## 4. macOS menu-bar app + DMG

Download the latest `Open-Dispatch-x.x.x.dmg` from the
[GitHub Releases](https://github.com/Matthew-Selvam/Open-Dispatch/releases) page.

1. Open the DMG, drag **Open-Dispatch.app** to **Applications**
2. **First launch:** right-click the app → **Open** → click **Open** in the Gatekeeper dialog (unsigned build — only needed once)
3. An icon appears in your menu bar
4. Click the icon → **Edit .env** to add your platform credentials
5. Click → **Start Server**
6. Click → **Open Dashboard** to open the web UI

> **Apple Silicon & Intel** — the release binary is native arm64; Rosetta 2 handles Intel Macs automatically.

The menubar app bundles the Python server and worker — no separate Python install required.

**Build the DMG yourself:**

```bash
# Prerequisites
xcode-select --install
brew install create-dmg     # optional (for prettier window)

bash scripts/make-dmg.sh
# Output: dist/Open-Dispatch-0.4.0.dmg
```

---

## 5. pip install (Python developers)

```bash
pip install open-dispatch            # installs `dispatch` CLI + all deps
# or
pip install "open-dispatch[redis]"   # + redis queue backend
pip install "open-dispatch[postgres]" # + postgres queue backend
```

Then run manually:

```bash
# Server
uvicorn api.app:app --reload

# Worker (separate terminal)
python -m scheduler.worker

# CLI
dispatch send --platforms telegram --text "hello"
```

> **Note:** PyPI publishing is pending — until the package lands on PyPI,
> install from the repo: `pip install git+https://github.com/Matthew-Selvam/Open-Dispatch.git`

---

## Quick comparison

| Method | Setup time | Requires | Best for |
|--------|-----------|----------|----------|
| Docker Compose | ~60s | Docker | Self-hosters, Linux servers |
| Homebrew | ~2 min | macOS/Linux + Homebrew | macOS developers |
| install.sh | ~90s | bash + Python 3.11+ | Linux servers, CI |
| DMG | ~10s | macOS 13+ | Non-technical macOS users |
| pip | instant | Python 3.11+ | Python devs / automation |
