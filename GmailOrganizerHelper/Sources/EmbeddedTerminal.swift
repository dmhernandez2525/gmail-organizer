import Cocoa

// MARK: - Terminal Output View

/// A view that displays terminal-like output from a running process
class TerminalOutputView: NSView {
    private var scrollView: NSScrollView!
    private var textView: NSTextView!
    private var process: Process?
    private var outputPipe: Pipe?
    private var errorPipe: Pipe?

    var title: String = "Terminal"
    var accentColor: NSColor = .systemBlue

    // Callbacks
    var onProcessComplete: ((Int32) -> Void)?
    var onOutputReceived: ((String) -> Void)?

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        setupView()
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
        setupView()
    }

    private func setupView() {
        wantsLayer = true
        layer?.backgroundColor = NSColor(white: 0.1, alpha: 1.0).cgColor
        layer?.cornerRadius = 8

        // Create scroll view
        scrollView = NSScrollView(frame: bounds)
        scrollView.hasVerticalScroller = true
        scrollView.hasHorizontalScroller = false
        scrollView.autoresizingMask = [.width, .height]
        scrollView.drawsBackground = false
        scrollView.borderType = .noBorder

        // Create text view
        textView = NSTextView(frame: bounds)
        textView.isEditable = false
        textView.isSelectable = true
        textView.backgroundColor = NSColor(white: 0.1, alpha: 1.0)
        textView.textColor = NSColor(white: 0.9, alpha: 1.0)
        textView.font = NSFont.monospacedSystemFont(ofSize: 12, weight: .regular)
        textView.autoresizingMask = [.width]
        textView.isVerticallyResizable = true
        textView.isHorizontallyResizable = false
        textView.textContainer?.widthTracksTextView = true
        textView.textContainer?.containerSize = NSSize(width: bounds.width, height: CGFloat.greatestFiniteMagnitude)

        scrollView.documentView = textView
        addSubview(scrollView)
    }

    override func layout() {
        super.layout()
        scrollView.frame = NSRect(x: 8, y: 8, width: bounds.width - 16, height: bounds.height - 16)
    }

    // MARK: - Process Management

    func runCommand(_ command: String, workingDirectory: String? = nil, environment: [String: String]? = nil) {
        // Clear previous output
        textView.string = ""
        appendText("$ \(command)\n\n", color: accentColor)

        process = Process()
        outputPipe = Pipe()
        errorPipe = Pipe()

        process?.executableURL = URL(fileURLWithPath: "/bin/zsh")
        process?.arguments = ["-c", command]
        process?.standardOutput = outputPipe
        process?.standardError = errorPipe

        if let dir = workingDirectory {
            process?.currentDirectoryURL = URL(fileURLWithPath: dir)
        }

        var env = ProcessInfo.processInfo.environment
        // Add user's PATH for claude command
        let homePath = NSHomeDirectory()
        env["PATH"] = "\(homePath)/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:" + (env["PATH"] ?? "")
        if let customEnv = environment {
            for (key, value) in customEnv {
                env[key] = value
            }
        }
        process?.environment = env

        // Handle stdout
        outputPipe?.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            if !data.isEmpty, let str = String(data: data, encoding: .utf8) {
                DispatchQueue.main.async {
                    self?.appendText(str, color: NSColor(white: 0.9, alpha: 1.0))
                    self?.onOutputReceived?(str)
                }
            }
        }

        // Handle stderr
        errorPipe?.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            if !data.isEmpty, let str = String(data: data, encoding: .utf8) {
                DispatchQueue.main.async {
                    self?.appendText(str, color: NSColor.systemRed)
                }
            }
        }

        // Handle completion
        process?.terminationHandler = { [weak self] proc in
            DispatchQueue.main.async {
                self?.outputPipe?.fileHandleForReading.readabilityHandler = nil
                self?.errorPipe?.fileHandleForReading.readabilityHandler = nil

                let exitCode = proc.terminationStatus
                let statusColor = exitCode == 0 ? NSColor.systemGreen : NSColor.systemRed
                self?.appendText("\n[Process completed with exit code: \(exitCode)]\n", color: statusColor)
                self?.onProcessComplete?(exitCode)
            }
        }

        do {
            try process?.run()
        } catch {
            appendText("Error starting process: \(error.localizedDescription)\n", color: .systemRed)
        }
    }

    func terminate() {
        process?.terminate()
    }

    func isRunning() -> Bool {
        return process?.isRunning ?? false
    }

    // MARK: - Text Output

    func appendText(_ text: String, color: NSColor = NSColor(white: 0.9, alpha: 1.0)) {
        let attrs: [NSAttributedString.Key: Any] = [
            .foregroundColor: color,
            .font: NSFont.monospacedSystemFont(ofSize: 12, weight: .regular)
        ]
        let attrStr = NSAttributedString(string: text, attributes: attrs)
        textView.textStorage?.append(attrStr)

        // Auto-scroll to bottom
        textView.scrollToEndOfDocument(nil)
    }

    func clear() {
        textView.string = ""
    }
}

// MARK: - Tabbed Terminal Container

/// A container that holds multiple terminal views in tabs
class TabbedTerminalView: NSView {
    private var tabBar: NSView!
    private var contentView: NSView!
    private var terminals: [(id: String, view: TerminalOutputView, button: NSButton)] = []
    private var selectedTabId: String?

