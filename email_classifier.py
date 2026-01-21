"""AI-powered email classification using Anthropic Claude"""

import anthropic
from typing import Dict, List, Tuple
from config import ANTHROPIC_API_KEY, CLASSIFICATION_PROMPT, CATEGORIES


class EmailClassifier:
    """Classifies emails using Anthropic Claude"""

    def __init__(self, api_key=None):
        self.api_key = api_key or ANTHROPIC_API_KEY
        if not self.api_key:
            raise ValueError("Anthropic API key not found. Set ANTHROPIC_API_KEY in .env")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.all_categories = self._get_all_categories()

    def _get_all_categories(self):
        """Get flat list of all category keys"""
        categories = []
        for group in CATEGORIES.values():
            categories.extend(group.keys())
        return categories

    def classify_email(self, subject: str, sender: str, body_preview: str = "") -> Tuple[str, float]:
        """
        Classify a single email using Anthropic Claude

        NOTE: body_preview is optional and excluded by default to save tokens.
        Sender + Subject is usually enough for accurate classification.

        Args:
            subject: Email subject line
            sender: Email sender
            body_preview: First ~500 chars of email body (OPTIONAL, saves tokens if omitted)

        Returns:
            tuple: (category, confidence_score)
        """
        # Prepare prompt - only use sender and subject to save tokens
        # Body preview adds ~100-200 tokens per email but rarely improves accuracy
        if body_preview and len(body_preview.strip()) > 0:
            prompt = CLASSIFICATION_PROMPT.format(
                subject=subject,
                sender=sender,
                body_preview=body_preview[:500]
            )
        else:
            # Optimized prompt without body - saves ~70% tokens
            prompt = f"""Classify this email:
From: {sender}
Subject: {subject}

Category (respond with one word only):"""

        try:
            response = self.client.messages.create(
                model="claude-3-5-haiku-20241022",  # Fast and cost-effective
                max_tokens=50,
                temperature=0.3,
                system="You are an email classification expert. Respond only with the category name, nothing else.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            category = response.content[0].text.strip().lower()

            # Validate category
            if category not in self.all_categories:
                # Try to find closest match
                category = self._fuzzy_match_category(category)

            # Confidence is based on stop_reason
            confidence = 0.9 if response.stop_reason == "end_turn" else 0.7

            return category, confidence

        except Exception as e:
            print(f"Classification error: {e}")
            return "saved", 0.5  # Default to saved with low confidence

    def _fuzzy_match_category(self, category_text: str) -> str:
        """Try to match invalid category to valid one"""
        category_text = category_text.lower()

        # Check if any valid category is mentioned
        for valid_cat in self.all_categories:
            if valid_cat in category_text or category_text in valid_cat:
                return valid_cat

        # Default fallback
        return "saved"

    def classify_batch(self, emails: List[Dict]) -> List[Dict]:
        """
        Classify multiple emails in batch

        Args:
            emails: List of dicts with keys: subject, sender, body_preview, email_id

        Returns:
            List of dicts with added keys: category, confidence
        """
        results = []

        for i, email in enumerate(emails):
            if (i + 1) % 10 == 0:
                print(f"  Classified {i + 1}/{len(emails)} emails...")

            # Token optimization: Don't send body_preview (saves ~70% tokens)
            category, confidence = self.classify_email(
                email.get('subject', ''),
                email.get('sender', ''),
                body_preview=""  # Omit to save tokens
            )

            email['category'] = category
            email['confidence'] = confidence
            results.append(email)

        return results

    def get_category_info(self, category_key: str) -> Dict:
        """Get full category information"""
        for group in CATEGORIES.values():
            if category_key in group:
                return group[category_key]
        return {"name": "Unknown", "description": "", "color": "#cccccc"}


def test_classifier():
    """Test the classifier with sample emails"""
    classifier = EmailClassifier()

    test_emails = [
        {
            "subject": "Application Status Update",
            "sender": "careers@company.com",
            "body_preview": "Thank you for applying to the Software Engineer position..."
        },
        {
            "subject": "Interview Invitation - Senior Developer Role",
            "sender": "hr@techcorp.com",
            "body_preview": "We'd like to invite you for an interview next Tuesday..."
        },
        {
            "subject": "Your Amazon Order Confirmation",
            "sender": "auto-confirm@amazon.com",
            "body_preview": "Your order #123-456 has been confirmed. Total: $59.99..."
        },
        {
            "subject": "Weekly Newsletter - Tech Trends",
            "sender": "newsletter@techcrunch.com",
            "body_preview": "Here are this week's top stories in technology..."
        }
    ]

    print("Testing Email Classifier with Anthropic Claude:\n")
    for email in test_emails:
        category, confidence = classifier.classify_email(
            email['subject'],
            email['sender'],
            email['body_preview']
        )

        cat_info = classifier.get_category_info(category)
        print(f"Subject: {email['subject']}")
        print(f"Category: {cat_info['name']} ({confidence:.0%} confidence)")
        print(f"Description: {cat_info['description']}\n")


if __name__ == "__main__":
    test_classifier()
