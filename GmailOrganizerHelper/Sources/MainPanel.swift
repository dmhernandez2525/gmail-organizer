import Cocoa

// MARK: - Google-Style Colors

struct GoogleColors {
    // Primary
    static let blue = NSColor(red: 0.10, green: 0.45, blue: 0.91, alpha: 1.0)        // #1A73E8
    static let blueLight = NSColor(red: 0.91, green: 0.94, blue: 0.99, alpha: 1.0)   // #E8F0FE
    static let blueHover = NSColor(red: 0.08, green: 0.34, blue: 0.69, alpha: 1.0)   // #1557B0

    // Gmail colors
    static let gmailRed = NSColor(red: 0.92, green: 0.26, blue: 0.21, alpha: 1.0)    // #EA4335

    // Status
    static let green = NSColor(red: 0.20, green: 0.66, blue: 0.33, alpha: 1.0)       // #34A853
    static let yellow = NSColor(red: 0.98, green: 0.74, blue: 0.02, alpha: 1.0)      // #FBBC04
    static let yellowBg = NSColor(red: 1.0, green: 0.97, blue: 0.88, alpha: 1.0)     // #FEF7E0
    static let red = NSColor(red: 0.92, green: 0.26, blue: 0.21, alpha: 1.0)         // #EA4335

    // Neutral
    static let textPrimary = NSColor(red: 0.13, green: 0.13, blue: 0.14, alpha: 1.0) // #202124
    static let textSecondary = NSColor(red: 0.37, green: 0.38, blue: 0.41, alpha: 1.0) // #5F6368
    static let textTertiary = NSColor(red: 0.50, green: 0.53, blue: 0.55, alpha: 1.0) // #80868B
    static let border = NSColor(red: 0.85, green: 0.87, blue: 0.88, alpha: 1.0)      // #DADCE0
    static let bgSecondary = NSColor(red: 0.95, green: 0.96, blue: 0.96, alpha: 1.0) // #F1F3F4
    static let bgHover = NSColor(red: 0.91, green: 0.92, blue: 0.93, alpha: 1.0)     // #E8EAED
}

// MARK: - Navigation

enum NavigationItem: String, CaseIterable {
    case home = "Home"
    case emails = "Emails"
    case rules = "Rules"
    case process = "Process"
    case settings = "Settings"

    var icon: String {
        switch self {
        case .home: return "house.fill"
        case .emails: return "envelope.fill"
        case .rules: return "gearshape.2.fill"
        case .process: return "cpu.fill"
        case .settings: return "slider.horizontal.3"
        }
    }
}

// MARK: - Email Activity Item

struct EmailActivityItem {
    let id: String
    let subject: String
    let sender: String
    let snippet: String
    let date: Date
    let labels: [String]
    let isRead: Bool

    var formattedDate: String {
        let formatter = DateFormatter()
        let calendar = Calendar.current
        if calendar.isDateInToday(date) {
            formatter.dateFormat = "h:mm a"
        } else if calendar.isDateInYesterday(date) {
            return "Yesterday"
        } else {
            formatter.dateFormat = "MMM d"
        }
        return formatter.string(from: date)
    }
}

// MARK: - Automation Rule

struct AutomationRule: Codable {
    var id: UUID
    var name: String
    var isEnabled: Bool
    var conditions: [RuleCondition]
    var actions: [RuleAction]

    struct RuleCondition: Codable {
        var field: ConditionField
        var matchType: MatchType
        var value: String

        enum ConditionField: String, Codable, CaseIterable {
            case from = "From"
            case to = "To"
            case subject = "Subject"
            case body = "Body"
            case hasAttachment = "Has Attachment"
        }

        enum MatchType: String, Codable, CaseIterable {
            case contains = "Contains"
            case equals = "Equals"
            case startsWith = "Starts with"
            case endsWith = "Ends with"
            case regex = "Matches regex"
        }
    }

    struct RuleAction: Codable {
        var actionType: ActionType
        var value: String

        enum ActionType: String, Codable, CaseIterable {
            case applyLabel = "Apply Label"
            case archive = "Archive"
            case markRead = "Mark as Read"
            case star = "Star"
            case moveToFolder = "Move to Folder"
            case delete = "Delete"
        }
    }
}

// MARK: - Processing Status

enum ProcessingStatus {
    case idle
    case analyzing(progress: Double, message: String)
    case processing(progress: Double, current: Int, total: Int)
    case complete(processed: Int, errors: Int)
    case error(message: String)

    var icon: String {
        switch self {
        case .idle: return "pause.circle.fill"
        case .analyzing, .processing: return "arrow.triangle.2.circlepath"
        case .complete: return "checkmark.circle.fill"
        case .error: return "exclamationmark.circle.fill"
        }
    }

    var color: NSColor {
        switch self {
        case .idle: return GoogleColors.textTertiary
        case .analyzing, .processing: return GoogleColors.blue
        case .complete: return GoogleColors.green
        case .error: return GoogleColors.red
        }
    }
}

// MARK: - Main Panel Controller

class MainPanelController: NSObject, NSWindowDelegate {
    private var window: NSPanel!
    private var contentContainer: NSView!
    private var sidebarView: NSView!
    private var headerView: NSView!

    // Navigation
    private var selectedNav: NavigationItem = .home
    private var navButtons: [NavigationItem: NSButton] = [:]

    // Data
    private var accounts: [AccountInfo] = []
    private var emailActivities: [EmailActivityItem] = []
    private var automationRules: [AutomationRule] = []
    private var processingStatus: ProcessingStatus = .idle

    // Selected account for processing
    private var selectedAccountIndex: Int = 0
    private var selectedAnalysisType: AnalysisType = .fullAnalysis
    private var useParallelProcessing: Bool = true
    private var accountsLoaded: Bool = false

    // Processing panel for parallel jobs
    private var processingPanel: ProcessingPanelController?

    // Callbacks
    var onProcessAccount: ((String) -> Void)?
    var onProcessAllAccounts: (() -> Void)?
    var onOpenWebInterface: (() -> Void)?
    var onRefreshAccounts: (() -> Void)?
    var onAddAccount: (() -> Void)?
    var onOpenProjectFolder: (() -> Void)?

    override init() {
        super.init()
        setupWindow()
        // Don't load data on init - wait for user action to avoid early permission prompts
        // loadData() will be called when user clicks "Load Accounts" or navigates to Home
    }

    // MARK: - Window Setup

    private func setupWindow() {
        window = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: 1100, height: 750),
            styleMask: [.titled, .closable, .resizable, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )
        window.title = "Gmail Organizer"
        window.titlebarAppearsTransparent = true
        window.titleVisibility = .hidden
        window.delegate = self
        window.isReleasedWhenClosed = false
        window.level = .floating
        window.collectionBehavior = [.canJoinAllSpaces, .transient]
        window.backgroundColor = .white
        window.minSize = NSSize(width: 900, height: 600)
        window.isMovableByWindowBackground = true

        let mainView = NSView(frame: window.contentView!.bounds)
        mainView.wantsLayer = true
        mainView.layer?.backgroundColor = NSColor.white.cgColor
        window.contentView = mainView

