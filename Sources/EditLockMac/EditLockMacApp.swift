import AppKit
import SwiftUI

final class EditLockAppDelegate: NSObject, NSApplicationDelegate {
    var stopEngine: (() -> Void)?

    func applicationWillTerminate(_ notification: Notification) {
        stopEngine?()
    }
}

@main
struct EditLockMacApp: App {
    @NSApplicationDelegateAdaptor(EditLockAppDelegate.self) private var appDelegate
    @StateObject private var state = EditLockState()

    var body: some Scene {
        WindowGroup("EditLock") {
            ContentView()
                .environmentObject(state)
                .onAppear { appDelegate.stopEngine = { state.stopEngine() } }
        }
        .defaultSize(width: 1080, height: 760)
    }
}
