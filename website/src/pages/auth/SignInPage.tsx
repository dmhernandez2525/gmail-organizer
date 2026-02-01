import { useNavigate } from 'react-router-dom';
import {
  Mail,
  Briefcase,
  User,
  Zap,
  Eye,
  ArrowRight,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { DEMO_USERS, type DemoUserRole } from '@/lib/demo-data';

// Check if demo mode is enabled via environment variable
const DEMO_MODE_ENABLED = import.meta.env.VITE_DEMO_MODE === 'true';

const roleIcons = {
  jobSeeker: Briefcase,
  professional: User,
  powerUser: Zap,
};

const roleColors = {
  jobSeeker: 'from-purple-500 to-purple-600',
  professional: 'from-cyan-500 to-cyan-600',
  powerUser: 'from-blue-500 to-blue-600',
};

export default function SignInPage() {
  const navigate = useNavigate();

  // In demo mode, show role selection instead of real auth
  if (DEMO_MODE_ENABLED) {
    const handleDemoLogin = (role: DemoUserRole) => {
      // Store demo role and redirect to appropriate demo page
      localStorage.setItem('gmail-organizer-demo-role', role);
      navigate(`/demo/${role}`);
    };

    return (
      <div className="min-h-screen flex items-center justify-center bg-background hero-gradient grid-pattern p-4">
        <div className="max-w-2xl w-full">
          <div className="glass-card rounded-2xl p-8 glow-purple">
            <div className="text-center mb-8">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-purple-500/20 border border-purple-500/40 mb-4">
                <Eye className="w-4 h-4 text-purple-400" />
                <span className="text-sm text-purple-400 font-medium">Demo Mode</span>
              </div>
              <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center">
                <Mail className="w-8 h-8 text-white" />
              </div>
              <h1 className="text-3xl font-bold mb-2">
                Welcome to <span className="gradient-text">Gmail Organizer</span>
              </h1>
              <p className="text-muted-foreground">
                Choose a demo persona to explore the platform
              </p>
            </div>

            <div className="space-y-4">
              {(Object.entries(DEMO_USERS) as [DemoUserRole, typeof DEMO_USERS[DemoUserRole]][]).map(
                ([role, user]) => {
                  const Icon = roleIcons[role];
                  const colorClass = roleColors[role];

                  return (
                    <button
                      key={role}
                      onClick={() => handleDemoLogin(role)}
                      className="w-full flex items-center gap-4 p-4 rounded-xl border border-border hover:border-purple-500/50 hover:bg-purple-500/5 transition-all group text-left"
                    >
                      <div
                        className={`w-14 h-14 rounded-xl bg-gradient-to-br ${colorClass} flex items-center justify-center flex-shrink-0`}
                      >
                        <Icon className="w-7 h-7 text-white" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-semibold group-hover:text-purple-400 transition-colors">
                            {user.name}
                          </span>
                          <Badge variant="outline" className="text-xs">
                            {user.role}
                          </Badge>
                        </div>
                        <p className="text-sm text-muted-foreground truncate">
                          {user.description}
                        </p>
                      </div>
                      <ArrowRight className="w-5 h-5 text-muted-foreground group-hover:text-purple-400 group-hover:translate-x-1 transition-all flex-shrink-0" />
                    </button>
                  );
                }
              )}
            </div>

            <div className="mt-8 pt-6 border-t border-border">
              <p className="text-center text-sm text-muted-foreground">
                This is a demo environment with sample data.
                <br />
                No real Gmail account connection is required.
              </p>
            </div>

            <div className="mt-6 text-center">
              <Button variant="ghost" onClick={() => navigate('/')}>
                Back to Home
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Normal mode - would show real authentication
  // For now, redirect to home since there's no real auth implemented
  return (
    <div className="min-h-screen flex items-center justify-center bg-background hero-gradient grid-pattern p-4">
      <Card className="max-w-md w-full glass-card border-border">
        <CardHeader className="text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center">
            <Mail className="w-8 h-8 text-white" />
          </div>
          <CardTitle className="text-2xl">Sign In</CardTitle>
          <CardDescription>
            Connect your Gmail account to get started
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button className="w-full bg-gradient-to-r from-purple-600 to-cyan-600 hover:from-purple-700 hover:to-cyan-700">
            <Mail className="w-4 h-4 mr-2" />
            Sign in with Google
          </Button>
          <p className="text-center text-sm text-muted-foreground">
            Gmail Organizer runs locally on your machine.
            <br />
            Your email data stays private.
          </p>
          <div className="pt-4 text-center">
            <Button variant="ghost" onClick={() => navigate('/')}>
              Back to Home
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
