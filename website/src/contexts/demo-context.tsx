'use client';

import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import {
  DEMO_USERS,
  DEMO_EMAILS,
  DEMO_ANALYTICS,
  DEMO_FILTERS,
  type DemoUserRole,
} from '@/lib/demo-data';

interface DemoContextType {
  isDemoMode: boolean;
  demoRole: DemoUserRole | null;
  demoUser: (typeof DEMO_USERS)[DemoUserRole] | null;
  enterDemoMode: (role: DemoUserRole) => void;
  exitDemoMode: () => void;
  switchDemoRole: (role: DemoUserRole) => void;
  // Demo data
  emails: (typeof DEMO_EMAILS)[DemoUserRole];
  analytics: (typeof DEMO_ANALYTICS)[DemoUserRole];
  filters: typeof DEMO_FILTERS;
}

const DemoContext = createContext<DemoContextType | undefined>(undefined);

export function DemoProvider({ children }: { children: ReactNode }) {
  const [isDemoMode, setIsDemoMode] = useState(false);
  const [demoRole, setDemoRole] = useState<DemoUserRole | null>(null);

  const enterDemoMode = useCallback((role: DemoUserRole) => {
    setIsDemoMode(true);
    setDemoRole(role);
    localStorage.setItem('gmail-organizer-demo-role', role);
  }, []);

  const exitDemoMode = useCallback(() => {
    setIsDemoMode(false);
    setDemoRole(null);
    localStorage.removeItem('gmail-organizer-demo-role');
  }, []);

  const switchDemoRole = useCallback((role: DemoUserRole) => {
    setDemoRole(role);
    localStorage.setItem('gmail-organizer-demo-role', role);
  }, []);

  const demoUser = demoRole ? DEMO_USERS[demoRole] : null;
  const emails = demoRole ? DEMO_EMAILS[demoRole] : [];
  const analytics = demoRole
    ? DEMO_ANALYTICS[demoRole]
    : {
        totalEmails: 0,
        categorized: 0,
        uncategorized: 0,
        byCategory: [],
        syncStats: {
          lastSync: new Date(),
          syncDuration: '0 seconds',
          newEmails: 0,
          mode: 'incremental' as const,
        },
        topSenders: [],
      };

  const value: DemoContextType = {
    isDemoMode,
    demoRole,
    demoUser,
    enterDemoMode,
    exitDemoMode,
    switchDemoRole,
    emails,
    analytics,
    filters: DEMO_FILTERS,
  };

  return <DemoContext.Provider value={value}>{children}</DemoContext.Provider>;
}

export function useDemo() {
  const context = useContext(DemoContext);
  if (context === undefined) {
    throw new Error('useDemo must be used within a DemoProvider');
  }
  return context;
}
