-- Gmail Organizer Launcher
-- Save this as an Application in Script Editor

on run
	set appPath to (path to me as text)
	set appFolder to getParentFolder(appPath)

	-- Change to app directory
	set shellScript to "cd " & quoted form of POSIX path of appFolder & " && ./launch_gmail_organizer.sh"

	-- Run in Terminal
	tell application "Terminal"
		activate
		do script shellScript
	end tell
end run

on getParentFolder(filePath)
	tell application "Finder"
		set fileItem to filePath as alias
		set parentFolder to container of fileItem as text
		return parentFolder
	end tell
end getParentFolder
