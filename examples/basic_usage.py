"""
Basic usage examples for OpenClaw Memory System.
"""

# Example 1: Simple add and search
from openclaw_memory import MemoryStore, MemoryEntry

store = MemoryStore()

# Add memories
entry1 = store.add(
    content="User prefers dark mode in all interfaces",
    tags=["preference", "ui", "dark-mode"],
    importance=0.8,
)
print(f"Added: {entry1.id}")

entry2 = store.add(
    content="Meeting scheduled for 2026-04-16 at 10:00 AM",
    tags=["calendar", "meeting"],
    importance=0.9,
)
print(f"Added: {entry2.id}")

# Search
results = store.search("display settings dark theme", k=5)
print(f"Search results: {results}")

# List all
all_entries = store.list(limit=10)
for e in all_entries:
    print(f"  {e.timestamp}: {e.content[:50]}")


# Example 2: Daily logs and long-term memory
store.append_daily_log("User asked about Frankfurt weather — it's sunny, 18°C")
store.update_longterm(
    content="User based in Frankfurt am Main, Germany. Timezone: Europe/Berlin.",
    section="Identity"
)

print("\nDaily logs:")
for e in store.get_daily_logs(days=2):
    print(f"  {e.timestamp}: {e.content}")

print("\nLong-term memory:")
for e in store.get_longterm_memory():
    print(f"  {e.content}")


# Example 3: Custom embedding model
from openclaw_memory import MemoryStore

custom_store = MemoryStore(embedding_model="sentence-transformers/all-mpnet-base-v2")
custom_store.add("Using a different embedding model for this store")
results = custom_store.search("embedding alternative model", k=5)
print(f"Custom model results: {results}")


# Example 4: CLI usage (run from shell)
# openclaw-memory add "Remember the Paris trip"
# openclaw-memory search "vacation"
# openclaw-memory list --limit 20 --type daily
# openclaw-memory stats