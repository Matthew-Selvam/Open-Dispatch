#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Open-Dispatch installer
# Usage:  curl -fsSL https://raw.githubusercontent.com/Matthew-Selvam/Open-Dispatch/main/install.sh | bash
# Or:     bash install.sh [--prefix /usr/local] [--version v0.4.1] [--no-service]
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── colours ───────────────────────────────────────────────────────────────────
if [ -t 1 ] && command -v tput &>/dev/null; then
  RED=$(tput setaf 1); GREEN=$(tput setaf 2); YELLOW=$(tput setaf 3)
  CYAN=$(tput setaf 6); BOLD=$(tput bold); RESET=$(tput sgr0)
else
  RED=""; GREEN=""; YELLOW=""; CYAN=""; BOLD=""; RESET=""
fi

info()    { echo "${CYAN}→${RESET} $*"; }
success() { echo "${GREEN}✓${RESET} $*"; }
warn()    { echo "${YELLOW}⚠${RESET} $*"; }
error()   { echo "${RED}✗${RESET} $*" >&2; exit 1; }

# ── defaults ──────────────────────────────────────────────────────────────────
# Default to ~/.local so a plain `curl | bash` never needs sudo — README and
# INSTALL_METHODS document this as the default.
PREFIX="${PREFIX:-${HOME}/.local}"
VERSION="${OPEN_DISPATCH_VERSION:-v0.4.1}"
INSTALL_DIR="${INSTALL_DIR:-${PREFIX}/opt/open-dispatch}"
DATA_DIR="${DATA_DIR:-${HOME}/.open-dispatch}"
INSTALL_SERVICE=true
BUNDLE=false

# ── argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix=*)     PREFIX="${1#*=}"; INSTALL_DIR="${PREFIX}/opt/open-dispatch"; shift ;;
    --prefix)       [[ $# -ge 2 ]] || error "--prefix requires a directory"; PREFIX="$2"; INSTALL_DIR="${PREFIX}/opt/open-dispatch"; shift 2 ;;
    --install-dir=*) INSTALL_DIR="${1#*=}"; shift ;;
    --install-dir)  [[ $# -ge 2 ]] || error "--install-dir requires a directory"; INSTALL_DIR="$2"; shift 2 ;;
    --version=*)    VERSION="${1#*=}"; shift ;;
    --version)      [[ $# -ge 2 ]] || error "--version requires a tag"; VERSION="$2"; shift 2 ;;
    --data-dir=*)   DATA_DIR="${1#*=}"; shift ;;
    --data-dir)     [[ $# -ge 2 ]] || error "--data-dir requires a directory"; DATA_DIR="$2"; shift 2 ;;
    --no-service) INSTALL_SERVICE=false; shift ;;
    --bundle) BUNDLE=true; INSTALL_SERVICE=false; shift ;;
    --help|-h)
      echo "Usage: install.sh [--prefix DIR] [--install-dir DIR] [--version TAG] [--data-dir DIR] [--no-service] [--bundle]"
      echo "  --bundle  emit relocatable wrappers for embedding (e.g. the macOS app bundle)"
      exit 0
      ;;
    *) error "Unknown option: $1" ;;
  esac
done

# ── banner ────────────────────────────────────────────────────────────────────
echo ""
echo "${BOLD}  Open-Dispatch ${VERSION} installer${RESET}"
echo "  ─────────────────────────────────"
echo "  Install dir : ${INSTALL_DIR}"
echo "  Data dir    : ${DATA_DIR}"
echo "  Bin dir     : ${PREFIX}/bin"
echo ""

# ── pre-flight ────────────────────────────────────────────────────────────────
OS=$(uname -s)
[[ "$OS" == "Linux" || "$OS" == "Darwin" ]] || error "Unsupported OS: $OS. Only macOS and Linux are supported."

# Python — prefer python3.12, python3.11, then python3
PYTHON=""
for candidate in python3.14 python3.13 python3.12 python3.11 python3; do
  if command -v "$candidate" &>/dev/null; then
    PY_VER=$("$candidate" -c 'import sys; print(sys.version_info[:2])' 2>/dev/null)
    if [[ "$PY_VER" == "(3, 11)" || "$PY_VER" == "(3, 12)" || "$PY_VER" =~ ^\(3,\ 1[3-9]\)$ ]]; then
      PYTHON="$candidate"
      break
    fi
  fi
done

