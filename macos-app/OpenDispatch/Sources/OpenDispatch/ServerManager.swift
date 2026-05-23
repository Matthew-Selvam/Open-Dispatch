import Foundation
import AppKit
import Combine

/// Tracks whether the open-dispatch server process is alive and polls /healthz.
@MainActor
final class ServerManager: ObservableObject {

    // ── published state ──────────────────────────────────────────────────────
    @Published private(set) var isRunning = false
    @Published private(set) var statusText = "Stopped"
    @Published private(set) var port: Int = UserDefaults.standard.integer(forKey: "od.port") == 0
                                             ? 8000
                                             : UserDefaults.standard.integer(forKey: "od.port")

    // ── private ──────────────────────────────────────────────────────────────
    private var serverProcess:  Process?
    private var workerProcess:  Process?
    private var pollTimer:      Timer?
    private let session = URLSession(configuration: .ephemeral)

    // ── URL helpers ───────────────────────────────────────────────────────────
    var dashboardURL: URL { URL(string: "http://localhost:\(port)")! }
    var healthzURL:   URL { URL(string: "http://localhost:\(port)/healthz")! }

    // ── resolution ────────────────────────────────────────────────────────────
    /// Returns the `open-dispatch` binary shipped inside the .app bundle,
    /// then falls back to the Homebrew path, then PATH.
    private var serverBin: String {
        let bundleBin = Bundle.main.bundlePath + "/Contents/Resources/bin/open-dispatch"
        if FileManager.default.isExecutableFile(atPath: bundleBin) { return bundleBin }
        let brewBin = "/usr/local/bin/open-dispatch"
        if FileManager.default.isExecutableFile(atPath: brewBin) { return brewBin }
        return "open-dispatch"   // rely on PATH
    }

    private var workerBin: String {
        let bundleBin = Bundle.main.bundlePath + "/Contents/Resources/bin/open-dispatch-worker"
        if FileManager.default.isExecutableFile(atPath: bundleBin) { return bundleBin }
        let brewBin = "/usr/local/bin/open-dispatch-worker"
        if FileManager.default.isExecutableFile(atPath: brewBin) { return brewBin }
        return "open-dispatch-worker"
    }

    private var dataDir: String {
        let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        let dir = appSupport.appendingPathComponent("open-dispatch")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.path
    }

    // ── start / stop ──────────────────────────────────────────────────────────
    func start() {
        guard serverProcess == nil else { return }

        statusText = "Starting…"

        // ── server ────────────────────────────────────────────────────────────
        let srv = Process()
        srv.executableURL = URL(fileURLWithPath: serverBin)
        srv.arguments     = ["--host", "127.0.0.1", "--port", "\(port)"]
        srv.environment   = enrichedEnv()
        srv.terminationHandler = { [weak self] _ in
            Task { @MainActor [weak self] in self?.handleTermination() }
        }

        do {
            try srv.run()
            serverProcess = srv
        } catch {
            statusText = "Failed to start: \(error.localizedDescription)"
            return
        }

        // ── worker ────────────────────────────────────────────────────────────
        let wrk = Process()
        wrk.executableURL = URL(fileURLWithPath: workerBin)
        wrk.environment   = enrichedEnv()
        try? wrk.run()
        workerProcess = wrk

        startPolling()
    }

    func stop() {
        pollTimer?.invalidate()
        pollTimer = nil

        workerProcess?.terminate()
        workerProcess = nil
        serverProcess?.terminate()
        serverProcess = nil

        isRunning  = false
        statusText = "Stopped"
    }

    func toggle() { isRunning ? stop() : start() }

    // ── env setup ─────────────────────────────────────────────────────────────
    private func enrichedEnv() -> [String: String] {
        var env = ProcessInfo.processInfo.environment
        env["OPEN_DISPATCH_DATA"] = dataDir
        env["PORT"]               = "\(port)"
        // Source .env file keys if present (simple KEY=VALUE parser)
        let envFile = dataDir + "/.env"
        if let lines = try? String(contentsOfFile: envFile).components(separatedBy: "\n") {
            for line in lines {
                let trimmed = line.trimmingCharacters(in: .whitespaces)
                guard !trimmed.hasPrefix("#"), trimmed.contains("=") else { continue }
                let parts = trimmed.components(separatedBy: "=")
                if parts.count >= 2 {
                    let key = parts[0]
                    let value = parts[1...].joined(separator: "=")
                        .trimmingCharacters(in: CharacterSet(charactersIn: "\"'"))
                    env[key] = value
                }
            }
        }
        return env
    }

    // ── health polling ────────────────────────────────────────────────────────
    private func startPolling() {
        pollTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] _ in
            Task { [weak self] in await self?.poll() }
        }
    }

    private func poll() async {
        guard serverProcess?.isRunning == true else {
            await MainActor.run { handleTermination() }
            return
        }
        do {
            let (_, response) = try await session.data(from: healthzURL)
            let ok = (response as? HTTPURLResponse)?.statusCode == 200
            await MainActor.run {
                isRunning  = ok
                statusText = ok ? "Running on port \(port)" : "Unhealthy"
            }
        } catch {
            await MainActor.run {
                isRunning  = false
                statusText = "Starting…"
            }
        }
    }

    private func handleTermination() {
        pollTimer?.invalidate()
        pollTimer      = nil
        serverProcess  = nil
        workerProcess?.terminate()
        workerProcess  = nil
        isRunning      = false
        statusText     = "Stopped"
    }

    // ── helpers ───────────────────────────────────────────────────────────────
    func openDataDir() {
        NSWorkspace.shared.open(URL(fileURLWithPath: dataDir))
    }

    func openEnvFile() {
        let path = dataDir + "/.env"
        // Create blank .env if missing
        if !FileManager.default.fileExists(atPath: path) {
            FileManager.default.createFile(atPath: path, contents: nil)
        }
        NSWorkspace.shared.open(URL(fileURLWithPath: path))
    }
}
