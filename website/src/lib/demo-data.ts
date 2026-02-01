// Demo data for showcasing Gmail Organizer without authentication

// Demo user personas representing different email use cases
export const DEMO_USERS = {
  jobSeeker: {
    id: 'demo-jobseeker-001',
    name: 'Alex Chen',
    email: 'alex.chen@gmail.com',
    role: 'Job Seeker',
    avatar: 'AC',
    description: 'Active job seeker with interviews, applications, and offer emails',
  },
  professional: {
    id: 'demo-professional-001',
    name: 'Sarah Johnson',
    email: 'sarah.johnson@gmail.com',
    role: 'Professional',
    avatar: 'SJ',
    description: 'Business professional with mixed work and personal emails',
  },
  powerUser: {
    id: 'demo-power-001',
    name: 'Mike Rodriguez',
    email: 'mike.rodriguez@gmail.com',
    role: 'Power User',
    avatar: 'MR',
    description: 'Multiple accounts with 80,000+ emails needing organization',
  },
};

export type DemoUserRole = keyof typeof DEMO_USERS;

// Email categories used by Gmail Organizer
export const EMAIL_CATEGORIES = [
  { id: 'interviews', name: 'Interviews', color: '#A855F7', icon: 'calendar' },
  { id: 'applications', name: 'Applications', color: '#3B82F6', icon: 'briefcase' },
  { id: 'offers', name: 'Job Offers', color: '#10B981', icon: 'star' },
  { id: 'rejections', name: 'Rejections', color: '#EF4444', icon: 'x-circle' },
  { id: 'newsletters', name: 'Newsletters', color: '#F59E0B', icon: 'newspaper' },
  { id: 'finance', name: 'Finance', color: '#06B6D4', icon: 'credit-card' },
  { id: 'shopping', name: 'Shopping', color: '#EC4899', icon: 'shopping-cart' },
  { id: 'social', name: 'Social', color: '#8B5CF6', icon: 'users' },
  { id: 'travel', name: 'Travel', color: '#14B8A6', icon: 'plane' },
  { id: 'important', name: 'Important', color: '#EF4444', icon: 'alert-circle' },
];

