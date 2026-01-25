import Foundation

// MARK: - Analysis Types

enum AnalysisType: String, CaseIterable {
    case fullAnalysis = "Full Analysis"
    case threadAnalysis = "Thread Analysis"
    case patternDetection = "Pattern Detection"
    case priorityScoring = "Priority Scoring"
    case actionItems = "Action Items"
    case conflictDetection = "Conflict Detection"
    case senderReputation = "Sender Analysis"
    case timeAnalysis = "Time-Based Analysis"
}

// MARK: - Prompt Templates

struct PromptTemplates {

    // MARK: - Main Processing Prompt

    static func generateFullProcessingPrompt(
        account: AccountInfo,
        syncStatePath: String,
        resultsPath: String,
        projectRoot: String
    ) -> String {
        return """
        ################################################################################
        #                     GMAIL ORGANIZER - EMAIL PROCESSING                        #
        #                            COMPREHENSIVE ANALYSIS                             #
        ################################################################################

        ACCOUNT: \(account.email)
        TOTAL EMAILS: \(account.emailCount.formatted())
        SYNC STATE FILE: \(syncStatePath)
        RESULTS OUTPUT: \(resultsPath)

        ================================================================================
        IMPORTANT: READ THIS ENTIRE PROMPT BEFORE STARTING
        ================================================================================

        You are an expert email analyst. Your task is to thoroughly analyze this Gmail
        inbox and provide actionable insights. This is NOT just about labeling - it's
        about understanding the email ecosystem of this account.

        ================================================================================
        PHASE 1: DATA EXTRACTION & VALIDATION
        ================================================================================

        First, read the sync state file and extract ALL email data:

        ```python
        import json
        with open('\(syncStatePath)', 'r') as f:
            data = json.load(f)

        emails = data.get('emails', [])
        print(f"Total emails in file: {len(emails)}")
        ```

        For EACH email, extract and store:
        - email_id (unique identifier)
        - thread_id (for grouping conversations)
        - subject (with [Re:], [Fwd:] prefixes noted)
        - sender (email address AND display name)
        - recipients (to, cc, bcc)
        - date (timestamp)
        - labels (existing Gmail labels)
        - snippet (preview text)
        - is_read status
        - has_attachments

        OUTPUT REQUIREMENT #1 - Print a validation summary:
        ```
        === DATA VALIDATION ===
        Total emails loaded: X
        Emails with thread_id: X
        Unique threads: X
        Date range: [oldest] to [newest]
        Emails missing sender: X
        Emails missing subject: X
        ```

        ================================================================================
        PHASE 2: THREAD ANALYSIS (CRITICAL)
        ================================================================================

        Group emails by thread_id to understand conversations:

        For each thread with 2+ emails, analyze:

        1. THREAD STRUCTURE:
           - Total emails in thread
           - Participants (who's involved)
           - Duration (first email to last)
           - Response times between messages

        2. THREAD CLASSIFICATION:
           - One-way (newsletters, notifications)
           - Two-way conversation
           - Multi-party discussion
           - Chain/forwarded thread

        3. THREAD STATUS:
           - Active (recent activity)
           - Stale (no activity > 30 days)
           - Awaiting response (last email FROM this account)
           - Needs response (last email TO this account, unanswered)

        OUTPUT REQUIREMENT #2 - Thread Summary Table:
        ```
        === THREAD ANALYSIS ===
        Total threads: X
        Active conversations: X
        Awaiting your response: X (LIST THESE - IMPORTANT!)
        Stale threads: X

        TOP 10 LONGEST THREADS:
        | Thread Subject | Participants | Emails | Duration | Status |
        |----------------|--------------|--------|----------|--------|
        | ...            | ...          | ...    | ...      | ...    |

        THREADS NEEDING ATTENTION:
        [List threads where user hasn't responded to incoming email]
        ```

        ================================================================================
        PHASE 3: SENDER ANALYSIS & REPUTATION
        ================================================================================

        Analyze each unique sender:

        1. SENDER METRICS:
           - Total emails from sender
           - First contact date
           - Last contact date
           - Average emails per month
           - Response rate (do they reply to this account?)

        2. SENDER CLASSIFICATION:
           - Human (personal contact)
           - Automated (noreply@, notifications)
           - Newsletter/Marketing
           - Transactional (receipts, confirmations)
           - Unknown/Spam-like

        3. RELATIONSHIP STRENGTH:
           - Strong (frequent 2-way communication)
           - Medium (occasional contact)
           - Weak (mostly one-way)
           - New (recent first contact)

        4. DOMAIN ANALYSIS:
           - Group senders by domain
           - Identify company relationships
           - Flag suspicious domains

        OUTPUT REQUIREMENT #3 - Sender Report:
        ```
        === SENDER ANALYSIS ===
        Unique senders: X
        Human contacts: X
        Automated senders: X
        Newsletter sources: X

        TOP 20 SENDERS BY VOLUME:
        | Sender | Count | Type | Relationship | Last Contact |
        |--------|-------|------|--------------|--------------|
        | ...    | ...   | ...  | ...          | ...          |

        DOMAIN BREAKDOWN:
        | Domain | Emails | Primary Type |
        |--------|--------|--------------|
        | gmail.com | X | Personal |
        | company.com | X | Work |
        | ...    | ...   | ...    |

        NEW CONTACTS (Last 30 days):
        [List new senders with context]

        POTENTIALLY IMPORTANT SENDERS NOT RESPONDED TO:
        [Critical - list senders who sent emails that may need response]
        ```

        ================================================================================
        PHASE 4: TEMPORAL PATTERN ANALYSIS
        ================================================================================

        Analyze time-based patterns:

        1. VOLUME PATTERNS:
           - Emails per day/week/month
           - Busiest days of week
           - Busiest hours of day
           - Trend (increasing/decreasing/stable)

        2. RESPONSE PATTERNS:
           - Average response time (this account)
           - Best response time (quick replies)
           - Worst response time (delayed replies)
           - Unanswered emails aging

        3. SEASONAL PATTERNS:
           - Monthly variations
           - Holiday effects
           - Unusual spikes (investigate cause)

        OUTPUT REQUIREMENT #4 - Temporal Analysis:
        ```
        === TIME-BASED ANALYSIS ===

        VOLUME BY DAY OF WEEK:
        Mon: ████████ (X emails)
        Tue: ██████████ (X emails)
        ...

        VOLUME BY HOUR:
        [Show peak hours]

        MONTHLY TREND (Last 12 months):
        [Show monthly counts with trend indicator]

        RESPONSE TIME ANALYSIS:
        - Emails sent by this account: X
        - Average time to respond: X hours
        - Oldest unanswered incoming email: [date, subject, sender]
        ```

        ================================================================================
        PHASE 5: CONTENT PATTERN DETECTION
        ================================================================================

        Analyze email content for patterns:

        1. SUBJECT LINE PATTERNS:
           - Common prefixes ([ACTION], [URGENT], etc.)
           - Keyword frequency
           - Question vs statement subjects

        2. TOPIC CLUSTERING:
           - Group emails by detected topic
           - Identify recurring themes
           - Flag unusual/outlier topics

        3. SENTIMENT INDICATORS:
           - Urgent language detection
           - Negative sentiment flags
           - Positive/neutral classification

        4. ACTION ITEM DETECTION:
           - Emails containing requests
           - Deadlines mentioned
           - Questions asked (needing answers)
           - Commitments made

        OUTPUT REQUIREMENT #5 - Content Patterns:
        ```
        === CONTENT ANALYSIS ===

        DETECTED TOPICS:
        | Topic | Email Count | Example Subject |
        |-------|-------------|-----------------|
        | ...   | ...         | ...             |

        URGENT/HIGH-PRIORITY INDICATORS FOUND:
        [List emails with urgent language]

        ACTION ITEMS DETECTED:
        | Email Subject | From | Action Required | Deadline |
        |---------------|------|-----------------|----------|
        | ...           | ...  | ...             | ...      |

        UNANSWERED QUESTIONS:
        [List emails containing questions directed at this account]
        ```

        ================================================================================
        PHASE 6: CONFLICT & ANOMALY DETECTION
        ================================================================================

        Look for potential issues:

        1. SCHEDULING CONFLICTS:
           - Multiple events same time
           - Overlapping commitments
           - Missed deadlines

        2. COMMUNICATION GAPS:
           - Long gaps in important threads
           - Dropped conversations
           - Unanswered important emails

        3. ANOMALIES:
           - Unusual sender patterns
           - Unexpected email volume spikes
           - Potential phishing indicators
           - Duplicate emails

        4. RELATIONSHIP ISSUES:
           - Threads with negative sentiment
           - Escalation patterns
           - Unresolved disputes

        OUTPUT REQUIREMENT #6 - Issues Report:
        ```
        === POTENTIAL ISSUES DETECTED ===

        CRITICAL (Needs immediate attention):
        [List with full details]

        WARNING (Should review soon):
        [List with details]

        INFO (For awareness):
        [List notable items]

        ANOMALIES:
        [Any unusual patterns detected]
        ```

        ================================================================================
        PHASE 7: SMART CATEGORIZATION
        ================================================================================

        Based on ALL analysis above, categorize each email:

        PRIMARY CATEGORIES (mutually exclusive):
        - work/professional
        - personal
        - finance (bills, banking, purchases)
        - travel (bookings, itineraries)
        - social (social media, events)
        - newsletters (subscriptions, marketing)
        - notifications (automated alerts)
        - spam_candidate (potential spam)

        SECONDARY LABELS (can have multiple):
        - action_required
        - awaiting_response
        - reference (keep for future)
        - time_sensitive
        - has_attachment
        - from_vip (important sender)

        SPECIAL LABELS (job search specific):
        - job_search/application
        - job_search/response
        - job_search/interview
        - job_search/offer
        - job_search/rejection
        - job_search/recruiter

        OUTPUT REQUIREMENT #7 - Categorization Plan:
        ```
        === CATEGORIZATION SUMMARY ===

        | Category | Count | % of Total |
        |----------|-------|------------|
        | ...      | ...   | ...        |

        EMAILS BY PRIORITY:
        - High (action required): X
        - Medium (should review): X
        - Low (informational): X
        - Archive (no action): X

        RECOMMENDED LABEL STRUCTURE:
        [Show proposed label hierarchy]
        ```

        ================================================================================
        PHASE 8: EXECUTE LABELING (WITH CONFIRMATION)
        ================================================================================

        Using the Python Gmail API:

        ```python
        import sys
        sys.path.insert(0, '\(projectRoot)')
        from gmail_organizer.operations import GmailOperations

        ops = GmailOperations(account_email='\(account.email)')

        # Create labels first
        labels_to_create = [
            'Organized/Work',
            'Organized/Personal',
            'Organized/Finance',
            'Organized/Newsletters',
            'Organized/Notifications',
            # ... etc
        ]

        for label in labels_to_create:
            ops.create_label(label)

        # Apply labels in batches
        # IMPORTANT: Print progress for each batch
        for i, (email_id, labels) in enumerate(categorization.items()):
            print(f"Processing {i+1}/{total}: {email_id[:20]}...")
            for label in labels:
                ops.apply_label_to_email(email_id, label)
            if i % 25 == 0:
                print(f"=== Batch checkpoint: {i}/{total} complete ===")
                time.sleep(2)  # Rate limit pause
        ```

        OUTPUT REQUIREMENT #8 - Execution Log:
        ```
        === LABELING EXECUTION ===
        Labels created: X
        Emails processed: X
        Errors encountered: X

        [Detailed log of what was applied]
        ```

        ================================================================================
        PHASE 9: SAVE COMPREHENSIVE RESULTS (REQUIRED)
        ================================================================================

        Save ALL analysis to JSON file at: \(resultsPath)

        The JSON MUST include:
        ```json
        {
            "accountEmail": "\(account.email)",
            "processedAt": "ISO8601 timestamp",
            "analysisVersion": "2.0",

            "summary": {
                "totalEmails": 0,
                "totalThreads": 0,
                "uniqueSenders": 0,
                "dateRange": {"start": "", "end": ""},
                "processingDuration": "X seconds"
            },

            "threadAnalysis": {
                "totalThreads": 0,
                "activeThreads": 0,
                "awaitingResponse": [],
                "needsResponse": [],
                "longestThreads": []
            },

            "senderAnalysis": {
                "totalSenders": 0,
                "topSenders": [],
                "domainBreakdown": {},
                "newContacts": [],
                "importantUnanswered": []
            },

            "temporalAnalysis": {
                "volumeByDayOfWeek": {},
                "volumeByHour": {},
                "monthlyTrend": [],
                "avgResponseTime": ""
            },

            "contentAnalysis": {
                "detectedTopics": [],
                "urgentEmails": [],
                "actionItems": [],
                "unansweredQuestions": []
            },

            "issuesDetected": {
                "critical": [],
                "warnings": [],
                "anomalies": []
            },

            "categorization": {
                "byCategory": {},
                "byPriority": {},
                "labelStructure": []
            },

            "actionsApplied": {
                "labelsCreated": [],
                "emailsLabeled": 0,
                "errors": []
            },

            "insights": [
                "Key insight 1...",
                "Key insight 2...",
                "Recommendation 1...",
                "Recommendation 2..."
            ]
        }
        ```

        ================================================================================
        PHASE 10: EXECUTIVE SUMMARY (FINAL OUTPUT)
        ================================================================================

        After all analysis, provide a human-readable executive summary:

        ```
        ╔══════════════════════════════════════════════════════════════════════════════╗
        ║                    EMAIL ANALYSIS COMPLETE - EXECUTIVE SUMMARY               ║
        ╠══════════════════════════════════════════════════════════════════════════════╣
        ║ Account: \(account.email)
        ║ Analyzed: [X] emails across [X] threads
        ║ Time Range: [start] to [end]
        ╠══════════════════════════════════════════════════════════════════════════════╣
        ║ KEY FINDINGS:
        ║ • [Most important finding 1]
        ║ • [Most important finding 2]
        ║ • [Most important finding 3]
        ╠══════════════════════════════════════════════════════════════════════════════╣
        ║ IMMEDIATE ATTENTION NEEDED:
        ║ • [X] emails awaiting your response
        ║ • [X] action items detected
        ║ • [X] potential issues flagged
        ╠══════════════════════════════════════════════════════════════════════════════╣
        ║ INBOX HEALTH SCORE: [X]/100
        ║ • Organization: [X]/25
        ║ • Response Rate: [X]/25
        ║ • Action Item Completion: [X]/25
        ║ • Communication Balance: [X]/25
        ╠══════════════════════════════════════════════════════════════════════════════╣
        ║ TOP RECOMMENDATIONS:
        ║ 1. [Actionable recommendation]
        ║ 2. [Actionable recommendation]
        ║ 3. [Actionable recommendation]
        ╚══════════════════════════════════════════════════════════════════════════════╝
        ```

        ================================================================================
        START PROCESSING NOW
        ================================================================================

        Begin with Phase 1. Show your work for each phase. Do not skip any phase.
        For accounts with <100 emails, process all emails.
        For accounts with >100 emails, sample strategically but analyze patterns across all.

        Remember: The goal is INSIGHT, not just labeling. Help the user understand their
        email ecosystem and take control of their inbox.
        """
    }

