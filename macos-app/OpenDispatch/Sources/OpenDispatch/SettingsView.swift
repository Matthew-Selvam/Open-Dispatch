import SwiftUI

/// Preferences window — accessible from the Mac menu bar (⌘,)
struct SettingsView: View {

    @EnvironmentObject private var manager: ServerManager

    @AppStorage("od.port")          private var port: Int    = 8000
    @AppStorage("od.startOnLogin")  private var startOnLogin = false
    @AppStorage("od.autoStart")     private var autoStart    = false

    var body: some View {
        Form {
            Section("Server") {
                LabeledContent("Port") {
                    TextField("", value: $port, format: .number)
                        .frame(width: 80)
                        .textFieldStyle(.roundedBorder)
                        .onChange(of: port) { _, new in
                            UserDefaults.standard.set(new, forKey: "od.port")
                        }
                }

                Toggle("Start server automatically on app launch", isOn: $autoStart)
                Toggle("Launch at login", isOn: $startOnLogin)
                    .onChange(of: startOnLogin) { _, enabled in
                        LoginItemManager.set(enabled: enabled)
                    }
            }

            Section("About") {
                LabeledContent("Version", value: "0.4.0")
                LabeledContent("License", value: "MIT")
                Link("Documentation", destination: URL(string: "https://open-dispatch-landing.vercel.app")!)
                Link("GitHub", destination: URL(string: "https://github.com/Matthew-Selvam/Open-Dispatch")!)
            }
        }
        .formStyle(.grouped)
        .frame(width: 360, height: 280)
        .onAppear {
            if autoStart && !manager.isRunning { manager.start() }
        }
    }
}

// ── login item helper (SMAppService, macOS 13+) ────────────────────────────────
import ServiceManagement

enum LoginItemManager {
    static func set(enabled: Bool) {
        do {
            if enabled {
                try SMAppService.mainApp.register()
            } else {
                try SMAppService.mainApp.unregister()
            }
        } catch {
            // Silently swallow — user can always toggle again
        }
    }
}