// Demo emails for each user type
export const DEMO_EMAILS = {
  jobSeeker: [
    {
      id: 'e1',
      subject: 'Interview Confirmation - Senior Frontend Developer',
      from: 'recruiting@techcorp.com',
      fromName: 'TechCorp Recruiting',
      date: new Date('2026-01-30T10:30:00'),
      category: 'interviews',
      preview: 'Thank you for your application. We are pleased to invite you for a technical interview...',
      isRead: false,
      isStarred: true,
      labels: ['Interviews', 'Action Required'],
    },
    {
      id: 'e2',
      subject: 'Application Received - Product Manager Role',
      from: 'careers@startupxyz.io',
      fromName: 'StartupXYZ Careers',
      date: new Date('2026-01-29T14:15:00'),
      category: 'applications',
      preview: 'Thank you for applying to the Product Manager position at StartupXYZ. Your application is under review...',
      isRead: true,
      isStarred: false,
      labels: ['Applications'],
    },
    {
      id: 'e3',
      subject: 'Congratulations! Job Offer - Software Engineer',
      from: 'hr@dreamcompany.com',
      fromName: 'Dream Company HR',
      date: new Date('2026-01-28T09:00:00'),
      category: 'offers',
      preview: 'We are excited to extend an offer for the Software Engineer position. Please review the attached...',
      isRead: false,
      isStarred: true,
      labels: ['Job Offers', 'Important'],
    },
    {
      id: 'e4',
      subject: 'Update on Your Application Status',
      from: 'noreply@bigtech.com',
      fromName: 'BigTech Recruiting',
      date: new Date('2026-01-27T16:45:00'),
      category: 'rejections',
      preview: 'Thank you for your interest in BigTech. After careful consideration, we have decided to move forward with...',
      isRead: true,
      isStarred: false,
      labels: ['Rejections'],
    },
    {
      id: 'e5',
      subject: 'Weekly Tech Jobs Digest',
      from: 'digest@techjobs.com',
      fromName: 'TechJobs Weekly',
      date: new Date('2026-01-26T08:00:00'),
      category: 'newsletters',
      preview: '47 new jobs matching your criteria: Frontend Developer, React Engineer, Full Stack...',
      isRead: true,
      isStarred: false,
      labels: ['Newsletters'],
    },
    {
      id: 'e6',
      subject: 'Your LinkedIn Premium Receipt',
      from: 'billing@linkedin.com',
      fromName: 'LinkedIn',
      date: new Date('2026-01-25T12:00:00'),
      category: 'finance',
      preview: 'Your payment of $29.99 for LinkedIn Premium has been processed...',
      isRead: true,
      isStarred: false,
      labels: ['Finance', 'Receipts'],
    },
  ],
  professional: [
    {
      id: 'p1',
      subject: 'Q1 Strategy Meeting - Agenda',
      from: 'ceo@company.com',
      fromName: 'John Smith',
      date: new Date('2026-01-30T09:00:00'),
      category: 'important',
      preview: 'Team, please review the attached agenda for our Q1 strategy meeting scheduled for...',
      isRead: false,
      isStarred: true,
      labels: ['Important', 'Work'],
    },
    {
      id: 'p2',
      subject: 'Your Amex Statement is Ready',
      from: 'statements@americanexpress.com',
      fromName: 'American Express',
      date: new Date('2026-01-29T06:00:00'),
      category: 'finance',
      preview: 'Your January statement is now available. Total balance: $3,247.82...',
      isRead: true,
      isStarred: false,
      labels: ['Finance', 'Statements'],
    },
    {
      id: 'p3',
      subject: 'Your Amazon Order Has Shipped',
      from: 'shipment@amazon.com',
      fromName: 'Amazon',
      date: new Date('2026-01-28T14:30:00'),
      category: 'shopping',
      preview: 'Your order #112-4567890-1234567 has shipped and will arrive by January 30...',
      isRead: true,
      isStarred: false,
      labels: ['Shopping', 'Tracking'],
    },
    {
      id: 'p4',
      subject: 'Flight Confirmation - SFO to NYC',
      from: 'reservations@united.com',
      fromName: 'United Airlines',
      date: new Date('2026-01-27T11:00:00'),
      category: 'travel',
      preview: 'Your flight UA 342 on February 15 from San Francisco to New York is confirmed...',
      isRead: true,
      isStarred: true,
      labels: ['Travel', 'Confirmations'],
    },
    {
      id: 'p5',
      subject: 'Sarah invited you to an event',
      from: 'noreply@calendar.google.com',
      fromName: 'Google Calendar',
      date: new Date('2026-01-26T15:00:00'),
      category: 'social',
      preview: "You've been invited to: Team Happy Hour at The Rooftop Bar on Friday at 6 PM...",
      isRead: false,
      isStarred: false,
      labels: ['Social', 'Events'],
    },
    {
      id: 'p6',
      subject: 'Morning Brew - Daily Newsletter',
      from: 'newsletter@morningbrew.com',
      fromName: 'Morning Brew',
      date: new Date('2026-01-26T06:00:00'),
      category: 'newsletters',
      preview: "Good morning! Here's what you need to know today: Markets rallied as...",
      isRead: true,
      isStarred: false,
      labels: ['Newsletters'],
    },
  ],
  powerUser: [
    {
      id: 'pu1',
      subject: 'Account 1: Bank Alert - Large Transaction',
      from: 'alerts@chase.com',
      fromName: 'Chase Bank',
      date: new Date('2026-01-30T08:45:00'),
      category: 'finance',
      preview: 'A transaction of $5,000.00 was made on your account ending in 4521...',
      isRead: false,
      isStarred: true,
      labels: ['Finance', 'Alerts', 'Account 1'],
    },
    {
      id: 'pu2',
      subject: 'Account 2: Server Down Alert',
      from: 'monitoring@render.com',
      fromName: 'Render',
      date: new Date('2026-01-30T07:30:00'),
      category: 'important',
      preview: 'Your service api-production is experiencing issues. Status: degraded...',
      isRead: false,
      isStarred: true,
      labels: ['Important', 'DevOps', 'Account 2'],
    },
    {
      id: 'pu3',
      subject: 'Account 3: Interview Scheduled',
      from: 'recruiting@meta.com',
      fromName: 'Meta Recruiting',
      date: new Date('2026-01-29T16:00:00'),
      category: 'interviews',
      preview: 'Your system design interview is scheduled for February 5 at 2 PM PST...',
      isRead: true,
      isStarred: true,
      labels: ['Interviews', 'Account 3'],
    },
    {
      id: 'pu4',
      subject: 'Account 1: Your Subscription Renewed',
      from: 'billing@anthropic.com',
      fromName: 'Anthropic',
      date: new Date('2026-01-28T12:00:00'),
      category: 'finance',
      preview: 'Your Claude Pro subscription has been renewed. Amount: $20.00...',
      isRead: true,
      isStarred: false,
      labels: ['Finance', 'Subscriptions', 'Account 1'],
    },
    {
      id: 'pu5',
      subject: 'Account 2: GitHub Security Alert',
      from: 'noreply@github.com',
      fromName: 'GitHub',
      date: new Date('2026-01-27T14:20:00'),
      category: 'important',
      preview: 'Dependabot detected a vulnerability in your repository gmail-organizer...',
      isRead: true,
      isStarred: false,
      labels: ['Important', 'Security', 'Account 2'],
    },
    {
      id: 'pu6',
      subject: 'Account 3: Weekly Tech Newsletter',
      from: 'weekly@hackernewsletter.com',
      fromName: 'Hacker Newsletter',
      date: new Date('2026-01-26T10:00:00'),
      category: 'newsletters',
      preview: 'This week: New LLM breakthroughs, Rust adoption growing, and more...',
      isRead: true,
      isStarred: false,
      labels: ['Newsletters', 'Account 3'],
    },
  ],
};

