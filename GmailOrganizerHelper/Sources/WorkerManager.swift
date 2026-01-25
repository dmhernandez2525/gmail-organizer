import Foundation

// MARK: - Worker Task Definition

struct WorkerTask {
    let id: String
    let name: String
    let phase: Int
    let model: String  // "haiku", "sonnet", "opus"
    let promptTemplate: String
    let dependencies: [String]  // Worker IDs that must complete first
    let outputKey: String  // Key in the results JSON

    // For chunk-based workers
    var chunkStart: Int?
    var chunkEnd: Int?
}

// MARK: - Processing Job

class ProcessingJob {
    let id: String
    let accountEmail: String
    let accountName: String
    let syncStatePath: String
    let resultsDir: String
    let totalEmails: Int

    var workers: [WorkerInfo] = []
    var results: [String: Any] = [:]
    var startTime: Date?
    var endTime: Date?

    var onWorkerStatusChanged: ((WorkerInfo) -> Void)?
    var onJobComplete: ((ProcessingJob) -> Void)?

    init(accountEmail: String, accountName: String, syncStatePath: String, resultsDir: String, totalEmails: Int) {
        self.id = UUID().uuidString
        self.accountEmail = accountEmail
        self.accountName = accountName
        self.syncStatePath = syncStatePath
        self.resultsDir = resultsDir
        self.totalEmails = totalEmails
    }

    var isComplete: Bool {
        return workers.allSatisfy { worker in
            if case .complete = worker.status { return true }
            if case .error = worker.status { return true }
            return false
        }
    }

    var completedCount: Int {
        return workers.filter { worker in
            if case .complete = worker.status { return true }
            return false
        }.count
    }

    var errorCount: Int {
        return workers.filter { worker in
            if case .error = worker.status { return true }
            return false
        }.count
    }
}

// MARK: - Worker Manager

class WorkerManager {
    static let shared = WorkerManager()

    private var activeJobs: [ProcessingJob] = []
    private let maxConcurrentWorkers: Int

    // Callbacks for UI updates
    var onJobCreated: ((ProcessingJob) -> Void)?
    var onWorkerStarted: ((ProcessingJob, WorkerInfo) -> Void)?
    var onWorkerCompleted: ((ProcessingJob, WorkerInfo) -> Void)?
    var onJobCompleted: ((ProcessingJob) -> Void)?

    init() {
        // Determine max workers based on CPU cores (leave 2 cores free)
        let cores = ProcessInfo.processInfo.activeProcessorCount
        self.maxConcurrentWorkers = max(2, cores - 2)
        print("WorkerManager initialized with max \(maxConcurrentWorkers) concurrent workers")
    }

    // MARK: - Job Creation

    func createJob(for account: AccountInfo) -> ProcessingJob {
        let safeEmail = account.email
            .replacingOccurrences(of: "@", with: "_at_")
            .replacingOccurrences(of: ".", with: "_")

        let syncStatePath = Paths.syncStateDir + "/sync_state_\(safeEmail).json"
        let resultsDir = Paths.projectRoot + "/.processing-results/\(safeEmail)"

        // Create results directory
        try? FileManager.default.createDirectory(atPath: resultsDir, withIntermediateDirectories: true)

        let job = ProcessingJob(
            accountEmail: account.email,
            accountName: account.name,
            syncStatePath: syncStatePath,
            resultsDir: resultsDir,
            totalEmails: account.emailCount
        )

        // Create worker tasks based on email count
        job.workers = createWorkers(for: job)

        activeJobs.append(job)
        onJobCreated?(job)

        return job
    }

