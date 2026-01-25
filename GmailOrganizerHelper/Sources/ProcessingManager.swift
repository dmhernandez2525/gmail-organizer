import Foundation

// MARK: - Account Info

struct AccountInfo {
    let name: String
    let email: String
    let emailCount: Int
    let lastSyncTime: String?
}

// MARK: - Processing State

enum ProcessingState {
    case idle
    case processing(accountName: String)
    case complete
    case error(message: String)
}

// MARK: - Processing Manager

class ProcessingManager {
    static let shared = ProcessingManager()

    var state: ProcessingState = .idle
    var onStateChanged: ((ProcessingState) -> Void)?

    // MARK: - Account Discovery

    func getAvailableAccounts() -> [AccountInfo] {
        var accounts: [AccountInfo] = []

        let syncStateDir = Paths.syncStateDir
        let fileManager = FileManager.default

        // Check if directory exists
        var isDir: ObjCBool = false
        guard fileManager.fileExists(atPath: syncStateDir, isDirectory: &isDir), isDir.boolValue else {
            return accounts
        }

        guard let files = try? fileManager.contentsOfDirectory(atPath: syncStateDir) else {
            return accounts
        }
        print("DEBUG: Found \(files.count) files in sync state dir")

        for file in files where file.hasPrefix("sync_state_") && file.hasSuffix(".json") {
            let path = syncStateDir + "/" + file

            // Extract account name from filename
            // sync_state_user_at_gmail_com.json -> user_at_gmail_com
            let nameComponent = file
                .replacingOccurrences(of: "sync_state_", with: "")
                .replacingOccurrences(of: ".json", with: "")

            // Convert back to email
            let email = nameComponent
                .replacingOccurrences(of: "_at_", with: "@")
                .replacingOccurrences(of: "_", with: ".")

            // Use first part of email as account name
            let accountName = email.components(separatedBy: "@").first ?? nameComponent

            // Get file size to estimate email count (files are ~2KB per email)
            var emailCount = 0
            var lastSync: String? = nil

            if let attrs = try? fileManager.attributesOfItem(atPath: path),
               let fileSize = attrs[.size] as? Int {
                // Rough estimate: ~2KB per email in the JSON
                emailCount = fileSize / 2000
            }

            // Read just the first 1KB to get metadata (last_sync_time, total_synced)
            if let handle = FileHandle(forReadingAtPath: path) {
                let headerData = handle.readData(ofLength: 2000)
                handle.closeFile()

                if let headerStr = String(data: headerData, encoding: .utf8) {
                    // Parse last_sync_time
                    if let range = headerStr.range(of: "\"last_sync_time\":\\s*\"([^\"]+)\"", options: .regularExpression) {
                        let match = headerStr[range]
                        if let valueRange = match.range(of: "\"[^\"]+\"$", options: .regularExpression) {
                            lastSync = String(match[valueRange]).trimmingCharacters(in: CharacterSet(charactersIn: "\""))
                        }
                    }

                    // Parse total_synced for accurate count
                    if let range = headerStr.range(of: "\"total_synced\":\\s*(\\d+)", options: .regularExpression) {
                        let match = headerStr[range]
                        if let numRange = match.range(of: "\\d+", options: .regularExpression) {
                            emailCount = Int(match[numRange]) ?? emailCount
                        }
                    }
                }
            }

            accounts.append(AccountInfo(
                name: accountName,
                email: email,
                emailCount: emailCount,
                lastSyncTime: lastSync
            ))
        }

        return accounts.sorted { $0.emailCount > $1.emailCount }
    }

    // MARK: - Debug

    func debugPaths() -> String {
        let fm = FileManager.default
        var info = "Project Root: \(Paths.projectRoot)\n"
        info += "Sync State Dir: \(Paths.syncStateDir)\n"
        info += "Directory exists: \(fm.fileExists(atPath: Paths.syncStateDir))\n"

        if let files = try? fm.contentsOfDirectory(atPath: Paths.syncStateDir) {
            info += "Files found: \(files.count)\n"
            for file in files.prefix(5) {
                info += "  - \(file)\n"
            }
        } else {
            info += "Could not list directory\n"
        }

        return info
    }

    // MARK: - Processing with Claude Code

    func processWithClaudeCode(accountName: String, analysisType: AnalysisType = .fullAnalysis) {
        processWithAnalysisType(accountName: accountName, analysisType: analysisType)
    }

    func processAllAccounts() {
        let accounts = getAvailableAccounts()

        if accounts.isEmpty {
            showNotification(title: "No Accounts", body: "No synced accounts to process")
            return
        }

        // For now, just process the first account
        // TODO: Could add batch processing
        if let first = accounts.first {
            processWithClaudeCode(accountName: first.name)
        }
    }

    // MARK: - Prompt Generation

    private func generateProcessingPrompt(for account: AccountInfo, analysisType: AnalysisType = .fullAnalysis) -> String {
        let builder = PromptBuilder(account: account)
        return builder.buildPrompt(type: analysisType)
    }

    // MARK: - Analysis Type Processing

    func processWithAnalysisType(accountName: String, analysisType: AnalysisType) {
        let accounts = getAvailableAccounts()

        guard let account = accounts.first(where: { $0.name == accountName }) else {
            showNotification(title: "Account Not Found", body: "No synced data for '\(accountName)'")
            return
        }

        state = .processing(accountName: accountName)
        onStateChanged?(state)

        // Create the processing prompt based on analysis type
        let prompt = generateProcessingPrompt(for: account, analysisType: analysisType)

        // Create processing directory and save prompt
        let processingDir = Paths.processingDir
        try? FileManager.default.createDirectory(atPath: processingDir, withIntermediateDirectories: true)

        // Build prompt path: accountname_analysis_type.md
        let analysisTypeSuffix = analysisType.rawValue.lowercased().replacingOccurrences(of: " ", with: "_")
        let promptPath = Paths.processingDir + "/\(accountName)_\(analysisTypeSuffix).md"
        _ = writeFile(prompt, to: promptPath)

        // Launch Claude Code with the prompt file
        launchClaudeCodeWithPromptFile(at: Paths.projectRoot, promptFile: promptPath)

        showNotification(
            title: "Email Analysis Started",
            body: "\(analysisType.rawValue) for \(account.emailCount.formatted()) emails in \(accountName)"
        )
    }
}

// MARK: - Number Formatting

extension Int {
    func formatted() -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        return formatter.string(from: NSNumber(value: self)) ?? String(self)
    }
}
