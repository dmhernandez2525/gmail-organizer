import Cocoa

// MARK: - Processing Panel Controller

/// A dedicated panel for parallel email processing with embedded terminals
class ProcessingPanelController: NSObject, NSWindowDelegate {
    private var window: NSPanel!
    private var terminalContainer: TabbedTerminalView!
    private var statusBar: NSView!
    private var progressView: NSView!

    private var currentJob: ProcessingJob?
    private var statusLabels: [String: NSTextField] = [:]

    // Track views for updates (since NSView.tag is read-only)
    private var subtitleLabel: NSTextField?
    private var statsLabel: NSTextField?
    private var workerRows: [NSView] = []
    private var workerIndicators: [NSView] = []
    private var workerNameLabels: [NSTextField] = []
    private var workerStatusLabels: [NSTextField] = []

    // Callbacks
    var onClose: (() -> Void)?

    override init() {
        super.init()
        setupWindow()
    }

    // MARK: - Window Setup

    private func setupWindow() {
        // Create a larger window for the processing view
        window = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: 1200, height: 800),
            styleMask: [.titled, .closable, .resizable, .miniaturizable],
            backing: .buffered,
            defer: false
        )
        window.title = "Email Processing"
        window.delegate = self
        window.isReleasedWhenClosed = false
        window.level = .normal
        window.backgroundColor = NSColor(white: 0.12, alpha: 1.0)
        window.minSize = NSSize(width: 900, height: 600)

        let mainView = NSView(frame: window.contentView!.bounds)
        mainView.wantsLayer = true
        mainView.layer?.backgroundColor = NSColor(white: 0.12, alpha: 1.0).cgColor
        window.contentView = mainView

        buildLayout(in: mainView)
    }

    private func buildLayout(in container: NSView) {
        let bounds = container.bounds

        // Header bar (60px)
        let header = buildHeader()
        header.frame = NSRect(x: 0, y: bounds.height - 60, width: bounds.width, height: 60)
        header.autoresizingMask = [.width, .minYMargin]
        container.addSubview(header)

        // Status sidebar (280px on left)
        statusBar = buildStatusSidebar()
        statusBar.frame = NSRect(x: 0, y: 0, width: 280, height: bounds.height - 60)
        statusBar.autoresizingMask = [.height]
        container.addSubview(statusBar)

        // Terminal container (fills remaining space)
        terminalContainer = TabbedTerminalView(frame: NSRect(
            x: 280,
            y: 0,
            width: bounds.width - 280,
            height: bounds.height - 60
        ))
        terminalContainer.autoresizingMask = [.width, .height]
        container.addSubview(terminalContainer)
    }

    private func buildHeader() -> NSView {
        let header = NSView(frame: NSRect(x: 0, y: 0, width: 800, height: 60))
        header.wantsLayer = true
        header.layer?.backgroundColor = NSColor(white: 0.15, alpha: 1.0).cgColor

        // Title
        let titleLabel = NSTextField(labelWithString: "Parallel Email Processing")
        titleLabel.frame = NSRect(x: 20, y: 20, width: 300, height: 24)
        titleLabel.font = NSFont.systemFont(ofSize: 18, weight: .semibold)
        titleLabel.textColor = .white
        header.addSubview(titleLabel)

        // Subtitle (will show account info)
        let subtitle = NSTextField(labelWithString: "No job running")
        subtitle.frame = NSRect(x: 20, y: 6, width: 400, height: 16)
        subtitle.font = NSFont.systemFont(ofSize: 12, weight: .regular)
        subtitle.textColor = NSColor(white: 0.6, alpha: 1.0)
        header.addSubview(subtitle)
        self.subtitleLabel = subtitle

        // Stop button
        let stopBtn = NSButton(frame: NSRect(x: 700, y: 15, width: 80, height: 30))
        stopBtn.title = "Stop All"
        stopBtn.bezelStyle = .rounded
        stopBtn.target = self
        stopBtn.action = #selector(stopAllClicked)
        stopBtn.autoresizingMask = [.minXMargin]
        header.addSubview(stopBtn)

        return header
    }

    private func buildStatusSidebar() -> NSView {
        let sidebar = NSView(frame: NSRect(x: 0, y: 0, width: 280, height: 500))
        sidebar.wantsLayer = true
        sidebar.layer?.backgroundColor = NSColor(white: 0.1, alpha: 1.0).cgColor

        var y = sidebar.frame.height - 20

        // Progress section
        let progressTitle = NSTextField(labelWithString: "Progress")
        progressTitle.frame = NSRect(x: 16, y: y - 18, width: 200, height: 18)
        progressTitle.font = NSFont.systemFont(ofSize: 14, weight: .semibold)
        progressTitle.textColor = .white
        sidebar.addSubview(progressTitle)
        y -= 40

        // Progress bar background
        let progressBg = NSView(frame: NSRect(x: 16, y: y - 8, width: 248, height: 8))
        progressBg.wantsLayer = true
        progressBg.layer?.backgroundColor = NSColor(white: 0.2, alpha: 1.0).cgColor
        progressBg.layer?.cornerRadius = 4
        sidebar.addSubview(progressBg)

        // Progress bar fill
        progressView = NSView(frame: NSRect(x: 16, y: y - 8, width: 0, height: 8))
        progressView.wantsLayer = true
        progressView.layer?.backgroundColor = NSColor.systemGreen.cgColor
        progressView.layer?.cornerRadius = 4
        sidebar.addSubview(progressView)
        y -= 30

        // Stats
        let stats = NSTextField(labelWithString: "0 / 0 workers complete")
        stats.frame = NSRect(x: 16, y: y - 16, width: 248, height: 16)
        stats.font = NSFont.systemFont(ofSize: 12, weight: .regular)
        stats.textColor = NSColor(white: 0.6, alpha: 1.0)
        sidebar.addSubview(stats)
        self.statsLabel = stats
        y -= 40

        // Separator
        let sep = NSView(frame: NSRect(x: 16, y: y, width: 248, height: 1))
        sep.wantsLayer = true
        sep.layer?.backgroundColor = NSColor(white: 0.2, alpha: 1.0).cgColor
        sidebar.addSubview(sep)
        y -= 20

        // Workers section title
        let workersTitle = NSTextField(labelWithString: "Workers")
        workersTitle.frame = NSRect(x: 16, y: y - 18, width: 200, height: 18)
        workersTitle.font = NSFont.systemFont(ofSize: 14, weight: .semibold)
        workersTitle.textColor = .white
        sidebar.addSubview(workersTitle)
        y -= 35

        // Worker status list (will be populated dynamically)
        // Clear previous arrays
        workerRows.removeAll()
        workerIndicators.removeAll()
        workerNameLabels.removeAll()
        workerStatusLabels.removeAll()

        for i in 0..<12 {
            let (row, indicator, nameLabel, statusLabel) = buildWorkerStatusRow(index: i)
            row.frame = NSRect(x: 16, y: y - 28, width: 248, height: 28)
            row.isHidden = true
            sidebar.addSubview(row)

            workerRows.append(row)
            workerIndicators.append(indicator)
            workerNameLabels.append(nameLabel)
            workerStatusLabels.append(statusLabel)
            y -= 32
        }

        return sidebar
    }

    private func buildWorkerStatusRow(index: Int) -> (row: NSView, indicator: NSView, nameLabel: NSTextField, statusLabel: NSTextField) {
        let row = NSView(frame: NSRect(x: 0, y: 0, width: 248, height: 28))

        // Status indicator
        let indicator = NSView(frame: NSRect(x: 0, y: 10, width: 8, height: 8))
        indicator.wantsLayer = true
        indicator.layer?.backgroundColor = NSColor.systemGray.cgColor
        indicator.layer?.cornerRadius = 4
        row.addSubview(indicator)

        // Worker name
        let nameLabel = NSTextField(labelWithString: "Worker \(index + 1)")
        nameLabel.frame = NSRect(x: 16, y: 6, width: 160, height: 16)
        nameLabel.font = NSFont.systemFont(ofSize: 12, weight: .medium)
        nameLabel.textColor = NSColor(white: 0.8, alpha: 1.0)
        row.addSubview(nameLabel)

        // Status text
        let statusLabel = NSTextField(labelWithString: "Pending")
        statusLabel.frame = NSRect(x: 180, y: 6, width: 68, height: 16)
        statusLabel.font = NSFont.systemFont(ofSize: 10, weight: .regular)
        statusLabel.textColor = NSColor(white: 0.5, alpha: 1.0)
        statusLabel.alignment = .right
        row.addSubview(statusLabel)

        return (row, indicator, nameLabel, statusLabel)
    }

    // MARK: - Public Methods

    func show() {
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func hide() {
        window.orderOut(nil)
    }

    func startProcessing(account: AccountInfo) {
        // Update header
        subtitleLabel?.stringValue = "Processing: \(account.email) (\(account.emailCount.formatted()) emails)"

        // Create and start job
        let job = WorkerManager.shared.createJob(for: account)
        currentJob = job

        // Setup worker status display
        updateWorkerDisplay()

        // Set up callbacks
        WorkerManager.shared.onWorkerStarted = { [weak self] _, worker in
            self?.updateWorkerStatus(worker)
        }
        WorkerManager.shared.onWorkerCompleted = { [weak self] job, worker in
            self?.updateWorkerStatus(worker)
            self?.updateProgress(job: job)
        }
        WorkerManager.shared.onJobCompleted = { [weak self] job in
            self?.handleJobComplete(job)
        }

        // Start the job
        WorkerManager.shared.startJob(job, terminalContainer: terminalContainer)
    }

    private func updateWorkerDisplay() {
        guard let job = currentJob else { return }

        for (index, worker) in job.workers.enumerated() {
            guard index < workerRows.count else { continue }
            workerRows[index].isHidden = false
            workerNameLabels[index].stringValue = worker.name
            updateWorkerStatus(worker)
        }

        // Hide unused rows
        for i in job.workers.count..<workerRows.count {
            workerRows[i].isHidden = true
        }
    }

    private func updateWorkerStatus(_ worker: WorkerInfo) {
        guard let job = currentJob,
              let index = job.workers.firstIndex(where: { $0.id == worker.id }),
              index < workerIndicators.count else { return }

        // Update indicator color
        workerIndicators[index].layer?.backgroundColor = worker.status.color.cgColor

        // Update status text
        let statusLabel = workerStatusLabels[index]
        switch worker.status {
        case .pending:
            statusLabel.stringValue = "Pending"
            statusLabel.textColor = NSColor(white: 0.5, alpha: 1.0)
        case .running:
            statusLabel.stringValue = "Running"
            statusLabel.textColor = NSColor.systemBlue
        case .complete:
            statusLabel.stringValue = "Done"
            statusLabel.textColor = NSColor.systemGreen
        case .error:
            statusLabel.stringValue = "Error"
            statusLabel.textColor = NSColor.systemRed
        }
    }

    private func updateProgress(job: ProcessingJob) {
        let total = job.workers.count
        let complete = job.completedCount

        // Update progress bar
        let progress = total > 0 ? CGFloat(complete) / CGFloat(total) : 0
        progressView.frame.size.width = 248 * progress

        // Update stats label
        statsLabel?.stringValue = "\(complete) / \(total) workers complete"
    }

    private func handleJobComplete(_ job: ProcessingJob) {
        // Update header
        let duration = job.endTime?.timeIntervalSince(job.startTime ?? Date()) ?? 0
        let minutes = Int(duration / 60)
        let seconds = Int(duration.truncatingRemainder(dividingBy: 60))
        subtitleLabel?.stringValue = "Complete! \(job.completedCount)/\(job.workers.count) workers finished in \(minutes)m \(seconds)s"

        // Show notification
        showNotification(
            title: "Email Processing Complete",
            body: "\(job.accountEmail): \(job.completedCount) workers finished, \(job.errorCount) errors"
        )
    }

    // MARK: - Actions

    @objc private func stopAllClicked() {
        terminalContainer.terminateAll()
        subtitleLabel?.stringValue = "Stopped by user"
    }

    // MARK: - Window Delegate

    func windowWillClose(_ notification: Notification) {
        terminalContainer.terminateAll()
        onClose?()
    }
}

// MARK: - Processing Panel Integration

extension MainPanelController {
    /// Launch parallel processing with embedded terminals
    func launchParallelProcessing(for account: AccountInfo) {
        let processingPanel = ProcessingPanelController()
        processingPanel.show()
        processingPanel.startProcessing(account: account)
    }
}
