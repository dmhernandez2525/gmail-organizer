"""
Gmail Organizer - AI-powered email management system.

This package provides tools for automatically categorizing and organizing
emails across multiple Gmail accounts using Claude AI.
"""

__version__ = "1.0.0"

from gmail_organizer.auth import GmailAuthManager
from gmail_organizer.operations import GmailOperations
from gmail_organizer.classifier import EmailClassifier
from gmail_organizer.analyzer import EmailAnalyzer
from gmail_organizer.config import CATEGORIES

__all__ = [
    "GmailAuthManager",
    "GmailOperations",
    "EmailClassifier",
    "EmailAnalyzer",
    "CATEGORIES",
]
