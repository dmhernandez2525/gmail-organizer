"""Multi-label email classification using rule-based pattern matching."""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class ClassificationRule:
    """A rule for classifying emails into a category."""

    label: str
    sender_patterns: List[str] = field(default_factory=list)
    subject_patterns: List[str] = field(default_factory=list)
    body_patterns: List[str] = field(default_factory=list)
    domain_patterns: List[str] = field(default_factory=list)
    weight: float = 1.0
    description: str = ""

    def __post_init__(self):
        self._compiled_sender = [re.compile(p, re.IGNORECASE) for p in self.sender_patterns]
        self._compiled_subject = [re.compile(p, re.IGNORECASE) for p in self.subject_patterns]
        self._compiled_body = [re.compile(p, re.IGNORECASE) for p in self.body_patterns]
        self._compiled_domain = [re.compile(p, re.IGNORECASE) for p in self.domain_patterns]


@dataclass
class LabelAssignment:
    """A label assignment with confidence score."""

    label: str
    confidence: float  # 0.0 to 1.0
    matched_rules: List[str] = field(default_factory=list)


@dataclass
class ClassificationResult:
    """Result of classifying a single email."""

    email_id: str
    primary_label: str = ""
    labels: List[LabelAssignment] = field(default_factory=list)
    all_labels: List[str] = field(default_factory=list)


# Default classification rules covering common email categories
DEFAULT_RULES: List[ClassificationRule] = [
    ClassificationRule(
        label="work",
        sender_patterns=[r"@(company|corp|enterprise|business)\.", r"jira", r"confluence", r"slack"],
        subject_patterns=[r"\b(meeting|standup|sprint|review|deploy|release|ticket)\b",
                          r"\b(project|milestone|deadline|deliverable)\b"],
        domain_patterns=[r"(atlassian|asana|monday|notion|linear)\.(com|io)"],
        weight=1.2,
        description="Work-related emails",
    ),
    ClassificationRule(
        label="finance",
        sender_patterns=[r"@(bank|paypal|venmo|chase|wellsfargo|capitalone|amex)",
                         r"(invoice|billing|payment|receipt)"],
        subject_patterns=[r"\b(payment|invoice|receipt|statement|transaction|balance)\b",
                          r"\b(tax|refund|charge|credit|debit)\b",
                          r"\$\d+"],
        weight=1.3,
        description="Financial transactions and statements",
    ),
    ClassificationRule(
        label="shopping",
        sender_patterns=[r"@(amazon|ebay|walmart|target|bestbuy|etsy|shopify)",
                         r"(order|shipping|delivery|tracking)"],
        subject_patterns=[r"\b(order|shipped|delivered|tracking|package|return)\b",
                          r"\b(cart|checkout|purchase|buy)\b"],
        weight=1.1,
        description="Shopping and e-commerce",
    ),
    ClassificationRule(
        label="social",
        sender_patterns=[r"@(facebook|twitter|linkedin|instagram|tiktok|reddit)",
                         r"(notification|friend|follow|like|comment|mention)"],
        subject_patterns=[r"\b(friend|follow|like|comment|share|mention|tag)\b",
                          r"\b(connection|endorse|network)\b"],
        domain_patterns=[r"(facebook|twitter|x|linkedin|instagram)\.(com|net)"],
        weight=1.0,
        description="Social media notifications",
    ),
    ClassificationRule(
        label="newsletter",
        sender_patterns=[r"(newsletter|digest|weekly|daily|update|news)",
                         r"(substack|mailchimp|sendgrid|constantcontact)"],
        subject_patterns=[r"\b(newsletter|digest|weekly|roundup|edition|issue)\b",
                          r"#\d+",
                          r"\b(this week|today's|daily)\b"],
        body_patterns=[r"\bunsubscribe\b", r"\bopt.out\b", r"\bpreferences\b"],
        weight=0.9,
        description="Newsletters and mailing lists",
    ),
    ClassificationRule(
        label="travel",
        sender_patterns=[r"@(airline|hotel|airbnb|booking|expedia|uber|lyft)",
                         r"(flight|reservation|booking|itinerary)"],
        subject_patterns=[r"\b(flight|hotel|reservation|booking|itinerary|trip)\b",
                          r"\b(boarding|check.in|confirmation|travel)\b"],
        weight=1.1,
        description="Travel bookings and notifications",
    ),
    ClassificationRule(
        label="education",
        sender_patterns=[r"@(university|edu|school|academy|coursera|udemy)",
                         r"(professor|instructor|tutor|student)"],
        subject_patterns=[r"\b(course|class|assignment|lecture|exam|grade|homework)\b",
                          r"\b(enrollment|semester|syllabus|study)\b"],
        domain_patterns=[r"\.edu$"],
        weight=1.1,
        description="Education and learning",
    ),
    ClassificationRule(
        label="health",
        sender_patterns=[r"@(hospital|clinic|doctor|pharmacy|health|medical)",
                         r"(appointment|prescription|lab|patient)"],
        subject_patterns=[r"\b(appointment|prescription|result|test|health|medical)\b",
                          r"\b(doctor|pharmacy|insurance|claim)\b"],
        weight=1.2,
        description="Health and medical",
    ),
    ClassificationRule(
        label="promotions",
        sender_patterns=[r"(deals|offers|promo|sale|discount|coupon)",
                         r"(marketing|campaign|special)"],
        subject_patterns=[r"\b(sale|discount|offer|deal|save|off|free|exclusive)\b",
                          r"\b(\d+%\s*off|limited.time|flash.sale|clearance)\b"],
        body_patterns=[r"\b(unsubscribe|opt.out)\b", r"\b(promo.code|coupon)\b"],
        weight=0.8,
        description="Promotional offers",
    ),
    ClassificationRule(
        label="security",
        sender_patterns=[r"(security|noreply|alert|verify)",
                         r"@(google|apple|microsoft|github|aws)"],
        subject_patterns=[r"\b(security|alert|verify|password|login|sign.in)\b",
                          r"\b(suspicious|unauthorized|two.factor|2fa|otp)\b"],
        weight=1.3,
        description="Security alerts and verifications",
    ),
]


