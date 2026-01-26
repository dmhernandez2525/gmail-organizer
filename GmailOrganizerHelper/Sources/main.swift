import Cocoa

// Create and run the application
let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate

// Register URL scheme handler
NSAppleEventManager.shared().setEventHandler(
    delegate,
    andSelector: #selector(AppDelegate.handleURLEvent(_:withReplyEvent:)),
    forEventClass: AEEventClass(kInternetEventClass),
    andEventID: AEEventID(kAEGetURL)
)

app.run()
