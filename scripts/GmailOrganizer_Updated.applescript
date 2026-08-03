-- Gmail Organizer Launcher (Portable Path)
set projectPath to (POSIX path of (path to home folder)) & "Desktop/Projects/gmail-organizer"

tell application "Terminal"
	activate
	do script "cd " & quoted form of projectPath & " && ./scripts/launch_gmail_organizer.sh"
end tell