class MultiLabelClassifier:
    """Classify emails with multiple labels using rule-based pattern matching.

    Each email can receive multiple labels with confidence scores.
    Labels are assigned based on pattern matching against sender, subject,
    body, and domain fields.
    """

    def __init__(self, rules: Optional[List[ClassificationRule]] = None,
                 confidence_threshold: float = 0.3):
        """Initialize the classifier.

        Args:
            rules: List of ClassificationRule instances. Uses DEFAULT_RULES if None.
            confidence_threshold: Minimum confidence to assign a label (0.0-1.0).
        """
        self.rules = rules or list(DEFAULT_RULES)
        self.confidence_threshold = confidence_threshold

    def classify_email(self, email: Dict) -> ClassificationResult:
        """Classify a single email with multiple labels.

        Args:
            email: Email dict with 'sender'/'from', 'subject', 'body'/'snippet',
                   and optionally 'id' fields.

        Returns:
            ClassificationResult with all matching labels and confidence scores.
        """
        email_id = email.get("id", "")
        sender = email.get("sender", email.get("from", "")).lower()
        subject = email.get("subject", "").lower()
        body = email.get("body", email.get("snippet", "")).lower()

        # Extract domain from sender
        domain = ""
        match = re.search(r"@([\w.-]+)", sender)
        if match:
            domain = match.group(1).lower()

        label_scores: Dict[str, Tuple[float, List[str]]] = defaultdict(lambda: (0.0, []))

        for rule in self.rules:
            score, reasons = self._evaluate_rule(rule, sender, subject, body, domain)
            if score > 0:
                current_score, current_reasons = label_scores[rule.label]
                new_score = current_score + score * rule.weight
                label_scores[rule.label] = (new_score, current_reasons + reasons)

        # Normalize scores to 0-1 confidence
        max_score = max((s for s, _ in label_scores.values()), default=1.0)
        if max_score == 0:
            max_score = 1.0

        assignments = []
        for label, (score, reasons) in label_scores.items():
            confidence = min(1.0, score / max(max_score, 3.0))
            if confidence >= self.confidence_threshold:
                assignments.append(LabelAssignment(
                    label=label,
                    confidence=round(confidence, 3),
                    matched_rules=reasons[:5],
                ))

        # Sort by confidence descending
        assignments.sort(key=lambda a: a.confidence, reverse=True)

        primary = assignments[0].label if assignments else "uncategorized"
        all_labels = [a.label for a in assignments]

        return ClassificationResult(
            email_id=email_id,
            primary_label=primary,
            labels=assignments,
            all_labels=all_labels,
        )

    def classify_batch(self, emails: List[Dict]) -> List[ClassificationResult]:
        """Classify a batch of emails.

        Args:
            emails: List of email dicts.

        Returns:
            List of ClassificationResult instances.
        """
        return [self.classify_email(email) for email in emails]

    def get_label_stats(self, results: List[ClassificationResult]) -> Dict:
        """Get classification statistics.

        Args:
            results: List of ClassificationResult instances.

        Returns:
            Dict with label counts, multi-label count, and avg labels per email.
        """
        label_counts: Dict[str, int] = defaultdict(int)
        multi_label_count = 0
        total_labels = 0

        for result in results:
            for label in result.all_labels:
                label_counts[label] += 1
            total_labels += len(result.all_labels)
            if len(result.all_labels) > 1:
                multi_label_count += 1

        return {
            "total_emails": len(results),
            "label_counts": dict(sorted(label_counts.items(), key=lambda x: x[1], reverse=True)),
            "multi_label_count": multi_label_count,
            "multi_label_pct": round(multi_label_count / max(len(results), 1) * 100, 1),
            "avg_labels_per_email": round(total_labels / max(len(results), 1), 2),
            "unique_labels": len(label_counts),
        }

    def add_rule(self, rule: ClassificationRule):
        """Add a new classification rule.

        Args:
            rule: The ClassificationRule to add.
        """
        self.rules.append(rule)

    def remove_rule(self, label: str) -> int:
        """Remove all rules for a given label.

        Args:
            label: Label name to remove rules for.

        Returns:
            Number of rules removed.
        """
        before = len(self.rules)
        self.rules = [r for r in self.rules if r.label != label]
        return before - len(self.rules)

    def get_available_labels(self) -> List[str]:
        """Get all available label names from configured rules."""
        return list(set(r.label for r in self.rules))

    def _evaluate_rule(
        self, rule: ClassificationRule,
        sender: str, subject: str, body: str, domain: str
    ) -> Tuple[float, List[str]]:
        """Evaluate a single rule against email fields.

        Returns:
            Tuple of (score, list of matched reason strings).
        """
        score = 0.0
        reasons = []

        # Check sender patterns
        for pattern in rule._compiled_sender:
            if pattern.search(sender):
                score += 1.0
                reasons.append(f"sender matches: {pattern.pattern}")

        # Check subject patterns (weighted higher)
        for pattern in rule._compiled_subject:
            if pattern.search(subject):
                score += 1.5
                reasons.append(f"subject matches: {pattern.pattern}")

        # Check body patterns
        for pattern in rule._compiled_body:
            if pattern.search(body):
                score += 0.5
                reasons.append(f"body matches: {pattern.pattern}")

        # Check domain patterns
        if domain:
            for pattern in rule._compiled_domain:
                if pattern.search(domain):
                    score += 1.0
                    reasons.append(f"domain matches: {pattern.pattern}")

        return score, reasons
