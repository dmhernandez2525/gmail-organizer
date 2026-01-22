"""Configuration for Gmail Organizer"""

import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Gmail API Scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.settings.basic'
]

# Email Categories
CATEGORIES = {
    "job_search": {
        "applications": {
            "name": "Job/Applications",
            "description": "Job applications you've submitted",
            "color": "#fb4c2f"  # Red
        },
        "responses": {
            "name": "Job/Responses",
            "description": "Responses from companies about applications",
            "color": "#fad165"  # Yellow
        },
        "interviews": {
            "name": "Job/Interviews",
            "description": "Interview scheduling and coordination",
            "color": "#16a766"  # Green
        },
        "offers": {
            "name": "Job/Offers",
            "description": "Job offers received",
            "color": "#7bd148"  # Bright green
        },
        "rejections": {
            "name": "Job/Rejections",
            "description": "Application rejections",
            "color": "#b99aff"  # Purple
        },
        "recruiters": {
            "name": "Job/Recruiters",
            "description": "Recruiter outreach and InMail",
            "color": "#ff7537"  # Orange
        }
    },
    "general": {
        "subscriptions": {
            "name": "Subscriptions",
            "description": "Newsletters and marketing emails",
            "color": "#cca6ac"  # Light gray
        },
        "finance": {
            "name": "Finance",
            "description": "Bills, receipts, banking notifications",
            "color": "#42d692"  # Mint green
        },
        "social": {
            "name": "Social",
            "description": "Social media notifications",
            "color": "#41236d"  # Dark purple
        },
        "updates": {
            "name": "Updates",
            "description": "Service notifications and updates",
            "color": "#95b9e0"  # Light blue
        },
        "todo": {
            "name": "To-Do",
            "description": "Emails requiring action or response",
            "color": "#e07798"  # Pink
        },
        "saved": {
            "name": "Saved",
            "description": "Important emails to keep",
            "color": "#89d3b2"  # Teal
        }
    }
}

# AI Classification Prompt
CLASSIFICATION_PROMPT = """You are an email classification assistant. Analyze the email and classify it into ONE of the following categories.

JOB SEARCH CATEGORIES:
- applications: Job applications the user submitted
- responses: Responses from companies (not rejections or offers)
- interviews: Interview scheduling, coordination, or invitations
- offers: Job offers or offer letters
- rejections: Application rejections
- recruiters: Messages from recruiters, InMail, cold outreach

GENERAL CATEGORIES:
- subscriptions: Newsletters, marketing emails, promotional content
- finance: Bills, receipts, invoices, banking notifications
- social: Social media notifications (LinkedIn, Twitter, Facebook, etc.)
- updates: Service notifications, account updates, password resets
- todo: Emails requiring action or response (not job-related)
- saved: Important personal emails to keep

Email Subject: {subject}
Email From: {sender}
Email Body Preview: {body_preview}

Respond with ONLY the category name (e.g., "applications", "subscriptions", "finance").
If uncertain, respond with your best guess based on the context.
"""

# Batch processing settings
BATCH_SIZE = 100  # Process emails in batches
MAX_EMAILS = None  # None = process all, or set a number for testing

# Credentials storage
CREDENTIALS_DIR = "credentials"
TOKEN_PREFIX = "token_"
