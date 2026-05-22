#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Open-Dispatch installer
# Usage:  curl -fsSL https://raw.githubusercontent.com/Matthew-Selvam/Open-Dispatch/main/install.sh | bash
# Or:     bash install.sh [--prefix /usr/local] [--version v0.4.0] [--no-service]
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
PREFIX="${PREFIX:-/usr/local}"
VERSION="${OPEN_DISPATCH_VERSION:-v0.4.0}"
INSTALL_DIR="${INSTALL_DIR:-${PREFIX}/opt/open-dispatch}"
DATA_DIR="${DATA_DIR:-${HOME}/.open-dispatch}"
INSTALL_SERVICE=true

# ── argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix)     PREFIX="$2";       INSTALL_DIR="${PREFIX}/opt/open-dispatch"; shift 2 ;;
    --version)    VERSION="$2";      shift 2 ;;
    --data-dir)   DATA_DIR="$2";     shift 2 ;;
    --no-service) INSTALL_SERVICE=false; shift ;;
    --help|-h)
      echo "Usage: install.sh [--prefix DIR] [--version TAG] [--data-dir DIR] [--no-service]"
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
for candidate in python3.12 python3.11 python3; do
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
TARBALL_URL="https://github.com/Matthew-Selvam/Open-Dispatch/archive/refs/tags/${VERSION}.tar.gz"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

info "Downloading Open-Dispatch ${VERSION} …"
$FETCH "$TARBALL_URL" | tar -xz -C "$TMP_DIR" --strip-components=1

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

write_script "${PREFIX}/bin/dispatch" <<SCRIPT
#!/usr/bin/env bash
export OPEN_DISPATCH_DATA="${DATA_DIR}"
exec "${VENV}/bin/python" "${INSTALL_DIR}/cli.py" "\$@"
SCRIPT

write_script "${PREFIX}/bin/open-dispatch" <<SCRIPT
#!/usr/bin/env bash
export OPEN_DISPATCH_DATA="${DATA_DIR}"
if [ -f "${DATA_DIR}/.env" ]; then
  set -o allexport; source "${DATA_DIR}/.env"; set +o allexport
fi
cd "${INSTALL_DIR}"
exec "${VENV}/bin/uvicorn" api.app:app --host "\${HOST:-127.0.0.1}" --port "\${PORT:-8000}" "\$@"
SCRIPT

write_script "${PREFIX}/bin/open-dispatch-worker" <<SCRIPT
#!/usr/bin/env bash
export OPEN_DISPATCH_DATA="${DATA_DIR}"
if [ -f "${DATA_DIR}/.env" ]; then
  set -o allexport; source "${DATA_DIR}/.env"; set +o allexport
fi
cd "${INSTALL_DIR}"
exec "${VENV}/bin/python" -m scheduler.worker "\$@"
SCRIPT

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
  <false/>
  <key>KeepAlive</key>
  <false/>
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

  success "Created launchd plist: ${PLIST}"
  info  "  Start server automatically at login: launchctl load ${PLIST}"
  info  "  Start right now:                     launchctl start dev.open-dispatch"
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

  success "Created systemd unit: ${SERVICE_DIR}/open-dispatch.service"
  info  "  Enable + start: systemctl --user enable --now open-dispatch"
fi

# ── final instructions ─────────────────────────────────────────────────────────
echo ""
echo "${BOLD}  ✓ Open-Dispatch ${VERSION} installed successfully!${RESET}"
echo ""
echo "  Next steps:"
echo "    1. Edit credentials:   \$EDITOR ${DATA_DIR}/.env"
echo "    2. Start server:       open-dispatch"
echo "    3. Open dashboard:     open http://localhost:8000   (macOS)"
echo "    4. Post via CLI:       dispatch send --platforms bluesky --text 'hello'"
echo ""
echo "  More info: https://open-dispatch-landing.vercel.app"
echo ""
