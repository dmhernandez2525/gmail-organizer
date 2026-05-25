"""Tests for gmail_organizer/search.py - SearchIndex TF-IDF search engine."""

import pytest

from gmail_organizer.search import SearchIndex


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_emails():
    """A set of emails covering different senders, subjects, and bodies."""
    return [
        {
            "email_id": "e1",
            "sender": "recruiter@bigcorp.com",
            "subject": "Senior Python Developer opening",
            "body_preview": "We have an exciting opportunity for a senior python developer.",
            "date": "Mon, 20 Mar 2026 10:00:00 +0000",
            "category": "recruiter_outreach",
            "labels": ["INBOX"],
        },
        {
            "email_id": "e2",
            "sender": "newsletter@techdigest.com",
            "subject": "Weekly Tech Newsletter",
            "body_preview": "Top stories this week: AI breakthroughs and cloud computing trends.",
            "date": "Tue, 21 Mar 2026 08:00:00 +0000",
            "category": "newsletters",
            "labels": ["INBOX", "CATEGORY_PROMOTIONS"],
        },
        {
            "email_id": "e3",
            "sender": "boss@company.com",
            "subject": "Quarterly review meeting",
            "body_preview": "Please prepare the quarterly performance report by Friday.",
            "date": "Wed, 22 Mar 2026 14:30:00 +0000",
            "category": "work",
            "labels": ["INBOX", "IMPORTANT"],
        },
        {
            "email_id": "e4",
            "sender": "friend@personal.com",
            "subject": "Weekend hiking trip",
            "body_preview": "Want to go hiking this weekend? The weather looks great.",
            "date": "Thu, 23 Mar 2026 18:00:00 +0000",
            "category": "personal",
            "labels": ["INBOX"],
        },
        {
            "email_id": "e5",
            "sender": "recruiter2@startup.io",
            "subject": "Python Engineer role at Startup",
            "body_preview": "Startup is looking for a python engineer to join the team.",
            "date": "Fri, 24 Mar 2026 09:00:00 +0000",
            "category": "recruiter_outreach",
            "labels": ["INBOX"],
        },
    ]


@pytest.fixture
def index(sample_emails):
    """Pre-built search index."""
    idx = SearchIndex()
    idx.build_index(sample_emails)
    return idx


# ---------------------------------------------------------------------------
# build_index
# ---------------------------------------------------------------------------

class TestBuildIndex:
    """Tests for building the TF-IDF index."""

    def test_document_count(self, index, sample_emails):
        assert index.document_count == len(sample_emails)

    def test_vocabulary_size_positive(self, index):
        assert index.vocabulary_size > 0

    def test_empty_index(self):
        idx = SearchIndex()
        idx.build_index([])
        assert idx.document_count == 0
        assert idx.vocabulary_size == 0

    def test_index_flag_set(self, index):
        assert index._indexed is True

    def test_unbuilt_index_flag(self):
        idx = SearchIndex()
        assert idx._indexed is False


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

class TestSearch:
    """Tests for the search method."""

    def test_basic_keyword_search(self, index):
        results = index.search("python developer")
        assert len(results) > 0
        # The two recruiter emails should rank high
        ids = [r[0]["email_id"] for r in results]
        assert "e1" in ids

    def test_returns_tuples_of_email_and_score(self, index):
        results = index.search("python")
        for email, score in results:
            assert isinstance(email, dict)
            assert isinstance(score, float)
            assert score > 0

    def test_empty_query_returns_nothing(self, index):
        assert index.search("") == []

    def test_stop_words_only_returns_nothing(self, index):
        # "the" and "a" are stop words
        assert index.search("the a") == []

    def test_no_results_for_unrelated_query(self, index):
        results = index.search("xylophone orchestra")
        assert results == []

    def test_limit_parameter(self, index):
        results = index.search("python", limit=1)
        assert len(results) <= 1

    def test_min_score_filters_low_results(self, index):
        results = index.search("python", min_score=999.0)
        assert results == []

    def test_search_before_build_returns_empty(self):
        idx = SearchIndex()
        assert idx.search("anything") == []

    def test_sender_filter(self, index):
        results = index.search("python", sender_filter="startup")
        ids = [r[0]["email_id"] for r in results]
        # Only e5 is from startup.io
        assert all(
            "startup" in r[0]["sender"] for r in results
        )

    def test_category_filter(self, index):
        results = index.search("python", category_filter="newsletters")
        ids = [r[0]["email_id"] for r in results]
        assert "e1" not in ids  # e1 is recruiter_outreach

    def test_label_filter(self, index):
        results = index.search("python", label_filter="IMPORTANT")
        # Only e3 has IMPORTANT label; it may or may not match "python"
        for email, _ in results:
            assert "IMPORTANT" in email.get("labels", [])

    def test_date_from_filter(self, index):
        results = index.search("python", date_from="2026-03-24")
        # Only e5 is on or after Mar 24
        for email, _ in results:
            assert email["email_id"] == "e5"

    def test_date_to_filter(self, index):
        results = index.search("python", date_to="2026-03-21")
        # Only emails before or on Mar 21
        for email, _ in results:
            assert email["email_id"] in ("e1", "e2")

    def test_exact_subject_match_boosted(self, index):
        """An exact substring match in subject should boost the score."""
        results = index.search("weekly tech newsletter")
        assert len(results) > 0
        # e2 has "Weekly Tech Newsletter" in subject, should rank first
        assert results[0][0]["email_id"] == "e2"

    def test_results_sorted_by_score_descending(self, index):
        results = index.search("python")
        scores = [s for _, s in results]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# find_similar