if [[ -z "$PYTHON" ]]; then
  error "Python 3.11+ is required but not found.
       macOS: brew install python@3.12
       Ubuntu/Debian: sudo apt install python3.12 python3.12-venv
       Fedora/RHEL: sudo dnf install python3.12"
fi

# Fail early with a targeted message when the venv module is missing
# (Debian splits it into python3.X-venv) instead of an opaque traceback later.
if ! "$PYTHON" -c 'import venv' 2>/dev/null; then
  error "Python venv module is missing (Debian/Ubuntu: sudo apt install python3.12-venv)."
fi

# Fail before creating anything when the prefix is not writable — a plain
# `curl | bash` runs unprivileged, and /usr/local needs sudo.
if [[ ! -w "$PREFIX" && ! -w "$(dirname "$PREFIX")" ]]; then
  error "Cannot write to ${PREFIX} - re-run with --prefix \"$HOME/.local\" (the default) or use sudo."
fi

info "Using Python: $($PYTHON --version)"

# curl or wget
if command -v curl &>/dev/null; then
  FETCH="curl -fsSL"
elif command -v wget &>/dev/null; then
  FETCH="wget -qO-"
else
  error "curl or wget is required to download Open-Dispatch."
fi

# ── download ──────────────────────────────────────────────────────────────────
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

info "Downloading Open-Dispatch ${VERSION} …"
if ! $FETCH "https://github.com/Matthew-Selvam/Open-Dispatch/archive/refs/tags/${VERSION}.tar.gz" | tar -xz -C "$TMP_DIR" --strip-components=1; then
  info "Tag ${VERSION} not found - trying a branch of that name …"
  $FETCH "https://github.com/Matthew-Selvam/Open-Dispatch/archive/refs/heads/${VERSION}.tar.gz" | tar -xz -C "$TMP_DIR" --strip-components=1
fi

# ── install ───────────────────────────────────────────────────────────────────
info "Installing to ${INSTALL_DIR} …"
mkdir -p "$INSTALL_DIR" "$DATA_DIR" "${PREFIX}/bin"

# Copy source
cp -r "$TMP_DIR"/. "$INSTALL_DIR/"

# Create virtualenv
VENV="${INSTALL_DIR}/venv"
info "Creating Python virtualenv …"
"$PYTHON" -m venv "$VENV"
"${VENV}/bin/pip" install --upgrade --quiet pip wheel
"${VENV}/bin/pip" install --quiet -r "${INSTALL_DIR}/requirements.txt"

if [[ "$BUNDLE" == "true" ]]; then
  # Bundle the interpreter itself: the .app must run on machines with no
  # Python installed, and a venv alone is not relocatable — its python
  # binary reaches the stdlib through pyvenv.cfg 'home' (an absolute path
  # to the build machine) and libpython through a relative rpath. So we
  # ship the base runtime next to the venv and point PYTHONHOME at it.
  PY_REAL="$(readlink -f "$(command -v "$PYTHON")")"
  BASE_DIR="$(cd "$(dirname "$PY_REAL")/.." && pwd)"
  if [[ ! -d "${BASE_DIR}/lib" ]]; then
    error "Cannot locate the base ${PYTHON} installation for bundling."
  fi
  # Only relative-rpath builds (uv-style distributions) relocate safely:
  # no load command may point into the base installation by absolute path.
  # (otool's header line echoes the binary path itself, so filter to
  # load-command name/path entries first.)
  if otool -l "$PY_REAL" 2>/dev/null \
      | grep -E '^[[:space:]]+(path|name)[[:space:]]' \
      | grep -v '@' \
      | grep -F "$BASE_DIR" >/dev/null; then
    error "${BASE_DIR} is not relocatable (absolute load commands).
       Install a relocatable Python, e.g.: uv python install 3.14"
  fi
  info "Bundling Python runtime from ${BASE_DIR} …"
  cp -R "${BASE_DIR}" "${PREFIX}/runtime"
  # The venv python's rpath is @executable_path/../lib — satisfy it from
  # the copied venv so it never reaches back into the build machine.
  cp "${BASE_DIR}/lib"/libpython*.dylib "${VENV}/lib/" 2>/dev/null || true
fi

# .env example → data dir (if first install)
if [[ ! -f "${DATA_DIR}/.env" && -f "${INSTALL_DIR}/.env.example" ]]; then
  cp "${INSTALL_DIR}/.env.example" "${DATA_DIR}/.env"
  info "Created ${DATA_DIR}/.env — edit it to add your platform credentials."