    // MARK: - Quick Analysis Prompt (Lighter version)

    static func generateQuickAnalysisPrompt(
        account: AccountInfo,
        syncStatePath: String,
        resultsPath: String
    ) -> String {
        return """
        ################################################################################
        #                     GMAIL ORGANIZER - QUICK ANALYSIS                          #
        ################################################################################

        ACCOUNT: \(account.email)
        EMAILS: \(account.emailCount.formatted())
        FILE: \(syncStatePath)

        Perform a quick analysis (5-10 minutes):

        1. Load and validate email data
        2. Identify top 10 senders
        3. Find emails needing response (incoming, unanswered)
        4. Detect any urgent/time-sensitive items
        5. Provide categorization recommendation

        Save results to: \(resultsPath)

        Output format: Concise bullet points with specific email IDs for action items.
        """
    }

    // MARK: - Thread-Focused Analysis

    static func generateThreadAnalysisPrompt(
        account: AccountInfo,
        syncStatePath: String
    ) -> String {
        return """
        ################################################################################
        #                     THREAD ANALYSIS - CONVERSATION MAPPING                    #
        ################################################################################

        ACCOUNT: \(account.email)
        FILE: \(syncStatePath)

        Focus ONLY on thread/conversation analysis:

        1. Group all emails by thread_id
        2. For each thread:
           - Count participants
           - Identify thread initiator
           - Track response chain
           - Determine thread status (active/stale/needs-response)

        3. Find conversation patterns:
           - Who does this account communicate with most?
           - What topics generate longest threads?
           - Average thread length by sender

        4. Critical output - THREADS NEEDING ATTENTION:
           - Last email was TO this account (needs response)
           - Thread has been active but went silent
           - Multiple participants waiting on this account

        Output as structured JSON with thread_id as keys.
        """
    }

