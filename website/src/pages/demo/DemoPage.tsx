import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Mail,
  Tag,
  BarChart3,
  Filter,
  RefreshCw,
  Star,
  Archive,
  CheckCircle2,
  Eye,
  ArrowLeftRight,
  LogOut,
  ChevronDown,
  Search,
  Settings,
  Inbox,
  AlertCircle,
  Users,
  Briefcase,
  Zap,
  User,
} from 'lucide-react';
import { useDemo } from '@/contexts/demo-context';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  DEMO_USERS,
  EMAIL_CATEGORIES,
  formatRelativeTime,
  getCategoryColor,
  type DemoUserRole,
} from '@/lib/demo-data';

const roleIcons = {
  jobSeeker: Briefcase,
  professional: User,
  powerUser: Zap,
};

export default function DemoPage() {
  const { role } = useParams<{ role: string }>();
  const navigate = useNavigate();
  const { isDemoMode, demoRole, demoUser, enterDemoMode, exitDemoMode, switchDemoRole, emails, analytics } =
    useDemo();
  const [activeTab, setActiveTab] = useState<'inbox' | 'analytics' | 'filters'>('inbox');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [showRoleSwitcher, setShowRoleSwitcher] = useState(false);

  useEffect(() => {
    if (role && role in DEMO_USERS) {
      if (!isDemoMode || demoRole !== role) {
        enterDemoMode(role as DemoUserRole);
      }
    } else {
      navigate('/sign-in');
    }
  }, [role, isDemoMode, demoRole, enterDemoMode, navigate]);

  if (!demoUser) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="animate-pulse text-muted-foreground">Loading demo...</div>
      </div>
    );
  }

  const filteredEmails = selectedCategory
    ? emails.filter((e) => e.category === selectedCategory)
    : emails;

  const handleSwitchRole = (newRole: DemoUserRole) => {
    switchDemoRole(newRole);
    setShowRoleSwitcher(false);
    navigate(`/demo/${newRole}`);
  };

  const handleExit = () => {
    exitDemoMode();
    navigate('/');
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Demo Banner */}
      <div className="bg-gradient-to-r from-purple-600 via-purple-500 to-cyan-500 py-2 px-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2 text-white text-sm">
            <Eye className="w-4 h-4" />
            <span className="font-medium">Demo Mode: {demoUser.role}</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowRoleSwitcher(!showRoleSwitcher)}
                className="text-white hover:bg-white/20 text-xs h-7"
              >
                <ArrowLeftRight className="w-3 h-3 mr-1" />
                Switch Persona
                <ChevronDown className="w-3 h-3 ml-1" />
              </Button>
              {showRoleSwitcher && (
                <div className="absolute right-0 top-full mt-1 w-56 bg-card border border-border rounded-lg shadow-lg z-50 py-1">
                  {(Object.entries(DEMO_USERS) as [DemoUserRole, typeof DEMO_USERS[DemoUserRole]][]).map(
                    ([r, u]) => (
                      <button
                        key={r}
                        onClick={() => handleSwitchRole(r)}
                        className={`w-full px-3 py-2 text-left text-sm hover:bg-muted flex items-center gap-2 ${
                          r === demoRole ? 'bg-purple-500/10 text-purple-400' : ''
                        }`}
                      >
                        {React.createElement(roleIcons[r], { className: 'w-4 h-4' })}
                        <span>{u.name}</span>
                        {r === demoRole && <CheckCircle2 className="w-3 h-3 ml-auto" />}
                      </button>
                    )
                  )}
                </div>
              )}
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleExit}
              className="text-white hover:bg-white/20 text-xs h-7"
            >
              <LogOut className="w-3 h-3 mr-1" />
              Exit Demo
            </Button>
          </div>
        </div>
      </div>

      {/* Header */}
      <header className="border-b border-border bg-card/80 backdrop-blur sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center">
                <Mail className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="font-bold text-lg">Gmail Organizer</h1>
                <p className="text-xs text-muted-foreground">{demoUser.email}</p>
              </div>
            </div>

            <div className="flex-1 max-w-md relative hidden md:block">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search emails..."
                className="w-full pl-10 pr-4 py-2 bg-muted/50 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/50"
              />
            </div>

            <div className="flex items-center gap-2">
              <Button variant="ghost" size="icon">
                <Settings className="w-5 h-5" />
              </Button>
              <div className="flex items-center gap-2 pl-2 border-l border-border">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center text-white text-sm font-medium">
                  {demoUser.avatar}
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Tabs */}
        <div className="flex gap-2 mb-6 border-b border-border pb-4">
          <Button
            variant={activeTab === 'inbox' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setActiveTab('inbox')}
            className={activeTab === 'inbox' ? 'bg-purple-600 hover:bg-purple-700' : ''}
          >
            <Inbox className="w-4 h-4 mr-2" />
            Inbox
          </Button>
          <Button
            variant={activeTab === 'analytics' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setActiveTab('analytics')}
            className={activeTab === 'analytics' ? 'bg-purple-600 hover:bg-purple-700' : ''}
          >
            <BarChart3 className="w-4 h-4 mr-2" />
            Analytics
          </Button>
          <Button
            variant={activeTab === 'filters' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setActiveTab('filters')}
            className={activeTab === 'filters' ? 'bg-purple-600 hover:bg-purple-700' : ''}
          >
            <Filter className="w-4 h-4 mr-2" />
            Smart Filters
          </Button>
        </div>

        {activeTab === 'inbox' && (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Sidebar - Categories */}
            <div className="lg:col-span-1 space-y-4">
              <Card className="glass-card border-border">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Tag className="w-4 h-4 text-purple-400" />
                    Categories
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-1">
                  <button
                    onClick={() => setSelectedCategory(null)}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors ${
                      !selectedCategory ? 'bg-purple-500/20 text-purple-400' : 'hover:bg-muted'
                    }`}
                  >
                    <span>All Emails</span>
                    <Badge variant="outline" className="text-xs">
                      {emails.length}
                    </Badge>
                  </button>
                  {EMAIL_CATEGORIES.slice(0, 8).map((cat) => {
                    const count = emails.filter((e) => e.category === cat.id).length;
                    if (count === 0) return null;
                    return (
                      <button
                        key={cat.id}
                        onClick={() => setSelectedCategory(cat.id)}
                        className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors ${
                          selectedCategory === cat.id
                            ? 'bg-purple-500/20 text-purple-400'
                            : 'hover:bg-muted'
                        }`}
                      >
                        <span className="flex items-center gap-2">
                          <span
                            className="w-2 h-2 rounded-full"
                            style={{ backgroundColor: cat.color }}
                          />
                          {cat.name}
                        </span>
                        <Badge variant="outline" className="text-xs">
                          {count}
                        </Badge>
                      </button>
                    );
                  })}
                </CardContent>
              </Card>

              {/* Sync Status */}
              <Card className="glass-card border-border">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <RefreshCw className="w-4 h-4 text-cyan-400" />
                    Sync Status
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Last sync</span>
                    <span className="flex items-center gap-1 text-green-400">
                      <CheckCircle2 className="w-3 h-3" />
                      {formatRelativeTime(analytics.syncStats.lastSync)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Duration</span>
                    <span>{analytics.syncStats.syncDuration}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">New emails</span>
                    <Badge className="bg-cyan-500/20 text-cyan-400 border-0">
                      +{analytics.syncStats.newEmails}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Mode</span>
                    <Badge variant="outline" className="text-xs capitalize">
                      <Zap className="w-3 h-3 mr-1" />
                      {analytics.syncStats.mode}
                    </Badge>
                  </div>
                  <Button className="w-full mt-2 bg-gradient-to-r from-purple-600 to-cyan-600 hover:from-purple-700 hover:to-cyan-700">
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Sync Now
                  </Button>
                </CardContent>
              </Card>
            </div>

            {/* Email List */}
            <div className="lg:col-span-3">
              <Card className="glass-card border-border">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm">
                      {selectedCategory
                        ? EMAIL_CATEGORIES.find((c) => c.id === selectedCategory)?.name
                        : 'All Emails'}
                    </CardTitle>
                    <div className="flex items-center gap-2">
                      <Button variant="ghost" size="sm">
                        <Archive className="w-4 h-4 mr-1" />
                        Archive
                      </Button>
                      <Button variant="ghost" size="sm">
                        <Tag className="w-4 h-4 mr-1" />
                        Label
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="p-0">
                  <div className="divide-y divide-border">
                    {filteredEmails.map((email) => (
                      <div
                        key={email.id}
                        className={`flex items-start gap-4 p-4 hover:bg-muted/50 cursor-pointer transition-colors ${
                          !email.isRead ? 'bg-purple-500/5' : ''
                        }`}
                      >
                        <div className="flex items-center gap-3 pt-1">
                          <button className="text-muted-foreground hover:text-yellow-400 transition-colors">
                            <Star
                              className={`w-4 h-4 ${email.isStarred ? 'fill-yellow-400 text-yellow-400' : ''}`}
                            />
                          </button>
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span
                              className={`font-medium truncate ${!email.isRead ? 'text-foreground' : 'text-muted-foreground'}`}
                            >
                              {email.fromName}
                            </span>
                            <Badge
                              className="text-xs px-2 py-0"
                              style={{
                                backgroundColor: `${getCategoryColor(email.category)}20`,
                                color: getCategoryColor(email.category),
                                borderColor: `${getCategoryColor(email.category)}40`,
                              }}
                            >
                              {EMAIL_CATEGORIES.find((c) => c.id === email.category)?.name}
                            </Badge>
                          </div>
                          <p
                            className={`text-sm truncate ${!email.isRead ? 'font-medium' : 'text-muted-foreground'}`}
                          >
                            {email.subject}
                          </p>
                          <p className="text-xs text-muted-foreground truncate mt-1">
                            {email.preview}
                          </p>
                          <div className="flex items-center gap-2 mt-2">
                            {email.labels.map((label, i) => (
                              <Badge key={i} variant="outline" className="text-xs">
                                {label}
                              </Badge>
                            ))}
                          </div>
                        </div>
                        <div className="text-xs text-muted-foreground whitespace-nowrap">
                          {formatRelativeTime(email.date)}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {activeTab === 'analytics' && <AnalyticsTab analytics={analytics} />}

        {activeTab === 'filters' && <FiltersTab />}
      </div>
    </div>
  );
}

interface CategoryBreakdown {
  category: string;
  count: number;
  percentage: number;
}

interface TopSender {
  sender: string;
  count: number;
}

interface Account {
  name: string;
  email: string;
  emails: number;
}

interface AnalyticsData {
  totalEmails: number;
  categorized: number;
  uncategorized: number;
  byCategory: CategoryBreakdown[];
  syncStats: {
    lastSync: Date;
    syncDuration: string;
    newEmails: number;
    mode: string;
  };
  topSenders: TopSender[];
  accounts?: Account[];
}

function AnalyticsTab({ analytics }: { analytics: AnalyticsData }) {
  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="glass-card border-border">
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-purple-500/20">
                <Mail className="w-6 h-6 text-purple-400" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Total Emails</p>
                <p className="text-2xl font-bold">{analytics.totalEmails.toLocaleString()}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="glass-card border-border">
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-green-500/20">
                <CheckCircle2 className="w-6 h-6 text-green-400" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Categorized</p>
                <p className="text-2xl font-bold">{analytics.categorized.toLocaleString()}</p>
                <p className="text-xs text-green-400">
                  {((analytics.categorized / analytics.totalEmails) * 100).toFixed(1)}%
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="glass-card border-border">
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-yellow-500/20">
                <AlertCircle className="w-6 h-6 text-yellow-400" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Uncategorized</p>
                <p className="text-2xl font-bold">{analytics.uncategorized.toLocaleString()}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="glass-card border-border">
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-cyan-500/20">
                <Zap className="w-6 h-6 text-cyan-400" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Last Sync</p>
                <p className="text-2xl font-bold">{analytics.syncStats.syncDuration}</p>
                <p className="text-xs text-cyan-400">Incremental mode</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Category Breakdown */}
        <Card className="glass-card border-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-purple-400" />
              Category Breakdown
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {analytics.byCategory.map((cat, i) => (
                <div key={i} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span>{cat.category}</span>
                    <span className="text-muted-foreground">
                      {cat.count.toLocaleString()} ({cat.percentage}%)
                    </span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-purple-500 to-cyan-500 rounded-full transition-all"
                      style={{ width: `${cat.percentage}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Top Senders */}
        <Card className="glass-card border-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="w-5 h-5 text-cyan-400" />
              Top Senders
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {analytics.topSenders.map((sender, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between p-3 rounded-lg bg-muted/50"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500/20 to-cyan-500/20 flex items-center justify-center text-sm font-medium">
                      {i + 1}
                    </div>
                    <span className="font-medium">{sender.sender}</span>
                  </div>
                  <Badge variant="outline">{sender.count.toLocaleString()} emails</Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Multi-account view for power user */}
      {analytics.accounts && (
        <Card className="glass-card border-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mail className="w-5 h-5 text-purple-400" />
              Connected Accounts
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {analytics.accounts.map((account, i) => (
                <div key={i} className="p-4 rounded-lg bg-muted/50 space-y-2">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center text-white text-xs font-medium">
                      {i + 1}
                    </div>
                    <div>
                      <p className="font-medium">{account.name}</p>
                      <p className="text-xs text-muted-foreground">{account.email}</p>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Emails</span>
                    <span className="font-mono">{account.emails.toLocaleString()}</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function FiltersTab() {
  const { filters } = useDemo();

  return (
    <div className="space-y-6">
      <Card className="glass-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="w-5 h-5 text-purple-400" />
            Smart Filter Suggestions
          </CardTitle>
          <CardDescription>
            AI-detected patterns from your emails. Create Gmail filters with one click.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {filters.map((filter) => (
              <div
                key={filter.id}
                className="p-4 rounded-xl border border-border hover:border-purple-500/50 transition-colors"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-2 flex-1">
                    <h4 className="font-medium">{filter.name}</h4>
                    <div className="space-y-1">
                      <div className="text-sm">
                        <span className="text-muted-foreground">Criteria: </span>
                        <code className="text-xs bg-muted px-2 py-1 rounded">
                          {filter.criteria}
                        </code>
                      </div>
                      <div className="text-sm">
                        <span className="text-muted-foreground">Action: </span>
                        <span className="text-cyan-400">{filter.action}</span>
                      </div>
                    </div>
                  </div>
                  <div className="text-right space-y-2">
                    <Badge className="bg-purple-500/20 text-purple-400 border-0">
                      {filter.matchCount} matches
                    </Badge>
                    <Button size="sm" className="block w-full">
                      Create Filter
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card className="glass-card border-border">
        <CardHeader>
          <CardTitle>How Smart Filters Work</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-muted-foreground">
          <p>
            Gmail Organizer analyzes your classified emails to detect common patterns from senders,
            domains, and subject lines.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 rounded-lg bg-muted/50">
              <Tag className="w-5 h-5 text-purple-400 mb-2" />
              <h4 className="font-medium text-foreground">Pattern Detection</h4>
              <p className="text-sm">Automatically detects sender and subject patterns</p>
            </div>
            <div className="p-4 rounded-lg bg-muted/50">
              <Eye className="w-5 h-5 text-cyan-400 mb-2" />
              <h4 className="font-medium text-foreground">Preview Matches</h4>
              <p className="text-sm">See how many emails match before creating</p>
            </div>
            <div className="p-4 rounded-lg bg-muted/50">
              <Zap className="w-5 h-5 text-yellow-400 mb-2" />
              <h4 className="font-medium text-foreground">One-Click Create</h4>
              <p className="text-sm">Create Gmail filters directly from the app</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// Need to import React for createElement
import React from 'react';
