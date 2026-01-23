"""Smart filter generator - creates Gmail filters from classification patterns"""

import re
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Optional
from googleapiclient.errors import HttpError


class FilterRule:
    """Represents a single Gmail filter rule"""

    def __init__(self, criteria: Dict, action_label: str, label_id: str = None,
                 description: str = "", match_count: int = 0):
        self.criteria = criteria  # {from, to, subject, hasTheWord, ...}
        self.action_label = action_label  # Label name to apply
        self.label_id = label_id
        self.description = description
        self.match_count = match_count

    def to_gmail_filter(self) -> Dict:
        """Convert to Gmail API filter format"""
        filter_body = {
            'criteria': self.criteria,
            'action': {}
        }
        if self.label_id:
            filter_body['action']['addLabelIds'] = [self.label_id]
        return filter_body

    def to_dict(self) -> Dict:
        """Serialize for display"""
        return {
            'criteria': self.criteria,
            'action_label': self.action_label,
            'description': self.description,
            'match_count': self.match_count
        }


class SmartFilterGenerator:
    """Generate Gmail filter rules from classified email patterns"""

    def __init__(self, service=None):
        self.service = service

    def _extract_email(self, sender: str) -> str:
        """Extract email address from sender string"""
        match = re.search(r'<(.+?)>', sender)
        if match:
            return match.group(1).lower()
        if '@' in sender:
            return sender.strip().lower()
        return sender.lower()

    def _extract_domain(self, sender: str) -> str:
        """Extract domain from sender"""
        email = self._extract_email(sender)
        if '@' in email:
            parts = email.split('@')
            if len(parts) >= 2 and parts[1]:
                return parts[1]
        return ""

    def analyze_patterns(self, classified_emails: List[Dict],
                         min_frequency: int = 3) -> List[FilterRule]:
        """
        Analyze classified emails to discover filter-worthy patterns.

        Args:
            classified_emails: List of emails with 'category' field
            min_frequency: Minimum occurrences to suggest a filter

        Returns:
            List of FilterRule objects sorted by match count
        """
        # Group emails by category
        category_emails = defaultdict(list)
        for email in classified_emails:
            category = email.get('category', '')
            if category:
                category_emails[category].append(email)

        rules = []

        for category, emails in category_emails.items():
            # Find sender patterns
            sender_rules = self._find_sender_patterns(emails, category, min_frequency)
            rules.extend(sender_rules)

            # Find domain patterns
            domain_rules = self._find_domain_patterns(emails, category, min_frequency)
            rules.extend(domain_rules)

            # Find subject keyword patterns
            keyword_rules = self._find_subject_patterns(emails, category, min_frequency)
            rules.extend(keyword_rules)

        # Deduplicate and sort by match count
        rules = self._deduplicate_rules(rules)
        rules.sort(key=lambda r: r.match_count, reverse=True)

        return rules

    def _find_sender_patterns(self, emails: List[Dict], category: str,
                               min_frequency: int) -> List[FilterRule]:
        """Find senders that consistently map to a category"""
        sender_counts = Counter()
        for email in emails:
            sender = email.get('sender', '')
            if sender:
                sender_counts[self._extract_email(sender)] += 1

        rules = []
        for sender, count in sender_counts.items():
            if count >= min_frequency and '@' in sender:
                rules.append(FilterRule(
                    criteria={'from': sender},
                    action_label=category,
                    description=f"Emails from {sender} → {category}",
                    match_count=count
                ))

        return rules

    def _find_domain_patterns(self, emails: List[Dict], category: str,
                               min_frequency: int) -> List[FilterRule]:
        """Find domains that consistently map to a category"""
        domain_counts = Counter()
        domain_senders = defaultdict(set)

        for email in emails:
            sender = email.get('sender', '')
            if sender:
                domain = self._extract_domain(sender)
                if domain:
                    domain_counts[domain] += 1
                    domain_senders[domain].add(self._extract_email(sender))

        rules = []
        for domain, count in domain_counts.items():
            # Only suggest domain filter if multiple senders from same domain
            if count >= min_frequency and len(domain_senders[domain]) >= 2:
                rules.append(FilterRule(
                    criteria={'from': f'@{domain}'},
                    action_label=category,
                    description=f"All emails from *@{domain} → {category} ({len(domain_senders[domain])} senders)",
                    match_count=count
                ))

        return rules

    def _find_subject_patterns(self, emails: List[Dict], category: str,
                                min_frequency: int) -> List[FilterRule]:
        """Find subject line keywords that indicate a category"""
        # Common keywords per category type
        keyword_counts = Counter()

        for email in emails:
            subject = email.get('subject', '').lower()
            # Extract significant words (3+ chars, not common words)
            words = re.findall(r'\b[a-z]{3,}\b', subject)
            stop_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all',
                         'can', 'has', 'her', 'was', 'one', 'our', 'out', 'his',
                         'had', 'new', 'now', 'way', 'may', 'day', 'too', 'use',
                         'how', 'its', 'let', 'get', 'got', 'did', 'she', 'him',
                         'have', 'this', 'that', 'with', 'they', 'been', 'from',
                         'your', 'will', 'more', 'when', 'what', 'some', 'than',
                         'them', 'into', 'just', 'only', 'also', 'very', 'here',
                         'were', 'said', 'each', 'which', 'their', 'about', 'would',
                         'there', 'could', 'other', 'after', 'these', 'email', 'mail'}
            significant = [w for w in words if w not in stop_words]
            for word in significant:
                keyword_counts[word] += 1

        rules = []
        for keyword, count in keyword_counts.most_common(5):
            if count >= min_frequency * 2:  # Higher threshold for keywords
                rules.append(FilterRule(
                    criteria={'subject': keyword},
                    action_label=category,
                    description=f'Subject contains "{keyword}" → {category}',
                    match_count=count
                ))

        return rules

    def _deduplicate_rules(self, rules: List[FilterRule]) -> List[FilterRule]:
        """Remove duplicate rules, keeping the one with highest match count"""
        seen = {}
        for rule in rules:
            key = (str(rule.criteria), rule.action_label)
            if key not in seen or rule.match_count > seen[key].match_count:
                seen[key] = rule
        return list(seen.values())

    def preview_filter(self, rule: FilterRule, emails: List[Dict]) -> List[Dict]:
        """Preview which emails a filter would match"""
        matches = []
        for email in emails:
            if self._matches_criteria(email, rule.criteria):
                matches.append(email)
        return matches

    def _matches_criteria(self, email: Dict, criteria: Dict) -> bool:
        """Check if an email matches filter criteria"""
        sender = email.get('sender', '').lower()
        subject = email.get('subject', '').lower()

        if 'from' in criteria:
            from_val = criteria['from'].lower()
            if from_val.startswith('@'):
                # Domain match
                if from_val[1:] != self._extract_domain(sender):
                    return False
            else:
                if from_val != self._extract_email(sender):
                    return False

        if 'subject' in criteria:
            if criteria['subject'].lower() not in subject:
                return False

        if 'hasTheWord' in criteria:
            body = email.get('body_preview', '').lower()
            full_text = f"{subject} {body}"
            if criteria['hasTheWord'].lower() not in full_text:
                return False

        return True

    def create_filter(self, rule: FilterRule) -> Optional[Dict]:
        """Create a Gmail filter via the API"""
        if not self.service:
            return None

        try:
            filter_body = rule.to_gmail_filter()
            result = self.service.users().settings().filters().create(
                userId='me',
                body=filter_body
            ).execute()
            return result
        except HttpError as e:
            print(f"Error creating filter: {e}")
            return None

    def list_existing_filters(self) -> List[Dict]:
        """List all existing Gmail filters"""
        if not self.service:
            return []

        try:
            results = self.service.users().settings().filters().list(
                userId='me'
            ).execute()
            return results.get('filter', [])
        except HttpError as e:
            print(f"Error listing filters: {e}")
            return []

    def delete_filter(self, filter_id: str) -> bool:
        """Delete a Gmail filter"""
        if not self.service:
            return False

        try:
            self.service.users().settings().filters().delete(
                userId='me',
                id=filter_id
            ).execute()
            return True
        except HttpError as e:
            print(f"Error deleting filter: {e}")
            return False
