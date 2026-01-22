"""Email pattern analysis to suggest categories"""

import anthropic
from typing import List, Dict
from collections import Counter
from .config import ANTHROPIC_API_KEY


class EmailAnalyzer:
    """Analyzes email patterns to suggest categories"""

    def __init__(self, api_key=None):
        self.api_key = api_key or ANTHROPIC_API_KEY
        if not self.api_key:
            raise ValueError("Anthropic API key not found")

        self.client = anthropic.Anthropic(api_key=self.api_key)

    def analyze_emails(self, emails: List[Dict]) -> Dict:
        """
        Analyze a sample of emails to discover patterns

        Args:
            emails: List of email dicts with subject, sender, body_preview

        Returns:
            Analysis results with suggested categories
        """
        print(f"Analyzing {len(emails)} emails to discover patterns...")

        # Extract patterns
        senders = Counter()
        domains = Counter()
        subjects_preview = []

        for email in emails[:1000]:  # Analyze up to 1000 emails
            sender = email.get('sender', '')
            subject = email.get('subject', '')

            senders[sender] += 1

            # Extract domain
            if '@' in sender:
                domain = sender.split('@')[-1].strip('>')
                domains[domain] += 1

            # Collect subject samples
            if subject and len(subjects_preview) < 100:
                subjects_preview.append(subject)

        # Prepare data for AI analysis
        top_senders = senders.most_common(20)
        top_domains = domains.most_common(20)

        analysis = {
            'total_emails': len(emails),
            'unique_senders': len(senders),
            'top_senders': top_senders,
            'top_domains': top_domains,
            'subject_samples': subjects_preview[:50]
        }

        return analysis

    def suggest_categories(self, analysis: Dict, job_search_focused: bool = True) -> List[Dict]:
        """
        Use Claude to suggest categories based on email analysis

        Args:
            analysis: Email analysis results
            job_search_focused: Whether to focus on job search categories

        Returns:
            List of suggested categories with reasoning
        """
        print("Using AI to suggest categories based on your emails...")

        # Build prompt with actual data
        prompt = f"""Analyze this email data and suggest 8-12 email categories that would be most useful for organizing this inbox.

EMAIL ANALYSIS:
- Total emails: {analysis['total_emails']}
- Unique senders: {analysis['unique_senders']}

TOP SENDERS:
{self._format_list(analysis['top_senders'][:10])}

TOP DOMAINS:
{self._format_list(analysis['top_domains'][:10])}

SAMPLE SUBJECTS:
{chr(10).join(f"- {s}" for s in analysis['subject_samples'][:20])}

USER CONTEXT:
{'- User is actively job searching and wants job-related email categories prioritized' if job_search_focused else '- User wants general inbox organization'}

REQUIREMENTS:
1. Suggest 8-12 categories based on ACTUAL patterns in the data above
2. Focus on categories that will have the most emails
3. Include job-related categories if you see recruiting/application patterns
4. Each category should have a clear purpose
5. Avoid overly generic categories

OUTPUT FORMAT (JSON):
{{
  "categories": [
    {{
      "name": "Category Name",
      "description": "What goes in this category",
      "reasoning": "Why this category based on the data",
      "estimated_volume": "high/medium/low"
    }}
  ],
  "summary": "Overall inbox analysis summary"
}}

Respond ONLY with valid JSON.
"""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",  # Use Sonnet for better analysis
                max_tokens=2000,
                temperature=0.5,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            result_text = response.content[0].text

            # Parse JSON response
            import json
            result = json.loads(result_text)

            return result

        except Exception as e:
            print(f"Error getting category suggestions: {e}")
            # Return default categories as fallback
            return {
                "categories": [
                    {
                        "name": "Job Search",
                        "description": "Applications, interviews, offers, recruiters",
                        "reasoning": "Common for job seekers",
                        "estimated_volume": "medium"
                    },
                    {
                        "name": "Subscriptions",
                        "description": "Newsletters and marketing emails",
                        "reasoning": "Usually high volume",
                        "estimated_volume": "high"
                    },
                    {
                        "name": "Finance",
                        "description": "Bills, receipts, banking",
                        "reasoning": "Important to separate",
                        "estimated_volume": "medium"
                    }
                ],
                "summary": "Default categories (AI analysis failed)"
            }

    def _format_list(self, items: List[tuple]) -> str:
        """Format a list of (item, count) tuples"""
        return '\n'.join(f"- {item[0]}: {item[1]} emails" for item in items)


def test_analyzer():
    """Test the analyzer with sample data"""
    analyzer = EmailAnalyzer()

    # Sample emails
    sample_emails = [
        {"sender": "noreply@linkedin.com", "subject": "New job matches for you", "body_preview": "..."},
        {"sender": "jobs@indeed.com", "subject": "5 jobs that match your profile", "body_preview": "..."},
        {"sender": "recruiter@company.com", "subject": "Exciting opportunity at TechCorp", "body_preview": "..."},
        {"sender": "newsletter@techcrunch.com", "subject": "Today's top tech news", "body_preview": "..."},
        {"sender": "no-reply@amazon.com", "subject": "Your order has shipped", "body_preview": "..."},
    ] * 20  # Repeat for sample size

    # Analyze
    analysis = analyzer.analyze_emails(sample_emails)
    print("\nEmail Analysis:")
    print(f"  Total: {analysis['total_emails']}")
    print(f"  Unique senders: {analysis['unique_senders']}")

    # Get suggestions
    suggestions = analyzer.suggest_categories(analysis, job_search_focused=True)
    print(f"\nSuggested Categories:")
    print(suggestions.get('summary', ''))
    for cat in suggestions.get('categories', [])[:5]:
        print(f"\n  {cat['name']}")
        print(f"    {cat['description']}")
        print(f"    Volume: {cat['estimated_volume']}")


if __name__ == "__main__":
    test_analyzer()
