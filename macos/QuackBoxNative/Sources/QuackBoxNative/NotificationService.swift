import Foundation
import UserNotifications

@MainActor
final class NotificationService {
    static let shared = NotificationService()

    private init() {}

    func requestAuthorizationIfNeeded() async {
        guard isRunningFromAppBundle else { return }
        let center = UNUserNotificationCenter.current()
        let settings = await center.notificationSettings()
        if settings.authorizationStatus == .notDetermined {
            _ = try? await center.requestAuthorization(options: [.alert, .sound, .badge])
        }
    }

    func postNewMailSummary(count: Int, latestSubject: String?) {
        guard isRunningFromAppBundle else { return }
        guard count > 0 else { return }

        let content = UNMutableNotificationContent()
        if count == 1 {
            content.title = "1 new email"
            content.body = latestSubject?.isEmpty == false ? latestSubject! : "New message received"
        } else {
            content.title = "\(count) new emails"
            content.body = latestSubject?.isEmpty == false ? "Latest: \(latestSubject!)" : "New messages received"
        }
        content.sound = .default

        let request = UNNotificationRequest(
            identifier: "quackbox.newmail.\(UUID().uuidString)",
            content: content,
            trigger: nil
        )
        UNUserNotificationCenter.current().add(request)
    }

    private var isRunningFromAppBundle: Bool {
        Bundle.main.bundleURL.pathExtension.lowercased() == "app"
    }
}