    // MARK: - Action Item Extraction

    static func generateActionItemPrompt(
        account: AccountInfo,
        syncStatePath: String
    ) -> String {
        return """
        ################################################################################
        #                     ACTION ITEM EXTRACTION                                    #
        ################################################################################

        ACCOUNT: \(account.email)
        FILE: \(syncStatePath)

        Extract ALL potential action items from emails:

        DETECTION PATTERNS:
        - Direct requests: "Can you...", "Please...", "Could you..."
        - Questions requiring answers: "?" at end of sentences
        - Deadlines: Dates, "by EOD", "by Friday", "ASAP"
        - Commitments made BY this account: "I will...", "I'll send..."
        - Meeting/call requests
        - Document/file requests
        - Approval requests

        For EACH action item found:
        ```json
        {
            "email_id": "...",
            "thread_id": "...",
            "from": "sender@email.com",
            "date": "ISO8601",
            "action_type": "request|question|deadline|commitment|meeting|approval",
            "action_text": "The actual text containing the action",
            "deadline": "extracted deadline or null",
            "priority": "high|medium|low",
            "status": "pending|possibly_completed|unknown",
            "context": "Brief context from email"
        }
        ```

        Sort by priority, then by deadline (earliest first).

        OUTPUT:
        1. Summary count by type
        2. Full list sorted by urgency
        3. Recommended next actions
        """
    }

