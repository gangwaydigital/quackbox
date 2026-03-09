import Foundation

enum MailNavigationMode: String, CaseIterable, Identifiable {
    case emails = "Emails"
    case threads = "Threads"

    var id: String { rawValue }
}

struct APIError: Decodable {
    let detail: String?
}

struct StatsResponse: Codable {
    let totalEmails: Int
    let uniqueSenders: Int
    let mboxSources: Int
    let version: String?

    enum CodingKeys: String, CodingKey {
        case totalEmails = "total_emails"
        case uniqueSenders = "unique_senders"
        case mboxSources = "mbox_sources"
        case version
    }
}

struct MailboxItem: Codable, Identifiable, Hashable {
    var id: String { mboxSource }
    let mboxSource: String
    let count: Int
    let firstDate: String?
    let lastDate: String?
    let uniqueSenders: Int

    enum CodingKeys: String, CodingKey {
        case mboxSource = "mbox_source"
        case count
        case firstDate = "first_date"
        case lastDate = "last_date"
        case uniqueSenders = "unique_senders"
    }
}

struct PaginatedEmailsResponse: Codable {
    let items: [EmailListItem]
    let total: Int
    let page: Int
    let totalPages: Int

    enum CodingKeys: String, CodingKey {
        case items
        case total
        case page
        case totalPages = "total_pages"
    }
}

struct EmailListItem: Codable, Identifiable, Hashable {
    let id: Int
    let subject: String?
    let senderName: String?
    let senderEmail: String?
    let dateSent: String?
    let hasAttachments: Bool
    let mboxSource: String?
    let threadGroupID: Int?
    let snippet: String?

    enum CodingKeys: String, CodingKey {
        case id
        case subject
        case senderName = "sender_name"
        case senderEmail = "sender_email"
        case dateSent = "date_sent"
        case hasAttachments = "has_attachments"
        case mboxSource = "mbox_source"
        case threadGroupID = "thread_group_id"
        case snippet
    }
}

struct Recipient: Codable, Hashable {
    let name: String?
    let email: String
    let type: String?

    enum CodingKeys: String, CodingKey {
        case name
        case email
        case address
        case type
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        name = try? c.decode(String.self, forKey: .name)
        type = try? c.decode(String.self, forKey: .type)
        email = (try? c.decode(String.self, forKey: .email))
            ?? (try? c.decode(String.self, forKey: .address))
            ?? ""
    }

    init(name: String?, email: String, type: String?) {
        self.name = name
        self.email = email
        self.type = type
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encodeIfPresent(name, forKey: .name)
        try c.encode(email, forKey: .email)
        try c.encodeIfPresent(type, forKey: .type)
    }
}

struct EmailDetail: Codable, Hashable {
    let id: Int
    let subject: String?
    let senderName: String?
    let senderEmail: String?
    let recipients: [Recipient]
    let dateSent: String?
    let bodyText: String?
    let bodyHTML: String?
    let hasAttachments: Bool
    let attachmentNames: [String]
    let mboxSource: String?

    enum CodingKeys: String, CodingKey {
        case id
        case subject
        case senderName = "sender_name"
        case senderEmail = "sender_email"
        case recipients
        case dateSent = "date_sent"
        case bodyText = "body_text"
        case bodyHTML = "body_html"
        case hasAttachments = "has_attachments"
        case attachmentNames = "attachment_names"
        case mboxSource = "mbox_source"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = (try? c.decode(Int.self, forKey: .id)) ?? 0
        subject = try? c.decode(String.self, forKey: .subject)
        senderName = try? c.decode(String.self, forKey: .senderName)
        senderEmail = try? c.decode(String.self, forKey: .senderEmail)
        dateSent = try? c.decode(String.self, forKey: .dateSent)
        bodyText = try? c.decode(String.self, forKey: .bodyText)
        bodyHTML = try? c.decode(String.self, forKey: .bodyHTML)
        hasAttachments = (try? c.decode(Bool.self, forKey: .hasAttachments)) ?? false
        attachmentNames = (try? c.decode([String].self, forKey: .attachmentNames)) ?? []
        mboxSource = try? c.decode(String.self, forKey: .mboxSource)

        if let parsedRecipients = try? c.decode([Recipient].self, forKey: .recipients) {
            recipients = parsedRecipients
        } else if let rawRecipients = try? c.decode(String.self, forKey: .recipients),
                  let data = rawRecipients.data(using: .utf8),
                  let parsed = try? JSONDecoder().decode([Recipient].self, from: data) {
            recipients = parsed
        } else {
            recipients = []
        }
    }
}

struct PaginatedThreadsResponse: Codable {
    let items: [ThreadListItem]
    let total: Int
    let page: Int
    let totalPages: Int

