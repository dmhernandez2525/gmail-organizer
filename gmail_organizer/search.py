"""Semantic Search Engine - TF-IDF based email search with relevance ranking"""

import re
import math
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
from email.utils import parsedate_to_datetime


class SearchIndex:
    """TF-IDF search index for emails"""

    # Common English stop words to exclude from indexing
    STOP_WORDS = frozenset({
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
        'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'or', 'she',
        'that', 'the', 'to', 'was', 'were', 'will', 'with', 'this',
        'but', 'they', 'have', 'had', 'what', 'when', 'where', 'who',
        'which', 'their', 'been', 'would', 'there', 'could', 'other',
        'than', 'then', 'these', 'those', 'your', 'you', 'not', 'can',
        'all', 'each', 'every', 'both', 'few', 'more', 'most', 'some',
        'such', 'only', 'own', 'same', 'into', 'just', 'very', 'also',
        'about', 'after', 'before', 'between', 'through', 'during',
        'above', 'below', 'up', 'down', 'out', 'off', 'over', 'under',
        're', 'fw', 'fwd', 'sent', 'http', 'https', 'www', 'com',
        'org', 'net', 'gmail', 'email', 'mail'
    })

    def __init__(self):
        self._documents: List[Dict] = []  # Original email dicts
        self._doc_vectors: List[Dict[str, float]] = []  # TF-IDF vectors per doc
        self._idf: Dict[str, float] = {}  # Inverse document frequency
        self._doc_terms: List[Set[str]] = []  # Terms per document
        self._indexed = False
        self._field_weights = {
            'subject': 3.0,    # Subject is most important
            'sender': 2.0,     # Sender is secondary
            'body': 1.0        # Body is base weight
        }

    def build_index(self, emails: List[Dict]):
        """
        Build the TF-IDF search index from emails.

        Args:
            emails: List of email dicts with sender, subject, body_preview, date fields
        """
        self._documents = emails
        self._doc_vectors = []
        self._doc_terms = []

        # Step 1: Tokenize all documents and compute document frequencies
        doc_freq: Counter = Counter()  # How many docs contain each term
        all_doc_terms = []

        for email in emails:
            terms = self._tokenize_email(email)
            unique_terms = set(terms)
            all_doc_terms.append(terms)
            self._doc_terms.append(unique_terms)
            for term in unique_terms:
                doc_freq[term] += 1

        # Step 2: Compute IDF
        n_docs = len(emails)
        self._idf = {}
        for term, df in doc_freq.items():
            # Smooth IDF to avoid zero division and handle rare terms
            self._idf[term] = math.log((n_docs + 1) / (df + 1)) + 1

        # Step 3: Compute TF-IDF vectors for each document
        for terms in all_doc_terms:
            tf = Counter(terms)
            max_tf = max(tf.values()) if tf else 1
            vector = {}
            for term, count in tf.items():
                # Augmented TF to prevent bias towards longer documents
                tf_score = 0.5 + 0.5 * (count / max_tf)
                vector[term] = tf_score * self._idf.get(term, 1.0)
            self._doc_vectors.append(vector)

        self._indexed = True

    def search(self, query: str, limit: int = 50,
               min_score: float = 0.01,
               sender_filter: str = "",
               category_filter: str = "",
               date_from: str = "",
               date_to: str = "",
               label_filter: str = "") -> List[Tuple[Dict, float]]:
        """
        Search emails using TF-IDF similarity.

        Args:
            query: Natural language search query
            limit: Max results to return
            min_score: Minimum relevance score (0-1)
            sender_filter: Filter by sender email/name (substring match)
            category_filter: Filter by category
            date_from: Filter emails after this date (YYYY-MM-DD)
            date_to: Filter emails before this date (YYYY-MM-DD)
            label_filter: Filter by Gmail label

        Returns:
            List of (email_dict, relevance_score) tuples, sorted by score desc
        """
        if not self._indexed:
            return []

        # Parse query into terms
        query_terms = self._tokenize_query(query)
        if not query_terms:
            return []

        # Build query vector
        query_tf = Counter(query_terms)
        max_qtf = max(query_tf.values()) if query_tf else 1
        query_vector = {}
        for term, count in query_tf.items():
            tf_score = 0.5 + 0.5 * (count / max_qtf)
            query_vector[term] = tf_score * self._idf.get(term, 1.0)

        # Compute cosine similarity with each document
        results = []
        query_norm = self._vector_norm(query_vector)
        if query_norm == 0:
            return []

        # Parse date filters
        date_from_dt = self._parse_filter_date(date_from) if date_from else None
        date_to_dt = self._parse_filter_date(date_to) if date_to else None

        for i, doc_vector in enumerate(self._doc_vectors):
            email = self._documents[i]

            # Apply filters before scoring (faster)
            if sender_filter:
                sender = email.get('sender', '').lower()
                if sender_filter.lower() not in sender:
                    continue

            if category_filter:
                if email.get('category', '') != category_filter:
                    continue

            if label_filter:
                labels = email.get('labels', [])
                if label_filter not in labels:
                    continue

            if date_from_dt or date_to_dt:
                email_date = self._parse_email_date(email.get('date', ''))
                if email_date:
                    if date_from_dt and email_date < date_from_dt:
                        continue
                    if date_to_dt and email_date > date_to_dt:
                        continue

            # Compute cosine similarity
            score = self._cosine_similarity(query_vector, doc_vector, query_norm)

            # Boost exact matches in subject
            subject = email.get('subject', '').lower()
            query_lower = query.lower()
            if query_lower in subject:
                score *= 2.0
            elif any(t in subject for t in query_terms[:3]):
                score *= 1.3

            if score >= min_score:
                results.append((email, score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def find_similar(self, email: Dict, limit: int = 10) -> List[Tuple[Dict, float]]:
        """
        Find emails similar to a given email.

        Args:
            email: Reference email dict
            limit: Max results

        Returns:
            List of (email_dict, similarity_score) tuples
        """
        if not self._indexed:
            return []

        # Find this email's index
        ref_idx = None
        email_id = email.get('email_id', '')
        for i, doc in enumerate(self._documents):
            if doc.get('email_id') == email_id:
                ref_idx = i
                break

        if ref_idx is None:
            # Build vector for unknown email
            terms = self._tokenize_email(email)
            tf = Counter(terms)
            max_tf = max(tf.values()) if tf else 1
            ref_vector = {}
            for term, count in tf.items():
                tf_score = 0.5 + 0.5 * (count / max_tf)
                ref_vector[term] = tf_score * self._idf.get(term, 1.0)
        else:
            ref_vector = self._doc_vectors[ref_idx]

        ref_norm = self._vector_norm(ref_vector)
        if ref_norm == 0:
            return []

        results = []
        for i, doc_vector in enumerate(self._doc_vectors):
            if i == ref_idx:
                continue
            score = self._cosine_similarity(ref_vector, doc_vector, ref_norm)
            if score > 0.05:
                results.append((self._documents[i], score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def get_suggestions(self, partial_query: str, limit: int = 8) -> List[str]:
        """
        Get search suggestions based on partial query.

        Returns terms from the index that start with the partial query.
        """
        if not self._indexed or not partial_query:
            return []

        partial = partial_query.lower().strip()
        last_word = partial.split()[-1] if partial.split() else ""
        if not last_word:
            return []

        # Find matching terms sorted by IDF (rarer = more useful)
        matches = []
        for term, idf in self._idf.items():
            if term.startswith(last_word) and term != last_word:
                matches.append((term, idf))

        matches.sort(key=lambda x: x[1], reverse=True)
        return [m[0] for m in matches[:limit]]

    def _tokenize_email(self, email: Dict) -> List[str]:
        """Tokenize an email into weighted terms"""
        terms = []

        # Subject (weighted higher via repetition)
        subject = email.get('subject', '')
        subject_terms = self._tokenize_text(subject)
        weight = int(self._field_weights['subject'])
        terms.extend(subject_terms * weight)

        # Sender
        sender = email.get('sender', '')
        sender_terms = self._tokenize_text(sender)
        weight = int(self._field_weights['sender'])
        terms.extend(sender_terms * weight)

        # Body preview
        body = email.get('body_preview', '')
        body_terms = self._tokenize_text(body)
        terms.extend(body_terms)

        return terms

    def _tokenize_query(self, query: str) -> List[str]:
        """Tokenize a search query"""
        return self._tokenize_text(query)

    def _tokenize_text(self, text: str) -> List[str]:
        """
        Tokenize text into normalized terms.

        Applies:
        - Lowercase
        - Remove special characters
        - Split on whitespace
        - Remove stop words
        - Remove very short tokens (< 2 chars)
        """
        if not text:
            return []

        text = text.lower()
        # Remove email addresses but keep the parts
        text = re.sub(r'([a-z0-9._%+-]+)@([a-z0-9.-]+)', r'\1 \2', text)
        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)
        # Remove special characters, keep alphanumeric and spaces
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        # Split and filter
        tokens = text.split()
        return [t for t in tokens if len(t) >= 2 and t not in self.STOP_WORDS]

    def _cosine_similarity(self, vec_a: Dict[str, float],
                           vec_b: Dict[str, float],
                           norm_a: float = 0) -> float:
        """Compute cosine similarity between two sparse vectors"""
        if not norm_a:
            norm_a = self._vector_norm(vec_a)
        norm_b = self._vector_norm(vec_b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        # Dot product (iterate over smaller set for performance)
        smaller, larger = (vec_a, vec_b) if len(vec_a) <= len(vec_b) else (vec_b, vec_a)
        dot = sum(smaller[term] * larger.get(term, 0) for term in smaller)
        return dot / (norm_a * norm_b)

    def _vector_norm(self, vector: Dict[str, float]) -> float:
        """Compute L2 norm of a sparse vector"""
        return math.sqrt(sum(v * v for v in vector.values()))

    def _parse_filter_date(self, date_str: str) -> Optional[datetime]:
        """Parse YYYY-MM-DD date string"""
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except (ValueError, TypeError):
            return None

    def _parse_email_date(self, date_str: str) -> Optional[datetime]:
        """Parse email date string"""
        if not date_str:
            return None
        try:
            return parsedate_to_datetime(date_str).replace(tzinfo=None)
        except Exception:
            for fmt in ('%Y-%m-%d %H:%M:%S', '%d %b %Y %H:%M:%S'):
                try:
                    return datetime.strptime(date_str[:20], fmt)
                except Exception:
                    continue
        return None

    @property
    def document_count(self) -> int:
        """Number of indexed documents"""
        return len(self._documents)

    @property
    def vocabulary_size(self) -> int:
        """Number of unique terms in the index"""
        return len(self._idf)