    // MARK: - Sender Reputation Analysis

    static func generateSenderReputationPrompt(
        account: AccountInfo,
        syncStatePath: String
    ) -> String {
        return """
        ################################################################################
        #                     SENDER REPUTATION & RELATIONSHIP ANALYSIS                 #
        ################################################################################

        ACCOUNT: \(account.email)
        FILE: \(syncStatePath)

        Build a complete sender profile for each unique sender:

        METRICS TO CALCULATE:
        1. Volume metrics:
           - Total emails received
           - Frequency (emails per month)
           - First contact date
           - Most recent contact

        2. Engagement metrics:
           - Does this account reply to them?
           - Do they reply to this account?
           - Average thread length with them
           - Response time (both directions)

        3. Classification:
           - Human vs Automated
           - Category (work, personal, newsletter, transactional)
           - Importance level (VIP, regular, low-priority)

        4. Relationship score (0-100):
           - Based on: frequency, recency, bidirectional communication, thread depth

        OUTPUT FORMAT:
        ```json
        {
            "sender_email": {
                "display_name": "...",
                "domain": "...",
                "total_emails": 0,
                "first_contact": "date",
                "last_contact": "date",
                "emails_per_month": 0.0,
                "classification": "human|automated|newsletter|transactional",
                "category": "work|personal|commercial|unknown",
                "this_account_replies": true/false,
                "they_reply": true/false,
                "avg_thread_length": 0.0,
                "relationship_score": 0,
                "recommended_label": "VIP|Regular|Low Priority|Unsubscribe Candidate",
                "notes": "Any notable patterns"
            }
        }
        ```

        Also identify:
        - Senders who should be VIP (high engagement, important topics)
        - Senders who could be unsubscribed (low engagement, marketing)
        - New relationships (recent first contact)
        - Fading relationships (historically active, now quiet)
        """
    }
}

