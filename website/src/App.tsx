import { motion, useScroll, useTransform } from 'framer-motion'
import { useState, useEffect } from 'react'
import {
  Mail,
  Zap,
  Shield,
  Brain,
  Tag,
  RefreshCw,
  Github,
  ChevronRight,
  CheckCircle2,
  Database,
  Timer,
  ArrowRight,
  Terminal,
  Layers,
  Users,
  Code2,
  Rocket,
  Target,
  Menu,
  X
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

const fadeInUp = {
  hidden: { opacity: 0, y: 30 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6 } }
}

const staggerContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.1 }
  }
}

const scaleIn = {
  hidden: { opacity: 0, scale: 0.9 },
  visible: { opacity: 1, scale: 1, transition: { duration: 0.5 } }
}

// Navigation Component
function Navigation() {
  const [isScrolled, setIsScrolled] = useState(false)
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)

  useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 50)
    window.addEventListener('scroll', handleScroll)
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  const navLinks = [
    { href: '#features', label: 'Features' },
    { href: '#how-it-works', label: 'How It Works' },
    { href: '#performance', label: 'Performance' },
    { href: '#roadmap', label: 'Roadmap' },
    { href: '#docs', label: 'Documentation' }
  ]

  return (
    <nav className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
      isScrolled ? 'bg-background/80 backdrop-blur-xl border-b border-border' : ''
    }`}>
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <a href="#" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center">
              <Mail className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-lg">Gmail Organizer</span>
          </a>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center gap-8">
            {navLinks.map(link => (
              <a key={link.href} href={link.href} className="nav-link text-sm text-muted-foreground hover:text-foreground">
                {link.label}
              </a>
            ))}
          </div>

          <div className="hidden md:flex items-center gap-4">
            <Button variant="ghost" size="sm" asChild>
              <a href="https://github.com/dmhernandez2525/gmail-organizer" target="_blank" rel="noopener noreferrer">
                <Github className="w-4 h-4 mr-2" />
                GitHub
              </a>
            </Button>
            <Button size="sm" className="bg-gradient-to-r from-purple-600 to-cyan-600 hover:from-purple-700 hover:to-cyan-700">
              Get Started
            </Button>
          </div>

          {/* Mobile Menu Button */}
          <button className="md:hidden" onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}>
            {isMobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>

        {/* Mobile Menu */}
        {isMobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="md:hidden py-4 border-t border-border"
          >
            {navLinks.map(link => (
              <a
                key={link.href}
                href={link.href}
                className="block py-2 text-muted-foreground hover:text-foreground"
                onClick={() => setIsMobileMenuOpen(false)}
              >
                {link.label}
              </a>
            ))}
          </motion.div>
        )}
      </div>
    </nav>
  )
}

// Hero Section
function HeroSection() {
  const { scrollY } = useScroll()
  const y = useTransform(scrollY, [0, 500], [0, 150])
  const opacity = useTransform(scrollY, [0, 300], [1, 0])

  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden hero-gradient grid-pattern">
      {/* Floating orbs */}
      <motion.div
        style={{ y }}
        className="absolute top-20 left-10 w-72 h-72 bg-purple-500/20 rounded-full blur-3xl"
      />
      <motion.div
        style={{ y: useTransform(scrollY, [0, 500], [0, -100]) }}
        className="absolute bottom-20 right-10 w-96 h-96 bg-cyan-500/20 rounded-full blur-3xl"
      />

      <motion.div style={{ opacity }} className="container mx-auto px-4 pt-24">
        <motion.div
          initial="hidden"
          animate="visible"
          variants={staggerContainer}
          className="text-center max-w-5xl mx-auto"
        >
          <motion.div variants={fadeInUp} className="mb-6">
            <Badge className="bg-purple-500/10 text-purple-400 border-purple-500/30 px-4 py-2 text-sm">
              <Zap className="w-4 h-4 mr-2" />
              AI-Powered Email Management
            </Badge>
          </motion.div>

          <motion.h1
            variants={fadeInUp}
            className="text-5xl md:text-7xl lg:text-8xl font-bold tracking-tight mb-6"
          >
            Organize Your{' '}
            <span className="gradient-text">Gmail</span>
            <br />
            With Intelligence
          </motion.h1>

          <motion.p
            variants={fadeInUp}
            className="text-xl md:text-2xl text-muted-foreground mb-10 max-w-3xl mx-auto leading-relaxed"
          >
            Automatically categorize and organize thousands of emails across multiple Gmail accounts.
            Smart sync fetches only new emails in seconds.
          </motion.p>

          <motion.div variants={fadeInUp} className="flex flex-wrap gap-4 justify-center mb-16">
            <Button size="lg" className="bg-gradient-to-r from-purple-600 to-cyan-600 hover:from-purple-700 hover:to-cyan-700 text-lg px-8 py-6" asChild>
              <a href="https://github.com/dmhernandez2525/gmail-organizer" target="_blank" rel="noopener noreferrer">
                <Github className="mr-2 h-5 w-5" />
                Clone Repository
                <ArrowRight className="ml-2 h-5 w-5" />
              </a>
            </Button>
            <Button size="lg" variant="outline" className="text-lg px-8 py-6 border-purple-500/30 hover:bg-purple-500/10" asChild>
              <a href="#docs">
                <Terminal className="mr-2 h-5 w-5" />
                View Documentation
              </a>
            </Button>
          </motion.div>

          {/* Hero Illustration */}
          <motion.div
            variants={scaleIn}
            className="relative max-w-4xl mx-auto"
          >
            <div className="glass-card rounded-2xl p-8 glow-purple">
              <img
                src="/images/hero-illustration.svg"
                alt="Gmail Organizer AI"
                className="w-full h-auto"
              />
            </div>
          </motion.div>
        </motion.div>
      </motion.div>

      {/* Scroll indicator */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1 }}
        className="absolute bottom-8 left-1/2 -translate-x-1/2"
      >
        <motion.div
          animate={{ y: [0, 10, 0] }}
          transition={{ repeat: Infinity, duration: 2 }}
          className="w-6 h-10 border-2 border-muted-foreground/30 rounded-full flex justify-center pt-2"
        >
          <div className="w-1.5 h-3 bg-purple-500 rounded-full" />
        </motion.div>
      </motion.div>
    </section>
  )
}

// Stats Section
function StatsSection() {
  const stats = [
    { value: '80,000+', label: 'Emails Processed', icon: Mail, color: 'text-purple-400' },
    { value: '< 10 min', label: 'Full Sync Time', icon: Timer, color: 'text-cyan-400' },
    { value: '95%', label: 'Accuracy Rate', icon: Target, color: 'text-green-400' },
    { value: 'Seconds', label: 'Incremental Sync', icon: Zap, color: 'text-yellow-400' }
  ]

  return (
    <section className="py-24 relative">
      <div className="section-divider mb-24" />
      <div className="container mx-auto px-4">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={staggerContainer}
          className="grid grid-cols-2 md:grid-cols-4 gap-8"
        >
          {stats.map((stat, index) => (
            <motion.div
              key={index}
              variants={fadeInUp}
              className="text-center"
            >
              <div className={`w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-purple-500/10 to-cyan-500/10 flex items-center justify-center ${stat.color}`}>
                <stat.icon className="w-8 h-8" />
              </div>
              <div className="text-4xl md:text-5xl font-bold mb-2 stat-value">{stat.value}</div>
              <div className="text-muted-foreground">{stat.label}</div>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  )
}

// Features Section
function FeaturesSection() {
  const features = [
    {
      icon: Brain,
      title: 'AI Classification',
      description: 'Leverages advanced AI to analyze sender patterns, subject lines, and content for intelligent email categorization with 95% accuracy.',
      color: 'from-purple-500 to-purple-600'
    },
    {
      icon: RefreshCw,
      title: 'Incremental Sync',
      description: 'After initial sync, uses Gmail History API to fetch only new emails. What took hours now takes seconds.',
      color: 'from-cyan-500 to-cyan-600'
    },
    {
      icon: Users,
      title: 'Multi-Account',
      description: 'Manage 5+ Gmail accounts from one interface. Each account gets secure OAuth tokens stored locally.',
      color: 'from-blue-500 to-blue-600'
    },
    {
      icon: Tag,
      title: 'Smart Categories',
      description: 'Job search focused categories (Interviews, Applications, Offers) plus general categories for newsletters, finance, shopping.',
      color: 'from-green-500 to-green-600'
    },
    {
      icon: Database,
      title: 'Checkpoint System',
      description: 'Progress saved after every batch. Network issues or rate limits? Resume exactly where you left off.',
      color: 'from-orange-500 to-orange-600'
    },
    {
      icon: Shield,
      title: 'Privacy First',
      description: 'All processing happens locally on your machine. Email content only sent to AI for classification. Zero external storage.',
      color: 'from-pink-500 to-pink-600'
    }
  ]

  return (
    <section id="features" className="py-24 relative">
      <div className="container mx-auto px-4">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={staggerContainer}
          className="text-center mb-16"
        >
          <motion.div variants={fadeInUp}>
            <Badge className="bg-cyan-500/10 text-cyan-400 border-cyan-500/30 mb-4">
              Core Features
            </Badge>
          </motion.div>
          <motion.h2 variants={fadeInUp} className="text-4xl md:text-5xl font-bold mb-4">
            Everything You Need
          </motion.h2>
          <motion.p variants={fadeInUp} className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Powerful features designed to tame inbox chaos and boost productivity
          </motion.p>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={staggerContainer}
          className="grid md:grid-cols-2 lg:grid-cols-3 gap-6"
        >
          {features.map((feature, index) => (
            <motion.div key={index} variants={fadeInUp}>
              <Card className="h-full glass-card feature-card border-border hover:border-purple-500/50">
                <CardHeader>
                  <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${feature.color} flex items-center justify-center mb-4`}>
                    <feature.icon className="w-6 h-6 text-white" />
                  </div>
                  <CardTitle className="text-xl">{feature.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <CardDescription className="text-base text-muted-foreground">
                    {feature.description}
                  </CardDescription>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  )
}