// Demo analytics data
export const DEMO_ANALYTICS = {
  jobSeeker: {
    totalEmails: 2847,
    categorized: 2654,
    uncategorized: 193,
    byCategory: [
      { category: 'Applications', count: 89, percentage: 3.1 },
      { category: 'Interviews', count: 23, percentage: 0.8 },
      { category: 'Job Offers', count: 5, percentage: 0.2 },
      { category: 'Rejections', count: 34, percentage: 1.2 },
      { category: 'Newsletters', count: 1247, percentage: 43.8 },
      { category: 'Finance', count: 312, percentage: 11.0 },
      { category: 'Shopping', count: 567, percentage: 19.9 },
      { category: 'Social', count: 234, percentage: 8.2 },
      { category: 'Other', count: 336, percentage: 11.8 },
    ],
    syncStats: {
      lastSync: new Date('2026-01-30T11:45:00'),
      syncDuration: '4 seconds',
      newEmails: 12,
      mode: 'incremental',
    },
    topSenders: [
      { sender: 'LinkedIn', count: 234 },
      { sender: 'Indeed', count: 189 },
      { sender: 'Glassdoor', count: 156 },
      { sender: 'Amazon', count: 123 },
      { sender: 'Google', count: 98 },
    ],
  },
  professional: {
    totalEmails: 12456,
    categorized: 11890,
    uncategorized: 566,
    byCategory: [
      { category: 'Work', count: 4567, percentage: 36.7 },
      { category: 'Finance', count: 1234, percentage: 9.9 },
      { category: 'Shopping', count: 2345, percentage: 18.8 },
      { category: 'Travel', count: 567, percentage: 4.5 },
      { category: 'Social', count: 890, percentage: 7.1 },
      { category: 'Newsletters', count: 1890, percentage: 15.2 },
      { category: 'Other', count: 963, percentage: 7.7 },
    ],
    syncStats: {
      lastSync: new Date('2026-01-30T10:30:00'),
      syncDuration: '7 seconds',
      newEmails: 28,
      mode: 'incremental',
    },
    topSenders: [
      { sender: 'company.com', count: 1567 },
      { sender: 'Amazon', count: 456 },
      { sender: 'LinkedIn', count: 345 },
      { sender: 'Google', count: 289 },
      { sender: 'Apple', count: 234 },
    ],
  },
  powerUser: {
    totalEmails: 82341,
    categorized: 79876,
    uncategorized: 2465,
    byCategory: [
      { category: 'Work', count: 23456, percentage: 28.5 },
      { category: 'Finance', count: 8765, percentage: 10.6 },
      { category: 'Shopping', count: 12345, percentage: 15.0 },
      { category: 'Newsletters', count: 18765, percentage: 22.8 },
      { category: 'Social', count: 5678, percentage: 6.9 },
      { category: 'DevOps', count: 4321, percentage: 5.2 },
      { category: 'Job Search', count: 2345, percentage: 2.8 },
      { category: 'Other', count: 6666, percentage: 8.1 },
    ],
    syncStats: {
      lastSync: new Date('2026-01-30T11:00:00'),
      syncDuration: '12 seconds',
      newEmails: 47,
      mode: 'incremental',
    },
    topSenders: [
      { sender: 'GitHub', count: 4567 },
      { sender: 'AWS', count: 3456 },
      { sender: 'Google', count: 2890 },
      { sender: 'LinkedIn', count: 2345 },
      { sender: 'Render', count: 1678 },
    ],
    accounts: [
      { name: 'Work Account', email: 'mike@company.com', emails: 34567 },
      { name: 'Personal', email: 'mike.rodriguez@gmail.com', emails: 28456 },
      { name: 'Side Projects', email: 'mikedev@gmail.com', emails: 19318 },
    ],
  },
};

// Demo filter suggestions
export const DEMO_FILTERS = [
  {
    id: 'f1',
    name: 'Job Application Auto-Label',
    criteria: 'from:(linkedin.com OR indeed.com OR glassdoor.com) subject:(application OR applied)',
    action: 'Apply label: Applications',
    matchCount: 156,
  },
  {
    id: 'f2',
    name: 'Interview Reminders',
    criteria: 'subject:(interview OR "phone screen" OR "technical interview")',
    action: 'Apply label: Interviews, Star',
    matchCount: 23,
  },
  {
    id: 'f3',
    name: 'Newsletter Cleanup',
    criteria: 'from:(newsletter OR digest OR weekly) unsubscribe',
    action: 'Skip inbox, Apply label: Newsletters',
    matchCount: 1247,
  },
  {
    id: 'f4',
    name: 'Receipts & Orders',
    criteria: 'from:(amazon.com OR apple.com OR paypal.com) subject:(order OR receipt OR invoice)',
    action: 'Apply label: Receipts',
    matchCount: 345,
  },
];

// Helper to format relative time
export function formatRelativeTime(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

// Helper to get category color
export function getCategoryColor(categoryId: string): string {
  const category = EMAIL_CATEGORIES.find((c) => c.id === categoryId);
  return category?.color || '#6B7280';
}