    enum CodingKeys: String, CodingKey {
        case items
        case total
        case page
        case totalPages = "total_pages"
    }
}

struct ThreadListItem: Codable, Identifiable, Hashable {
    let id: Int
    let rootMessageID: String?
    let subjectNormalized: String?
    let participantCount: Int
    let messageCount: Int
    let firstDate: String?
    let lastDate: String?
    let mailboxSources: [String]
    let originalSubject: String?

    enum CodingKeys: String, CodingKey {
        case id
        case rootMessageID = "root_message_id"
        case subjectNormalized = "subject_normalized"
        case participantCount = "participant_count"
        case messageCount = "message_count"
        case firstDate = "first_date"
        case lastDate = "last_date"
        case mailboxSources = "mailbox_sources"
        case originalSubject = "original_subject"
    }
}

struct ThreadDetail: Codable, Hashable {
    let id: Int
    let participantCount: Int
    let messageCount: Int
    let firstDate: String?
    let lastDate: String?
    let mailboxSources: [String]
    let emails: [ThreadEmail]

    enum CodingKeys: String, CodingKey {
        case id
        case participantCount = "participant_count"
        case messageCount = "message_count"
        case firstDate = "first_date"
        case lastDate = "last_date"
        case mailboxSources = "mailbox_sources"
        case emails
    }
}

struct ThreadEmail: Codable, Identifiable, Hashable {
    let id: Int
    let subject: String?
    let senderName: String?
    let senderEmail: String?
    let dateSent: String?
    let bodyText: String?
    let hasAttachments: Bool
    let attachmentNames: [String]

    enum CodingKeys: String, CodingKey {
        case id
        case subject
        case senderName = "sender_name"
        case senderEmail = "sender_email"
        case dateSent = "date_sent"
        case bodyText = "body_text"
        case hasAttachments = "has_attachments"
        case attachmentNames = "attachment_names"
    }
}

struct AccountEnvelope: Codable {
    let items: [MailAccount]
}

struct MailAccount: Codable, Identifiable, Hashable {
    let id: Int
    let displayName: String
    let emailAddress: String
    let imap: MailServerConfig
    let smtp: MailServerConfig
    let oauthProvider: String?
    let enabled: Bool

    enum CodingKeys: String, CodingKey {
        case id
        case displayName = "display_name"
        case emailAddress = "email_address"
        case imap
        case smtp
        case oauthProvider = "oauth_provider"
        case enabled
    }
}

struct MailServerConfig: Codable, Hashable {
    let host: String
    let port: Int
    let security: String
    let username: String
}

struct CreateAccountRequest: Codable {
    var displayName: String
    var emailAddress: String
    var imapHost: String
    var imapPort: Int
    var imapSecurity: String
    var imapUsername: String
    var imapPassword: String?
    var smtpHost: String
    var smtpPort: Int
    var smtpSecurity: String
    var smtpUsername: String
    var smtpPassword: String?
    var oauthProvider: String?
    var oauthClientID: String?
    var oauthClientSecret: String?
    var oauthRefreshToken: String?
    var oauthAccessToken: String?
    var oauthTokenURL: String?
    var oauthExpiresAt: String?
    var enabled: Bool

    enum CodingKeys: String, CodingKey {
        case displayName = "display_name"
        case emailAddress = "email_address"
        case imapHost = "imap_host"
        case imapPort = "imap_port"
        case imapSecurity = "imap_security"
        case imapUsername = "imap_username"
        case imapPassword = "imap_password"
        case smtpHost = "smtp_host"
        case smtpPort = "smtp_port"
        case smtpSecurity = "smtp_security"
        case smtpUsername = "smtp_username"
        case smtpPassword = "smtp_password"
        case oauthProvider = "oauth_provider"
        case oauthClientID = "oauth_client_id"
        case oauthClientSecret = "oauth_client_secret"
        case oauthRefreshToken = "oauth_refresh_token"
        case oauthAccessToken = "oauth_access_token"
        case oauthTokenURL = "oauth_token_url"
        case oauthExpiresAt = "oauth_expires_at"
        case enabled
    }
}

struct SendEmailRequest: Codable {
    var to: [String]
    var cc: [String]
    var bcc: [String]
    var subject: String
    var bodyText: String
    var bodyHTML: String?

    enum CodingKeys: String, CodingKey {
        case to
        case cc
        case bcc
        case subject
        case bodyText = "body_text"
        case bodyHTML = "body_html"
    }
}

struct AccountPatchRequest: Codable {
    var displayName: String?
    var emailAddress: String?
    var imapHost: String?
    var imapPort: Int?
    var imapSecurity: String?
    var imapUsername: String?
    var imapPassword: String?
    var smtpHost: String?
    var smtpPort: Int?
    var smtpSecurity: String?
    var smtpUsername: String?
    var smtpPassword: String?
    var oauthProvider: String?
    var oauthClientID: String?
    var oauthClientSecret: String?
    var oauthRefreshToken: String?
    var oauthAccessToken: String?
    var oauthTokenURL: String?
    var oauthExpiresAt: String?
    var enabled: Bool?

