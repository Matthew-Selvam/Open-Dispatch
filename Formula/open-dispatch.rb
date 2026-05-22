class OpenDispatch < Formula
  desc "One API to dispatch your content anywhere — self-hostable cross-poster"
  homepage "https://open-dispatch-landing.vercel.app"
  url "https://github.com/Matthew-Selvam/Open-Dispatch/archive/refs/tags/v0.4.0.tar.gz"
  sha256 "05de98a63f848dcad2116265d6075ea17ffd8f536909b11fd9dba3084138704b"
  license "MIT"
  version "0.4.0"

  head "https://github.com/Matthew-Selvam/Open-Dispatch.git", branch: "main"

  depends_on "python@3.12"

  # ── installation ─────────────────────────────────────────────────────────
  def install
    python = Formula["python@3.12"].opt_bin/"python3"
    venv   = libexec/"venv"

    # Create an isolated virtualenv so the system Python is untouched
    system python, "-m", "venv", venv
    system "#{venv}/bin/pip", "install", "--upgrade", "--quiet", "pip", "wheel"
    system "#{venv}/bin/pip", "install", "--quiet", "-r", "requirements.txt"

    # Install the package itself (gives access to all modules by path)
    libexec.install Dir["*"]

    # Persist user data in the standard Homebrew var dir
    (var/"open-dispatch").mkpath

    # ── CLI wrapper ──────────────────────────────────────────────────────
    (bin/"dispatch").write <<~SHELL
      #!/bin/bash
      # open-dispatch CLI — installed by Homebrew
      export OPEN_DISPATCH_DATA="#{var}/open-dispatch"
      exec "#{libexec}/venv/bin/python" "#{libexec}/cli.py" "$@"
    SHELL

    # ── API server wrapper ───────────────────────────────────────────────
    (bin/"open-dispatch").write <<~SHELL
      #!/bin/bash
      # open-dispatch server — installed by Homebrew
      export OPEN_DISPATCH_DATA="#{var}/open-dispatch"
      cd "#{libexec}"

      # Load .env from data dir if present
      if [ -f "#{var}/open-dispatch/.env" ]; then
        set -o allexport
        source "#{var}/open-dispatch/.env"
        set +o allexport
      fi

      exec "#{libexec}/venv/bin/uvicorn" api.app:app \
        --host "${HOST:-127.0.0.1}" \
        --port "${PORT:-8000}" \
        "$@"
    SHELL

    # ── background worker wrapper ────────────────────────────────────────
    (bin/"open-dispatch-worker").write <<~SHELL
      #!/bin/bash
      # open-dispatch worker — installed by Homebrew
      export OPEN_DISPATCH_DATA="#{var}/open-dispatch"
      cd "#{libexec}"

      if [ -f "#{var}/open-dispatch/.env" ]; then
        set -o allexport
        source "#{var}/open-dispatch/.env"
        set +o allexport
      fi

      exec "#{libexec}/venv/bin/python" -m scheduler.worker "$@"
    SHELL
  end

  # ── brew services (launchd) ───────────────────────────────────────────────
  service do
    run          [opt_bin/"open-dispatch"]
    working_dir  var/"open-dispatch"
    log_path     var/"log/open-dispatch.log"
    error_log_path var/"log/open-dispatch-error.log"
    keep_alive   true
    process_type :background
  end

  # ── post-install caveats ──────────────────────────────────────────────────
  def caveats
    <<~EOS
      Open-Dispatch has been installed. To get started:

      1. Create your credentials file:
           cp #{opt_libexec}/.env.example #{var}/open-dispatch/.env
           $EDITOR #{var}/open-dispatch/.env

      2. Start the server (foreground):
           open-dispatch

      3. Or run as a background service (auto-starts on login):
           brew services start open-dispatch

      4. Open the dashboard:
           open http://localhost:8000

      5. Post via the CLI:
           dispatch send --platforms bluesky,twitter --text "hello world"

      Data directory: #{var}/open-dispatch
    EOS
  end

  # ── test ─────────────────────────────────────────────────────────────────
  test do
    require "socket"

    # Pick a free port
    server = TCPServer.new("127.0.0.1", 0)
    port   = server.addr[1]
    server.close

    pid = fork do
      ENV["OPEN_DISPATCH_DATA"] = testpath
      exec bin/"open-dispatch", "--port", port.to_s, "--host", "127.0.0.1"
    end

    # Wait up to 8s for the server to be ready
    8.times do
      sleep 1
      output = shell_output("curl -sf http://127.0.0.1:#{port}/healthz", allow_failure: true)
      if output.include?("ok")
        assert_match "ok", output
        break
      end
    end
  ensure
    Process.kill("TERM", pid) if pid
  end
end
