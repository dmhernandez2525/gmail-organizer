"""Tests for CategoryTrainer in gmail_organizer/training.py."""

import json
import pytest
from gmail_organizer.training import CategoryTrainer, TrainingExample, CategoryModel, PredictionResult


@pytest.fixture
def trainer(tmp_path):
    return CategoryTrainer(config_dir=str(tmp_path))


def _email(email_id="e1", sender="alice@example.com", subject="Hello world"):
    return {"email_id": email_id, "sender": sender, "subject": subject}


class TestAddExample:
    def test_adds_example(self, trainer):
        trainer.add_example(_email(), "inbox")
        assert len(trainer._examples) == 1
        assert trainer._examples[0].category == "inbox"
        assert trainer._examples[0].sender == "alice@example.com"

    def test_extracts_domain(self, trainer):
        trainer.add_example(_email(sender="bob@company.org"), "work")
        assert trainer._examples[0].domain == "company.org"

    def test_extracts_keywords(self, trainer):
        trainer.add_example(_email(subject="urgent meeting tomorrow"), "work")
        kw = trainer._examples[0].keywords
        assert "urgent" in kw
        assert "meeting" in kw
        assert "tomorrow" in kw

    def test_marks_untrained(self, trainer):
        trainer.train()
        assert trainer._is_trained
        trainer.add_example(_email(), "inbox")
        assert not trainer._is_trained

    def test_saves_to_disk(self, trainer, tmp_path):
        trainer.add_example(_email(), "inbox")
        filepath = tmp_path / CategoryTrainer.TRAINING_FILE
        assert filepath.exists()
        data = json.loads(filepath.read_text())
        assert len(data) == 1
        assert data[0]["category"] == "inbox"


class TestAddExamplesBatch:
    def test_adds_multiple(self, trainer):
        emails = [_email(f"e{i}", f"s{i}@test.com", f"subject {i}") for i in range(5)]
        trainer.add_examples_batch(emails, "promo")
        assert len(trainer._examples) == 5
        assert all(e.category == "promo" for e in trainer._examples)


class TestRemoveCategory:
    def test_removes_all_examples(self, trainer):
        trainer.add_example(_email("e1"), "keep")
        trainer.add_example(_email("e2"), "remove")
        trainer.add_example(_email("e3"), "remove")
        removed = trainer.remove_category("remove")
        assert removed == 2
        assert len(trainer._examples) == 1

    def test_returns_zero_for_missing(self, trainer):
        assert trainer.remove_category("nope") == 0


class TestTrain:
    def test_builds_models(self, trainer):
        trainer.add_example(_email("e1", "a@x.com", "sale discount"), "promo")
        trainer.add_example(_email("e2", "b@x.com", "big sale"), "promo")
        trainer.add_example(_email("e3", "c@work.com", "meeting agenda"), "work")
        trainer.train()
        assert "promo" in trainer._models
        assert "work" in trainer._models
        assert trainer._models["promo"].example_count == 2

    def test_marks_trained(self, trainer):
        trainer.add_example(_email(), "cat")
        trainer.train()
        assert trainer._is_trained


class TestPredict:
    def test_predicts_matching_sender(self, trainer):
        for i in range(3):
            trainer.add_example(_email(f"e{i}", "newsletter@promo.com", f"deals {i}"), "promo")
        trainer.add_example(_email("w1", "boss@work.com", "meeting"), "work")
        trainer.train()

        result = trainer.predict(_email("new", "newsletter@promo.com", "latest deals"))
        assert result.predicted_category == "promo"
        assert result.confidence > 0

    def test_returns_unknown_with_no_models(self, trainer):
        result = trainer.predict(_email())
        assert result.predicted_category == "unknown"
        assert result.confidence == 0.0

    def test_auto_trains_if_needed(self, trainer):
        trainer.add_example(_email("e1", "a@x.com", "test"), "cat")
        assert not trainer._is_trained
        trainer.predict(_email("e2", "a@x.com", "test"))
        assert trainer._is_trained

    def test_returns_prediction_result(self, trainer):
        trainer.add_example(_email("e1", "a@x.com", "invoice payment"), "finance")
        result = trainer.predict(_email("e2", "a@x.com", "invoice"))
        assert isinstance(result, PredictionResult)
        assert result.email_id == "e2"