        buildLayout(in: mainView)
    }

    private func buildLayout(in container: NSView) {
        container.subviews.forEach { $0.removeFromSuperview() }

        let bounds = container.bounds
        let sidebarWidth: CGFloat = 240

        // Header (56px)
        headerView = buildHeader()
        headerView.frame = NSRect(x: 0, y: bounds.height - 56, width: bounds.width, height: 56)
        headerView.autoresizingMask = [.width, .minYMargin]
        container.addSubview(headerView)

        // Sidebar
        sidebarView = buildSidebar()
        sidebarView.frame = NSRect(x: 0, y: 0, width: sidebarWidth, height: bounds.height - 56)
        sidebarView.autoresizingMask = [.height]
        container.addSubview(sidebarView)

        // Content area
        contentContainer = NSView(frame: NSRect(x: sidebarWidth, y: 0, width: bounds.width - sidebarWidth, height: bounds.height - 56))
        contentContainer.wantsLayer = true
        contentContainer.autoresizingMask = [.width, .height]
        container.addSubview(contentContainer)

        showScreen(selectedNav)
    }

    // MARK: - Header

    private func buildHeader() -> NSView {
        let header = NSView(frame: NSRect(x: 0, y: 0, width: 800, height: 56))
        header.wantsLayer = true
        header.layer?.backgroundColor = NSColor.white.cgColor

        // Bottom border
        let border = NSView(frame: NSRect(x: 0, y: 0, width: 800, height: 1))
        border.wantsLayer = true
        border.layer?.backgroundColor = GoogleColors.border.cgColor
        border.autoresizingMask = [.width]
        header.addSubview(border)

        // Gmail icon
        let appIcon = NSImageView(frame: NSRect(x: 20, y: 14, width: 28, height: 28))
        if let img = NSImage(systemSymbolName: "envelope.badge.fill", accessibilityDescription: nil) {
            let config = NSImage.SymbolConfiguration(pointSize: 24, weight: .regular)
                .applying(NSImage.SymbolConfiguration(paletteColors: [GoogleColors.gmailRed]))
            appIcon.image = img.withSymbolConfiguration(config)
        }
        header.addSubview(appIcon)

        // App title
        let title = NSTextField(labelWithString: "Gmail Organizer")
        title.frame = NSRect(x: 54, y: 18, width: 160, height: 20)
        title.font = NSFont.systemFont(ofSize: 16, weight: .semibold)
        title.textColor = GoogleColors.textPrimary
        header.addSubview(title)

        // Right side buttons
        var rightX: CGFloat = 760

        // Refresh button
        let refreshBtn = createIconButton(icon: "arrow.clockwise", action: #selector(refreshClicked))
        refreshBtn.frame = NSRect(x: rightX - 32, y: 12, width: 32, height: 32)
        refreshBtn.autoresizingMask = [.minXMargin]
        refreshBtn.toolTip = "Refresh accounts"
        header.addSubview(refreshBtn)
        rightX -= 40

        // Web interface button
        let webBtn = createIconButton(icon: "globe", action: #selector(openWebClicked))
        webBtn.frame = NSRect(x: rightX - 32, y: 12, width: 32, height: 32)
        webBtn.autoresizingMask = [.minXMargin]
        webBtn.toolTip = "Open web interface"
        header.addSubview(webBtn)

        return header
    }

    private func createIconButton(icon: String, action: Selector) -> NSButton {
        let btn = NSButton(frame: NSRect(x: 0, y: 0, width: 32, height: 32))
        btn.bezelStyle = .regularSquare
        btn.isBordered = false
        btn.target = self
        btn.action = action

        if let img = NSImage(systemSymbolName: icon, accessibilityDescription: nil) {
            let config = NSImage.SymbolConfiguration(pointSize: 16, weight: .regular)
                .applying(NSImage.SymbolConfiguration(paletteColors: [GoogleColors.textSecondary]))
            btn.image = img.withSymbolConfiguration(config)
        }

        return btn
    }

    // MARK: - Sidebar

    private func buildSidebar() -> NSView {
        let sidebarWidth: CGFloat = 240
        let sidebar = NSView(frame: NSRect(x: 0, y: 0, width: sidebarWidth, height: 500))
        sidebar.wantsLayer = true
        sidebar.layer?.backgroundColor = NSColor.white.cgColor

        var y = sidebar.frame.height - 20
        let padding: CGFloat = 16
        let buttonWidth = sidebarWidth - (padding * 2)

        // Account selector popup
        let accountLabel = NSTextField(labelWithString: "Account")
        accountLabel.frame = NSRect(x: padding, y: y - 16, width: 100, height: 16)
        accountLabel.font = NSFont.systemFont(ofSize: 11, weight: .medium)
        accountLabel.textColor = GoogleColors.textSecondary
        sidebar.addSubview(accountLabel)
        y -= 24

        let accountPopup = NSPopUpButton(frame: NSRect(x: padding - 2, y: y - 30, width: buttonWidth + 4, height: 30))
        accountPopup.removeAllItems()
        if accounts.isEmpty {
            accountPopup.addItem(withTitle: "No accounts synced")
        } else {
            for account in accounts {
                let emailCount = account.emailCount.formatted()
                accountPopup.addItem(withTitle: "\(account.name) - \(emailCount) emails")
            }
        }
        accountPopup.target = self
        accountPopup.action = #selector(accountSelected(_:))
        sidebar.addSubview(accountPopup)
        y -= 48

        // Add account button
        let addAccountBtn = NSButton(frame: NSRect(x: padding, y: y - 32, width: buttonWidth, height: 32))
        addAccountBtn.title = "  Add Account"
        addAccountBtn.bezelStyle = .rounded
        addAccountBtn.target = self
        addAccountBtn.action = #selector(addAccountClicked)
        addAccountBtn.font = NSFont.systemFont(ofSize: 12, weight: .medium)
        if let img = NSImage(systemSymbolName: "plus.circle", accessibilityDescription: nil) {
            let config = NSImage.SymbolConfiguration(pointSize: 12, weight: .regular)
                .applying(NSImage.SymbolConfiguration(paletteColors: [GoogleColors.textSecondary]))
            addAccountBtn.image = img.withSymbolConfiguration(config)
            addAccountBtn.imagePosition = .imageLeft
        }
        sidebar.addSubview(addAccountBtn)
        y -= 50

        // Separator
        let sep = NSView(frame: NSRect(x: padding, y: y, width: buttonWidth, height: 1))
        sep.wantsLayer = true
        sep.layer?.backgroundColor = GoogleColors.border.cgColor
        sidebar.addSubview(sep)
        y -= 20

        // Navigation items
        navButtons.removeAll()

        for item in NavigationItem.allCases {
            let navBtn = createNavButton(item: item)
            navBtn.frame = NSRect(x: padding - 4, y: y - 40, width: buttonWidth + 8, height: 40)
            sidebar.addSubview(navBtn)
            navButtons[item] = navBtn
            y -= 44
        }

        updateNavSelection()

        // Bottom section - version info
        let versionLabel = NSTextField(labelWithString: "v1.0.0")
        versionLabel.frame = NSRect(x: padding, y: 16, width: 100, height: 14)
        versionLabel.font = NSFont.systemFont(ofSize: 10, weight: .regular)
        versionLabel.textColor = GoogleColors.textTertiary
        sidebar.addSubview(versionLabel)

        return sidebar
    }

    private func createNavButton(item: NavigationItem) -> NSButton {
        let btn = NSButton(frame: NSRect(x: 0, y: 0, width: 196, height: 36))
        btn.title = "  \(item.rawValue)"
        btn.bezelStyle = .regularSquare
        btn.isBordered = false
        btn.target = self
        btn.action = #selector(navItemClicked(_:))
        btn.font = NSFont.systemFont(ofSize: 13, weight: .medium)
        btn.alignment = .left
        btn.tag = NavigationItem.allCases.firstIndex(of: item) ?? 0

        btn.wantsLayer = true
        btn.layer?.cornerRadius = 18

        if let img = NSImage(systemSymbolName: item.icon, accessibilityDescription: nil) {
            let config = NSImage.SymbolConfiguration(pointSize: 14, weight: .regular)
            btn.image = img.withSymbolConfiguration(config)
            btn.imagePosition = .imageLeft
        }

        return btn
    }

    private func updateNavSelection() {
        for (item, btn) in navButtons {
            let isSelected = item == selectedNav

            if isSelected {
                btn.layer?.backgroundColor = GoogleColors.blueLight.cgColor
                btn.contentTintColor = GoogleColors.blue

                if let img = NSImage(systemSymbolName: item.icon, accessibilityDescription: nil) {
                    let config = NSImage.SymbolConfiguration(pointSize: 14, weight: .regular)
                        .applying(NSImage.SymbolConfiguration(paletteColors: [GoogleColors.blue]))
                    btn.image = img.withSymbolConfiguration(config)
                }

                let attrStr = NSMutableAttributedString(string: "  \(item.rawValue)")
                attrStr.addAttributes([
                    .foregroundColor: GoogleColors.blue,
                    .font: NSFont.systemFont(ofSize: 13, weight: .medium)
                ], range: NSRange(location: 0, length: attrStr.length))
                btn.attributedTitle = attrStr
            } else {
                btn.layer?.backgroundColor = NSColor.clear.cgColor
                btn.contentTintColor = GoogleColors.textSecondary

                if let img = NSImage(systemSymbolName: item.icon, accessibilityDescription: nil) {
                    let config = NSImage.SymbolConfiguration(pointSize: 14, weight: .regular)
                        .applying(NSImage.SymbolConfiguration(paletteColors: [GoogleColors.textSecondary]))
                    btn.image = img.withSymbolConfiguration(config)
                }

                let attrStr = NSMutableAttributedString(string: "  \(item.rawValue)")
                attrStr.addAttributes([
                    .foregroundColor: GoogleColors.textSecondary,
                    .font: NSFont.systemFont(ofSize: 13, weight: .medium)
                ], range: NSRange(location: 0, length: attrStr.length))
                btn.attributedTitle = attrStr
            }
        }
    }

    // MARK: - Screen Content

    private func showScreen(_ screen: NavigationItem) {
        contentContainer.subviews.forEach { $0.removeFromSuperview() }

        switch screen {
        case .home:
            buildHomeScreen()
        case .emails:
            buildEmailsScreen()
        case .rules:
            buildRulesScreen()
        case .process:
            buildProcessScreen()
        case .settings:
            buildSettingsScreen()
        }
    }

    // MARK: - Home Screen

    private func buildHomeScreen() {
        let bounds = contentContainer.bounds

        // Create a scroll view for the content
        let scrollView = NSScrollView(frame: bounds)
        scrollView.hasVerticalScroller = true
        scrollView.hasHorizontalScroller = false
        scrollView.autoresizingMask = [.width, .height]
        scrollView.drawsBackground = false

        // Calculate total height needed
        let cardHeight: CGFloat = 110
        let cardSpacing: CGFloat = 15
        let cardWidth = (bounds.width - 80) / 2
        let accountRows = ceil(Double(max(accounts.count, 1)) / 2.0)
        let accountsHeight = CGFloat(accountRows) * (cardHeight + cardSpacing)
        let quickActionsHeight: CGFloat = 180
        let headerHeight: CGFloat = 120
        let totalHeight = max(bounds.height, headerHeight + accountsHeight + quickActionsHeight + 100)

        let documentView = NSView(frame: NSRect(x: 0, y: 0, width: bounds.width, height: totalHeight))
        scrollView.documentView = documentView

        var y = totalHeight - 30

        // Welcome header
        let welcomeLabel = NSTextField(labelWithString: "Welcome to Gmail Organizer")
        welcomeLabel.frame = NSRect(x: 30, y: y - 32, width: 400, height: 32)
        welcomeLabel.font = NSFont.systemFont(ofSize: 24, weight: .medium)
        welcomeLabel.textColor = GoogleColors.textPrimary
        documentView.addSubview(welcomeLabel)
        y -= 60

        // Show "Load Accounts" button if accounts haven't been loaded yet
        if !accountsLoaded {
            let loadCard = NSView(frame: NSRect(x: 30, y: y - 120, width: bounds.width - 60, height: 120))
            loadCard.wantsLayer = true
            loadCard.layer?.backgroundColor = GoogleColors.blueLight.cgColor
            loadCard.layer?.cornerRadius = 12

            let icon = NSImageView(frame: NSRect(x: (bounds.width - 60 - 48) / 2, y: 65, width: 48, height: 48))
            if let img = NSImage(systemSymbolName: "folder.badge.gearshape", accessibilityDescription: nil) {
                let config = NSImage.SymbolConfiguration(pointSize: 40, weight: .regular)
                    .applying(NSImage.SymbolConfiguration(paletteColors: [GoogleColors.blue]))
                icon.image = img.withSymbolConfiguration(config)
            }
            loadCard.addSubview(icon)

            let loadBtn = NSButton(frame: NSRect(x: (bounds.width - 60 - 180) / 2, y: 15, width: 180, height: 36))
            loadBtn.title = "  Load Synced Accounts"
            loadBtn.bezelStyle = .rounded
            loadBtn.font = NSFont.systemFont(ofSize: 14, weight: .medium)
            loadBtn.target = self
            loadBtn.action = #selector(loadAccountsClicked)
            if let img = NSImage(systemSymbolName: "arrow.clockwise", accessibilityDescription: nil) {
                loadBtn.image = img
                loadBtn.imagePosition = .imageLeft
            }
            loadCard.addSubview(loadBtn)

            let infoLabel = NSTextField(labelWithString: "Click to scan for synced Gmail accounts.\nThis will request folder access permission if needed.")
            infoLabel.frame = NSRect(x: 0, y: 118, width: bounds.width - 60, height: 30)
            infoLabel.alignment = .center
            infoLabel.font = NSFont.systemFont(ofSize: 11, weight: .regular)
            infoLabel.textColor = GoogleColors.textSecondary
            infoLabel.maximumNumberOfLines = 2

            documentView.addSubview(loadCard)
            y -= 140

            contentContainer.addSubview(scrollView)
            return
        }

        // Account status cards
        let cardsTitle = NSTextField(labelWithString: "Synced Accounts (\(accounts.count))")
        cardsTitle.frame = NSRect(x: 30, y: y - 20, width: 200, height: 20)
        cardsTitle.font = NSFont.systemFont(ofSize: 14, weight: .medium)
        cardsTitle.textColor = GoogleColors.textSecondary
        documentView.addSubview(cardsTitle)
        y -= 40

        if accounts.isEmpty {
            let emptyCard = buildEmptyAccountCard(width: bounds.width - 60)
            emptyCard.frame = NSRect(x: 30, y: y - 100, width: bounds.width - 60, height: 100)
            documentView.addSubview(emptyCard)
            y -= 120
        } else {
            // Show ALL accounts in a 2-column grid
            for (index, account) in accounts.enumerated() {
                let card = buildAccountCard(account: account, index: index, width: cardWidth)
                let col = index % 2
                let row = index / 2
                card.frame = NSRect(
                    x: 30 + CGFloat(col) * (cardWidth + 20),
                    y: y - cardHeight - CGFloat(row) * (cardHeight + cardSpacing),
                    width: cardWidth,
                    height: cardHeight
                )
                documentView.addSubview(card)
            }
            y -= CGFloat(accountRows) * (cardHeight + cardSpacing) + 20
        }

        // Quick actions section
        let actionsTitle = NSTextField(labelWithString: "Quick Actions")
        actionsTitle.frame = NSRect(x: 30, y: y - 20, width: 200, height: 20)
        actionsTitle.font = NSFont.systemFont(ofSize: 14, weight: .medium)
        actionsTitle.textColor = GoogleColors.textSecondary
        documentView.addSubview(actionsTitle)
        y -= 45

        let quickActions: [(title: String, icon: String, action: Selector, description: String)] = [
            ("Process Selected Account", "cpu.fill", #selector(processSelectedClicked), "Classify emails using Claude AI"),
            ("Process All Accounts", "arrow.triangle.2.circlepath", #selector(processAllClicked), "Process all synced accounts"),
            ("Open Web Interface", "globe", #selector(openWebClicked), "Full-featured Streamlit web app"),
            ("View Project Folder", "folder.fill", #selector(openFolderClicked), "Open project in Finder")
        ]

        let actionWidth = (bounds.width - 80) / 2
        for (index, action) in quickActions.enumerated() {
            let card = buildQuickActionCard(title: action.title, icon: action.icon, description: action.description, action: action.action, width: actionWidth)
            let col = index % 2
            let row = index / 2
            card.frame = NSRect(
                x: 30 + CGFloat(col) * (actionWidth + 20),
                y: y - 70 - CGFloat(row) * 80,
                width: actionWidth,
                height: 65
            )
            documentView.addSubview(card)
        }

        contentContainer.addSubview(scrollView)
    }

    private func buildEmptyAccountCard(width: CGFloat) -> NSView {
        let card = NSView(frame: NSRect(x: 0, y: 0, width: width, height: 100))
        card.wantsLayer = true
        card.layer?.backgroundColor = GoogleColors.bgSecondary.cgColor
        card.layer?.cornerRadius = 12

        let icon = NSImageView(frame: NSRect(x: (width - 40) / 2, y: 50, width: 40, height: 40))
        if let img = NSImage(systemSymbolName: "envelope.badge.shield.half.filled", accessibilityDescription: nil) {
            let config = NSImage.SymbolConfiguration(pointSize: 32, weight: .regular)
                .applying(NSImage.SymbolConfiguration(paletteColors: [GoogleColors.textTertiary]))
            icon.image = img.withSymbolConfiguration(config)
        }
        card.addSubview(icon)

        let label = NSTextField(labelWithString: "No accounts synced yet")
        label.frame = NSRect(x: 0, y: 25, width: width, height: 20)
        label.alignment = .center
        label.font = NSFont.systemFont(ofSize: 13, weight: .medium)
        label.textColor = GoogleColors.textSecondary
        card.addSubview(label)

        let subLabel = NSTextField(labelWithString: "Use the web interface to add and sync accounts")
        subLabel.frame = NSRect(x: 0, y: 8, width: width, height: 16)
        subLabel.alignment = .center
        subLabel.font = NSFont.systemFont(ofSize: 11, weight: .regular)
        subLabel.textColor = GoogleColors.textTertiary
        card.addSubview(subLabel)

        return card
    }

    private func buildAccountCard(account: AccountInfo, index: Int, width: CGFloat) -> NSView {
        let cardHeight: CGFloat = 100
        let card = NSView(frame: NSRect(x: 0, y: 0, width: width, height: cardHeight))
        card.wantsLayer = true
        card.layer?.backgroundColor = GoogleColors.bgSecondary.cgColor
        card.layer?.cornerRadius = 12

        // Account icon
        let icon = NSImageView(frame: NSRect(x: 16, y: cardHeight - 40, width: 32, height: 32))
        if let img = NSImage(systemSymbolName: "person.circle.fill", accessibilityDescription: nil) {
            let config = NSImage.SymbolConfiguration(pointSize: 28, weight: .regular)
                .applying(NSImage.SymbolConfiguration(paletteColors: [GoogleColors.blue]))
            icon.image = img.withSymbolConfiguration(config)
        }
        card.addSubview(icon)

        // Account name (top right of icon)
        let nameLabel = NSTextField(labelWithString: account.name)
        nameLabel.frame = NSRect(x: 56, y: cardHeight - 32, width: width - 80, height: 20)
        nameLabel.font = NSFont.systemFont(ofSize: 14, weight: .semibold)
        nameLabel.textColor = GoogleColors.textPrimary
        nameLabel.lineBreakMode = .byTruncatingTail
        card.addSubview(nameLabel)

        // Email (below name)
        let emailLabel = NSTextField(labelWithString: account.email)
        emailLabel.frame = NSRect(x: 56, y: cardHeight - 50, width: width - 80, height: 16)
        emailLabel.font = NSFont.systemFont(ofSize: 11, weight: .regular)
        emailLabel.textColor = GoogleColors.textSecondary
        emailLabel.lineBreakMode = .byTruncatingTail
        card.addSubview(emailLabel)

        // Email count badge (on its own line)
        let countBadge = NSTextField(labelWithString: "\(account.emailCount.formatted()) emails")
        countBadge.frame = NSRect(x: 16, y: 38, width: 120, height: 18)
        countBadge.font = NSFont.systemFont(ofSize: 13, weight: .medium)
        countBadge.textColor = GoogleColors.blue
        card.addSubview(countBadge)

        // Last sync time
        let syncText = account.lastSyncTime ?? "Not synced"
        let syncLabel = NSTextField(labelWithString: "Synced: \(syncText)")
        syncLabel.frame = NSRect(x: 16, y: 12, width: width - 100, height: 16)
        syncLabel.font = NSFont.systemFont(ofSize: 10, weight: .regular)
        syncLabel.textColor = GoogleColors.textTertiary
        card.addSubview(syncLabel)

        // Process button (bottom right)
        let processBtn = NSButton(frame: NSRect(x: width - 85, y: 10, width: 75, height: 28))
        processBtn.title = "Process"
        processBtn.bezelStyle = .rounded
        processBtn.font = NSFont.systemFont(ofSize: 12, weight: .medium)
        processBtn.target = self
        processBtn.action = #selector(processAccountClicked(_:))
        processBtn.tag = index
        card.addSubview(processBtn)

        return card
    }

    private func buildQuickActionCard(title: String, icon: String, description: String, action: Selector, width: CGFloat) -> NSView {
        let card = NSButton(frame: NSRect(x: 0, y: 0, width: width, height: 65))
        card.wantsLayer = true
        card.bezelStyle = .regularSquare
        card.isBordered = false
        card.layer?.backgroundColor = GoogleColors.bgSecondary.cgColor
        card.layer?.cornerRadius = 12
        card.target = self
        card.action = action

        let contentView = NSView(frame: card.bounds)
        contentView.wantsLayer = true

        // Icon
        let iconView = NSImageView(frame: NSRect(x: 16, y: 20, width: 24, height: 24))
        if let img = NSImage(systemSymbolName: icon, accessibilityDescription: nil) {
            let config = NSImage.SymbolConfiguration(pointSize: 20, weight: .regular)
                .applying(NSImage.SymbolConfiguration(paletteColors: [GoogleColors.blue]))
            iconView.image = img.withSymbolConfiguration(config)
        }
        contentView.addSubview(iconView)

        // Title
        let titleLabel = NSTextField(labelWithString: title)
        titleLabel.frame = NSRect(x: 48, y: 35, width: width - 70, height: 18)
        titleLabel.font = NSFont.systemFont(ofSize: 13, weight: .medium)
        titleLabel.textColor = GoogleColors.textPrimary
        contentView.addSubview(titleLabel)

        // Description
        let descLabel = NSTextField(labelWithString: description)
        descLabel.frame = NSRect(x: 48, y: 18, width: width - 70, height: 16)
        descLabel.font = NSFont.systemFont(ofSize: 11, weight: .regular)
        descLabel.textColor = GoogleColors.textSecondary
        contentView.addSubview(descLabel)

        card.addSubview(contentView)

        return card
    }

    // MARK: - Emails Screen

    private func buildEmailsScreen() {
        let bounds = contentContainer.bounds
        var y = bounds.height - 30

        // Title
        let titleLabel = NSTextField(labelWithString: "Email Activity")
        titleLabel.frame = NSRect(x: 30, y: y - 28, width: 300, height: 28)
        titleLabel.font = NSFont.systemFont(ofSize: 22, weight: .regular)
        titleLabel.textColor = GoogleColors.textPrimary
        contentContainer.addSubview(titleLabel)
        y -= 50

        // Account info
        if !accounts.isEmpty && selectedAccountIndex < accounts.count {
            let account = accounts[selectedAccountIndex]
            let infoLabel = NSTextField(labelWithString: "\(account.email) - \(account.emailCount.formatted()) emails synced")
            infoLabel.frame = NSRect(x: 30, y: y - 20, width: bounds.width - 60, height: 20)
            infoLabel.font = NSFont.systemFont(ofSize: 13, weight: .regular)
            infoLabel.textColor = GoogleColors.textSecondary
            contentContainer.addSubview(infoLabel)
            y -= 35
        }

        // Filter bar
        let filterBar = buildFilterBar(width: bounds.width - 60)
        filterBar.frame = NSRect(x: 30, y: y - 40, width: bounds.width - 60, height: 40)
        contentContainer.addSubview(filterBar)
        y -= 55

        // Email list (placeholder - would be populated from sync state)
        if emailActivities.isEmpty {
            let emptyLabel = NSTextField(labelWithString: "No email activity to display")
            emptyLabel.frame = NSRect(x: 30, y: y - 40, width: bounds.width - 60, height: 20)
            emptyLabel.font = NSFont.systemFont(ofSize: 13, weight: .regular)
            emptyLabel.textColor = GoogleColors.textSecondary
            contentContainer.addSubview(emptyLabel)

            let helpLabel = NSTextField(labelWithString: "Sync your accounts using the web interface, then return here to view and manage emails.")
            helpLabel.frame = NSRect(x: 30, y: y - 70, width: bounds.width - 60, height: 40)
            helpLabel.font = NSFont.systemFont(ofSize: 12, weight: .regular)
            helpLabel.textColor = GoogleColors.textTertiary
            helpLabel.maximumNumberOfLines = 2
            contentContainer.addSubview(helpLabel)
        } else {
            // Scroll view for emails
            let scrollView = NSScrollView(frame: NSRect(x: 30, y: 20, width: bounds.width - 60, height: y - 40))
            scrollView.hasVerticalScroller = true
            scrollView.borderType = .noBorder
            scrollView.autoresizingMask = [.width, .height]
            contentContainer.addSubview(scrollView)
        }
    }

    private func buildFilterBar(width: CGFloat) -> NSView {
        let bar = NSView(frame: NSRect(x: 0, y: 0, width: width, height: 40))

        // Filter buttons
        let filters = ["All", "Unread", "Starred", "Important", "Job Search", "Subscriptions"]
        var x: CGFloat = 0

        for filter in filters {
            let btn = NSButton(frame: NSRect(x: x, y: 5, width: 80, height: 30))
            btn.title = filter
            btn.bezelStyle = .rounded
            btn.font = NSFont.systemFont(ofSize: 11, weight: .medium)
            btn.target = self
            btn.action = #selector(filterClicked(_:))
            bar.addSubview(btn)
            x += 85
        }

        return bar
    }

    // MARK: - Rules Screen

    private func buildRulesScreen() {
        let bounds = contentContainer.bounds
        var y = bounds.height - 30

        // Title
        let titleLabel = NSTextField(labelWithString: "Automation Rules")
        titleLabel.frame = NSRect(x: 30, y: y - 28, width: 300, height: 28)
        titleLabel.font = NSFont.systemFont(ofSize: 22, weight: .regular)
        titleLabel.textColor = GoogleColors.textPrimary
        contentContainer.addSubview(titleLabel)

        // Add rule button
        let addBtn = NSButton(frame: NSRect(x: bounds.width - 130, y: y - 32, width: 100, height: 32))
        addBtn.title = "Add Rule"
        addBtn.bezelStyle = .rounded
        addBtn.font = NSFont.systemFont(ofSize: 12, weight: .medium)
        addBtn.target = self
        addBtn.action = #selector(addRuleClicked)
        addBtn.autoresizingMask = [.minXMargin]
        contentContainer.addSubview(addBtn)
        y -= 55

        // Description
        let descLabel = NSTextField(labelWithString: "Create rules to automatically organize incoming emails. Rules are processed by Claude Code when you run the Process action.")
        descLabel.frame = NSRect(x: 30, y: y - 40, width: bounds.width - 60, height: 40)
        descLabel.font = NSFont.systemFont(ofSize: 12, weight: .regular)
        descLabel.textColor = GoogleColors.textSecondary
        descLabel.maximumNumberOfLines = 2
        contentContainer.addSubview(descLabel)
        y -= 55

        if automationRules.isEmpty {
            // Empty state
            let emptyCard = buildEmptyRulesCard(width: bounds.width - 60)
            emptyCard.frame = NSRect(x: 30, y: y - 150, width: bounds.width - 60, height: 150)
            contentContainer.addSubview(emptyCard)
        } else {
            // Rule cards
            for (index, rule) in automationRules.enumerated() {
                let card = buildRuleCard(rule: rule, index: index, width: bounds.width - 60)
                card.frame = NSRect(x: 30, y: y - 80, width: bounds.width - 60, height: 70)
                contentContainer.addSubview(card)
                y -= 85
            }
        }

        // Preset rules section
        y -= 30
        let presetsLabel = NSTextField(labelWithString: "Quick Preset Rules")
        presetsLabel.frame = NSRect(x: 30, y: y - 20, width: 200, height: 20)
        presetsLabel.font = NSFont.systemFont(ofSize: 14, weight: .medium)
        presetsLabel.textColor = GoogleColors.textSecondary
        contentContainer.addSubview(presetsLabel)
        y -= 35

        let presets: [(name: String, description: String)] = [
            ("Newsletter Filter", "Auto-label and archive newsletters"),
            ("Job Application Tracker", "Organize job search emails by status"),
            ("Social Media Cleanup", "Archive social notifications"),
            ("Important Sender", "Star emails from specific contacts")
        ]

        let presetWidth = (bounds.width - 80) / 2
        for (index, preset) in presets.enumerated() {
            let card = buildPresetCard(name: preset.name, description: preset.description, width: presetWidth)
            let col = index % 2
            let row = index / 2
            card.frame = NSRect(
                x: 30 + CGFloat(col) * (presetWidth + 20),
                y: y - 60 - CGFloat(row) * 70,
                width: presetWidth,
                height: 55
            )
            contentContainer.addSubview(card)
        }
    }

    private func buildEmptyRulesCard(width: CGFloat) -> NSView {
        let card = NSView(frame: NSRect(x: 0, y: 0, width: width, height: 150))
        card.wantsLayer = true
        card.layer?.backgroundColor = GoogleColors.bgSecondary.cgColor
        card.layer?.cornerRadius = 12
        card.layer?.borderWidth = 1
        card.layer?.borderColor = GoogleColors.border.cgColor

        let icon = NSImageView(frame: NSRect(x: (width - 48) / 2, y: 85, width: 48, height: 48))
        if let img = NSImage(systemSymbolName: "gearshape.2", accessibilityDescription: nil) {
            let config = NSImage.SymbolConfiguration(pointSize: 40, weight: .regular)
                .applying(NSImage.SymbolConfiguration(paletteColors: [GoogleColors.textTertiary]))
            icon.image = img.withSymbolConfiguration(config)
        }
        card.addSubview(icon)

        let label = NSTextField(labelWithString: "No automation rules yet")
        label.frame = NSRect(x: 0, y: 55, width: width, height: 20)
        label.alignment = .center
        label.font = NSFont.systemFont(ofSize: 14, weight: .medium)
        label.textColor = GoogleColors.textPrimary
        card.addSubview(label)

        let subLabel = NSTextField(labelWithString: "Create rules to automatically organize your emails")
        subLabel.frame = NSRect(x: 0, y: 35, width: width, height: 18)
        subLabel.alignment = .center
        subLabel.font = NSFont.systemFont(ofSize: 12, weight: .regular)
        subLabel.textColor = GoogleColors.textSecondary
        card.addSubview(subLabel)

        return card
    }

    private func buildRuleCard(rule: AutomationRule, index: Int, width: CGFloat) -> NSView {
        let card = NSView(frame: NSRect(x: 0, y: 0, width: width, height: 70))
        card.wantsLayer = true
        card.layer?.backgroundColor = GoogleColors.bgSecondary.cgColor
        card.layer?.cornerRadius = 8

        // Toggle
        let toggle = NSSwitch(frame: NSRect(x: 16, y: 22, width: 38, height: 24))
        toggle.state = rule.isEnabled ? .on : .off
        toggle.target = self
        toggle.action = #selector(ruleToggled(_:))
        toggle.tag = index
        card.addSubview(toggle)

        // Rule name
        let nameLabel = NSTextField(labelWithString: rule.name)
        nameLabel.frame = NSRect(x: 65, y: 40, width: width - 180, height: 20)
        nameLabel.font = NSFont.systemFont(ofSize: 14, weight: .medium)
        nameLabel.textColor = GoogleColors.textPrimary
        card.addSubview(nameLabel)

        // Rule summary
        let conditionCount = rule.conditions.count
        let actionCount = rule.actions.count
        let summary = "\(conditionCount) condition\(conditionCount != 1 ? "s" : ""), \(actionCount) action\(actionCount != 1 ? "s" : "")"
        let summaryLabel = NSTextField(labelWithString: summary)
        summaryLabel.frame = NSRect(x: 65, y: 18, width: width - 180, height: 18)
        summaryLabel.font = NSFont.systemFont(ofSize: 12, weight: .regular)
        summaryLabel.textColor = GoogleColors.textSecondary
        card.addSubview(summaryLabel)

        // Edit button
        let editBtn = NSButton(frame: NSRect(x: width - 110, y: 20, width: 50, height: 28))
        editBtn.title = "Edit"
        editBtn.bezelStyle = .rounded
        editBtn.font = NSFont.systemFont(ofSize: 11, weight: .medium)
        editBtn.target = self
        editBtn.action = #selector(editRuleClicked(_:))
        editBtn.tag = index
        card.addSubview(editBtn)

        // Delete button
        let deleteBtn = NSButton(frame: NSRect(x: width - 55, y: 20, width: 45, height: 28))
        deleteBtn.title = "Del"
        deleteBtn.bezelStyle = .rounded
        deleteBtn.font = NSFont.systemFont(ofSize: 11, weight: .medium)
        deleteBtn.target = self
        deleteBtn.action = #selector(deleteRuleClicked(_:))
        deleteBtn.tag = index
        card.addSubview(deleteBtn)

        return card
    }

    private func buildPresetCard(name: String, description: String, width: CGFloat) -> NSView {
        let card = NSButton(frame: NSRect(x: 0, y: 0, width: width, height: 55))
        card.wantsLayer = true
        card.bezelStyle = .regularSquare
        card.isBordered = false
        card.layer?.backgroundColor = NSColor.white.cgColor
        card.layer?.cornerRadius = 8
        card.layer?.borderWidth = 1
        card.layer?.borderColor = GoogleColors.border.cgColor
        card.target = self
        card.action = #selector(presetClicked(_:))
        card.title = name

        let contentView = NSView(frame: card.bounds)
        contentView.wantsLayer = true

        let nameLabel = NSTextField(labelWithString: name)
        nameLabel.frame = NSRect(x: 16, y: 28, width: width - 50, height: 18)
        nameLabel.font = NSFont.systemFont(ofSize: 13, weight: .medium)
        nameLabel.textColor = GoogleColors.textPrimary
        contentView.addSubview(nameLabel)

        let descLabel = NSTextField(labelWithString: description)
        descLabel.frame = NSRect(x: 16, y: 10, width: width - 50, height: 16)
        descLabel.font = NSFont.systemFont(ofSize: 11, weight: .regular)
        descLabel.textColor = GoogleColors.textSecondary
        contentView.addSubview(descLabel)

        let addIcon = NSImageView(frame: NSRect(x: width - 30, y: 18, width: 18, height: 18))
        if let img = NSImage(systemSymbolName: "plus.circle", accessibilityDescription: nil) {
            let config = NSImage.SymbolConfiguration(pointSize: 14, weight: .regular)
                .applying(NSImage.SymbolConfiguration(paletteColors: [GoogleColors.blue]))
            addIcon.image = img.withSymbolConfiguration(config)
        }
        contentView.addSubview(addIcon)

        card.addSubview(contentView)

        return card
    }

    // MARK: - Process Screen

    private func buildProcessScreen() {
        let bounds = contentContainer.bounds

        // Create scroll view for content
        let scrollView = NSScrollView(frame: bounds)
        scrollView.hasVerticalScroller = true
        scrollView.hasHorizontalScroller = false
        scrollView.autoresizingMask = [.width, .height]
        scrollView.drawsBackground = false

        let contentHeight: CGFloat = 900
        let documentView = NSView(frame: NSRect(x: 0, y: 0, width: bounds.width, height: contentHeight))
        scrollView.documentView = documentView

        var y = contentHeight - 30

        // Title
        let titleLabel = NSTextField(labelWithString: "Process Emails with Claude AI")
        titleLabel.frame = NSRect(x: 30, y: y - 32, width: 400, height: 32)
        titleLabel.font = NSFont.systemFont(ofSize: 24, weight: .medium)
        titleLabel.textColor = GoogleColors.textPrimary
        documentView.addSubview(titleLabel)
        y -= 55

        // Description
        let descLabel = NSTextField(labelWithString: "Analyze email patterns, detect threads, extract action items, and organize your inbox intelligently.")
        descLabel.frame = NSRect(x: 30, y: y - 40, width: bounds.width - 60, height: 40)
        descLabel.font = NSFont.systemFont(ofSize: 13, weight: .regular)
        descLabel.textColor = GoogleColors.textSecondary
        descLabel.maximumNumberOfLines = 2
        documentView.addSubview(descLabel)
        y -= 55

        // Analysis Type Selection
        let analysisLabel = NSTextField(labelWithString: "Analysis Type")
        analysisLabel.frame = NSRect(x: 30, y: y - 20, width: 200, height: 20)
        analysisLabel.font = NSFont.systemFont(ofSize: 14, weight: .medium)
        analysisLabel.textColor = GoogleColors.textSecondary
        documentView.addSubview(analysisLabel)
        y -= 30

        // Analysis type cards
        let analysisTypes: [(type: AnalysisType, icon: String, description: String)] = [
            (.fullAnalysis, "doc.text.magnifyingglass", "Complete inbox analysis with thread mapping, sender reputation, patterns, and smart labeling"),
            (.threadAnalysis, "bubble.left.and.bubble.right", "Map email conversations, find threads needing response, track discussion status"),
            (.actionItems, "checklist", "Extract tasks, deadlines, questions, and commitments from emails"),
            (.senderReputation, "person.2", "Analyze sender relationships, engagement patterns, and contact importance"),
            (.patternDetection, "chart.bar.xaxis", "Detect time patterns, volume trends, and communication anomalies")
        ]

        let cardWidth = (bounds.width - 80) / 2
        for (index, item) in analysisTypes.enumerated() {
            let card = buildAnalysisTypeCard(
                type: item.type,
                icon: item.icon,
                description: item.description,
                isSelected: selectedAnalysisType == item.type,
                width: cardWidth
            )
            let col = index % 2
            let row = index / 2
            card.frame = NSRect(
                x: 30 + CGFloat(col) * (cardWidth + 20),
                y: y - 80 - CGFloat(row) * 90,
                width: cardWidth,
                height: 80
            )
            card.tag = index
            documentView.addSubview(card)
        }
        y -= CGFloat((analysisTypes.count + 1) / 2) * 90 + 20

        // Processing status card
        let statusCard = buildProcessingStatusCard(width: bounds.width - 60)
        statusCard.frame = NSRect(x: 30, y: y - 100, width: bounds.width - 60, height: 100)
        documentView.addSubview(statusCard)
        y -= 120

        // Account selection for processing
        let accountLabel = NSTextField(labelWithString: "Select Account to Process")
        accountLabel.frame = NSRect(x: 30, y: y - 20, width: 250, height: 20)
        accountLabel.font = NSFont.systemFont(ofSize: 14, weight: .medium)
        accountLabel.textColor = GoogleColors.textSecondary
        documentView.addSubview(accountLabel)
        y -= 35

        if accounts.isEmpty {
            let noAccountLabel = NSTextField(labelWithString: "No synced accounts available. Use the web interface to sync your Gmail accounts first.")
            noAccountLabel.frame = NSRect(x: 30, y: y - 40, width: bounds.width - 60, height: 40)
            noAccountLabel.font = NSFont.systemFont(ofSize: 12, weight: .regular)
            noAccountLabel.textColor = GoogleColors.textTertiary
            noAccountLabel.maximumNumberOfLines = 2
            documentView.addSubview(noAccountLabel)
        } else {
            for (index, account) in accounts.enumerated() {
                let row = buildProcessAccountRow(account: account, index: index, width: bounds.width - 60)
                row.frame = NSRect(x: 30, y: y - 55, width: bounds.width - 60, height: 50)
                documentView.addSubview(row)
                y -= 58
            }
        }

        // Parallel processing toggle
        y -= 20
        let parallelCard = NSView(frame: NSRect(x: 30, y: y - 60, width: bounds.width - 60, height: 60))
        parallelCard.wantsLayer = true
        parallelCard.layer?.backgroundColor = useParallelProcessing ? GoogleColors.blueLight.cgColor : GoogleColors.bgSecondary.cgColor
        parallelCard.layer?.cornerRadius = 10
        parallelCard.layer?.borderWidth = useParallelProcessing ? 2 : 1
        parallelCard.layer?.borderColor = useParallelProcessing ? GoogleColors.blue.cgColor : GoogleColors.border.cgColor

        let parallelIcon = NSImageView(frame: NSRect(x: 16, y: 18, width: 24, height: 24))
        if let img = NSImage(systemSymbolName: "rectangle.split.3x3", accessibilityDescription: nil) {
            let iconColor = useParallelProcessing ? GoogleColors.blue : GoogleColors.textSecondary
            let config = NSImage.SymbolConfiguration(pointSize: 20, weight: .regular)
                .applying(NSImage.SymbolConfiguration(paletteColors: [iconColor]))
            parallelIcon.image = img.withSymbolConfiguration(config)
        }
        parallelCard.addSubview(parallelIcon)

        let parallelTitle = NSTextField(labelWithString: "Parallel Processing (Recommended)")
        parallelTitle.frame = NSRect(x: 50, y: 32, width: 300, height: 18)
        parallelTitle.font = NSFont.systemFont(ofSize: 14, weight: .semibold)
        parallelTitle.textColor = useParallelProcessing ? GoogleColors.blue : GoogleColors.textPrimary
        parallelCard.addSubview(parallelTitle)

        let parallelDesc = NSTextField(labelWithString: "Use multiple Haiku workers for faster processing with embedded terminals")
        parallelDesc.frame = NSRect(x: 50, y: 12, width: bounds.width - 180, height: 16)
        parallelDesc.font = NSFont.systemFont(ofSize: 11, weight: .regular)
        parallelDesc.textColor = GoogleColors.textSecondary
        parallelCard.addSubview(parallelDesc)

        let parallelToggle = NSSwitch(frame: NSRect(x: bounds.width - 120, y: 18, width: 38, height: 24))
        parallelToggle.state = useParallelProcessing ? .on : .off
        parallelToggle.target = self
        parallelToggle.action = #selector(toggleParallelProcessing(_:))
        parallelCard.addSubview(parallelToggle)

        documentView.addSubview(parallelCard)
        y -= 80

        // Process all button
        let processAllBtn = NSButton(frame: NSRect(x: 30, y: y - 40, width: 200, height: 36))
        processAllBtn.title = "  Process All Accounts"
        processAllBtn.bezelStyle = .rounded
        processAllBtn.font = NSFont.systemFont(ofSize: 13, weight: .medium)
        processAllBtn.target = self
        processAllBtn.action = #selector(processAllClicked)
        if let img = NSImage(systemSymbolName: "arrow.triangle.2.circlepath", accessibilityDescription: nil) {
            let config = NSImage.SymbolConfiguration(pointSize: 14, weight: .regular)
            processAllBtn.image = img.withSymbolConfiguration(config)
            processAllBtn.imagePosition = .imageLeft
        }
        documentView.addSubview(processAllBtn)

        contentContainer.addSubview(scrollView)
    }

    private func buildAnalysisTypeCard(type: AnalysisType, icon: String, description: String, isSelected: Bool, width: CGFloat) -> NSButton {
        let card = NSButton(frame: NSRect(x: 0, y: 0, width: width, height: 80))
        card.wantsLayer = true
        card.bezelStyle = .regularSquare
        card.isBordered = false
        card.target = self
        card.action = #selector(analysisTypeClicked(_:))
        card.title = type.rawValue

        if isSelected {
            card.layer?.backgroundColor = GoogleColors.blueLight.cgColor
            card.layer?.borderColor = GoogleColors.blue.cgColor
            card.layer?.borderWidth = 2
        } else {
            card.layer?.backgroundColor = GoogleColors.bgSecondary.cgColor
            card.layer?.borderColor = GoogleColors.border.cgColor
            card.layer?.borderWidth = 1
        }
        card.layer?.cornerRadius = 10

        let contentView = NSView(frame: card.bounds)
        contentView.wantsLayer = true

        // Icon
        let iconView = NSImageView(frame: NSRect(x: 16, y: 28, width: 24, height: 24))
        if let img = NSImage(systemSymbolName: icon, accessibilityDescription: nil) {
            let iconColor = isSelected ? GoogleColors.blue : GoogleColors.textSecondary
            let config = NSImage.SymbolConfiguration(pointSize: 20, weight: .regular)
                .applying(NSImage.SymbolConfiguration(paletteColors: [iconColor]))
            iconView.image = img.withSymbolConfiguration(config)
        }
        contentView.addSubview(iconView)

        // Title
        let titleLabel = NSTextField(labelWithString: type.rawValue)
        titleLabel.frame = NSRect(x: 48, y: 48, width: width - 65, height: 20)
        titleLabel.font = NSFont.systemFont(ofSize: 14, weight: .semibold)
        titleLabel.textColor = isSelected ? GoogleColors.blue : GoogleColors.textPrimary
        contentView.addSubview(titleLabel)

        // Description
        let descLabel = NSTextField(labelWithString: description)
        descLabel.frame = NSRect(x: 48, y: 10, width: width - 65, height: 36)
        descLabel.font = NSFont.systemFont(ofSize: 11, weight: .regular)
        descLabel.textColor = GoogleColors.textSecondary
        descLabel.maximumNumberOfLines = 2
        descLabel.lineBreakMode = .byWordWrapping
        contentView.addSubview(descLabel)

        // Selected indicator
        if isSelected {
            let checkView = NSImageView(frame: NSRect(x: width - 28, y: 52, width: 18, height: 18))
            if let img = NSImage(systemSymbolName: "checkmark.circle.fill", accessibilityDescription: nil) {
                let config = NSImage.SymbolConfiguration(pointSize: 16, weight: .regular)
                    .applying(NSImage.SymbolConfiguration(paletteColors: [GoogleColors.blue]))
                checkView.image = img.withSymbolConfiguration(config)
            }
            contentView.addSubview(checkView)
        }

        card.addSubview(contentView)
        return card
    }

    @objc private func analysisTypeClicked(_ sender: NSButton) {
        let types: [AnalysisType] = [.fullAnalysis, .threadAnalysis, .actionItems, .senderReputation, .patternDetection]
        if sender.tag < types.count {
            selectedAnalysisType = types[sender.tag]
            showScreen(.process)
        }
    }

    private func buildProcessingStatusCard(width: CGFloat) -> NSView {
        let card = NSView(frame: NSRect(x: 0, y: 0, width: width, height: 100))
        card.wantsLayer = true
        card.layer?.backgroundColor = GoogleColors.bgSecondary.cgColor
        card.layer?.cornerRadius = 12

        // Status icon
        let iconView = NSImageView(frame: NSRect(x: 20, y: 38, width: 24, height: 24))
        if let img = NSImage(systemSymbolName: processingStatus.icon, accessibilityDescription: nil) {
            let config = NSImage.SymbolConfiguration(pointSize: 20, weight: .regular)
                .applying(NSImage.SymbolConfiguration(paletteColors: [processingStatus.color]))
            iconView.image = img.withSymbolConfiguration(config)
        }
        card.addSubview(iconView)

        // Status text
        let statusText: String
        let subtitleText: String

        switch processingStatus {
        case .idle:
            statusText = "Ready to Process"
            subtitleText = "Select an account and click Process to start"
        case .analyzing(_, let message):
            statusText = "Analyzing..."
            subtitleText = message
        case .processing(let progress, let current, let total):
            statusText = "Processing Emails"
            subtitleText = "Email \(current) of \(total) (\(Int(progress * 100))%)"
        case .complete(let processed, let errors):
            statusText = "Processing Complete"
            subtitleText = "\(processed) emails processed" + (errors > 0 ? ", \(errors) errors" : "")
        case .error(let message):
            statusText = "Error"
            subtitleText = message
        }

        let statusLabel = NSTextField(labelWithString: statusText)
        statusLabel.frame = NSRect(x: 54, y: 55, width: width - 80, height: 22)
        statusLabel.font = NSFont.systemFont(ofSize: 16, weight: .medium)
        statusLabel.textColor = GoogleColors.textPrimary
        card.addSubview(statusLabel)

        let subtitleLabel = NSTextField(labelWithString: subtitleText)
        subtitleLabel.frame = NSRect(x: 54, y: 35, width: width - 80, height: 18)
        subtitleLabel.font = NSFont.systemFont(ofSize: 12, weight: .regular)
        subtitleLabel.textColor = GoogleColors.textSecondary
        card.addSubview(subtitleLabel)

        // Progress bar (if processing)
        if case .processing(let progress, _, _) = processingStatus {
            let progressBg = NSView(frame: NSRect(x: 20, y: 15, width: width - 40, height: 4))
            progressBg.wantsLayer = true
            progressBg.layer?.backgroundColor = GoogleColors.border.cgColor
            progressBg.layer?.cornerRadius = 2
            card.addSubview(progressBg)

            let progressFill = NSView(frame: NSRect(x: 20, y: 15, width: (width - 40) * CGFloat(progress), height: 4))
            progressFill.wantsLayer = true
            progressFill.layer?.backgroundColor = GoogleColors.blue.cgColor
            progressFill.layer?.cornerRadius = 2
            card.addSubview(progressFill)
        }

        return card
    }

    private func buildProcessAccountRow(account: AccountInfo, index: Int, width: CGFloat) -> NSView {
        let row = NSView(frame: NSRect(x: 0, y: 0, width: width, height: 45))
        row.wantsLayer = true
        row.layer?.backgroundColor = NSColor.white.cgColor
        row.layer?.borderWidth = 1
        row.layer?.borderColor = GoogleColors.border.cgColor
        row.layer?.cornerRadius = 8

        // Account icon
        let icon = NSImageView(frame: NSRect(x: 12, y: 10, width: 24, height: 24))
        if let img = NSImage(systemSymbolName: "envelope.fill", accessibilityDescription: nil) {
            let config = NSImage.SymbolConfiguration(pointSize: 18, weight: .regular)
                .applying(NSImage.SymbolConfiguration(paletteColors: [GoogleColors.gmailRed]))
            icon.image = img.withSymbolConfiguration(config)
        }
        row.addSubview(icon)

        // Account info
        let nameLabel = NSTextField(labelWithString: account.email)
        nameLabel.frame = NSRect(x: 44, y: 22, width: width - 200, height: 18)
        nameLabel.font = NSFont.systemFont(ofSize: 13, weight: .medium)
        nameLabel.textColor = GoogleColors.textPrimary
        nameLabel.lineBreakMode = .byTruncatingTail
        row.addSubview(nameLabel)

        let countLabel = NSTextField(labelWithString: "\(account.emailCount.formatted()) emails")
        countLabel.frame = NSRect(x: 44, y: 6, width: width - 200, height: 16)
        countLabel.font = NSFont.systemFont(ofSize: 11, weight: .regular)
        countLabel.textColor = GoogleColors.textSecondary
        row.addSubview(countLabel)

        // Process button
        let processBtn = NSButton(frame: NSRect(x: width - 90, y: 8, width: 80, height: 28))
        processBtn.title = "Process"
        processBtn.bezelStyle = .rounded
        processBtn.font = NSFont.systemFont(ofSize: 12, weight: .medium)
        processBtn.target = self
        processBtn.action = #selector(processAccountClicked(_:))
        processBtn.tag = index
        row.addSubview(processBtn)

        return row
    }

    // MARK: - Settings Screen

    private func buildSettingsScreen() {
        let bounds = contentContainer.bounds
        var y = bounds.height - 30

        // Title
        let titleLabel = NSTextField(labelWithString: "Settings")
        titleLabel.frame = NSRect(x: 30, y: y - 28, width: 200, height: 28)
        titleLabel.font = NSFont.systemFont(ofSize: 22, weight: .regular)
        titleLabel.textColor = GoogleColors.textPrimary
        contentContainer.addSubview(titleLabel)
        y -= 55

        // Sections
        let sections: [(title: String, items: [(label: String, type: SettingType)])] = [
            ("Processing", [
                ("Classification Method", .popup(options: ["Claude Code (CLI)", "Claude API", "Manual"])),
                ("Auto-apply labels", .toggle),
                ("Confirm before applying", .toggle)
            ]),
            ("Sync", [
                ("Auto-sync on launch", .toggle),
                ("Sync interval", .popup(options: ["Manual", "Every hour", "Every 6 hours", "Daily"])),
                ("Keep local cache", .toggle)
            ]),
            ("Appearance", [
                ("Show in menu bar", .toggle),
                ("Show notifications", .toggle),
                ("Launch at login", .toggle)
            ])
        ]

        for section in sections {
            // Section title
            let sectionLabel = NSTextField(labelWithString: section.title)
            sectionLabel.frame = NSRect(x: 30, y: y - 20, width: 200, height: 20)
            sectionLabel.font = NSFont.systemFont(ofSize: 14, weight: .medium)
            sectionLabel.textColor = GoogleColors.textSecondary
            contentContainer.addSubview(sectionLabel)
            y -= 35

            // Section items
            for item in section.items {
                let row = buildSettingRow(label: item.label, type: item.type, width: bounds.width - 60)
                row.frame = NSRect(x: 30, y: y - 40, width: bounds.width - 60, height: 40)
                contentContainer.addSubview(row)
                y -= 45
            }

            y -= 15
        }

        // About section
        let aboutLabel = NSTextField(labelWithString: "About")
        aboutLabel.frame = NSRect(x: 30, y: y - 20, width: 200, height: 20)
        aboutLabel.font = NSFont.systemFont(ofSize: 14, weight: .medium)
        aboutLabel.textColor = GoogleColors.textSecondary
        contentContainer.addSubview(aboutLabel)
        y -= 40

        let versionInfo = NSTextField(labelWithString: "Gmail Organizer Helper v1.0.0")
        versionInfo.frame = NSRect(x: 30, y: y - 16, width: 300, height: 16)
        versionInfo.font = NSFont.systemFont(ofSize: 12, weight: .regular)
        versionInfo.textColor = GoogleColors.textTertiary
        contentContainer.addSubview(versionInfo)
    }

    enum SettingType {
        case toggle
        case popup(options: [String])
        case button(title: String)
    }

    private func buildSettingRow(label: String, type: SettingType, width: CGFloat) -> NSView {
        let row = NSView(frame: NSRect(x: 0, y: 0, width: width, height: 40))

        let labelField = NSTextField(labelWithString: label)
        labelField.frame = NSRect(x: 0, y: 10, width: width - 200, height: 20)
        labelField.font = NSFont.systemFont(ofSize: 13, weight: .regular)
        labelField.textColor = GoogleColors.textPrimary
        row.addSubview(labelField)

        switch type {
        case .toggle:
            let toggle = NSSwitch(frame: NSRect(x: width - 50, y: 8, width: 38, height: 24))
            toggle.state = .on
            row.addSubview(toggle)

        case .popup(let options):
            let popup = NSPopUpButton(frame: NSRect(x: width - 180, y: 5, width: 180, height: 30))
            popup.removeAllItems()
            popup.addItems(withTitles: options)
            row.addSubview(popup)

        case .button(let title):
            let btn = NSButton(frame: NSRect(x: width - 100, y: 5, width: 100, height: 30))
            btn.title = title
            btn.bezelStyle = .rounded
            row.addSubview(btn)
        }

        return row
    }

    // MARK: - Data Loading

    private func loadData() {
        accounts = ProcessingManager.shared.getAvailableAccounts()
        accountsLoaded = true
        loadRules()
    }

    @objc private func loadAccountsClicked() {
        // This will trigger file system access and permission prompt
        loadData()
        buildLayout(in: window.contentView!)
        showNotification(title: "Accounts Loaded", body: "Found \(accounts.count) synced account(s)")
    }

    private func loadRules() {
        let rulesPath = Paths.projectRoot + "/.automation-rules.json"
        if let data = FileManager.default.contents(atPath: rulesPath),
           let rules = try? JSONDecoder().decode([AutomationRule].self, from: data) {
            automationRules = rules
        } else {
            automationRules = []
        }
    }

    private func saveRules() {
        let rulesPath = Paths.projectRoot + "/.automation-rules.json"
        if let data = try? JSONEncoder().encode(automationRules) {
            try? data.write(to: URL(fileURLWithPath: rulesPath))
        }
    }

    // MARK: - Public Methods

    func show(near statusItem: NSStatusItem) {
        // Only rebuild if needed - don't force load data on every show
        buildLayout(in: window.contentView!)

        if let button = statusItem.button, let buttonWindow = button.window {
            let buttonFrame = button.convert(button.bounds, to: nil)
            let screenFrame = buttonWindow.convertToScreen(buttonFrame)
            let windowFrame = window.frame

            var x = screenFrame.midX - windowFrame.width / 2
            let y = screenFrame.minY - windowFrame.height - 5

            if let screen = NSScreen.main {
                let screenRight = screen.visibleFrame.maxX
                if x + windowFrame.width > screenRight {
                    x = screenRight - windowFrame.width - 10
                }
                if x < screen.visibleFrame.minX {
                    x = screen.visibleFrame.minX + 10
                }
            }

            window.setFrameOrigin(NSPoint(x: x, y: y))
        } else {
            window.center()
        }

        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func hide() {
        window.orderOut(nil)
    }

    func refreshData() {
        loadData()
        if window.isVisible {
            showScreen(selectedNav)
        }
    }

    // MARK: - Actions

    @objc private func navItemClicked(_ sender: NSButton) {
        guard let item = NavigationItem.allCases[safe: sender.tag] else { return }
        selectedNav = item
        updateNavSelection()
        showScreen(item)
    }

    @objc private func accountSelected(_ sender: NSPopUpButton) {
        selectedAccountIndex = sender.indexOfSelectedItem
    }

    @objc private func addAccountClicked() {
        onAddAccount?()
    }

    @objc private func refreshClicked() {
        loadData()
        buildLayout(in: window.contentView!)
        showNotification(title: "Refreshed", body: "Account data refreshed")
    }

    @objc private func openWebClicked() {
        onOpenWebInterface?()
    }

    @objc private func openFolderClicked() {
        onOpenProjectFolder?()
    }

    @objc private func processAccountClicked(_ sender: NSButton) {
        guard sender.tag < accounts.count else { return }
        let account = accounts[sender.tag]

        if useParallelProcessing {
            // Launch parallel processing with embedded terminals
            hide()
            processingPanel = ProcessingPanelController()
            processingPanel?.show()
            processingPanel?.startProcessing(account: account)
        } else {
            // Use single-threaded processing (original behavior)
            hide()
            ProcessingManager.shared.processWithClaudeCode(accountName: account.name, analysisType: selectedAnalysisType)
        }
    }

    @objc private func processSelectedClicked() {
        guard selectedAccountIndex < accounts.count else { return }
        let account = accounts[selectedAccountIndex]

        if useParallelProcessing {
            hide()
            processingPanel = ProcessingPanelController()
            processingPanel?.show()
            processingPanel?.startProcessing(account: account)
        } else {
            hide()
            onProcessAccount?(account.name)
        }
    }

    @objc private func processAllClicked() {
        // For process all, use parallel for first account
        // TODO: Could queue all accounts
        if useParallelProcessing && !accounts.isEmpty {
            hide()
            processingPanel = ProcessingPanelController()
            processingPanel?.show()
            processingPanel?.startProcessing(account: accounts[0])
        } else {
            hide()
            onProcessAllAccounts?()
        }
    }

    @objc private func toggleParallelProcessing(_ sender: NSButton) {
        useParallelProcessing = sender.state == .on
    }

    @objc private func filterClicked(_ sender: NSButton) {
        // Handle filter selection
    }

    @objc private func addRuleClicked() {
        // Show add rule dialog
        showAddRuleDialog()
    }

    @objc private func editRuleClicked(_ sender: NSButton) {
        guard sender.tag < automationRules.count else { return }
        showEditRuleDialog(index: sender.tag)
    }

    @objc private func deleteRuleClicked(_ sender: NSButton) {
        guard sender.tag < automationRules.count else { return }
        let alert = NSAlert()
        alert.messageText = "Delete Rule?"
        alert.informativeText = "Are you sure you want to delete the rule '\(automationRules[sender.tag].name)'?"
        alert.addButton(withTitle: "Delete")
        alert.addButton(withTitle: "Cancel")
        alert.alertStyle = .warning

        if alert.runModal() == .alertFirstButtonReturn {
            automationRules.remove(at: sender.tag)
            saveRules()
            showScreen(.rules)
        }
    }

    @objc private func ruleToggled(_ sender: NSSwitch) {
        guard sender.tag < automationRules.count else { return }
        automationRules[sender.tag].isEnabled = sender.state == .on
        saveRules()
    }

    @objc private func presetClicked(_ sender: NSButton) {
        // Add preset rule
        let presetName = sender.title
        var newRule = AutomationRule(
            id: UUID(),
            name: presetName,
            isEnabled: true,
            conditions: [],
            actions: []
        )

        // Configure based on preset
        switch presetName {
        case "Newsletter Filter":
            newRule.conditions = [
                AutomationRule.RuleCondition(field: .from, matchType: .contains, value: "newsletter"),
                AutomationRule.RuleCondition(field: .subject, matchType: .contains, value: "unsubscribe")
            ]
            newRule.actions = [
                AutomationRule.RuleAction(actionType: .applyLabel, value: "Newsletters"),
                AutomationRule.RuleAction(actionType: .archive, value: "")
            ]
        case "Job Application Tracker":
            newRule.conditions = [
                AutomationRule.RuleCondition(field: .subject, matchType: .contains, value: "application")
            ]
            newRule.actions = [
                AutomationRule.RuleAction(actionType: .applyLabel, value: "Job Search/Applications")
            ]
        default:
            break
        }

        automationRules.append(newRule)
        saveRules()
        showScreen(.rules)
    }

    private func showAddRuleDialog() {
        let alert = NSAlert()
        alert.messageText = "Add Automation Rule"
        alert.informativeText = "Enter a name for the new rule:"
        alert.addButton(withTitle: "Create")
        alert.addButton(withTitle: "Cancel")

        let input = NSTextField(frame: NSRect(x: 0, y: 0, width: 250, height: 24))
        input.stringValue = "New Rule"
        alert.accessoryView = input

        if alert.runModal() == .alertFirstButtonReturn {
            let newRule = AutomationRule(
                id: UUID(),
                name: input.stringValue,
                isEnabled: true,
                conditions: [],
                actions: []
            )
            automationRules.append(newRule)
            saveRules()
            showScreen(.rules)
        }
    }

    private func showEditRuleDialog(index: Int) {
        let alert = NSAlert()
        alert.messageText = "Edit Rule"
        alert.informativeText = "Edit rule name:"
        alert.addButton(withTitle: "Save")
        alert.addButton(withTitle: "Cancel")

        let input = NSTextField(frame: NSRect(x: 0, y: 0, width: 250, height: 24))
        input.stringValue = automationRules[index].name
        alert.accessoryView = input

        if alert.runModal() == .alertFirstButtonReturn {
            automationRules[index].name = input.stringValue
            saveRules()
            showScreen(.rules)
        }
    }
}

// MARK: - Array Extension

extension Array {
    subscript(safe index: Int) -> Element? {
        return indices.contains(index) ? self[index] : nil
    }
}
