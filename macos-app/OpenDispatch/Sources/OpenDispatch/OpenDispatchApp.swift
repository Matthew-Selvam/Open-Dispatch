import SwiftUI

@main
struct OpenDispatchApp: App {

    @StateObject private var manager = ServerManager()

    var body: some Scene {
        // MenuBarExtra gives us a status-bar icon + popover.
        // The app has no Dock icon (LSUIElement = YES in Info.plist).
        MenuBarExtra {
            MenuBarView()
                .environmentObject(manager)
        } label: {
            // Use a template image so it adapts to dark/light menu bar
            Label {
                Text("Open-Dispatch")  // accessibility label
            } icon: {
                Image(systemName: manager.isRunning
                    ? "arrow.up.doc.fill"
                    : "arrow.up.doc")
                    .symbolRenderingMode(.hierarchical)
                    .foregroundStyle(manager.isRunning ? .green : .primary)
            }
        }
        .menuBarExtraStyle(.window)

        Settings {
            SettingsView()
                .environmentObject(manager)
        }
    }
}
