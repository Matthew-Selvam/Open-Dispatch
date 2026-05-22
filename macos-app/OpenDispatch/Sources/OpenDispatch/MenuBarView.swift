import SwiftUI

/// The popover that drops down from the menu-bar icon.
struct MenuBarView: View {

    @EnvironmentObject private var manager: ServerManager

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {

            // ── header ────────────────────────────────────────────────────
            HStack(spacing: 10) {
                Circle()
                    .fill(manager.isRunning ? Color.green : Color.red)
                    .frame(width: 8, height: 8)
                VStack(alignment: .leading, spacing: 2) {
                    Text("open-dispatch")
                        .font(.system(.headline, design: .monospaced))
                    Text(manager.statusText)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 12)

            Divider()

            // ── actions ───────────────────────────────────────────────────
            Group {
                // Start / stop
                Button {
                    manager.toggle()
                } label: {
                    Label(
                        manager.isRunning ? "Stop Server" : "Start Server",
                        systemImage: manager.isRunning ? "stop.fill" : "play.fill"
                    )
                }
                .keyboardShortcut("s", modifiers: [.command])

                Divider()

                // Dashboard
                Button {
                    NSWorkspace.shared.open(manager.dashboardURL)
                } label: {
                    Label("Open Dashboard", systemImage: "safari")
                }
                .disabled(!manager.isRunning)
                .keyboardShortcut("d", modifiers: [.command])

                Divider()

                // Config
                Button {
                    manager.openEnvFile()
                } label: {
                    Label("Edit .env", systemImage: "pencil")
                }

                Button {
                    manager.openDataDir()
                } label: {
                    Label("Open Data Folder", systemImage: "folder")
                }

                Divider()

                // About / quit
                Button("About Open-Dispatch") {
                    NSWorkspace.shared.open(URL(string: "https://open-dispatch-landing.vercel.app")!)
                }

                Button("Quit") {
                    manager.stop()
                    NSApp.terminate(nil)
                }
                .keyboardShortcut("q", modifiers: [.command])
            }
            .buttonStyle(MenuItemButtonStyle())
        }
        .frame(width: 240)
        .background(.regularMaterial)
    }
}

// ── custom menu-item button style ─────────────────────────────────────────────
struct MenuItemButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 14)
            .padding(.vertical, 7)
            .background(configuration.isPressed
                ? Color.accentColor.opacity(0.15)
                : Color.clear)
            .contentShape(Rectangle())
    }
}