// How It Works Section
function HowItWorksSection() {
  const steps = [
    {
      number: '01',
      title: 'Connect Gmail',
      description: 'Add your Gmail accounts via secure OAuth 2.0. Tokens are encrypted and stored locally - your password never leaves your machine.',
      icon: Users
    },
    {
      number: '02',
      title: 'AI Analysis',
      description: 'The AI scans your inbox, analyzing sender patterns, subject lines, and email metadata to understand your unique email landscape.',
      icon: Brain
    },
    {
      number: '03',
      title: 'Smart Sync',
      description: 'Initial sync fetches all emails. Future runs use Gmail History API - only new emails are processed, completing in seconds.',
      icon: RefreshCw
    },
    {
      number: '04',
      title: 'Auto Labels',
      description: 'Gmail labels are automatically created and applied. Your inbox is organized without lifting a finger.',
      icon: Tag
    }
  ]

  return (
    <section id="how-it-works" className="py-24 relative">
      <div className="section-divider mb-24" />
      <div className="container mx-auto px-4">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={staggerContainer}
          className="text-center mb-16"
        >
          <motion.div variants={fadeInUp}>
            <Badge className="bg-purple-500/10 text-purple-400 border-purple-500/30 mb-4">
              Simple Process
            </Badge>
          </motion.div>
          <motion.h2 variants={fadeInUp} className="text-4xl md:text-5xl font-bold mb-4">
            How It Works
          </motion.h2>
          <motion.p variants={fadeInUp} className="text-xl text-muted-foreground max-w-2xl mx-auto">
            From chaos to organized inbox in four simple steps
          </motion.p>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={staggerContainer}
          className="grid md:grid-cols-2 lg:grid-cols-4 gap-8"
        >
          {steps.map((step, index) => (
            <motion.div
              key={index}
              variants={fadeInUp}
              className="relative"
            >
              <div className="text-8xl font-bold text-purple-500/10 absolute -top-8 -left-4">
                {step.number}
              </div>
              <Card className="relative glass-card border-border pt-8">
                <CardHeader>
                  <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-purple-500/20 to-cyan-500/20 flex items-center justify-center mb-4 border border-purple-500/30">
                    <step.icon className="w-7 h-7 text-purple-400" />
                  </div>
                  <CardTitle>{step.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <CardDescription className="text-muted-foreground">
                    {step.description}
                  </CardDescription>
                </CardContent>
              </Card>
              {index < steps.length - 1 && (
                <div className="hidden lg:block absolute top-1/2 -right-4 transform -translate-y-1/2">
                  <ChevronRight className="w-8 h-8 text-purple-500/30" />
                </div>
              )}
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  )
}

// Performance Section
function PerformanceSection() {
  const metrics = [
    { label: 'Batch API requests', value: '50 emails/request', description: 'Efficient batching reduces HTTP overhead' },
    { label: 'Metadata-only mode', value: '10x faster', description: 'Skip email bodies for classification' },
    { label: 'Incremental sync', value: 'Seconds', description: 'Only fetch new emails after initial sync' },
    { label: 'Partial recovery', value: 'Zero loss', description: 'Rate limits save successful emails' },
    { label: 'Exponential backoff', value: '3^n retry', description: 'Smart retry logic for reliability' },
    { label: 'Checkpoint system', value: 'Full resume', description: 'Continue from any interruption' }
  ]

  return (
    <section id="performance" className="py-24 relative">
      <div className="section-divider mb-24" />
      <div className="container mx-auto px-4">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
          >
            <motion.div variants={fadeInUp}>
              <Badge className="bg-green-500/10 text-green-400 border-green-500/30 mb-4">
                Optimized
              </Badge>
            </motion.div>
            <motion.h2 variants={fadeInUp} className="text-4xl md:text-5xl font-bold mb-4">
              Gmail API
              <br />
              <span className="gradient-text">Optimizations</span>
            </motion.h2>
            <motion.p variants={fadeInUp} className="text-xl text-muted-foreground mb-8">
              Built to handle Gmail's strict rate limits gracefully while maximizing throughput.
            </motion.p>

            <motion.div variants={fadeInUp} className="glass-card rounded-xl p-6 mb-6">
              <h4 className="text-sm font-medium text-muted-foreground mb-4">Gmail API Limits</h4>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-2xl font-bold text-purple-400">15,000</div>
                  <div className="text-sm text-muted-foreground">quota units/min</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-cyan-400">3,000</div>
                  <div className="text-sm text-muted-foreground">max emails/min</div>
                </div>
              </div>
            </motion.div>

            <motion.div variants={fadeInUp}>
              <img src="/images/sync-illustration.svg" alt="Sync Process" className="w-full max-w-sm" />
            </motion.div>
          </motion.div>

          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
            className="space-y-4"
          >
            {metrics.map((metric, index) => (
              <motion.div
                key={index}
                variants={fadeInUp}
                className="glass-card rounded-xl p-5 flex items-center justify-between hover:border-purple-500/30 transition-colors"
              >
                <div className="flex items-center gap-4">
                  <CheckCircle2 className="w-6 h-6 text-green-400 flex-shrink-0" />
                  <div>
                    <div className="font-medium">{metric.label}</div>
                    <div className="text-sm text-muted-foreground">{metric.description}</div>
                  </div>
                </div>
                <Badge variant="secondary" className="bg-purple-500/10 text-purple-300 border-0">
                  {metric.value}
                </Badge>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </div>
    </section>
  )
}

// Roadmap Section
function RoadmapSection() {
  const roadmapItems = [
    {
      status: 'completed',
      title: 'Core Classification',
      description: 'AI-powered email categorization with batch processing',
      items: ['Multi-account support', 'Gmail label creation', 'Checkpoint system']
    },
    {
      status: 'completed',
      title: 'Incremental Sync',
      description: 'Gmail History API integration for lightning-fast updates',
      items: ['History ID tracking', 'Delta sync', 'State persistence']
    },
    {
      status: 'in-progress',
      title: 'Smart Filters',
      description: 'Auto-generate Gmail filters based on classification patterns',
      items: ['Pattern detection', 'Filter suggestions', 'One-click apply']
    },
    {
      status: 'planned',
      title: 'Analytics Dashboard',
      description: 'Visualize your email patterns and organization health',
      items: ['Email volume trends', 'Category distribution', 'Sender insights']
    },
    {
      status: 'planned',
      title: 'Mobile Companion',
      description: 'Quick classification on the go with a mobile-optimized interface',
      items: ['Quick actions', 'Push notifications', 'Swipe gestures']
    }
  ]

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-500'
      case 'in-progress': return 'bg-yellow-500'
      default: return 'bg-muted'
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed': return <Badge className="bg-green-500/10 text-green-400 border-green-500/30">Complete</Badge>
      case 'in-progress': return <Badge className="bg-yellow-500/10 text-yellow-400 border-yellow-500/30">In Progress</Badge>
      default: return <Badge className="bg-muted text-muted-foreground border-border">Planned</Badge>
    }
  }

  return (
    <section id="roadmap" className="py-24 relative">
      <div className="section-divider mb-24" />
      <div className="container mx-auto px-4">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={staggerContainer}
          className="text-center mb-16"
        >
          <motion.div variants={fadeInUp}>
            <Badge className="bg-orange-500/10 text-orange-400 border-orange-500/30 mb-4">
              <Rocket className="w-4 h-4 mr-2" />
              Roadmap
            </Badge>
          </motion.div>
          <motion.h2 variants={fadeInUp} className="text-4xl md:text-5xl font-bold mb-4">
            What's Next
          </motion.h2>
          <motion.p variants={fadeInUp} className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Our vision for the future of intelligent email management
          </motion.p>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={staggerContainer}
          className="max-w-4xl mx-auto relative"
        >
          {/* Timeline line */}
          <div className="absolute left-8 top-0 bottom-0 w-0.5 timeline-line hidden md:block" />

          {roadmapItems.map((item, index) => (
            <motion.div
              key={index}
              variants={fadeInUp}
              className="relative flex gap-8 mb-8"
            >
              {/* Timeline dot */}
              <div className="hidden md:flex flex-col items-center">
                <div className={`w-4 h-4 rounded-full ${getStatusColor(item.status)} z-10`} />
              </div>

              <Card className="flex-1 glass-card border-border hover:border-purple-500/30 transition-colors">
                <CardHeader>
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <CardTitle>{item.title}</CardTitle>
                    {getStatusBadge(item.status)}
                  </div>
                  <CardDescription>{item.description}</CardDescription>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2">
                    {item.items.map((subItem, subIndex) => (
                      <li key={subIndex} className="flex items-center gap-2 text-sm text-muted-foreground">
                        <CheckCircle2 className={`w-4 h-4 ${item.status === 'completed' ? 'text-green-400' : 'text-muted'}`} />
                        {subItem}
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  )
}

// Documentation Section
function DocsSection() {
  return (
    <section id="docs" className="py-24 relative">
      <div className="section-divider mb-24" />
      <div className="container mx-auto px-4">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={staggerContainer}
          className="text-center mb-16"
        >
          <motion.div variants={fadeInUp}>
            <Badge className="bg-blue-500/10 text-blue-400 border-blue-500/30 mb-4">
              <Code2 className="w-4 h-4 mr-2" />
              Documentation
            </Badge>
          </motion.div>
          <motion.h2 variants={fadeInUp} className="text-4xl md:text-5xl font-bold mb-4">
            Get Started
          </motion.h2>
          <motion.p variants={fadeInUp} className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Everything you need to set up and run Gmail Organizer
          </motion.p>
        </motion.div>

        <div className="grid lg:grid-cols-2 gap-8 max-w-6xl mx-auto">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={fadeInUp}
          >
            <Card className="glass-card border-border h-full">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Terminal className="w-5 h-5 text-purple-400" />
                  Quick Start
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="code-block">
                  <code className="text-green-400"># Clone the repository</code>
                  <br />
                  <code>git clone https://github.com/dmhernandez2525/gmail-organizer.git</code>
                  <br />
                  <code>cd gmail-organizer</code>
                  <br /><br />
                  <code className="text-green-400"># Set up environment</code>
                  <br />
                  <code>cp .env.example .env</code>
                  <br />
                  <code>python3 -m venv venv</code>
                  <br />
                  <code>source venv/bin/activate</code>
                  <br />
                  <code>pip install -r requirements.txt</code>
                  <br /><br />
                  <code className="text-green-400"># Launch the app</code>
                  <br />
                  <code>streamlit run frontend.py</code>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={fadeInUp}
            className="space-y-6"
          >
            <Card className="glass-card border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Layers className="w-5 h-5 text-cyan-400" />
                  Requirements
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-3">
                  <li className="flex items-center gap-3">
                    <Badge variant="outline">Python</Badge>
                    <span className="text-muted-foreground">3.11+</span>
                  </li>
                  <li className="flex items-center gap-3">
                    <Badge variant="outline">Gmail API</Badge>
                    <span className="text-muted-foreground">OAuth 2.0 credentials</span>
                  </li>
                  <li className="flex items-center gap-3">
                    <Badge variant="outline">Optional</Badge>
                    <span className="text-muted-foreground">Claude Code CLI for free classification</span>
                  </li>
                </ul>
              </CardContent>
            </Card>

            <Card className="glass-card border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Timer className="w-5 h-5 text-green-400" />
                  Sync Modes
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <div>
                      <div className="font-medium">Full Sync</div>
                      <div className="text-sm text-muted-foreground">First run - fetches all emails</div>
                    </div>
                    <Badge className="bg-yellow-500/10 text-yellow-400">~10 min</Badge>
                  </div>
                  <div className="flex justify-between items-center">
                    <div>
                      <div className="font-medium">Incremental Sync</div>
                      <div className="text-sm text-muted-foreground">Future runs - new emails only</div>
                    </div>
                    <Badge className="bg-green-500/10 text-green-400">Seconds</Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </div>
    </section>
  )
}

// CTA Section
function CTASection() {
  return (
    <section className="py-24 relative">
      <div className="section-divider mb-24" />
      <div className="container mx-auto px-4">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={staggerContainer}
          className="text-center max-w-4xl mx-auto"
        >
          <motion.div
            variants={scaleIn}
            className="glass-card rounded-3xl p-12 md:p-16 glow-purple relative overflow-hidden"
          >
            {/* Background decoration */}
            <div className="absolute top-0 right-0 w-64 h-64 bg-purple-500/20 rounded-full blur-3xl" />
            <div className="absolute bottom-0 left-0 w-48 h-48 bg-cyan-500/20 rounded-full blur-3xl" />

            <div className="relative">
              <motion.h2 variants={fadeInUp} className="text-4xl md:text-5xl font-bold mb-4">
                Ready to Organize?
              </motion.h2>
              <motion.p variants={fadeInUp} className="text-xl text-muted-foreground mb-8">
                Open source and free to use. Clone the repo and take control of your inbox.
              </motion.p>
              <motion.div variants={fadeInUp} className="flex flex-wrap gap-4 justify-center">
                <Button size="lg" className="bg-gradient-to-r from-purple-600 to-cyan-600 hover:from-purple-700 hover:to-cyan-700 text-lg px-8" asChild>
                  <a href="https://github.com/dmhernandez2525/gmail-organizer" target="_blank" rel="noopener noreferrer">
                    <Github className="mr-2 h-5 w-5" />
                    Get Started Free
                  </a>
                </Button>
              </motion.div>
            </div>
          </motion.div>
        </motion.div>
      </div>
    </section>
  )
}

// Footer
function Footer() {
  return (
    <footer className="py-12 border-t border-border">
      <div className="container mx-auto px-4">
        <div className="grid md:grid-cols-4 gap-8 mb-12">
          <div className="md:col-span-2">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center">
                <Mail className="w-5 h-5 text-white" />
              </div>
              <span className="font-bold text-lg">Gmail Organizer</span>
            </div>
            <p className="text-muted-foreground max-w-md">
              AI-powered email management that automatically categorizes and organizes
              your Gmail inbox. Open source and privacy-focused.
            </p>
          </div>

          <div>
            <h4 className="font-semibold mb-4">Links</h4>
            <ul className="space-y-2 text-muted-foreground">
              <li><a href="#features" className="hover:text-foreground transition-colors">Features</a></li>
              <li><a href="#how-it-works" className="hover:text-foreground transition-colors">How It Works</a></li>
              <li><a href="#roadmap" className="hover:text-foreground transition-colors">Roadmap</a></li>
              <li><a href="#docs" className="hover:text-foreground transition-colors">Documentation</a></li>
            </ul>
          </div>

          <div>
            <h4 className="font-semibold mb-4">Resources</h4>
            <ul className="space-y-2 text-muted-foreground">
              <li>
                <a href="https://github.com/dmhernandez2525/gmail-organizer" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors flex items-center gap-2">
                  <Github className="w-4 h-4" />
                  GitHub
                </a>
              </li>
              <li>
                <a href="https://github.com/dmhernandez2525/gmail-organizer/issues" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">
                  Report Issues
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div className="section-divider mb-8" />

        <div className="flex flex-col md:flex-row justify-between items-center gap-4 text-sm text-muted-foreground">
          <div>Open source under MIT License.</div>
          <div className="flex items-center gap-4">
            <a href="https://github.com/dmhernandez2525/gmail-organizer" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">
              <Github className="w-5 h-5" />
            </a>
          </div>
        </div>
      </div>
    </footer>
  )
}

// Main App
function App() {
  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <HeroSection />
      <StatsSection />
      <FeaturesSection />
      <HowItWorksSection />
      <PerformanceSection />
      <RoadmapSection />
      <DocsSection />
      <CTASection />
      <Footer />
    </div>
  )
}

export default App
