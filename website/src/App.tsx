import { motion } from 'framer-motion'
import {
  Mail,
  Zap,
  Shield,
  Brain,
  Inbox,
  Tag,
  RefreshCw,
  Github,
  ExternalLink,
  CheckCircle2,
  Sparkles,
  Database,
  Timer
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

const fadeInUp = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 }
}

const staggerContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1
    }
  }
}

function App() {
  return (
    <div className="min-h-screen bg-background">
      {/* Hero Section */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-gmail-blue/5" />
        <div className="container mx-auto px-4 py-24 md:py-32">
          <motion.div
            initial="hidden"
            animate="visible"
            variants={staggerContainer}
            className="text-center max-w-4xl mx-auto"
          >
            <motion.div variants={fadeInUp} className="flex justify-center mb-6">
              <Badge variant="secondary" className="text-sm px-4 py-1">
                <Sparkles className="w-4 h-4 mr-2" />
                AI-Powered Email Management
              </Badge>
            </motion.div>

            <motion.h1
              variants={fadeInUp}
              className="text-5xl md:text-7xl font-bold tracking-tight mb-6"
            >
              Gmail <span className="text-primary">Organizer</span>
            </motion.h1>

            <motion.p
              variants={fadeInUp}
              className="text-xl md:text-2xl text-muted-foreground mb-8 max-w-2xl mx-auto"
            >
              Automatically categorize and organize thousands of emails across multiple Gmail accounts using Claude AI.
            </motion.p>

            <motion.div variants={fadeInUp} className="flex flex-wrap gap-4 justify-center">
              <Button size="lg" asChild>
                <a href="https://github.com/dmhernandez2525/gmail-organizer" target="_blank" rel="noopener noreferrer">
                  <Github className="mr-2 h-5 w-5" />
                  View on GitHub
                </a>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <a href="#features">
                  Learn More
                  <ExternalLink className="ml-2 h-4 w-4" />
                </a>
              </Button>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-16 bg-muted/30">
        <div className="container mx-auto px-4">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
            className="grid grid-cols-2 md:grid-cols-4 gap-8"
          >
            {[
              { value: '80,000+', label: 'Emails Processed', icon: Mail },
              { value: '< 10min', label: 'Full Inbox Scan', icon: Timer },
              { value: '95%', label: 'Classification Accuracy', icon: Brain },
              { value: '$0', label: 'With Claude Code CLI', icon: Zap }
            ].map((stat, index) => (
              <motion.div
                key={index}
                variants={fadeInUp}
                className="text-center"
              >
                <stat.icon className="w-8 h-8 mx-auto mb-3 text-primary" />
                <div className="text-3xl md:text-4xl font-bold mb-1">{stat.value}</div>
                <div className="text-sm text-muted-foreground">{stat.label}</div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-24">
        <div className="container mx-auto px-4">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
            className="text-center mb-16"
          >
            <motion.h2 variants={fadeInUp} className="text-3xl md:text-4xl font-bold mb-4">
              Powerful Features
            </motion.h2>
            <motion.p variants={fadeInUp} className="text-lg text-muted-foreground max-w-2xl mx-auto">
              Everything you need to tame your inbox chaos
            </motion.p>
          </motion.div>

          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
            className="grid md:grid-cols-2 lg:grid-cols-3 gap-6"
          >
            {[
              {
                icon: Brain,
                title: 'AI-Powered Classification',
                description: 'Claude AI analyzes sender, subject, and content to intelligently categorize emails with 95% accuracy.'
              },
              {
                icon: RefreshCw,
                title: 'Incremental Sync',
                description: 'After initial sync, future runs only fetch NEW emails using Gmail History API - seconds instead of hours!'
              },
              {
                icon: Inbox,
                title: 'Multi-Account Support',
                description: 'Manage 5+ Gmail accounts from one interface. OAuth tokens stored securely and encrypted.'
              },
              {
                icon: Tag,
                title: 'Smart Categories',
                description: 'Job search focused categories: Interviews, Applications, Offers, plus general categories for newsletters, shopping, finance.'
              },
              {
                icon: Database,
                title: 'Checkpoint System',
                description: 'Progress is saved after each batch. Interrupted? Resume exactly where you left off.'
              },
              {
                icon: Shield,
                title: 'Privacy First',
                description: 'All processing happens locally. Email content only sent to Claude for classification. No data stored externally.'
              }
            ].map((feature, index) => (
              <motion.div key={index} variants={fadeInUp}>
                <Card className="h-full hover:shadow-lg transition-shadow">
                  <CardHeader>
                    <feature.icon className="w-10 h-10 text-primary mb-2" />
                    <CardTitle>{feature.title}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <CardDescription className="text-base">
                      {feature.description}
                    </CardDescription>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="py-24 bg-muted/30">
        <div className="container mx-auto px-4">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
            className="text-center mb-16"
          >
            <motion.h2 variants={fadeInUp} className="text-3xl md:text-4xl font-bold mb-4">
              How It Works
            </motion.h2>
            <motion.p variants={fadeInUp} className="text-lg text-muted-foreground max-w-2xl mx-auto">
              From chaos to organized inbox in three simple steps
            </motion.p>
          </motion.div>

          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
            className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto"
          >
            {[
              {
                step: '01',
                title: 'Connect Your Gmail',
                description: 'Add one or more Gmail accounts via secure OAuth. Your credentials are never stored - only encrypted tokens.'
              },
              {
                step: '02',
                title: 'AI Analyzes Emails',
                description: 'Claude AI scans your inbox, learning patterns from senders and subjects to suggest optimal categories.'
              },
              {
                step: '03',
                title: 'Auto-Apply Labels',
                description: 'Gmail labels are created and applied automatically. Future syncs only process new emails.'
              }
            ].map((item, index) => (
              <motion.div
                key={index}
                variants={fadeInUp}
                className="relative"
              >
                <div className="text-7xl font-bold text-primary/10 absolute -top-6 -left-2">
                  {item.step}
                </div>
                <Card className="relative bg-card/50 backdrop-blur">
                  <CardHeader>
                    <CardTitle className="text-xl">{item.title}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <CardDescription className="text-base">
                      {item.description}
                    </CardDescription>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Tech Stack Section */}
      <section className="py-24">
        <div className="container mx-auto px-4">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
            className="text-center mb-16"
          >
            <motion.h2 variants={fadeInUp} className="text-3xl md:text-4xl font-bold mb-4">
              Built With Modern Tech
            </motion.h2>
          </motion.div>

          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
            className="flex flex-wrap justify-center gap-4"
          >
            {[
              'Python 3.11',
              'Streamlit',
              'Claude AI',
              'Gmail API',
              'OAuth 2.0',
              'React',
              'Tailwind CSS v4',
              'TypeScript',
              'Vite'
            ].map((tech, index) => (
              <motion.div key={index} variants={fadeInUp}>
                <Badge variant="outline" className="text-base px-4 py-2">
                  {tech}
                </Badge>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Performance Section */}
      <section className="py-24 bg-muted/30">
        <div className="container mx-auto px-4">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
            className="max-w-4xl mx-auto"
          >
            <motion.h2 variants={fadeInUp} className="text-3xl md:text-4xl font-bold mb-8 text-center">
              Gmail API Optimizations
            </motion.h2>

            <motion.div variants={fadeInUp}>
              <Card>
                <CardContent className="p-6">
                  <div className="space-y-4">
                    {[
                      { label: 'Batch API requests', value: '50 emails per HTTP request' },
                      { label: 'Metadata-only fetching', value: '10x faster than full body' },
                      { label: 'Incremental sync', value: 'Only new emails after first run' },
                      { label: 'Partial batch recovery', value: 'Saves successful emails on rate limit' },
                      { label: 'Exponential backoff', value: 'Smart retry with 3^n multiplier' },
                      { label: 'Checkpoint system', value: 'Resume from interruption' }
                    ].map((item, index) => (
                      <div key={index} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                        <div className="flex items-center gap-2">
                          <CheckCircle2 className="w-5 h-5 text-gmail-green" />
                          <span>{item.label}</span>
                        </div>
                        <Badge variant="secondary">{item.value}</Badge>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24">
        <div className="container mx-auto px-4">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
            className="text-center max-w-3xl mx-auto"
          >
            <motion.h2 variants={fadeInUp} className="text-3xl md:text-4xl font-bold mb-4">
              Ready to Organize Your Inbox?
            </motion.h2>
            <motion.p variants={fadeInUp} className="text-lg text-muted-foreground mb-8">
              Open source and free to use. Clone the repo and get started in minutes.
            </motion.p>
            <motion.div variants={fadeInUp} className="flex flex-wrap gap-4 justify-center">
              <Button size="lg" asChild>
                <a href="https://github.com/dmhernandez2525/gmail-organizer" target="_blank" rel="noopener noreferrer">
                  <Github className="mr-2 h-5 w-5" />
                  Clone Repository
                </a>
              </Button>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 border-t border-border">
        <div className="container mx-auto px-4">
          <div className="flex flex-col md:flex-row justify-between items-center gap-4">
            <div className="flex items-center gap-2">
              <Mail className="w-5 h-5 text-primary" />
              <span className="font-semibold">Gmail Organizer</span>
            </div>
            <div className="text-sm text-muted-foreground">
              Open source under MIT License.
            </div>
            <div className="flex gap-4">
              <a
                href="https://github.com/dmhernandez2525/gmail-organizer"
                target="_blank"
                rel="noopener noreferrer"
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                <Github className="w-5 h-5" />
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}

export default App
