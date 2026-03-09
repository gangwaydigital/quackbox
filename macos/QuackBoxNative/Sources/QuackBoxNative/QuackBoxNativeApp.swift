import SwiftUI

@main
struct QuackBoxNativeApp: App {
    @StateObject private var state = MailAppState()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            RootSplitView()
                .environmentObject(state)
                .task {
                    await state.loadInitialData()
                }
                .onChange(of: scenePhase) { _, phase in
                    state.setAppIsActive(phase == .active)
                }
        }
        .defaultSize(width: 1320, height: 860)
        .commands {
            MailCommands(state: state)
        }

        Settings {
            SettingsView()
                .environmentObject(state)
                .frame(width: 1240, height: 780)
        }
    }
}
