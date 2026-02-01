# Demo Mode Architecture

## Overview

Demo mode allows the Gmail Organizer website to be showcased without requiring real Gmail authentication or API connections. This is essential for portfolio demonstrations and showcasing the application's capabilities.

## How It Works

### Environment Variable

```env
VITE_DEMO_MODE=true
```

When this environment variable is set to `true`, the application operates in demo mode.

### Architecture Flow

```
+-------------------------------------------------------------------+
|                        Marketing Pages                              |
|  (Homepage, Features, Pricing, About - Always the same)            |
+-------------------------------------------------------------------+
                                |
                                | User clicks "Get Started"
                                v
+-------------------------------------------------------------------+
|                    Auth Pages (/sign-in, /sign-up)                 |
|                                                                     |
|  +-------------------------+    +-------------------------+        |
|  |  VITE_DEMO_MODE=false   |    |  VITE_DEMO_MODE=true    |        |
|  |  Show Google OAuth      |    |  Show Persona Selector  |        |
|  +-------------------------+    +-------------------------+        |
+-------------------------------------------------------------------+
                                |
                                | User selects persona
                                v
+-------------------------------------------------------------------+
|                    Demo Experience Pages                            |
|                                                                     |
|  /demo/jobSeeker    - Job search focused email organization        |
|  /demo/professional - Business professional email management       |
|  /demo/powerUser    - Multi-account power user with 80k+ emails    |
+-------------------------------------------------------------------+
```

### Key Components

#### 1. Auth Pages (`/sign-in`, `/sign-up`)

When `VITE_DEMO_MODE=true`:
- Shows persona selection UI instead of Google OAuth
- Stores selected persona in localStorage
- Redirects to appropriate demo page

```tsx
// src/pages/auth/SignInPage.tsx
const DEMO_MODE_ENABLED = import.meta.env.VITE_DEMO_MODE === 'true';

if (DEMO_MODE_ENABLED) {
  // Show persona selection
  return <DemoPersonaSelector />;
}

// Normal Google OAuth
return <GoogleSignIn />;
```

#### 2. Demo Data (`/lib/demo-data.ts`)

Contains all mock data for the demo experience:
- `DEMO_USERS` - Three persona types (Job Seeker, Professional, Power User)
- `EMAIL_CATEGORIES` - Gmail Organizer's classification categories
- `DEMO_EMAILS` - Sample emails for each persona
- `DEMO_ANALYTICS` - Dashboard metrics and statistics
- `DEMO_FILTERS` - Smart filter suggestions

#### 3. Demo Context (`/contexts/demo-context.tsx`)

Provides demo state and data to components:
- `isDemoMode` - Whether demo mode is active
- `demoRole` - Current persona (jobSeeker/professional/powerUser)
- `demoUser` - Current mock user data
- Demo data getters (emails, analytics, filters)

#### 4. Demo Pages (`/demo/:role`)

Full-featured demo experiences:
- **Job Seeker**: Interview, application, and offer tracking
- **Professional**: Mixed work and personal email management
- **Power User**: Multi-account view with 80,000+ emails

## Demo Personas

### Job Seeker (Alex Chen)
- Focus: Job search email management
- Categories: Interviews, Applications, Job Offers, Rejections
- Use case: Active job seeker tracking applications

### Professional (Sarah Johnson)
- Focus: Work-life email balance
- Categories: Work, Finance, Shopping, Travel, Social
- Use case: Business professional managing mixed inbox

### Power User (Mike Rodriguez)
- Focus: Multi-account management at scale
- Accounts: 3 Gmail accounts, 80,000+ total emails
- Categories: DevOps, Work, Finance, Newsletters
- Use case: Technical user with complex email needs

## Render Deployment

The `render.yaml` configures deployment with demo mode:

```yaml
services:
  - type: web
    name: gmail-organizer-site
    runtime: static
    envVars:
      - key: VITE_DEMO_MODE
        value: "true"
```

## Security Considerations

1. **No Real Data**: Demo mode uses only mock data
2. **No Real API Calls**: Gmail API is not called in demo mode
3. **No Real Auth**: Google OAuth is bypassed, no real user accounts
4. **Environment Isolation**: Production deployments can set `VITE_DEMO_MODE=false`

## Adding Demo Mode to New Features

When adding new features:

1. Check if demo mode is enabled:
   ```tsx
   const isDemoMode = import.meta.env.VITE_DEMO_MODE === 'true';
   ```

2. Provide mock data for demo mode:
   ```tsx
   const data = isDemoMode ? DEMO_DATA : await fetchRealData();
   ```

3. Disable real API calls in demo mode:
   ```tsx
   if (!isDemoMode) {
     await gmailApi.syncEmails();
   }
   ```

## Testing Demo Mode

```bash
# Local development with demo mode
VITE_DEMO_MODE=true npm run dev

# Build with demo mode
VITE_DEMO_MODE=true npm run build

# Local development without demo mode
npm run dev
```

## File Structure

```
website/src/
|-- main.tsx                     # Router setup with demo routes
|-- App.tsx                      # Landing page (unchanged by demo mode)
|-- pages/
|   |-- auth/
|   |   +-- SignInPage.tsx       # Demo-aware sign-in with persona selector
|   +-- demo/
|       |-- DemoLayout.tsx       # Demo layout with DemoProvider
|       +-- DemoPage.tsx         # Main demo experience page
|-- contexts/
|   +-- demo-context.tsx         # Demo state management
+-- lib/
    |-- demo-data.ts             # Mock data definitions
    +-- utils.ts                 # Utility functions
```

## Enabling/Disabling Demo Mode

### Enable Demo Mode
```bash
# In .env or environment
VITE_DEMO_MODE=true
```

### Disable Demo Mode
```bash
# Remove the variable or set to false
VITE_DEMO_MODE=false
```

### Render Dashboard
1. Go to your service in Render Dashboard
2. Navigate to Environment tab
3. Add/modify `VITE_DEMO_MODE` environment variable
4. Trigger a new deploy