    private func createWorkers(for job: ProcessingJob) -> [WorkerInfo] {
        var workers: [WorkerInfo] = []
        let promptDir = Paths.processingDir + "/\(job.accountName)"

        // Create prompt directory
        try? FileManager.default.createDirectory(atPath: promptDir, withIntermediateDirectories: true)

        // Phase 1: Data Indexing (Haiku) - Creates index for other workers
        workers.append(WorkerInfo(
            id: "indexer",
            name: "Data Indexer",
            phase: 1,
            description: "Extract and index email metadata",
            model: "haiku",
            promptFile: promptDir + "/01_indexer.md"
        ))

        // Phase 2: Thread Analysis (Haiku workers based on email count)
        let threadWorkerCount = min(4, max(1, job.totalEmails / 10000))
        for i in 0..<threadWorkerCount {
            workers.append(WorkerInfo(
                id: "thread_\(i)",
                name: "Thread Analyzer \(i + 1)",
                phase: 2,
                description: "Map conversations and thread status",
                model: "haiku",
                promptFile: promptDir + "/02_thread_\(i).md"
            ))
        }

        // Phase 3: Sender Analysis (Haiku)
        workers.append(WorkerInfo(
            id: "sender",
            name: "Sender Analyzer",
            phase: 3,
            description: "Analyze sender patterns and reputation",
            model: "haiku",
            promptFile: promptDir + "/03_sender.md"
        ))

        // Phase 4: Temporal Analysis (Haiku)
        workers.append(WorkerInfo(
            id: "temporal",
            name: "Temporal Analyzer",
            phase: 4,
            description: "Detect time-based patterns",
            model: "haiku",
            promptFile: promptDir + "/04_temporal.md"
        ))

        // Phase 5: Content Analysis (Haiku - sample-based for large inboxes)
        workers.append(WorkerInfo(
            id: "content",
            name: "Content Analyzer",
            phase: 5,
            description: "Extract topics and action items",
            model: "haiku",
            promptFile: promptDir + "/05_content.md"
        ))

        // Phase 6: Anomaly Detection (Haiku)
        workers.append(WorkerInfo(
            id: "anomaly",
            name: "Anomaly Detector",
            phase: 6,
            description: "Find conflicts and issues",
            model: "haiku",
            promptFile: promptDir + "/06_anomaly.md"
        ))

        // Phase 7: Aggregator & Categorizer (Sonnet - needs reasoning)
        workers.append(WorkerInfo(
            id: "categorizer",
            name: "Smart Categorizer",
            phase: 7,
            description: "Aggregate results and create categories",
            model: "sonnet",
            promptFile: promptDir + "/07_categorizer.md"
        ))

        // Phase 8: Label Executor (Sonnet - makes API calls)
        workers.append(WorkerInfo(
            id: "executor",
            name: "Label Executor",
            phase: 8,
            description: "Apply labels via Gmail API",
            model: "sonnet",
            promptFile: promptDir + "/08_executor.md"
        ))

        // Phase 9: Summary Generator (Sonnet)
        workers.append(WorkerInfo(
            id: "summary",
            name: "Summary Generator",
            phase: 9,
            description: "Create executive summary",
            model: "sonnet",
            promptFile: promptDir + "/09_summary.md"
        ))

        return workers
    }

    // MARK: - Prompt Generation

    func generatePrompts(for job: ProcessingJob) {
        for worker in job.workers {
            let prompt = generatePrompt(for: worker, job: job)
            _ = writeFile(prompt, to: worker.promptFile)
        }
    }

    private func generatePrompt(for worker: WorkerInfo, job: ProcessingJob) -> String {
        let header = """
        ################################################################################
        # GMAIL ORGANIZER - \(worker.name.uppercased())
        # Phase \(worker.phase): \(worker.description)
        ################################################################################

        ACCOUNT: \(job.accountEmail)
        TOTAL EMAILS: \(job.totalEmails)
        SYNC STATE: \(job.syncStatePath)
        OUTPUT DIR: \(job.resultsDir)

        """

        switch worker.id {
        case "indexer":
            return header + generateIndexerPrompt(job: job)
        case let id where id.hasPrefix("thread_"):
            let index = Int(id.replacingOccurrences(of: "thread_", with: "")) ?? 0
            return header + generateThreadPrompt(job: job, workerIndex: index)
        case "sender":
            return header + generateSenderPrompt(job: job)
        case "temporal":
            return header + generateTemporalPrompt(job: job)
        case "content":
            return header + generateContentPrompt(job: job)
        case "anomaly":
            return header + generateAnomalyPrompt(job: job)
        case "categorizer":
            return header + generateCategorizerPrompt(job: job)
        case "executor":
            return header + generateExecutorPrompt(job: job)
        case "summary":
            return header + generateSummaryPrompt(job: job)
        default:
            return header + "Unknown worker type"
        }
    }

    // MARK: - Individual Prompts

    private func generateIndexerPrompt(job: ProcessingJob) -> String {
        return """
        ================================================================================
        TASK: Create an index of all emails for parallel processing
        ================================================================================

        1. Read the sync state JSON file
        2. Extract key fields from each email:
           - email_id, thread_id, sender, date, subject (first 50 chars), labels

        3. Create index files:
           a) \(job.resultsDir)/index_by_thread.json - Emails grouped by thread_id
           b) \(job.resultsDir)/index_by_sender.json - Emails grouped by sender domain
           c) \(job.resultsDir)/index_by_date.json - Emails grouped by month
           d) \(job.resultsDir)/email_summary.json - Basic stats

        4. Save email_summary.json with:
        ```json
        {
            "totalEmails": N,
            "uniqueThreads": N,
            "uniqueSenders": N,
            "dateRange": {"start": "ISO", "end": "ISO"},
            "topSenderDomains": [{"domain": "x", "count": N}],
            "indexCreatedAt": "ISO timestamp"
        }
        ```

        Use this Python code to read the large JSON efficiently:
        ```python
        import json
        import ijson  # For streaming large JSON - pip install ijson

        # For files < 500MB, direct load is fine
        with open('\(job.syncStatePath)', 'r') as f:
            data = json.load(f)
        emails = data.get('emails', [])
        ```

        OUTPUT: Confirm all index files created with counts.
        """
    }