    // Tab colors for different worker types
    static let tabColors: [NSColor] = [
        NSColor.systemBlue,
        NSColor.systemGreen,
        NSColor.systemOrange,
        NSColor.systemPurple,
        NSColor.systemPink,
        NSColor.systemTeal,
        NSColor.systemYellow,
        NSColor.systemIndigo
    ]

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        setupView()
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
        setupView()
    }

    private func setupView() {
        wantsLayer = true
        layer?.backgroundColor = NSColor(white: 0.15, alpha: 1.0).cgColor

        // Tab bar at top
        tabBar = NSView(frame: NSRect(x: 0, y: bounds.height - 36, width: bounds.width, height: 36))
        tabBar.wantsLayer = true
        tabBar.layer?.backgroundColor = NSColor(white: 0.12, alpha: 1.0).cgColor
        tabBar.autoresizingMask = [.width, .minYMargin]
        addSubview(tabBar)

        // Content area
        contentView = NSView(frame: NSRect(x: 0, y: 0, width: bounds.width, height: bounds.height - 36))
        contentView.wantsLayer = true
        contentView.autoresizingMask = [.width, .height]
        addSubview(contentView)
    }

    // MARK: - Tab Management

    func addTerminal(id: String, title: String, colorIndex: Int = 0) -> TerminalOutputView {
        let terminal = TerminalOutputView(frame: contentView.bounds)
        terminal.title = title
        terminal.accentColor = TabbedTerminalView.tabColors[colorIndex % TabbedTerminalView.tabColors.count]
        terminal.autoresizingMask = [.width, .height]
        terminal.isHidden = true
        contentView.addSubview(terminal)

        // Create tab button
        let tabButton = NSButton(frame: .zero)
        tabButton.title = title
        tabButton.bezelStyle = .rounded
        tabButton.isBordered = false
        tabButton.wantsLayer = true
        tabButton.layer?.cornerRadius = 4
        tabButton.font = NSFont.systemFont(ofSize: 11, weight: .medium)
        tabButton.target = self
        tabButton.action = #selector(tabClicked(_:))
        tabButton.tag = terminals.count

        // Status indicator
        let indicator = NSView(frame: NSRect(x: 4, y: 12, width: 8, height: 8))
        indicator.wantsLayer = true
        indicator.layer?.backgroundColor = terminal.accentColor.cgColor
        indicator.layer?.cornerRadius = 4
        tabButton.addSubview(indicator)

        terminals.append((id: id, view: terminal, button: tabButton))
        tabBar.addSubview(tabButton)

        layoutTabs()

        // Select first tab automatically
        if terminals.count == 1 {
            selectTab(id: id)
        }

        return terminal
    }

    func removeTerminal(id: String) {
        if let index = terminals.firstIndex(where: { $0.id == id }) {
            terminals[index].view.terminate()
            terminals[index].view.removeFromSuperview()
            terminals[index].button.removeFromSuperview()
            terminals.remove(at: index)
            layoutTabs()

            // Select another tab if current was removed
            if selectedTabId == id, let first = terminals.first {
                selectTab(id: first.id)
            }
        }
    }

    func getTerminal(id: String) -> TerminalOutputView? {
        return terminals.first(where: { $0.id == id })?.view
    }

    func selectTab(id: String) {
        selectedTabId = id

        for (termId, view, button) in terminals {
            let isSelected = termId == id
            view.isHidden = !isSelected
            button.layer?.backgroundColor = isSelected
                ? NSColor(white: 0.25, alpha: 1.0).cgColor
                : NSColor.clear.cgColor

            let titleColor = isSelected ? NSColor.white : NSColor(white: 0.6, alpha: 1.0)
            let attrTitle = NSAttributedString(string: "  " + view.title, attributes: [
                .foregroundColor: titleColor,
                .font: NSFont.systemFont(ofSize: 11, weight: isSelected ? .semibold : .medium)
            ])
            button.attributedTitle = attrTitle
        }
    }

    @objc private func tabClicked(_ sender: NSButton) {
        if sender.tag < terminals.count {
            selectTab(id: terminals[sender.tag].id)
        }
    }

    private func layoutTabs() {
        var x: CGFloat = 8
        for (_, _, button) in terminals {
            let width: CGFloat = 140
            button.frame = NSRect(x: x, y: 4, width: width, height: 28)
            x += width + 4
        }
    }

    // MARK: - Convenience Methods

    func terminateAll() {
        for (_, view, _) in terminals {
            view.terminate()
        }
    }

    func clearAll() {
        for (_, view, _) in terminals {
            view.clear()
        }
    }

    var runningCount: Int {
        return terminals.filter { $0.view.isRunning() }.count
    }

    var totalCount: Int {
        return terminals.count
    }
}

// MARK: - Worker Status

enum WorkerStatus {
    case pending
    case running
    case complete
    case error(String)

    var color: NSColor {
        switch self {
        case .pending: return .systemGray
        case .running: return .systemBlue
        case .complete: return .systemGreen
        case .error: return .systemRed
        }
    }

    var icon: String {
        switch self {
        case .pending: return "circle"
        case .running: return "arrow.triangle.2.circlepath"
        case .complete: return "checkmark.circle.fill"
        case .error: return "exclamationmark.circle.fill"
        }
    }
}

// MARK: - Worker Info

struct WorkerInfo {
    let id: String
    let name: String
    let phase: Int
    let description: String
    let model: String  // "haiku" or "sonnet"
    let promptFile: String
    var status: WorkerStatus = .pending
    var startTime: Date?
    var endTime: Date?
    var outputFile: String?
}