class TestPredictBatch:
    def test_predicts_all(self, trainer):
        trainer.add_example(_email("e1", "a@x.com", "sale"), "promo")
        emails = [_email(f"e{i}", "a@x.com", "sale") for i in range(3)]
        results = trainer.predict_batch(emails)
        assert len(results) == 3


class TestGetCategories:
    def test_returns_categories(self, trainer):
        trainer.add_example(_email("e1"), "a")
        trainer.add_example(_email("e2"), "b")
        trainer.add_example(_email("e3"), "a")
        cats = trainer.get_categories()
        assert set(cats) == {"a", "b"}


class TestGetCategoryStats:
    def test_returns_stats(self, trainer):
        trainer.add_example(_email("e1", "a@x.com", "hello world"), "cat")
        trainer.add_example(_email("e2", "b@y.com", "hello again"), "cat")
        stats = trainer.get_category_stats()
        assert "cat" in stats
        assert stats["cat"]["example_count"] == 2


class TestGetTrainingSummary:
    def test_summary(self, trainer):
        trainer.add_example(_email("e1"), "a")
        trainer.add_example(_email("e2"), "b")
        s = trainer.get_training_summary()
        assert s["total_examples"] == 2
        assert s["category_count"] == 2
        assert not s["is_trained"]


class TestExtractKeywords:
    def test_filters_stop_words(self, trainer):
        kw = trainer._extract_keywords("this is the best email about nothing")
        assert "this" not in kw
        assert "best" not in kw  # best is a stop word
        assert "nothing" in kw

    def test_filters_short_words(self, trainer):
        kw = trainer._extract_keywords("go to the big party")
        assert "go" not in kw
        assert "to" not in kw
        assert "party" in kw


class TestPersistence:
    def test_load_from_disk(self, tmp_path):
        t1 = CategoryTrainer(config_dir=str(tmp_path))
        t1.add_example(_email("e1", "a@x.com", "test"), "cat")
        t1.add_example(_email("e2", "b@y.com", "stuff"), "other")

        t2 = CategoryTrainer(config_dir=str(tmp_path))
        assert len(t2._examples) == 2
        assert t2._is_trained  # auto-trains on load

    def test_corrupt_file_handled(self, tmp_path):
        filepath = tmp_path / CategoryTrainer.TRAINING_FILE
        filepath.write_text("NOT JSON{{{")
        t = CategoryTrainer(config_dir=str(tmp_path))
        assert len(t._examples) == 0


class TestBuildModel:
    def test_model_has_patterns(self, trainer):
        trainer.add_example(_email("e1", "a@x.com", "sale discount offer"), "promo")
        trainer.add_example(_email("e2", "a@x.com", "big sale today"), "promo")
        trainer.train()
        model = trainer._models["promo"]
        assert "a@x.com" in model.sender_patterns
        assert "x.com" in model.domain_patterns
        assert "sale" in model.keyword_weights


class TestScoreEmail:
    def test_sender_match_boosts_score(self, trainer):
        model = CategoryModel(
            name="test",
            example_count=5,
            sender_patterns={"a@x.com": 3},
            domain_patterns={},
            keyword_weights={},
        )
        reasons = []
        score = trainer._score_email("a@x.com", "x.com", [], model, reasons)
        assert score > 0
        assert len(reasons) > 0

    def test_domain_match_boosts_score(self, trainer):
        model = CategoryModel(
            name="test",
            example_count=5,
            sender_patterns={},
            domain_patterns={"x.com": 4},
            keyword_weights={},
        )
        reasons = []
        score = trainer._score_email("b@x.com", "x.com", [], model, reasons)
        assert score > 0

    def test_keyword_match_boosts_score(self, trainer):
        model = CategoryModel(
            name="test",
            example_count=5,
            sender_patterns={},
            domain_patterns={},
            keyword_weights={"sale": 2.0, "discount": 1.5},
        )
        reasons = []
        score = trainer._score_email("", "", ["sale", "discount"], model, reasons)
        assert score == pytest.approx(3.5)