fi

# ── write wrapper scripts ──────────────────────────────────────────────────────
write_script() {
  local path="$1"
  cat > "$path"
  chmod +x "$path"
}

if [[ "$BUNDLE" == "true" ]]; then
  # Relocatable wrappers for embedding (macOS .app Resources/bin, Docker
  # images, portable tars). Build-time absolute paths broke as soon as the
  # bundle moved: the wrappers pointed at the deleted staging prefix. These
  # resolve everything from the wrapper's own location instead, and they
  # honour an inherited OPEN_DISPATCH_DATA so a host app can choose the
  # data dir (the Swift app points at ~/Library/Application Support).
  write_script "${PREFIX}/bin/dispatch" <<'SCRIPT'
#!/usr/bin/env bash
set -e
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="${SELF_DIR}/../server"
RUNTIME_DIR="${SELF_DIR}/../runtime"
if [ -d "${RUNTIME_DIR}" ]; then export PYTHONHOME="${RUNTIME_DIR}"; fi
export OPEN_DISPATCH_DATA="${OPEN_DISPATCH_DATA:-${HOME}/.open-dispatch}"
if [ -f "${OPEN_DISPATCH_DATA}/.env" ]; then
  set -o allexport; source "${OPEN_DISPATCH_DATA}/.env"; set +o allexport
fi
exec "${SERVER_DIR}/venv/bin/python" "${SERVER_DIR}/cli.py" "$@"
SCRIPT

  write_script "${PREFIX}/bin/open-dispatch" <<'SCRIPT'
#!/usr/bin/env bash
set -e
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="${SELF_DIR}/../server"
RUNTIME_DIR="${SELF_DIR}/../runtime"
if [ -d "${RUNTIME_DIR}" ]; then export PYTHONHOME="${RUNTIME_DIR}"; fi
export OPEN_DISPATCH_DATA="${OPEN_DISPATCH_DATA:-${HOME}/.open-dispatch}"
if [ -f "${OPEN_DISPATCH_DATA}/.env" ]; then
  set -o allexport; source "${OPEN_DISPATCH_DATA}/.env"; set +o allexport
fi
cd "${SERVER_DIR}"
# Run via the venv python, not the uvicorn console script: venv console
# scripts embed the absolute build-time interpreter path in their shebang
# and break the moment the bundle is relocated.
exec "${SERVER_DIR}/venv/bin/python" -m uvicorn api.app:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}" "$@"
SCRIPT

  write_script "${PREFIX}/bin/open-dispatch-worker" <<'SCRIPT'
#!/usr/bin/env bash
set -e
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="${SELF_DIR}/../server"
RUNTIME_DIR="${SELF_DIR}/../runtime"
if [ -d "${RUNTIME_DIR}" ]; then export PYTHONHOME="${RUNTIME_DIR}"; fi
export OPEN_DISPATCH_DATA="${OPEN_DISPATCH_DATA:-${HOME}/.open-dispatch}"
if [ -f "${OPEN_DISPATCH_DATA}/.env" ]; then
  set -o allexport; source "${OPEN_DISPATCH_DATA}/.env"; set +o allexport
fi
cd "${SERVER_DIR}"
exec "${SERVER_DIR}/venv/bin/python" -m scheduler.worker "$@"
SCRIPT
else
write_script "${PREFIX}/bin/dispatch" <<SCRIPT
#!/usr/bin/env bash
if [ -f "${DATA_DIR}/.env" ]; then
  set -o allexport; source "${DATA_DIR}/.env"; set +o allexport
fi
# The wrapper owns the data dir - it wins over any value inside .env, so the
# CLI and the server always agree on where the queue lives.
export OPEN_DISPATCH_DATA="${DATA_DIR}"
exec "${VENV}/bin/python" "${INSTALL_DIR}/cli.py" "\$@"
SCRIPT

write_script "${PREFIX}/bin/open-dispatch" <<SCRIPT
#!/usr/bin/env bash
if [ -f "${DATA_DIR}/.env" ]; then
  set -o allexport; source "${DATA_DIR}/.env"; set +o allexport
fi
# The wrapper owns the data dir - it wins over any value inside .env.
export OPEN_DISPATCH_DATA="${DATA_DIR}"
cd "${INSTALL_DIR}"
exec "${VENV}/bin/uvicorn" api.app:app --host "\${HOST:-127.0.0.1}" --port "\${PORT:-8000}" "\$@"
SCRIPT

