import Cocoa
import UserNotifications

class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem!
    var processingManager: ProcessingManager!
    var mainPanel: MainPanelController!
    var isProcessing = false
    var animationTimer: Timer?
    var animationFrame = 0

    // Settings
    private var autoStartStreamlit: Bool {
        get { UserDefaults.standard.bool(forKey: "autoStartStreamlit") }
        set { UserDefaults.standard.set(newValue, forKey: "autoStartStreamlit") }
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Request notification permissions
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { _, _ in }

        // Initialize processing manager
        processingManager = ProcessingManager()

        // Initialize main panel
        mainPanel = MainPanelController()
        setupMainPanelCallbacks()

        // Setup menubar
        setupStatusBar()

        // Check if Streamlit is running
        checkStreamlitStatus()

        // Write debug info to file on launch
        let debugInfo = processingManager.debugPaths()
        let debugPath = Paths.projectRoot + "/.helper-debug.log"
        try? debugInfo.write(toFile: debugPath, atomically: true, encoding: .utf8)

        let accounts = processingManager.getAvailableAccounts()
        showNotification(title: "Gmail Organizer Helper", body: "Found \(accounts.count) synced accounts")
    }

    private func setupMainPanelCallbacks() {
        mainPanel.onProcessAccount = { [weak self] accountName in
            self?.processingManager.processWithClaudeCode(accountName: accountName)
        }

        mainPanel.onProcessAllAccounts = { [weak self] in
            self?.processingManager.processAllAccounts()
        }

        mainPanel.onOpenWebInterface = { [weak self] in
            self?.openWebInterface()
        }

        mainPanel.onRefreshAccounts = { [weak self] in
            self?.refreshAccounts()
        }

        mainPanel.onAddAccount = { [weak self] in
            self?.addAccount()
        }

        mainPanel.onOpenProjectFolder = { [weak self] in
            self?.openProjectFolder()
        }
    }

    private func checkStreamlitStatus() {
        let result = runShellCommand("pgrep -f 'streamlit run app.py'")
        let isRunning = result.exitCode == 0
        if !isRunning && autoStartStreamlit {
            startStreamlit()
        }
    }

    private func startStreamlit() {
        let command = "cd '\(Paths.projectRoot)' && ./venv/bin/streamlit run app.py --server.headless true --server.port 8501 &"
        _ = runShellCommand(command)
        showNotification(title: "Streamlit Started", body: "Web interface starting at localhost:8501")
    }

    // MARK: - Status Bar

    private func setupStatusBar() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)

        if let button = statusItem.button {
            button.image = NSImage(systemSymbolName: "envelope.badge.fill", accessibilityDescription: "Gmail Organizer")
        }

        let menu = NSMenu()

        menu.addItem(NSMenuItem(title: "Gmail Organizer Helper", action: nil, keyEquivalent: ""))
        menu.addItem(NSMenuItem.separator())

        // Show main window
        let showWindowItem = NSMenuItem(title: "Open Gmail Organizer", action: #selector(showMainWindow), keyEquivalent: "o")
        showWindowItem.target = self
        if let icon = NSImage(systemSymbolName: "rectangle.and.text.magnifyingglass", accessibilityDescription: nil) {
            showWindowItem.image = icon
        }
        menu.addItem(showWindowItem)
        menu.addItem(NSMenuItem.separator())

        // Account processing submenu
        let accountsItem = NSMenuItem(title: "Process Account", action: nil, keyEquivalent: "")
        let accountsMenu = NSMenu()

        // Load available accounts
        let accounts = processingManager.getAvailableAccounts()
        if accounts.isEmpty {
            accountsMenu.addItem(NSMenuItem(title: "No accounts synced", action: nil, keyEquivalent: ""))
        } else {
            for account in accounts {
                let item = NSMenuItem(
                    title: "\(account.name) (\(account.emailCount) emails)",
                    action: #selector(processAccount(_:)),
                    keyEquivalent: ""
                )
                item.target = self
                item.representedObject = account.name
                accountsMenu.addItem(item)
            }
        }
        accountsItem.submenu = accountsMenu
        menu.addItem(accountsItem)

        menu.addItem(NSMenuItem.separator())

        // Streamlit status and controls
        let streamlitRunning = isStreamlitRunning()
        if streamlitRunning {
            let statusItem = NSMenuItem(title: "Web Interface Running", action: nil, keyEquivalent: "")
            statusItem.isEnabled = false
            if let icon = NSImage(systemSymbolName: "checkmark.circle.fill", accessibilityDescription: nil) {
                let config = NSImage.SymbolConfiguration(paletteColors: [.systemGreen])
                statusItem.image = icon.withSymbolConfiguration(config)
            }
            menu.addItem(statusItem)

            let openAppItem = NSMenuItem(title: "Open Web Interface", action: #selector(openWebInterface), keyEquivalent: "o")
            openAppItem.target = self
            menu.addItem(openAppItem)
        } else {
            let startItem = NSMenuItem(title: "Start Web Interface", action: #selector(startStreamlitAction), keyEquivalent: "")
            startItem.target = self
            if let icon = NSImage(systemSymbolName: "play.circle", accessibilityDescription: nil) {
                startItem.image = icon
            }
            menu.addItem(startItem)
        }

        menu.addItem(NSMenuItem.separator())

        // Settings submenu
        let settingsItem = NSMenuItem(title: "Settings", action: nil, keyEquivalent: "")
        let settingsMenu = NSMenu()

        let autoStartItem = NSMenuItem(title: "Auto-start Web Interface", action: #selector(toggleAutoStartStreamlit), keyEquivalent: "")
        autoStartItem.target = self
        autoStartItem.state = autoStartStreamlit ? .on : .off
        settingsMenu.addItem(autoStartItem)

        settingsItem.submenu = settingsMenu
        menu.addItem(settingsItem)

        // Open project folder
        let openFolderItem = NSMenuItem(title: "Open Project Folder", action: #selector(openProjectFolder), keyEquivalent: "")
        openFolderItem.target = self
        menu.addItem(openFolderItem)

        menu.addItem(NSMenuItem.separator())

        // Refresh accounts
        let refreshItem = NSMenuItem(title: "Refresh Accounts", action: #selector(refreshAccounts), keyEquivalent: "r")
        refreshItem.target = self
        menu.addItem(refreshItem)

        // Add account (opens web interface)
        let addAccountItem = NSMenuItem(title: "Add Account (via Web)...", action: #selector(addAccount), keyEquivalent: "")
        addAccountItem.target = self
        menu.addItem(addAccountItem)

        menu.addItem(NSMenuItem.separator())

        // Debug info
        let debugItem = NSMenuItem(title: "Show Debug Info", action: #selector(showDebugInfo), keyEquivalent: "d")
        debugItem.target = self
        menu.addItem(debugItem)

        menu.addItem(NSMenuItem.separator())

        let quitItem = NSMenuItem(title: "Quit", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        menu.addItem(quitItem)

        statusItem.menu = menu
    }

    // MARK: - Actions

    @objc func showMainWindow() {
        mainPanel.show(near: statusItem)
    }

    @objc func processAccount(_ sender: NSMenuItem) {
        guard let accountName = sender.representedObject as? String else { return }
        processingManager.processWithClaudeCode(accountName: accountName)
    }

    @objc func openWebInterface() {
        if let url = URL(string: "http://localhost:8501") {
            NSWorkspace.shared.open(url)
        }
    }

    @objc func openProjectFolder() {
        NSWorkspace.shared.selectFile(nil, inFileViewerRootedAtPath: Paths.projectRoot)
    }

    @objc func refreshAccounts() {
        setupStatusBar()
        showNotification(title: "Accounts Refreshed", body: "Menu updated with latest sync data")
    }

    @objc func startStreamlitAction() {
        startStreamlit()
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in
            self?.setupStatusBar()
        }
    }

    @objc func toggleAutoStartStreamlit() {
        autoStartStreamlit = !autoStartStreamlit
        setupStatusBar()
    }

    private func isStreamlitRunning() -> Bool {
        let result = runShellCommand("pgrep -f 'streamlit run app.py'")
        return result.exitCode == 0
    }

    @objc func addAccount() {
        // Start Streamlit if not running
        if !isStreamlitRunning() {
            startStreamlit()
            DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                if let url = URL(string: "http://localhost:8501") {
                    NSWorkspace.shared.open(url)
                }
            }
        } else {
            if let url = URL(string: "http://localhost:8501") {
                NSWorkspace.shared.open(url)
            }
        }
        showNotification(title: "Add Account", body: "Use the sidebar in the web interface to add and authenticate accounts")
    }

    @objc func showDebugInfo() {
        let debugInfo = processingManager.debugPaths()

        let alert = NSAlert()
        alert.messageText = "Debug Information"
        alert.informativeText = debugInfo
        alert.alertStyle = .informational
        alert.addButton(withTitle: "OK")
        alert.addButton(withTitle: "Copy to Clipboard")

        let response = alert.runModal()
        if response == .alertSecondButtonReturn {
            copyToClipboard(debugInfo)
        }
    }

    // MARK: - URL Scheme Handler

    @objc func handleURLEvent(_ event: NSAppleEventDescriptor, withReplyEvent reply: NSAppleEventDescriptor) {
        guard let urlString = event.paramDescriptor(forKeyword: keyDirectObject)?.stringValue,
              let url = URL(string: urlString) else {
            return
        }

        handleURL(url)
    }

    private func handleURL(_ url: URL) {
        // URL format: gmailorganizer://action/parameter
        // Examples:
        //   gmailorganizer://process/personal
        //   gmailorganizer://process-all
        //   gmailorganizer://open

        guard url.scheme == "gmailorganizer" else { return }

        let action = url.host ?? ""
        let path = url.path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))

        switch action {
        case "process":
            if !path.isEmpty {
                processingManager.processWithClaudeCode(accountName: path)
            }

        case "process-all":
            processingManager.processAllAccounts()

        case "open":
            openWebInterface()

        default:
            print("Unknown URL action: \(action)")
        }
    }
}
