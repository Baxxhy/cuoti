import pytest
from fastapi import HTTPException
from test_learning_safety import FakeDb, Rows

from app import main
from app.models import DatasetPracticeAttempt, DatasetQuestion, PracticeRecommendation, Question, User
from app.schemas import PracticeAttemptRequest, PracticeRecommendRequest
from app.services.practice_retrieval import RetrievalCandidate
from app.services.question_lifecycle import question_source_fingerprint


class PracticeLifecycleDb(FakeDb):
    """Persist cache writes/deletes and apply the predicates used by this lifecycle."""

    def __init__(self, *rows):
        super().__init__(*rows)
        self.persisted = {id(row) for row in rows}

    async def scalars(self, statement):
        rows = await super().scalars(statement)
        model = statement.column_descriptions[0]["entity"]
        if model not in {PracticeRecommendation, DatasetPracticeAttempt}:
            return rows
        values = {key.rsplit("_", 1)[0]: value for key, value in statement.compile().params.items()}
        rows = Rows(
            row for row in reversed(rows) if all(getattr(row, key) == value for key, value in values.items())
        )
        name = statement.column_descriptions[0]["name"]
        return rows if name == model.__name__ else Rows(getattr(row, name) for row in rows)

    async def execute(self, statement):
        result = await super().execute(statement)
        if getattr(statement, "is_delete", False) and statement.table.name == "practice_recommendations":
            source_id = statement.compile().params["mistake_id_1"]
            self.rows = {
                key: row
                for key, row in self.rows.items()
                if not isinstance(row, PracticeRecommendation) or row.mistake_id != source_id
            }
        return result

    async def flush(self):
        await super().flush()
        for row in self.added:
            if id(row) not in self.persisted:
                self.rows[(type(row), row.id)] = row
                self.persisted.add(id(row))


@pytest.fixture
def practice_lifecycle(monkeypatch):
    user = User(id="student")
    source = Question(
        id="source",
        user_id=user.id,
        subject="数学",
        grade="初一",
        title="方程",
        question_text="解方程2x=8",
        question_type="填空题",
        knowledge_points=[],
        confirmed=True,
    )
    old = DatasetQuestion(
        id="old",
        subject="数学",
        grade="初一",
        question_text="x+1=3",
        question_type="填空题",
        image_paths=[],
        options=[],
        knowledge_points=[],
        usable_for_auto_grade=True,
    )
    recommendation = PracticeRecommendation(
        id="cached",
        user_id=user.id,
        mistake_id=source.id,
        dataset_question_id=old.id,
        mode="reinforce",
        retrieval_trace={"source_question_fingerprint": question_source_fingerprint(source)},
    )
    history = DatasetPracticeAttempt(
        id="history",
        user_id=user.id,
        mistake_id=source.id,
        dataset_question_id="previously-completed",
        mode="reinforce",
        grading_details={"correct": True},
    )
    new = DatasetQuestion(
        id="new",
        subject="物理",
        grade="初一",
        question_text="一个物体受到三个力的作用，求合力。",
        question_type="填空题",
        image_paths=[],
        options=[],
        knowledge_points=[],
    )
    candidate = RetrievalCandidate(new, "test", [], 1, 1, 1, 0.8)
    db = PracticeLifecycleDb(source, old, new, recommendation, history)
    queries = []

    async def knowledge(*_args):
        return []

    async def hybrid(query, subject, *_args):
        queries.append((query, subject))
        return [candidate], {}, {}

    async def load(*_args):
        return [candidate]

    async def rank(*_args):
        return [candidate]

    async def forbidden_update(*_args, **_kwargs):
        raise AssertionError("An outdated recommendation must not grade or update mastery")

    monkeypatch.setattr(main, "_practice_knowledge", knowledge)
    monkeypatch.setattr(main, "hybrid_ids", hybrid)
    monkeypatch.setattr(main, "load_candidates", load)
    monkeypatch.setattr(main, "rerank_candidates", rank)
    monkeypatch.setattr(main, "grade_answer", forbidden_update)
    monkeypatch.setattr(main, "update_cognition", forbidden_update)
    return user, source, old, recommendation, history, db, queries


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "edits",
    [
        {"question_text": "解方程3x=15"},
        {"subject": "物理", "question_text": "求物体所受合力"},
        {"student_steps": [{"text": "2x=8，然后x=4"}]},
    ],
)
async def test_question_edit_replaces_cached_practice_and_blocks_old_submission(practice_lifecycle, edits):
    user, source, old, cached, history, db, queries = practice_lifecycle
    request = PracticeRecommendRequest(mistake_id=source.id, mode="reinforce")
    before = await main.recommend_practice(request, user, db)
    assert before["data"]["question_id"] == old.id and not queries

    await main.apply_ocr_edits(source, edits, db)
    await db.commit()
    assert (PracticeRecommendation, cached.id) not in db.rows
    assert db.rows[(DatasetPracticeAttempt, history.id)] is history
    assert history.grading_details["question_changed"] is True

    old_answer = PracticeAttemptRequest(
        mistake_id=source.id, question_id=old.id, mode="reinforce", student_answer="2"
    )
    with pytest.raises(HTTPException) as deleted_error:
        await main.attempt_practice(old_answer, user, db)
    assert deleted_error.value.status_code == 409

    # Even a legacy/stale cache row cannot authorize grading against the new text.
    db.rows[(PracticeRecommendation, cached.id)] = cached
    with pytest.raises(HTTPException) as stale_error:
        await main.attempt_practice(old_answer, user, db)
    assert stale_error.value.status_code == 409
    after = await main.recommend_practice(request, user, db)
    assert after["data"]["question_id"] == "new"
    assert queries[0][1] == source.subject and source.question_text in queries[0][0]
    assert not any(isinstance(row, DatasetPracticeAttempt) for row in db.added)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "edits", [{"subject": "物理", "question_text": "求合力"}, {"student_steps": [{"text": "x=4"}]}]
)
async def test_edit_during_retrieval_does_not_publish_a_stale_recommendation(
    practice_lifecycle, monkeypatch, edits
):
    user, source, _old, _cached, history, db, _queries = practice_lifecycle
    original_rank = main.rerank_candidates

    async def edit_while_ranking(*args):
        await main.apply_ocr_edits(source, edits, db)
        return await original_rank(*args)

    monkeypatch.setattr(main, "rerank_candidates", edit_while_ranking)
    with pytest.raises(HTTPException) as error:
        await main.recommend_practice(
            PracticeRecommendRequest(mistake_id=source.id, mode="reinforce", force_new=True), user, db
        )
    assert error.value.status_code == 409
    assert not any(isinstance(row, PracticeRecommendation) for row in db.added)
    assert db.rows[(DatasetPracticeAttempt, history.id)] is history