    private func generateThreadPrompt(job: ProcessingJob, workerIndex: Int) -> String {
        return """
        ================================================================================
        TASK: Analyze email threads (Worker \(workerIndex + 1))
        ================================================================================

        PREREQUISITE: Wait for \(job.resultsDir)/index_by_thread.json to exist

        1. Load the thread index
        2. Process threads assigned to this worker (based on thread_id hash % worker_count)
        3. For each thread:
           - Count emails in thread
           - Identify participants
           - Determine thread status:
             * active (activity in last 7 days)
             * stale (no activity > 30 days)
             * needs_response (last email TO account, unanswered)
             * awaiting_response (last email FROM account)
           - Calculate response times

        4. Save results to: \(job.resultsDir)/threads_worker_\(workerIndex).json
        ```json
        {
            "workerId": \(workerIndex),
            "threadsAnalyzed": N,
            "threads": {
                "thread_id": {
                    "emailCount": N,
                    "participants": ["email1", "email2"],
                    "status": "needs_response",
                    "lastActivity": "ISO date",
                    "avgResponseTime": "X hours"
                }
            },
            "needsResponse": ["thread_id1", "thread_id2"],
            "longestThreads": [{"id": "x", "count": N}]
        }
        ```

        OUTPUT: Summary of threads analyzed and key findings.
        """
    }

    private func generateSenderPrompt(job: ProcessingJob) -> String {
        return """
        ================================================================================
        TASK: Analyze sender patterns and build reputation scores
        ================================================================================

        PREREQUISITE: Wait for \(job.resultsDir)/index_by_sender.json to exist

        1. Load the sender index
        2. For each unique sender:
           - Total email count
           - First and last contact dates
           - Frequency (emails per month)
           - Classification: human, automated, newsletter, transactional
           - Relationship score (0-100 based on frequency, recency, bidirectional)

        3. Group by domain to identify organizational relationships

        4. Save results to: \(job.resultsDir)/sender_analysis.json
        ```json
        {
            "totalSenders": N,
            "senders": {
                "email@domain.com": {
                    "displayName": "Name",
                    "domain": "domain.com",
                    "totalEmails": N,
                    "firstContact": "ISO",
                    "lastContact": "ISO",
                    "classification": "human",
                    "relationshipScore": 85
                }
            },
            "domains": {
                "domain.com": {"count": N, "type": "work"}
            },
            "vipCandidates": ["email1", "email2"],
            "unsubscribeCandidates": ["email3"]
        }
        ```

        OUTPUT: Top 10 senders, VIP candidates, unsubscribe candidates.
        """
    }

    private func generateTemporalPrompt(job: ProcessingJob) -> String {
        return """
        ================================================================================
        TASK: Analyze time-based patterns
        ================================================================================

        PREREQUISITE: Wait for \(job.resultsDir)/index_by_date.json to exist

        1. Load the date index
        2. Calculate:
           - Volume by day of week
           - Volume by hour of day
           - Monthly trend (last 12 months)
           - Identify spikes (>2x average)

        3. Save results to: \(job.resultsDir)/temporal_analysis.json
        ```json
        {
            "volumeByDayOfWeek": {"Mon": N, "Tue": N, ...},
            "volumeByHour": {"0": N, "1": N, ...},
            "monthlyTrend": [{"month": "2024-01", "count": N}],
            "peakDays": ["Mon", "Wed"],
            "peakHours": [9, 14],
            "spikes": [{"date": "2024-01-15", "count": N, "reason": "unknown"}],
            "trend": "increasing"  // or "decreasing", "stable"
        }
        ```

        OUTPUT: Summary of peak times and trends.
        """
    }

