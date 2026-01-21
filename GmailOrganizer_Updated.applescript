-- Gmail Organizer Launcher (Updated Path)
set projectPath to "/Users/daniel/Desktop/Projects/PersonalProjects/gmail-organizer"

tell application "Terminal"
	activate
	do script "cd " & quoted form of projectPath & " && ./launch_gmail_organizer.sh"
end tell