write_script "${PREFIX}/bin/open-dispatch-worker" <<SCRIPT
#!/usr/bin/env bash
if [ -f "${DATA_DIR}/.env" ]; then
  set -o allexport; source "${DATA_DIR}/.env"; set +o allexport
fi
# The wrapper owns the data dir - it wins over any value inside .env.
export OPEN_DISPATCH_DATA="${DATA_DIR}"
cd "${INSTALL_DIR}"
exec "${VENV}/bin/python" -m scheduler.worker "\$@"
SCRIPT
fi

success "Installed: dispatch, open-dispatch, open-dispatch-worker"

# ── launchd service (macOS) ───────────────────────────────────────────────────
if [[ "$OS" == "Darwin" && "$INSTALL_SERVICE" == "true" ]]; then
  PLIST_DIR="${HOME}/Library/LaunchAgents"
  PLIST="${PLIST_DIR}/dev.open-dispatch.plist"
  mkdir -p "$PLIST_DIR"

  cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>dev.open-dispatch</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PREFIX}/bin/open-dispatch</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${DATA_DIR}/server.log</string>
  <key>StandardErrorPath</key>
  <string>${DATA_DIR}/server-error.log</string>
  <key>WorkingDirectory</key>
  <string>${DATA_DIR}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>OPEN_DISPATCH_DATA</key>
    <string>${DATA_DIR}</string>
  </dict>
</dict>
</plist>
PLIST

  cat > "${PLIST_DIR}/dev.open-dispatch.worker.plist" <<WPLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>dev.open-dispatch.worker</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PREFIX}/bin/open-dispatch-worker</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${DATA_DIR}/worker.log</string>
  <key>StandardErrorPath</key>
  <string>${DATA_DIR}/worker-error.log</string>
  <key>WorkingDirectory</key>
  <string>${DATA_DIR}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>OPEN_DISPATCH_DATA</key>
    <string>${DATA_DIR}</string>
  </dict>
</dict>
</plist>
WPLIST

  success "Created launchd plists: ${PLIST} + dev.open-dispatch.worker.plist"
  info  "  Start both at login:  launchctl bootstrap gui/$(id -u) ${PLIST_DIR}"
  info  "  (or right now:        launchctl load ${PLIST} ${PLIST_DIR}/dev.open-dispatch.worker.plist)"
fi

# ── systemd service (Linux) ────────────────────────────────────────────────────
if [[ "$OS" == "Linux" && "$INSTALL_SERVICE" == "true" ]]; then
  SERVICE_DIR="${HOME}/.config/systemd/user"
  mkdir -p "$SERVICE_DIR"

  cat > "${SERVICE_DIR}/open-dispatch.service" <<UNIT
[Unit]
Description=Open-Dispatch API server
After=network.target

[Service]
Type=simple
ExecStart=${PREFIX}/bin/open-dispatch
WorkingDirectory=${DATA_DIR}
Environment="OPEN_DISPATCH_DATA=${DATA_DIR}"
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
UNIT

  cat > "${SERVICE_DIR}/open-dispatch-worker.service" <<WUNIT
[Unit]
Description=Open-Dispatch scheduler worker
After=network.target

[Service]
Type=simple
ExecStart=${PREFIX}/bin/open-dispatch-worker
WorkingDirectory=${DATA_DIR}
Environment="OPEN_DISPATCH_DATA=${DATA_DIR}"
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
WUNIT

  success "Created systemd units: open-dispatch.service + open-dispatch-worker.service"
  info  "  Enable + start both: systemctl --user enable --now open-dispatch open-dispatch-worker"
fi

# ── final instructions ─────────────────────────────────────────────────────────
echo ""
echo "${BOLD}  ✓ Open-Dispatch ${VERSION} installed successfully!${RESET}"
echo ""
echo "  Next steps:"
echo "    1. Edit credentials:   \$EDITOR ${DATA_DIR}/.env"
echo "    2. Start server:       open-dispatch        (auto-starts at login if service installed)"
echo "    3. Start worker:       open-dispatch-worker (auto-starts at login if service installed)"
echo "    4. Open dashboard:     open http://localhost:8000   (macOS)"
echo "    5. Post via CLI:       dispatch send --platforms bluesky --text 'hello'"
echo "    6. Check health:       dispatch doctor"
echo ""
echo "  More info: https://open-dispatch-landing.vercel.app"
echo ""