    private func generateContentPrompt(job: ProcessingJob) -> String {
        let sampleSize = min(500, job.totalEmails)
        return """
        ================================================================================
        TASK: Analyze email content patterns (sample-based)
        ================================================================================

        1. Load sync state and sample \(sampleSize) emails:
           - 50% most recent
           - 30% random
           - 20% from top senders

        2. Analyze subjects for:
           - Common keywords
           - Topic clusters
           - Urgency indicators ([URGENT], ASAP, etc.)
           - Questions (subjects ending with ?)

        3. Extract action items from snippets:
           - Requests ("Can you...", "Please...")
           - Deadlines (dates, "by EOD", etc.)
           - Questions needing answers

        4. Save results to: \(job.resultsDir)/content_analysis.json
        ```json
        {
            "sampleSize": \(sampleSize),
            "topics": [{"topic": "billing", "count": N, "examples": ["..."]}],
            "urgentEmails": [{"id": "x", "subject": "...", "reason": "contains URGENT"}],
            "actionItems": [{"id": "x", "type": "request", "text": "...", "deadline": null}],
            "unansweredQuestions": [{"id": "x", "subject": "...?"}],
            "keywordFrequency": {"invoice": N, "meeting": N}
        }
        ```

        OUTPUT: Top topics, urgent items, and action items found.
        """
    }

    private func generateAnomalyPrompt(job: ProcessingJob) -> String {
        return """
        ================================================================================
        TASK: Detect anomalies and potential issues
        ================================================================================

        PREREQUISITES: Wait for these files to exist:
        - \(job.resultsDir)/threads_worker_*.json
        - \(job.resultsDir)/sender_analysis.json
        - \(job.resultsDir)/temporal_analysis.json

        1. Load all analysis results
        2. Detect:
           - Dropped conversations (active thread suddenly stopped)
           - Unanswered important emails (from high-score senders)
           - Volume anomalies (sudden spikes/drops)
           - Potential phishing (unknown sender + urgent language)
           - Duplicate threads (same subject, different thread IDs)

        3. Save results to: \(job.resultsDir)/anomaly_report.json
        ```json
        {
            "critical": [{"type": "unanswered_important", "details": {...}}],
            "warnings": [{"type": "dropped_conversation", "details": {...}}],
            "info": [{"type": "volume_spike", "details": {...}}],
            "potentialPhishing": [{"id": "x", "reason": "..."}]
        }
        ```

        OUTPUT: List of critical issues and warnings.
        """
    }

    private func generateCategorizerPrompt(job: ProcessingJob) -> String {
        return """
        ================================================================================
        TASK: Aggregate results and create smart categorization
        ================================================================================

        PREREQUISITES: ALL previous worker files must exist in \(job.resultsDir)/

        1. Load all analysis files:
           - email_summary.json
           - threads_worker_*.json (merge all)
           - sender_analysis.json
           - temporal_analysis.json
           - content_analysis.json
           - anomaly_report.json

        2. Create unified categorization:
           - Primary category for each email (work, personal, finance, etc.)
           - Secondary labels (action_required, vip, etc.)
           - Priority score (1-5)

        3. Create label mapping:
        ```json
        {
            "categorization": {
                "email_id": {
                    "primary": "work",
                    "secondary": ["action_required", "from_vip"],
                    "priority": 4,
                    "reasoning": "From VIP sender, contains deadline"
                }
            },
            "labelStructure": [
                "Organized/Work",
                "Organized/Personal",
                "Organized/Finance",
                ...
            ],
            "summary": {
                "byCategory": {"work": N, "personal": N},
                "byPriority": {"high": N, "medium": N, "low": N}
            }
        }
        ```

        4. Save to: \(job.resultsDir)/categorization.json

        OUTPUT: Category distribution and label structure.
        """
    }

    private func generateExecutorPrompt(job: ProcessingJob) -> String {
        return """
        ================================================================================
        TASK: Execute Gmail label operations
        ================================================================================

        PREREQUISITE: \(job.resultsDir)/categorization.json must exist

        1. Load categorization results
        2. Use Gmail API to:
           a) Create required labels (if they don't exist)
           b) Apply labels to emails in batches of 25

        ```python
        import sys
        sys.path.insert(0, '\(Paths.projectRoot)')
        from gmail_organizer.operations import GmailOperations

        ops = GmailOperations(account_email='\(job.accountEmail)')

        # Create labels
        for label in label_structure:
            try:
                ops.create_label(label)
                print(f"Created label: {label}")
            except Exception as e:
                print(f"Label exists or error: {e}")

        # Apply labels in batches
        for i, (email_id, cats) in enumerate(categorization.items()):
            for label in cats['labels']:
                ops.apply_label_to_email(email_id, label)
            if i % 25 == 0:
                print(f"Progress: {i}/{total}")
                time.sleep(1)  # Rate limit
        ```

        3. Save execution log to: \(job.resultsDir)/execution_log.json
        ```json
        {
            "labelsCreated": ["label1", "label2"],
            "emailsLabeled": N,
            "errors": [{"email_id": "x", "error": "..."}],
            "executedAt": "ISO timestamp"
        }
        ```

        OUTPUT: Execution summary with success/error counts.
        """
    }

