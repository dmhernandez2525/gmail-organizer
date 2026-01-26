import Foundation

// MARK: - Processing Results Models

struct ProcessingResults: Codable {
    let accountEmail: String
    let processedAt: Date
    let totalEmails: Int
    let dateRange: DateRange?
    let topSenders: [SenderStats]
    let existingLabels: [String]
    let suggestedCategories: [CategorySuggestion]
    let actionsApplied: [AppliedAction]
    let summary: String

    struct DateRange: Codable {
        let earliest: String
        let latest: String
    }

    struct SenderStats: Codable {
        let sender: String
        let count: Int
        let sampleSubjects: [String]
    }

    struct CategorySuggestion: Codable {
        let category: String
        let emailIds: [String]
        let count: Int
        let description: String
    }

    struct AppliedAction: Codable {
        let action: String  // "label_created", "label_applied", "email_archived", etc.
        let target: String  // label name or email ID
        let count: Int
        let timestamp: Date
    }
}

// MARK: - Results Manager

class ResultsManager {
    static let shared = ResultsManager()

    private let resultsDir: String

    init() {
        resultsDir = Paths.projectRoot + "/.processing-results"
        try? FileManager.default.createDirectory(atPath: resultsDir, withIntermediateDirectories: true)
    }

    // MARK: - Save Results

    func saveResults(_ results: ProcessingResults) {
        let filename = sanitizeFilename(results.accountEmail) + "_\(ISO8601DateFormatter().string(from: results.processedAt)).json"
        let path = resultsDir + "/" + filename

        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]

        if let data = try? encoder.encode(results) {
            try? data.write(to: URL(fileURLWithPath: path))
        }

        // Also update the latest results for this account
        let latestPath = resultsDir + "/" + sanitizeFilename(results.accountEmail) + "_latest.json"
        if let data = try? encoder.encode(results) {
            try? data.write(to: URL(fileURLWithPath: latestPath))
        }
    }

    // MARK: - Load Results

    func getLatestResults(for email: String) -> ProcessingResults? {
        let path = resultsDir + "/" + sanitizeFilename(email) + "_latest.json"
        guard let data = FileManager.default.contents(atPath: path) else { return nil }

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try? decoder.decode(ProcessingResults.self, from: data)
    }

    func getAllResults(for email: String) -> [ProcessingResults] {
        let fm = FileManager.default
        guard let files = try? fm.contentsOfDirectory(atPath: resultsDir) else { return [] }

        let prefix = sanitizeFilename(email)
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        return files
            .filter { $0.hasPrefix(prefix) && !$0.hasSuffix("_latest.json") }
            .compactMap { filename -> ProcessingResults? in
                let path = resultsDir + "/" + filename
                guard let data = fm.contents(atPath: path) else { return nil }
                return try? decoder.decode(ProcessingResults.self, from: data)
            }
            .sorted { $0.processedAt > $1.processedAt }
    }

    func getAllAccountResults() -> [String: ProcessingResults] {
        let fm = FileManager.default
        guard let files = try? fm.contentsOfDirectory(atPath: resultsDir) else { return [:] }

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        var results: [String: ProcessingResults] = [:]

        for file in files where file.hasSuffix("_latest.json") {
            let path = resultsDir + "/" + file
            guard let data = fm.contents(atPath: path),
                  let result = try? decoder.decode(ProcessingResults.self, from: data) else { continue }
            results[result.accountEmail] = result
        }

        return results
    }

    // MARK: - Helpers

    private func sanitizeFilename(_ email: String) -> String {
        return email
            .replacingOccurrences(of: "@", with: "_at_")
            .replacingOccurrences(of: ".", with: "_")
    }
}

// MARK: - Label Statistics

struct LabelStatistics: Codable {
    let labelName: String
    let emailCount: Int
    let newestEmail: String?
    let oldestEmail: String?
}

// MARK: - Account Statistics

struct AccountStatistics: Codable {
    let email: String
    let totalEmails: Int
    let unreadCount: Int
    let labelStats: [LabelStatistics]
    let topSenders: [ProcessingResults.SenderStats]
    let lastUpdated: Date
}
