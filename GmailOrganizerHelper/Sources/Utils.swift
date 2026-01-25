import Cocoa
import UserNotifications

// MARK: - Paths

struct Paths {
    static let projectRoot = NSString(string: "~/Desktop/Projects/PersonalProjects/gmail-organizer").expandingTildeInPath
    static let syncStateDir = projectRoot + "/.sync-state"
    static let processingDir = projectRoot + "/.processing"

    static func syncStatePath(_ email: String) -> String {
        let safeEmail = email.replacingOccurrences(of: "@", with: "_at_")
                             .replacingOccurrences(of: ".", with: "_")
        return syncStateDir + "/sync_state_\(safeEmail).json"
    }

    static func processingPromptPath(_ accountName: String) -> String {
        return processingDir + "/\(accountName)_prompt.md"
    }
}

// MARK: - Shell Utilities

func runShellCommand(_ command: String, at directory: String? = nil) -> (output: String, exitCode: Int32) {
    let task = Process()
    let pipe = Pipe()

    task.standardOutput = pipe
    task.standardError = pipe
    task.arguments = ["-c", command]
    task.executableURL = URL(fileURLWithPath: "/bin/zsh")

    if let dir = directory {
        task.currentDirectoryURL = URL(fileURLWithPath: dir)
    }

    do {
        try task.run()
        task.waitUntilExit()

        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let output = String(data: data, encoding: .utf8) ?? ""

        return (output, task.terminationStatus)
    } catch {
        return ("Error: \(error.localizedDescription)", 1)
    }
}

// MARK: - Terminal Launching

func openInTerminal(_ path: String) {
    let script = """
    tell application "Terminal"
        activate
        do script "cd '\(path)'"
    end tell
    """
    _ = runAppleScript(script)
}

func launchClaudeCode(at directory: String, withPrompt prompt: String? = nil) {
    // Use full path to claude since AppleScript Terminal may not have full PATH
    let claudePath = NSString(string: "~/.local/bin/claude").expandingTildeInPath
    var command = "cd '\(directory)' && '\(claudePath)'"
    if let prompt = prompt {
        // Escape the prompt for shell
        let escaped = prompt.replacingOccurrences(of: "'", with: "'\\''")
        command += " --print '\(escaped)'"
    }

    let script = """
    tell application "Terminal"
        activate
        do script "\(command)"
    end tell
    """

    _ = runAppleScript(script)
}

func launchClaudeCodeInteractive(at directory: String, promptFile: String? = nil) {
    // Use full path to claude since AppleScript Terminal may not have full PATH
    let claudePath = NSString(string: "~/.local/bin/claude").expandingTildeInPath
    let script = """
    tell application "Terminal"
        activate
        do script "cd '\(directory)' && '\(claudePath)'"
    end tell
    """

    // If there's a prompt file, copy a helpful message to clipboard
    if let promptFile = promptFile {
        let message = "Read \(promptFile) and follow the instructions."
        copyToClipboard(message)
    }

    _ = runAppleScript(script)
}

