-- Gmail Organizer Launcher
-- Save this as an Application in Script Editor

on run
	-- Hardcoded project path for reliability
	set projectPath to "~/Desktop/Projects/PersonalProjects/gmail-organizer"

	-- Run the launch script from scripts directory
	set shellScript to "cd " & projectPath & " && ./scripts/launch_gmail_organizer.sh"

	-- Run in Terminal
	tell application "Terminal"
		activate
		do script shellScript
	end tell
end run
