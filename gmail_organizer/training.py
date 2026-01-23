"""Custom category training module for user-defined email classification."""

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class TrainingExample:
    """A single training example - an email labeled with a category."""

    email_id: str
    category: str
    sender: str = ""
    subject: str = ""
    domain: str = ""
    keywords: List[str] = field(default_factory=list)


@dataclass
class CategoryModel:
    """Learned model for a single category."""

    name: str
    description: str = ""
    example_count: int = 0
    sender_patterns: Dict[str, int] = field(default_factory=dict)
    domain_patterns: Dict[str, int] = field(default_factory=dict)
    keyword_weights: Dict[str, float] = field(default_factory=dict)
    subject_patterns: Dict[str, int] = field(default_factory=dict)


@dataclass
class PredictionResult:
    """Result of predicting a category for an email."""

    email_id: str
    predicted_category: str
    confidence: float
    scores: Dict[str, float] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)


class CategoryTrainer:
    """Train custom email categories from user-provided examples.

    Uses a lightweight pattern-based learning approach:
    - Extracts sender, domain, and keyword features from training examples
    - Builds per-category frequency models
    - Predicts categories for new emails using TF-IDF-like scoring
    """

    TRAINING_FILE = "custom_categories.json"
    STOP_WORDS = {
        'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'has',
        'was', 'one', 'our', 'out', 'had', 'new', 'now', 'may', 'too', 'use',
        'how', 'its', 'let', 'get', 'got', 'did', 'have', 'this', 'that',
        'with', 'they', 'been', 'from', 'your', 'will', 'more', 'when', 'what',
        'some', 'them', 'into', 'just', 'only', 'also', 'very', 'here', 'were',
        'each', 'which', 'their', 'about', 'would', 'there', 'could', 'other',
        'these', 'email', 'mail', 'sent', 'message', 'please', 'thanks',
        'thank', 'regards', 'hello', 'dear', 'best', 'kind',
    }

    def __init__(self, config_dir: Optional[str] = None):
        """Initialize the trainer.

        Args:
            config_dir: Directory for storing training data.
                       Defaults to .sync-state/ in project root.
        """
        if config_dir:
            self._config_dir = Path(config_dir)
        else:
            self._config_dir = Path(__file__).parent.parent / ".sync-state"
        self._config_dir.mkdir(exist_ok=True)

        self._examples: List[TrainingExample] = []
        self._models: Dict[str, CategoryModel] = {}
        self._is_trained = False

        self._load_training_data()

    def add_example(self, email: Dict, category: str):
        """Add a training example.

        Args:
            email: Email dict with 'id', 'sender'/'from', 'subject' fields.
            category: The category label for this email.
        """
        sender = email.get("sender", email.get("from", "")).lower()
        subject = email.get("subject", "").lower()
        email_id = email.get("id", "")

        domain = ""
        match = re.search(r"@([\w.-]+)", sender)
        if match:
            domain = match.group(1)

        keywords = self._extract_keywords(subject)

        example = TrainingExample(
            email_id=email_id,
            category=category,
            sender=sender,
            subject=subject,
            domain=domain,
            keywords=keywords,
        )

        self._examples.append(example)
        self._is_trained = False
        self._save_training_data()

    def add_examples_batch(self, emails: List[Dict], category: str):
        """Add multiple training examples for a category.

        Args:
            emails: List of email dicts.
            category: The category label for all emails.
        """
        for email in emails:
            sender = email.get("sender", email.get("from", "")).lower()
            subject = email.get("subject", "").lower()
            email_id = email.get("id", "")

            domain = ""
            match = re.search(r"@([\w.-]+)", sender)
            if match:
                domain = match.group(1)

            keywords = self._extract_keywords(subject)

            example = TrainingExample(
                email_id=email_id,
                category=category,
                sender=sender,
                subject=subject,
                domain=domain,
                keywords=keywords,
            )
            self._examples.append(example)

        self._is_trained = False
        self._save_training_data()

    def remove_category(self, category: str) -> int:
        """Remove all examples for a category.

        Args:
            category: Category name to remove.

        Returns:
            Number of examples removed.
        """
        before = len(self._examples)
        self._examples = [e for e in self._examples if e.category != category]
        removed = before - len(self._examples)
        if removed > 0:
            self._is_trained = False
            if category in self._models:
                del self._models[category]
            self._save_training_data()
        return removed

    def train(self):
        """Train models from the current examples.

        Builds per-category frequency models from all training examples.
        Must be called before predict() will work with new examples.
        """
        self._models = {}

        categories = set(e.category for e in self._examples)

        for category in categories:
            cat_examples = [e for e in self._examples if e.category == category]
            model = self._build_model(category, cat_examples)
            self._models[category] = model

        self._is_trained = True

    def predict(self, email: Dict) -> PredictionResult:
        """Predict the category for an email.

        Args:
            email: Email dict with 'sender'/'from', 'subject' fields.

        Returns:
            PredictionResult with predicted category and confidence.
        """
        if not self._is_trained:
            self.train()

        if not self._models:
            return PredictionResult(
                email_id=email.get("id", ""),
                predicted_category="unknown",
                confidence=0.0,
            )

        sender = email.get("sender", email.get("from", "")).lower()
        subject = email.get("subject", "").lower()

        domain = ""
        match = re.search(r"@([\w.-]+)", sender)
        if match:
            domain = match.group(1)

        keywords = self._extract_keywords(subject)

        scores: Dict[str, float] = {}
        reasons: Dict[str, List[str]] = defaultdict(list)

        for cat_name, model in self._models.items():
            score = self._score_email(sender, domain, keywords, model, reasons[cat_name])
            scores[cat_name] = score

        if not scores:
            return PredictionResult(
                email_id=email.get("id", ""),
                predicted_category="unknown",
                confidence=0.0,
            )

        max_cat = max(scores, key=scores.get)
        max_score = scores[max_cat]
        total_score = sum(scores.values())

        confidence = max_score / total_score if total_score > 0 else 0.0
        confidence = min(1.0, confidence)

        return PredictionResult(
            email_id=email.get("id", ""),
            predicted_category=max_cat,
            confidence=round(confidence, 3),
            scores={k: round(v, 3) for k, v in sorted(scores.items(), key=lambda x: x[1], reverse=True)},
            reasons=reasons.get(max_cat, [])[:5],
        )

    def predict_batch(self, emails: List[Dict]) -> List[PredictionResult]:
        """Predict categories for a batch of emails.

        Args:
            emails: List of email dicts.

        Returns:
            List of PredictionResult instances.
        """
        if not self._is_trained:
            self.train()
        return [self.predict(email) for email in emails]

    def get_categories(self) -> List[str]:
        """Get all trained category names."""
        return list(set(e.category for e in self._examples))

    def get_category_stats(self) -> Dict[str, Dict]:
        """Get statistics for each category.

        Returns:
            Dict mapping category name to stats dict with
            example_count, top_senders, top_domains, top_keywords.
        """
        stats = {}
        categories = self.get_categories()

        for category in categories:
            cat_examples = [e for e in self._examples if e.category == category]

            sender_counts = Counter(e.sender for e in cat_examples if e.sender)
            domain_counts = Counter(e.domain for e in cat_examples if e.domain)
            keyword_counts = Counter()
            for e in cat_examples:
                keyword_counts.update(e.keywords)

            stats[category] = {
                "example_count": len(cat_examples),
                "top_senders": sender_counts.most_common(5),
                "top_domains": domain_counts.most_common(5),
                "top_keywords": keyword_counts.most_common(10),
            }

        return stats

    def get_training_summary(self) -> Dict:
        """Get overall training summary.

        Returns:
            Dict with total_examples, category_count, is_trained, categories.
        """
        categories = self.get_categories()
        return {
            "total_examples": len(self._examples),
            "category_count": len(categories),
            "is_trained": self._is_trained,
            "categories": categories,
            "examples_per_category": {
                cat: sum(1 for e in self._examples if e.category == cat)
                for cat in categories
            },
        }

    def _build_model(self, category: str, examples: List[TrainingExample]) -> CategoryModel:
        """Build a category model from examples."""
        sender_counts: Dict[str, int] = Counter()
        domain_counts: Dict[str, int] = Counter()
        keyword_counts: Dict[str, int] = Counter()
        subject_word_counts: Dict[str, int] = Counter()

        for example in examples:
            if example.sender:
                sender_counts[example.sender] += 1
            if example.domain:
                domain_counts[example.domain] += 1
            keyword_counts.update(example.keywords)
            words = re.findall(r"\b[a-z]{3,}\b", example.subject)
            subject_word_counts.update(w for w in words if w not in self.STOP_WORDS)

        # Calculate keyword weights using inverse frequency
        total_examples = len(self._examples)
        keyword_weights = {}
        for keyword, count in keyword_counts.items():
            # How many examples across ALL categories contain this keyword?
            global_count = sum(
                1 for e in self._examples if keyword in e.keywords
            )
            idf = total_examples / max(global_count, 1)
            tf = count / len(examples)
            keyword_weights[keyword] = round(tf * idf, 3)

        return CategoryModel(
            name=category,
            example_count=len(examples),
            sender_patterns=dict(sender_counts.most_common(20)),
            domain_patterns=dict(domain_counts.most_common(10)),
            keyword_weights=dict(sorted(keyword_weights.items(), key=lambda x: x[1], reverse=True)[:30]),
            subject_patterns=dict(subject_word_counts.most_common(20)),
        )

    def _score_email(
        self, sender: str, domain: str, keywords: List[str],
        model: CategoryModel, reasons: List[str]
    ) -> float:
        """Score an email against a category model."""
        score = 0.0

        # Sender match (strong signal)
        if sender in model.sender_patterns:
            sender_weight = model.sender_patterns[sender] / max(model.example_count, 1)
            score += sender_weight * 3.0
            reasons.append(f"sender '{sender}' seen {model.sender_patterns[sender]}x")

        # Domain match
        if domain in model.domain_patterns:
            domain_weight = model.domain_patterns[domain] / max(model.example_count, 1)
            score += domain_weight * 2.0
            reasons.append(f"domain '{domain}' seen {model.domain_patterns[domain]}x")

        # Keyword matches
        for keyword in keywords:
            if keyword in model.keyword_weights:
                score += model.keyword_weights[keyword]
                if model.keyword_weights[keyword] > 0.5:
                    reasons.append(f"keyword '{keyword}' (weight: {model.keyword_weights[keyword]:.2f})")

        return score

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract significant keywords from text."""
        words = re.findall(r"\b[a-z]{3,}\b", text.lower())
        return [w for w in words if w not in self.STOP_WORDS]

    def _save_training_data(self):
        """Save training examples to disk."""
        filepath = self._config_dir / self.TRAINING_FILE
        data = []
        for example in self._examples:
            data.append({
                "email_id": example.email_id,
                "category": example.category,
                "sender": example.sender,
                "subject": example.subject,
                "domain": example.domain,
                "keywords": example.keywords,
            })

        try:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _load_training_data(self):
        """Load training examples from disk."""
        filepath = self._config_dir / self.TRAINING_FILE
        if not filepath.exists():
            return

        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            self._examples = []
            for item in data:
                self._examples.append(TrainingExample(
                    email_id=item.get("email_id", ""),
                    category=item.get("category", ""),
                    sender=item.get("sender", ""),
                    subject=item.get("subject", ""),
                    domain=item.get("domain", ""),
                    keywords=item.get("keywords", []),
                ))

            if self._examples:
                self.train()
        except Exception:
            pass
