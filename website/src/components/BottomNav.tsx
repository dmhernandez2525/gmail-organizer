import { useLocation } from 'react-router-dom'
import {
  Home,
  Sparkles,
  Rocket,
  BookOpen,
  LogIn,
} from 'lucide-react'

const NAV_ITEMS = [
  { href: '/', hash: '', label: 'Home', icon: Home },
  { href: '/', hash: '#features', label: 'Features', icon: Sparkles },
  { href: '/', hash: '#roadmap', label: 'Roadmap', icon: Rocket },
  { href: '/', hash: '#docs', label: 'Docs', icon: BookOpen },
  { href: '/sign-in', hash: '', label: 'Sign In', icon: LogIn },
]

export default function BottomNav() {
  const { pathname, hash } = useLocation()

  const isActive = (item: (typeof NAV_ITEMS)[number]) => {
    // Sign-in page
    if (item.href === '/sign-in') {
      return pathname === '/sign-in' || pathname === '/sign-up'
    }
    // Hash-based sections on the home page
    if (item.hash && pathname === '/') {
      return hash === item.hash
    }
    // Home with no hash
    if (!item.hash && item.href === '/') {
      return pathname === '/' && !hash
    }
    return false
  }

  const handleClick = (item: (typeof NAV_ITEMS)[number]) => {
    if (item.hash && pathname === '/') {
      // Smooth scroll to section on the same page
      const el = document.querySelector(item.hash)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth' })
      }
    }
  }

  // Hide on demo pages - the demo has its own navigation
  if (pathname.startsWith('/demo')) {
    return null
  }

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 md:hidden bottom-nav-enter">
      <div className="bg-background/80 backdrop-blur-xl border-t border-border">
        <div className="flex items-center justify-around h-16 px-2">
          {NAV_ITEMS.map((item) => {
            const active = isActive(item)
            const Icon = item.icon

            // For hash links on the home page, use <a>; for route links, use <a> with href
            const href = item.hash
              ? item.href === '/' && pathname === '/'
                ? item.hash
                : `/${item.hash}`
              : item.href

            return (
              <a
                key={item.label}
                href={href}
                onClick={() => handleClick(item)}
                className={`flex flex-col items-center justify-center gap-1 flex-1 py-2 rounded-lg transition-colors ${
                  active
                    ? 'text-purple-400'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <div
                  className={`p-1.5 rounded-lg transition-colors ${
                    active ? 'bg-purple-500/15' : ''
                  }`}
                >
                  <Icon className="w-5 h-5" />
                </div>
                <span className="text-[10px] font-medium leading-none">
                  {item.label}
                </span>
              </a>
            )
          })}
        </div>
      </div>
      {/* Safe area for devices with home indicator */}
      <div className="bg-background/80 backdrop-blur-xl h-[env(safe-area-inset-bottom)]" />
    </nav>
  )
}