# ---------------------------------------------------------------------------

class TestFindSimilar:
    """Tests for find_similar."""

    def test_finds_similar_emails(self, index, sample_emails):
        # e1 and e5 are both about python/recruiter roles
        results = index.find_similar(sample_emails[0])  # e1
        ids = [r[0]["email_id"] for r in results]
        assert "e5" in ids

    def test_excludes_reference_email(self, index, sample_emails):
        results = index.find_similar(sample_emails[0])
        ids = [r[0]["email_id"] for r in results]
        assert "e1" not in ids

    def test_unknown_email(self, index):
        unknown = {
            "email_id": "unknown",
            "sender": "recruiter@bigcorp.com",
            "subject": "Python Developer opportunity",
            "body_preview": "Looking for python developers.",
        }
        results = index.find_similar(unknown)
        assert isinstance(results, list)

    def test_find_similar_on_empty_index(self):
        idx = SearchIndex()
        assert idx.find_similar({"email_id": "x"}) == []

    def test_limit_parameter(self, index, sample_emails):
        results = index.find_similar(sample_emails[0], limit=1)
        assert len(results) <= 1


# ---------------------------------------------------------------------------
# get_suggestions
# ---------------------------------------------------------------------------

class TestGetSuggestions:
    """Tests for get_suggestions (autocomplete)."""

    def test_returns_matching_terms(self, index):
        suggestions = index.get_suggestions("pyth")
        assert "python" in suggestions

    def test_empty_query_returns_nothing(self, index):
        assert index.get_suggestions("") == []

    def test_respects_limit(self, index):
        suggestions = index.get_suggestions("p", limit=2)
        assert len(suggestions) <= 2

    def test_unbuilt_index_returns_nothing(self):
        idx = SearchIndex()
        assert idx.get_suggestions("test") == []

    def test_no_match_returns_empty(self, index):
        assert index.get_suggestions("zzzzz") == []

    def test_exact_term_not_in_suggestions(self, index):
        """If the query is already a complete term, it should not suggest itself."""
        suggestions = index.get_suggestions("python")
        assert "python" not in suggestions


# ---------------------------------------------------------------------------
# tokenization
# ---------------------------------------------------------------------------

class TestTokenization:
    """Tests for internal tokenization logic."""

    def test_removes_stop_words(self):
        idx = SearchIndex()
        tokens = idx._tokenize_text("the quick brown fox and the lazy dog")
        assert "the" not in tokens
        assert "and" not in tokens
        assert "quick" in tokens

    def test_lowercases_text(self):
        idx = SearchIndex()
        tokens = idx._tokenize_text("HELLO World")
        assert "hello" in tokens
        assert "world" in tokens

    def test_removes_short_tokens(self):
        idx = SearchIndex()
        tokens = idx._tokenize_text("I am a big person")
        # "i", "a" are single-char, should be excluded
        assert "i" not in tokens

    def test_handles_email_addresses(self):
        idx = SearchIndex()
        tokens = idx._tokenize_text("Contact user@example.com today")
        # Email is split into parts; "user" and "example" should appear
        assert "user" in tokens
        assert "example" in tokens

    def test_empty_string_returns_empty(self):
        idx = SearchIndex()
        assert idx._tokenize_text("") == []

    def test_urls_are_removed(self):
        idx = SearchIndex()
        tokens = idx._tokenize_text("Visit https://example.com/page for info")
        assert "https" not in tokens
        assert "example" not in tokens


# ---------------------------------------------------------------------------
# date parsing
# ---------------------------------------------------------------------------

class TestDateParsing:
    """Tests for internal date parsing helpers."""

    def test_parse_filter_date_valid(self):
        idx = SearchIndex()
        dt = idx._parse_filter_date("2026-03-20")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 3

    def test_parse_filter_date_invalid(self):
        idx = SearchIndex()
        assert idx._parse_filter_date("not-a-date") is None

    def test_parse_email_date_rfc2822(self):
        idx = SearchIndex()
        dt = idx._parse_email_date("Mon, 20 Mar 2026 10:00:00 +0000")
        assert dt is not None
        assert dt.year == 2026

    def test_parse_email_date_empty(self):
        idx = SearchIndex()
        assert idx._parse_email_date("") is None

    def test_parse_email_date_fallback(self):
        idx = SearchIndex()
        dt = idx._parse_email_date("2026-03-20 14:30:00")
        assert dt is not None


# ---------------------------------------------------------------------------
# cosine similarity edge cases
# ---------------------------------------------------------------------------

class TestCosineSimilarity:
    """Tests for the cosine similarity computation."""

    def test_identical_vectors_return_one(self):
        idx = SearchIndex()
        vec = {"hello": 1.0, "world": 2.0}
        score = idx._cosine_similarity(vec, vec)
        assert abs(score - 1.0) < 1e-6

    def test_orthogonal_vectors_return_zero(self):
        idx = SearchIndex()
        a = {"hello": 1.0}
        b = {"world": 1.0}
        score = idx._cosine_similarity(a, b)
        assert score == 0.0

    def test_empty_vector_returns_zero(self):
        idx = SearchIndex()
        assert idx._cosine_similarity({}, {"hello": 1.0}) == 0.0
        assert idx._cosine_similarity({"hello": 1.0}, {}) == 0.0
