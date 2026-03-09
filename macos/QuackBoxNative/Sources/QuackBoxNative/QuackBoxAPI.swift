import Foundation

struct QuackBoxAPI {
    enum APIClientError: LocalizedError {
        case invalidURL
        case server(String)
        case decoding(String)

        var errorDescription: String? {
            switch self {
            case .invalidURL:
                return "Invalid API URL."
            case .server(let message):
                return message
            case .decoding(let message):
                return "Failed to decode API response: \(message)"
            }
        }
    }

    var baseURL: URL

    init(baseURL: URL) {
        self.baseURL = baseURL
    }

    func fetchStats() async throws -> StatsResponse {
        try await request(path: "/api/stats")
    }

    func fetchMailboxes() async throws -> [MailboxItem] {
        let payload: WrappedAnalytics<[MailboxItem]> = try await request(path: "/api/analytics/mailboxes")
        return payload.data
    }

    func fetchEmails(search: String, mailbox: String?) async throws -> PaginatedEmailsResponse {
        if search.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            var query = [
                URLQueryItem(name: "page", value: "1"),
                URLQueryItem(name: "page_size", value: "200"),
                URLQueryItem(name: "sort_by", value: "date_timestamp"),
                URLQueryItem(name: "sort_order", value: "desc")
            ]
            if let mailbox, !mailbox.isEmpty {
                query.append(URLQueryItem(name: "mbox_source", value: mailbox))
            }
            return try await request(path: "/api/emails", queryItems: query)
        }

        var query = [
            URLQueryItem(name: "q", value: search),
            URLQueryItem(name: "page", value: "1"),
            URLQueryItem(name: "page_size", value: "200"),
            URLQueryItem(name: "sort_by", value: "date_timestamp"),
            URLQueryItem(name: "sort_order", value: "desc")
        ]
        if let mailbox, !mailbox.isEmpty {
            query.append(URLQueryItem(name: "mbox_source", value: mailbox))
        }
        return try await request(path: "/api/emails/advanced-search", queryItems: query)
    }

    func fetchEmailDetail(id: Int) async throws -> EmailDetail {
        try await request(path: "/api/emails/\(id)")
    }

    func fetchThreads() async throws -> PaginatedThreadsResponse {
        try await request(path: "/api/threads", queryItems: [
            URLQueryItem(name: "min_messages", value: "1"),
            URLQueryItem(name: "page", value: "1"),
            URLQueryItem(name: "page_size", value: "200"),
            URLQueryItem(name: "sort_by", value: "last_date"),
            URLQueryItem(name: "sort_order", value: "desc")
        ])
    }

    func fetchThreadDetail(id: Int) async throws -> ThreadDetail {
        try await request(path: "/api/threads/\(id)")
    }

    func fetchAccounts() async throws -> [MailAccount] {
        let payload: AccountEnvelope = try await request(path: "/api/accounts")
        return payload.items
    }

    func createAccount(_ req: CreateAccountRequest) async throws -> MailAccount {
        try await request(path: "/api/accounts", method: "POST", body: req)
    }

    func updateAccount(accountID: Int, request req: AccountPatchRequest) async throws -> MailAccount {
        try await request(path: "/api/accounts/\(accountID)", method: "PATCH", body: req)
    }

    func deleteAccount(accountID: Int) async throws {
        struct DeleteResponse: Decodable { let ok: Bool }
        _ = try await request(path: "/api/accounts/\(accountID)", method: "DELETE") as DeleteResponse
    }

    func syncAccount(accountID: Int, folder: String = "INBOX", limit: Int = 200) async throws -> SyncResponse {
        try await request(path: "/api/accounts/\(accountID)/sync", queryItems: [
            URLQueryItem(name: "folder", value: folder),
            URLQueryItem(name: "limit", value: "\(limit)")
        ], method: "POST")
    }

    func sendEmail(accountID: Int, request req: SendEmailRequest) async throws -> SendEmailResponse {
        try await request(path: "/api/accounts/\(accountID)/send", method: "POST", body: req)
    }

    func attachmentDownloadURL(emailID: Int, filename: String) -> URL? {
        var comps = URLComponents(url: baseURL, resolvingAgainstBaseURL: false)
        comps?.path = "/api/export/email/\(emailID)/attachment/\(filename.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? filename)"
        return comps?.url
    }

    private func request<T: Decodable>(path: String, queryItems: [URLQueryItem] = [], method: String = "GET") async throws -> T {
        try await request(path: path, queryItems: queryItems, method: method, bodyData: nil)
    }

    private func request<T: Decodable, B: Encodable>(path: String, queryItems: [URLQueryItem] = [], method: String, body: B) async throws -> T {
        let bodyData = try JSONEncoder().encode(body)
        return try await request(path: path, queryItems: queryItems, method: method, bodyData: bodyData)
    }

    private func request<T: Decodable>(path: String, queryItems: [URLQueryItem], method: String, bodyData: Data?) async throws -> T {
        guard var components = URLComponents(url: baseURL, resolvingAgainstBaseURL: false) else {
            throw APIClientError.invalidURL
        }

        components.path = path
        if !queryItems.isEmpty {
            components.queryItems = queryItems
        }

        guard let url = components.url else {
            throw APIClientError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = bodyData

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIClientError.server("Invalid server response.")
        }

        let decoder = JSONDecoder()

        guard (200 ..< 300).contains(httpResponse.statusCode) else {
            if let serverError = try? decoder.decode(APIError.self, from: data),
               let message = serverError.detail,
               !message.isEmpty {
                throw APIClientError.server(message)
            }
            throw APIClientError.server("Server error (\(httpResponse.statusCode)).")
        }

        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            // Fallback for malformed UTF-8/control bytes from legacy email bodies.
            let lossy = String(decoding: data, as: UTF8.self)
            if let normalized = lossy.data(using: .utf8),
               let decoded = try? decoder.decode(T.self, from: normalized) {
                return decoded
            }
            throw APIClientError.decoding("\(path): \(error.localizedDescription)")
        }
    }
}

private struct WrappedAnalytics<T: Decodable>: Decodable {
    let data: T
}