/// Launch Claude Code with a prompt file - auto-executes the prompt
/// model: "sonnet" (default, balanced), "haiku" (fast/cheap), "opus" (most capable)
func launchClaudeCodeWithPromptFile(at directory: String, promptFile: String, model: String = "sonnet") {
    // Use claude with -p flag to pass the prompt directly
    // The prompt tells Claude to read the file
    let prompt = "Read \(promptFile) and follow the instructions to classify and label the emails for this Gmail account. Use the existing OAuth credentials in the credentials/ folder."
    let escaped = prompt.replacingOccurrences(of: "\"", with: "\\\"")

    // Use full path to claude since AppleScript Terminal may not have full PATH
    // Use --dangerously-skip-permissions to auto-approve file/bash operations
    let claudePath = NSString(string: "~/.local/bin/claude").expandingTildeInPath
    let command = "cd '\(directory)' && '\(claudePath)' --model \(model) --dangerously-skip-permissions -p \"\(escaped)\""

    // AppleScript that creates Terminal window centered on the main screen
    let script = """
    tell application "Terminal"
        -- Create new window with the command
        do script "\(command)"
        activate

        -- Get the frontmost window
        set frontWindow to front window

        -- Get screen dimensions (main screen)
        tell application "Finder"
            set screenBounds to bounds of window of desktop
            set screenWidth to item 3 of screenBounds
            set screenHeight to item 4 of screenBounds
        end tell

        -- Set window size (width: 1000, height: 700)
        set windowWidth to 1000
        set windowHeight to 700

        -- Calculate center position
        set xPos to (screenWidth - windowWidth) / 2
        set yPos to (screenHeight - windowHeight) / 2

        -- Position and resize the window
        set bounds of frontWindow to {xPos, yPos, xPos + windowWidth, yPos + windowHeight}

        -- Bring to front
        set index of frontWindow to 1
    end tell

    -- Ensure Terminal is frontmost application
    tell application "System Events"
        set frontmost of process "Terminal" to true
    end tell
    """

    // Try AppleScript first
    if !runAppleScript(script) {
        // Fallback: Create a shell script and open it with Terminal
        let shellScript = """
        #!/bin/zsh
        # ============================================================
        # Gmail Organizer - Email Processing
        # ============================================================
        # This script launches Claude Code to analyze and organize
        # your Gmail inbox. Progress will be displayed below.
        # ============================================================

        echo ""
        echo "============================================================"
        echo "  GMAIL ORGANIZER - Starting Email Processing"
        echo "============================================================"
        echo ""
        echo "  Working directory: \(directory)"
        echo "  Prompt file: \(promptFile)"
        echo ""
        echo "  Claude Code is analyzing your emails..."
        echo "  This may take a few minutes depending on inbox size."
        echo ""
        echo "============================================================"
        echo ""

        # Run claude with auto-approval for file operations
        \(command)

        echo ""
        echo "============================================================"
        echo "  Processing complete!"
        echo "  Check .processing-results/ for saved analysis data."
        echo "============================================================"
        echo ""
        """
        let scriptPath = directory + "/.run-claude.sh"
        try? shellScript.write(toFile: scriptPath, atomically: true, encoding: .utf8)

        // Make executable and open with Terminal
        let chmod = Process()
        chmod.executableURL = URL(fileURLWithPath: "/bin/chmod")
        chmod.arguments = ["+x", scriptPath]
        try? chmod.run()
        chmod.waitUntilExit()

        // Open the script with Terminal using open command
        let openProcess = Process()
        openProcess.executableURL = URL(fileURLWithPath: "/usr/bin/open")
        openProcess.arguments = ["-a", "Terminal", scriptPath]
        try? openProcess.run()
    }
}

/// Run Claude Code completely in background (no Terminal window)
func runClaudeCodeBackground(at directory: String, prompt: String, completion: @escaping (Bool, String) -> Void) {
    DispatchQueue.global(qos: .userInitiated).async {
        let escaped = prompt.replacingOccurrences(of: "\"", with: "\\\"")
        // Use full path to claude
        let claudePath = NSString(string: "~/.local/bin/claude").expandingTildeInPath
        let command = "cd '\(directory)' && '\(claudePath)' -p \"\(escaped)\" 2>&1"

        let result = runShellCommand(command)

        DispatchQueue.main.async {
            completion(result.exitCode == 0, result.output)
        }
    }
}

private func runAppleScript(_ source: String) -> Bool {
    if let script = NSAppleScript(source: source) {
        var error: NSDictionary?
        script.executeAndReturnError(&error)
        if let error = error {
            print("AppleScript error: \(error)")
            // Show notification about permission issue
            if let errorNum = error["NSAppleScriptErrorNumber"] as? Int, errorNum == -1743 {
                showNotification(
                    title: "Permission Required",
                    body: "Please enable Terminal access in System Preferences > Privacy & Security > Automation"
                )
            }
            return false
        }
        return true
    }
    return false
}

// MARK: - Clipboard

func copyToClipboard(_ text: String) {
    NSPasteboard.general.clearContents()
    NSPasteboard.general.setString(text, forType: .string)
}

// MARK: - Notifications

func showNotification(title: String, body: String) {
    let content = UNMutableNotificationContent()
    content.title = title
    content.body = body
    content.sound = .default

    let request = UNNotificationRequest(
        identifier: UUID().uuidString,
        content: content,
        trigger: nil
    )

    UNUserNotificationCenter.current().add(request) { error in
        if let error = error {
            print("Notification error: \(error)")
        }
    }
}

// MARK: - File Utilities

func fileExists(_ path: String) -> Bool {
    return FileManager.default.fileExists(atPath: path)
}

func readFile(_ path: String) -> String? {
    do {
        return try String(contentsOfFile: path, encoding: .utf8)
    } catch {
        return nil
    }
}

func writeFile(_ content: String, to path: String) -> Bool {
    do {
        // Create parent directory if needed
        let parentDir = (path as NSString).deletingLastPathComponent
        try FileManager.default.createDirectory(atPath: parentDir, withIntermediateDirectories: true)

        try content.write(toFile: path, atomically: true, encoding: .utf8)
        return true
    } catch {
        print("Error writing file: \(error)")
        return false
    }
}

// MARK: - JSON Utilities

func parseJSON<T>(_ data: Data) -> T? where T: Decodable {
    do {
        return try JSONDecoder().decode(T.self, from: data)
    } catch {
        return nil
    }
}

func parseJSONFile<T>(_ path: String) -> T? where T: Decodable {
    guard let data = FileManager.default.contents(atPath: path) else {
        return nil
    }
    return parseJSON(data)
}
