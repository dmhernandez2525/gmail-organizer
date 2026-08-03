-- Gmail Organizer Launcher
-- Save this as an Application in Script Editor

on run
	-- Derive the current user's project path without embedding an account name
	set projectPath to (POSIX path of (path to home folder)) & "Desktop/Projects/gmail-organizer"

	-- Run the launch script from scripts directory
	set shellScript to "cd " & quoted form of projectPath & " && ./scripts/launch_gmail_organizer.sh"

	-- Run in Terminal
	tell application "Terminal"
		activate
		do script shellScript
	end tell
end run