    enum CodingKeys: String, CodingKey {
        case displayName = "display_name"
        case emailAddress = "email_address"
        case imapHost = "imap_host"
        case imapPort = "imap_port"
        case imapSecurity = "imap_security"
        case imapUsername = "imap_username"
        case imapPassword = "imap_password"
        case smtpHost = "smtp_host"
        case smtpPort = "smtp_port"
        case smtpSecurity = "smtp_security"
        case smtpUsername = "smtp_username"
        case smtpPassword = "smtp_password"
        case oauthProvider = "oauth_provider"
        case oauthClientID = "oauth_client_id"
        case oauthClientSecret = "oauth_client_secret"
        case oauthRefreshToken = "oauth_refresh_token"
        case oauthAccessToken = "oauth_access_token"
        case oauthTokenURL = "oauth_token_url"
        case oauthExpiresAt = "oauth_expires_at"
        case enabled
    }
}

struct SendEmailResponse: Codable {
    let ok: Bool
    let sentAt: String
    let accountID: Int
    let recipientCount: Int
    let subject: String

    enum CodingKeys: String, CodingKey {
        case ok
        case sentAt = "sent_at"
        case accountID = "account_id"
        case recipientCount = "recipient_count"
        case subject
    }
}

struct SyncResponse: Codable {
    let accountID: Int
    let folder: String
    let fetchedCount: Int
    let insertedCount: Int
    let skippedCount: Int
    let lastUID: Int

    enum CodingKeys: String, CodingKey {
        case accountID = "account_id"
        case folder
        case fetchedCount = "fetched_count"
        case insertedCount = "inserted_count"
        case skippedCount = "skipped_count"
        case lastUID = "last_uid"
    }
}

struct ComposeDraft: Identifiable {
    let id = UUID()
    var accountID: Int?
    var to: String = ""
    var cc: String = ""
    var bcc: String = ""
    var subject: String = ""
    var body: String = ""
    var bodyHTML: String? = nil
}

struct CachedSnapshot: Codable {
    var stats: StatsResponse?
    var mailboxes: [MailboxItem]
    var emails: [EmailListItem]
    var threads: [ThreadListItem]
    var selectedEmailDetail: EmailDetail?
    var selectedThreadDetail: ThreadDetail?
    var accounts: [MailAccount]
    var archivedEmailIDs: [Int]
    var seenEmailIDs: [Int]
    var unreadEmailIDs: [Int]
    var savedAt: String
}

enum RuleField: String, Codable, CaseIterable, Identifiable {
    case sender
    case subject
    case snippet

    var id: String { rawValue }
}

enum RuleAction: String, Codable, CaseIterable, Identifiable {
    case archive
    case markRead
    case markUnread
    case markJunk

    var id: String { rawValue }
}

struct SignatureItem: Codable, Identifiable, Hashable {
    var id: UUID = UUID()
    var name: String
    var body: String
    var isHTML: Bool
}

struct MailRule: Codable, Identifiable, Hashable {
    var id: UUID = UUID()
    var enabled: Bool = true
    var name: String
    var field: RuleField
    var contains: String
    var action: RuleAction
    var continueEvaluating: Bool = false
}

struct AppPreferences: Codable {
    var junkFilterEnabled: Bool = true
    var hideJunkFromInbox: Bool = true
    var junkKeywordsRaw: String = "unsubscribe, lottery, winner, promo"
    var blockedSendersRaw: String = ""

    var composeFontName: String = "Helvetica Neue"
    var composeFontSize: Double = 14
    var composeTextColorHex: String = "#1F1F24"

    var showMessagePreview: Bool = true
    var showSenderAvatars: Bool = true
    var compactListDensity: Bool = false
    var preferPlainTextReading: Bool = true
    var readingFontSize: Double = 14
    var useThreadedViewByDefault: Bool = true

    var composeInRichText: Bool = true
    var spellCheckWhileTyping: Bool = true
    var autoDetectLinks: Bool = true
    var smartQuotes: Bool = true
    var smartDashes: Bool = true
    var includeSignatureOnNew: Bool = true
    var includeSignatureOnReply: Bool = true

    var signatures: [SignatureItem] = [SignatureItem(name: "Default", body: "Sent from QuackBox Native", isHTML: false)]
    var defaultSignatureID: UUID?

    var rulesEnabled: Bool = true
    var rules: [MailRule] = []

    var allowNotifications: Bool = true
    var loadRemoteContent: Bool = false
    var protectMailActivity: Bool = true
}
