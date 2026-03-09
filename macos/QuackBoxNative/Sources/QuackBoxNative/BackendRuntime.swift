import Foundation

actor BackendRuntime {
    static let shared = BackendRuntime()

    private var process: Process?
    private var triedStart = false

    func ensureRunning(baseURL: URL) async throws {
        if await isReachable(baseURL: baseURL) {
            return
        }

        if !triedStart {
            triedStart = true
            try startLocalBackend()
        }

        let deadline = Date().addingTimeInterval(45)
        while Date() < deadline {
            if await isReachable(baseURL: baseURL) {
                return
            }
            try await Task.sleep(nanoseconds: 300_000_000)
        }
        throw NSError(
            domain: "QuackBoxNative",
            code: 9001,
            userInfo: [NSLocalizedDescriptionKey: "Could not start local backend automatically. Ensure Python dependencies are installed in backend/requirements.txt."]
        )
    }

    private func startLocalBackend() throws {
        guard let backendDir = backendDirectory() else {
            throw NSError(
                domain: "QuackBoxNative",
                code: 9002,
                userInfo: [NSLocalizedDescriptionKey: "Could not locate backend directory for self-contained runtime."]
            )
        }

        let python = try ensureBackendPython(in: backendDir)

        let p = Process()
        p.executableURL = python
        p.arguments = ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]
        p.currentDirectoryURL = backendDir
        p.environment = mergedEnvironment(["PYTHONUNBUFFERED": "1"])

        let out = Pipe()
        p.standardOutput = out
        p.standardError = out

        try p.run()
        process = p
    }

    private func ensureBackendPython(in backendDir: URL) throws -> URL {
        if let python = existingVenvPython(in: backendDir) {
            if try hasUvicorn(python: python, cwd: backendDir) {
                return python
            }
            try installRequirements(python: python, backendDir: backendDir)
            return python
        }

        try runCommand(
            executable: URL(fileURLWithPath: "/usr/bin/env"),
            arguments: ["python3", "-m", "venv", ".venv"],
            cwd: backendDir,
            errorCode: 9003,
            userMessage: "Could not create Python virtual environment in backend/.venv."
        )

        guard let python = existingVenvPython(in: backendDir) else {
            throw NSError(
                domain: "QuackBoxNative",
                code: 9004,
                userInfo: [NSLocalizedDescriptionKey: "Python virtual environment was created but Python executable is missing."]
            )
        }

        try installRequirements(python: python, backendDir: backendDir)
        return python
    }

    private func existingVenvPython(in backendDir: URL) -> URL? {
        let fileManager = FileManager.default
        let candidates = [".venv/bin/python3", ".venv/bin/python"]
        for relative in candidates {
            let path = backendDir.appendingPathComponent(relative)
            if fileManager.fileExists(atPath: path.path) {
                return path
            }
        }
        return nil
    }

    private func hasUvicorn(python: URL, cwd: URL) throws -> Bool {
        let result = try runCommand(
            executable: python,
            arguments: ["-c", "import uvicorn"],
            cwd: cwd,
            errorCode: 9005,
            userMessage: "Python dependency check failed.",
            allowFailure: true
        )
        return result.terminationStatus == 0
    }

    private func installRequirements(python: URL, backendDir: URL) throws {
        try runCommand(
            executable: python,
            arguments: ["-m", "pip", "install", "-r", "requirements.txt"],
            cwd: backendDir,
            errorCode: 9006,
            userMessage: "Could not install backend Python dependencies from requirements.txt."
        )
    }

    @discardableResult
    private func runCommand(
        executable: URL,
        arguments: [String],
        cwd: URL,
        errorCode: Int,
        userMessage: String,
        allowFailure: Bool = false
    ) throws -> Process {
        let proc = Process()
        proc.executableURL = executable
        proc.arguments = arguments
        proc.currentDirectoryURL = cwd
        proc.environment = mergedEnvironment(["PYTHONUNBUFFERED": "1"])

        let output = Pipe()
        proc.standardOutput = output
        proc.standardError = output

        try proc.run()
        proc.waitUntilExit()

        if !allowFailure && proc.terminationStatus != 0 {
            let data = output.fileHandleForReading.readDataToEndOfFile()
            let text = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines)
            let detail = (text?.isEmpty == false) ? " \(text!)" : ""
            throw NSError(
                domain: "QuackBoxNative",
                code: errorCode,
                userInfo: [NSLocalizedDescriptionKey: "\(userMessage)\(detail)"]
            )
        }

        return proc
    }

    private func mergedEnvironment(_ extra: [String: String]) -> [String: String] {
        var env = ProcessInfo.processInfo.environment
        for (k, v) in extra {
            env[k] = v
        }
        return env
    }

    private func backendDirectory() -> URL? {
        // /repo/macos/QuackBoxNative/Sources/QuackBoxNative/BackendRuntime.swift -> /repo/backend
        let src = URL(fileURLWithPath: #filePath)
        let repoRoot = src
            .deletingLastPathComponent() // QuackBoxNative
            .deletingLastPathComponent() // Sources
            .deletingLastPathComponent() // QuackBoxNative (package dir)
            .deletingLastPathComponent() // macos
            .deletingLastPathComponent() // repo root
        let backend = repoRoot.appendingPathComponent("backend")
        return FileManager.default.fileExists(atPath: backend.path) ? backend : nil
    }

    private func isReachable(baseURL: URL) async -> Bool {
        var comps = URLComponents(url: baseURL, resolvingAgainstBaseURL: false)
        comps?.path = "/api/settings"
        guard let url = comps?.url else { return false }

        var req = URLRequest(url: url)
        req.timeoutInterval = 1.2

        do {
            let (_, response) = try await URLSession.shared.data(for: req)
            guard let http = response as? HTTPURLResponse else { return false }
            return (200 ..< 500).contains(http.statusCode)
        } catch {
            return false
        }
    }
}