    private func generateSummaryPrompt(job: ProcessingJob) -> String {
        return """
        ================================================================================
        TASK: Generate executive summary
        ================================================================================

        PREREQUISITES: ALL files in \(job.resultsDir)/ must exist

        1. Load all results files
        2. Generate comprehensive summary

        3. Save final report to: \(job.resultsDir)/final_report.json
        ```json
        {
            "accountEmail": "\(job.accountEmail)",
            "processedAt": "ISO timestamp",
            "summary": {
                "totalEmails": N,
                "totalThreads": N,
                "uniqueSenders": N,
                "dateRange": {...}
            },
            "keyFindings": [
                "Finding 1...",
                "Finding 2..."
            ],
            "attentionNeeded": {
                "awaitingResponse": N,
                "actionItems": N,
                "criticalIssues": N
            },
            "inboxHealthScore": {
                "overall": 75,
                "organization": 20,
                "responseRate": 18,
                "actionCompletion": 22,
                "communicationBalance": 15
            },
            "recommendations": [
                "Recommendation 1...",
                "Recommendation 2..."
            ],
            "categorization": {...},
            "executionResults": {...}
        }
        ```

        4. Print executive summary to terminal:
        ```
        ╔══════════════════════════════════════════════════════════════╗
        ║           EMAIL ANALYSIS COMPLETE                            ║
        ╠══════════════════════════════════════════════════════════════╣
        ║ Inbox Health Score: XX/100                                   ║
        ╚══════════════════════════════════════════════════════════════╝
        ```

        OUTPUT: Full executive summary displayed.
        """
    }

    // MARK: - Job Execution

    func startJob(_ job: ProcessingJob, terminalContainer: TabbedTerminalView) {
        job.startTime = Date()
        generatePrompts(for: job)

        // Start workers respecting dependencies
        startNextWorkers(job: job, terminalContainer: terminalContainer)
    }

    private func startNextWorkers(job: ProcessingJob, terminalContainer: TabbedTerminalView) {
        // Find workers that can start (pending, dependencies met)
        let runningCount = job.workers.filter {
            if case .running = $0.status { return true }
            return false
        }.count

        let availableSlots = maxConcurrentWorkers - runningCount

        if availableSlots <= 0 { return }

        // Phase 1 must complete before others
        let phase1Complete = job.workers.first(where: { $0.id == "indexer" }).map { worker in
            if case .complete = worker.status { return true }
            return false
        } ?? false

        var startedCount = 0
        for i in 0..<job.workers.count {
            if startedCount >= availableSlots { break }

            var worker = job.workers[i]
            guard case .pending = worker.status else { continue }

            // Check dependencies
            if worker.phase > 1 && !phase1Complete { continue }

            // Start this worker
            worker.status = .running
            worker.startTime = Date()
            job.workers[i] = worker

            let terminal = terminalContainer.addTerminal(
                id: worker.id,
                title: worker.name,
                colorIndex: worker.phase - 1
            )

            // Build command
            let claudePath = NSString(string: "~/.local/bin/claude").expandingTildeInPath
            let command = "'\(claudePath)' --model \(worker.model) -p \"Read \(worker.promptFile) and execute the task. Save results to the specified output file.\""

            terminal.onProcessComplete = { [weak self] exitCode in
                self?.handleWorkerComplete(job: job, workerId: worker.id, exitCode: exitCode, terminalContainer: terminalContainer)
            }

            terminal.runCommand(command, workingDirectory: Paths.projectRoot)
            onWorkerStarted?(job, worker)
            startedCount += 1
        }
    }

    private func handleWorkerComplete(job: ProcessingJob, workerId: String, exitCode: Int32, terminalContainer: TabbedTerminalView) {
        guard let index = job.workers.firstIndex(where: { $0.id == workerId }) else { return }

        var worker = job.workers[index]
        worker.endTime = Date()
        worker.status = exitCode == 0 ? .complete : .error("Exit code: \(exitCode)")
        job.workers[index] = worker

        onWorkerCompleted?(job, worker)

        // Check if job is complete
        if job.isComplete {
            job.endTime = Date()
            onJobCompleted?(job)
        } else {
            // Start more workers
            startNextWorkers(job: job, terminalContainer: terminalContainer)
        }
    }
}
