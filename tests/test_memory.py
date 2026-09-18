from app.memory.store import MemoryStore


def test_memory_round_trip(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.remember("Find unread emails", "Found 3", "gmail")
    store.remember("What is my history?", "Recent local memory", "memory")

    assert store.count() == 2
    recent = store.recent(2)
    assert recent[0].command == "What is my history?"
    assert recent[1].response == "Found 3"


def test_mode_counts(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.remember("a", "b", "demo")
    store.remember("c", "d", "demo")
    store.remember("e", "f", "gmail")

    assert store.mode_counts() == {"demo": 2, "gmail": 1}


def test_feedback_and_conversation_context(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.remember("What is RAG?", "Retrieval augmented generation.", "ai:Local AI")
    store.remember("Explain that more.", "It combines retrieval with generation.", "ai:Cloud AI")

    feedback_id = store.record_feedback(
        "Explain that more.",
        "It combines retrieval with generation.",
        "down",
        "Cloud AI",
    )

    assert feedback_id > 0
    context = store.recent_context(limit=2, max_chars=1000)
    assert "What is RAG?" in context
    assert "Explain that more." in context
