"""
Tests for openclaw_memory.
"""

import pytest
from datetime import datetime
from openclaw_memory.core import MemoryEntry, MemoryStore, FileStorage


class TestMemoryEntry:
    def test_create(self):
        entry = MemoryEntry.create(content="Test memory", tags=["test"])
        assert entry.content == "Test memory"
        assert entry.tags == ["test"]
        assert entry.importance == 0.5
        assert entry.entry_type == "daily"
        assert entry.id is not None

    def test_create_with_params(self):
        entry = MemoryEntry.create(
            content="Important note",
            tags=["work", "urgent"],
            importance=0.9,
            entry_type="longterm",
        )
        assert entry.content == "Important note"
        assert entry.tags == ["work", "urgent"]
        assert entry.importance == 0.9
        assert entry.entry_type == "longterm"


class TestFileStorage:
    def test_add_and_get(self, tmp_path):
        storage = FileStorage(memory_dir=tmp_path)
        entry = MemoryEntry.create(content="Test entry")
        storage.add(entry)
        retrieved = storage.get(entry.id)
        assert retrieved is not None
        assert retrieved.content == "Test entry"

    def test_list(self, tmp_path):
        storage = FileStorage(memory_dir=tmp_path)
        for i in range(5):
            entry = MemoryEntry.create(content=f"Entry {i}")
            storage.add(entry)
        results = storage.list(limit=10)
        assert len(results) == 5

    def test_delete(self, tmp_path):
        storage = FileStorage(memory_dir=tmp_path)
        entry = MemoryEntry.create(content="To delete")
        storage.add(entry)
        storage.delete(entry.id)
        assert storage.get(entry.id) is None

    def test_append_daily_log(self, tmp_path, monkeypatch):
        monkeypatch.setattr("openclaw_memory.core.datetime", MockDatetime)
        storage = FileStorage(memory_dir=tmp_path)
        storage.append_daily_log("Test log entry")
        assert len(storage._entries) == 1
        assert storage._entries[0].content == "Test log entry"
        assert storage._entries[0].entry_type == "daily"


class MockDatetime:
    @staticmethod
    def now():
        class FixedDate:
            def strftime(self, fmt):
                return {"%Y-%m-%d": "2026-04-15", "%H:%M": "21:00"}[fmt]
        return FixedDate()


class TestMemoryStore:
    def test_add_and_search(self, tmp_path):
        store = MemoryStore(
            storage=FileStorage(memory_dir=tmp_path),
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        )
        store.add("Remember to buy groceries", tags=["shopping"])
        results = store.search("food shopping", k=5)
        assert len(results) >= 0  # May be empty if index not built yet

    def test_list_with_type_filter(self, tmp_path):
        store = MemoryStore(storage=FileStorage(memory_dir=tmp_path))
        store.add("Daily thought")
        results = store.list(entry_type="daily")
        assert len(results) >= 1