// MARK: - Prompt Builder

class PromptBuilder {
    private let account: AccountInfo
    private let projectRoot: String
    private let syncStatePath: String
    private let resultsPath: String

    init(account: AccountInfo) {
        self.account = account
        self.projectRoot = Paths.projectRoot

        let safeEmail = account.email
            .replacingOccurrences(of: "@", with: "_at_")
            .replacingOccurrences(of: ".", with: "_")

        self.syncStatePath = "\(Paths.syncStateDir)/sync_state_\(safeEmail).json"
        self.resultsPath = "\(Paths.projectRoot)/.processing-results/\(safeEmail)_latest.json"
    }

    func buildPrompt(type: AnalysisType) -> String {
        switch type {
        case .fullAnalysis:
            return PromptTemplates.generateFullProcessingPrompt(
                account: account,
                syncStatePath: syncStatePath,
                resultsPath: resultsPath,
                projectRoot: projectRoot
            )
        case .threadAnalysis:
            return PromptTemplates.generateThreadAnalysisPrompt(
                account: account,
                syncStatePath: syncStatePath
            )
        case .actionItems:
            return PromptTemplates.generateActionItemPrompt(
                account: account,
                syncStatePath: syncStatePath
            )
        case .senderReputation:
            return PromptTemplates.generateSenderReputationPrompt(
                account: account,
                syncStatePath: syncStatePath
            )
        default:
            // For other types, use quick analysis for now
            return PromptTemplates.generateQuickAnalysisPrompt(
                account: account,
                syncStatePath: syncStatePath,
                resultsPath: resultsPath
            )
        }
    }

    func getResultsPath() -> String {
        return resultsPath
    }

    func getSyncStatePath() -> String {
        return syncStatePath
    }
}
