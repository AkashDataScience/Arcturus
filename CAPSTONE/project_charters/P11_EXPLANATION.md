# Project 11 "Mnemo" - Explained for Students

## 🎯 What is This Project About? (The Big Picture)

Imagine you have a personal assistant that remembers everything you've ever discussed with it. Right now, Arcturus can remember things, but it's like having a messy filing cabinet where:
- Files are stored in random folders (JSON files on your computer)
- Finding something requires digging through everything
- You can't easily see how different pieces of information connect
- It only works on one device

**Project 11 "Mnemo"** is about transforming this messy filing cabinet into a **smart, interconnected knowledge system** that:
- Works like Google's search (finds things instantly)
- Works like Wikipedia (shows how concepts connect)
- Works like Dropbox (syncs across all your devices)
- Works like a smart assistant (organizes things automatically)

---

## 📚 Current State: What Arcturus Has Right Now

Let me explain what's already built, as if we're looking at the current system:

### 1. **Episodic Memory System** (`core/episodic_memory.py`)
**What it does:**
- Saves every conversation/session as a "skeleton" (lightweight summary)
- Stores these as JSON files in `memory/session_summaries_index/`
- Each skeleton contains: what you asked, what tools were used, the outcome

**How it works:**
```python
# When you finish a task, it saves:
{
  "id": "session_123",
  "original_query": "How to bake a cake",
  "nodes": [
    {"agent": "CoderAgent", "task_goal": "Baking logic", "actions": [...]}
  ]
}
```

**Limitations:**
- ❌ Search is basic (probably just text matching)
- ❌ No way to see connections between different sessions
- ❌ Stored locally only (JSON files)
- ❌ Can't organize by topics/projects

### 2. **REMME Memory System** (`remme/store.py`)
**What it does:**
- Uses **FAISS** (Facebook AI Similarity Search) for vector-based memory
- Stores user preferences and facts learned from conversations
- Can search memories by similarity (semantic search)

**How it works:**
- Converts text into vectors (numbers representing meaning)
- Uses FAISS to find similar memories quickly
- Stores both the vector index and metadata in JSON

**Current Architecture:**
```
remme/
├── store.py          # FAISS vector store (local file-based)
├── extractor.py      # Extracts preferences from conversations
└── hubs/            # Structured preference storage
```

**Limitations:**
- ❌ FAISS is local-only (no cloud sync)
- ❌ No knowledge graph (can't see relationships)
- ❌ No spaces/collections (everything is in one big pile)
- ❌ Limited to single device

### 3. **RAG System** (`mcp_servers/server_rag.py`)
**What it does:**
- Uses FAISS for document search
- Combines keyword search (BM25) with vector search
- Indexes your local files and documents

**Note:** This is separate from the memory system but uses similar technology.

---

## 🔄 What Needs to Change: The Transformation

Think of this as upgrading from a **bicycle** to a **Tesla**. Same goal (getting around), but completely different capabilities.

### **Phase 1: Upgrade the Storage Engine** (Weeks 1-2)

**Current:** FAISS (local file, single device)
**New:** Qdrant or Weaviate (cloud-hosted, multi-device)

**Why?**
- FAISS is like a local hard drive - fast but only on one computer
- Qdrant/Weaviate is like Google Drive - accessible from anywhere, scales better

**What you'll build:**
- `memory/vector_store.py` - New adapter that talks to Qdrant/Weaviate
- Migrate existing FAISS data to the new system
- Keep the same API so existing code doesn't break

**Student Task:** This is like replacing the engine in a car - everything else stays the same, but now it's more powerful.

---

### **Phase 2: Add Knowledge Graph** (Weeks 3-5)

**Current:** Memories are isolated - like index cards in a box
**New:** Memories are connected - like Wikipedia with hyperlinks

**What is a Knowledge Graph?**
Imagine you tell Arcturus:
- "I work at Google"
- "Google is in Mountain View"
- "I live in San Francisco"

**Current system:** Stores these as 3 separate memories
**New system:** Creates connections:
```
[You] --works_at--> [Google] --located_in--> [Mountain View]
[You] --lives_in--> [San Francisco]
```

**What you'll build:**
- `memory/knowledge_graph.py` - Extracts entities (people, places, concepts) and relationships
- Uses Neo4j or NetworkX to store the graph
- Agent can query: "What do I know about Google and how does it relate to me?"

**Example Query:**
```python
# Agent asks: "What companies have I mentioned?"
graph.query("MATCH (p:Person {name: 'user'})-[:works_at]->(c:Company) RETURN c")
# Returns: [Google, Microsoft, ...]
```

**Student Task:** This is like adding a "See Also" section to every Wikipedia article - now information is interconnected.

---

### **Phase 3: Spaces & Collections** (Weeks 6-7)

**Current:** All memories in one big pile
**New:** Organized into "Spaces" (like folders, but smarter)

**What are Spaces?**
Think of them as dedicated knowledge areas:
- **"Startup Research"** - All memories about your startup project
- **"Home Renovation"** - All memories about renovating your house
- **"Work Projects"** - All memories about work

**Features:**
- **Personal Spaces:** Only you can see
- **Shared Spaces:** Team members can contribute (like Google Docs)
- **Auto-organization:** Agent suggests which space new info belongs to
- **Templates:** Pre-made spaces for common use cases

**What you'll build:**
- `memory/spaces.py` - Manages spaces and collections
- Frontend UI to create/manage spaces
- Auto-categorization logic

**Student Task:** This is like organizing your messy desk into labeled drawers - same stuff, but now you can find things faster.

---

### **Phase 4: Cross-Device Sync** (Weeks 8-10)

**Current:** Memories only on one device
**New:** Memories sync across all devices (phone, laptop, tablet)

**How it works:**
- Uses **CRDTs** (Conflict-free Replicated Data Types)
- Think of it like Google Docs - multiple people can edit simultaneously without conflicts
- Works offline, syncs when connected

**What you'll build:**
- `memory/sync.py` - CRDT-based synchronization
- Handles conflicts gracefully
- Selective sync (some spaces can be local-only for privacy)

**Student Task:** This is like making your notebook available on all your devices - edit on phone, see on laptop.

---

### **Phase 5: Smart Memory Management** (Ongoing)

**Current:** All memories treated equally
**New:** Memories have "importance scores" and lifecycle

**Features:**
- **Importance Scoring:** Frequently accessed memories get promoted
- **Decay & Archival:** Old, unused memories get archived (still searchable, but not in active results)
- **Contradiction Resolution:** If you say "I like pizza" then "I hate pizza", system flags both and asks you to clarify
- **Privacy Controls:** Mark memories as private/shareable/public

**What you'll build:**
- `memory/lifecycle.py` - Importance scoring, decay, archival logic
- UI to manage memory privacy

**Student Task:** This is like having a smart filing system that automatically moves important files to the front and archives old ones.

---

## 🎓 Technical Breakdown: What Each Component Does

### **1. Vector Store (`memory/vector_store.py`)**

**Purpose:** Store and search memories using vector similarity

**Key Functions:**
```python
class VectorStore:
    def add(memory_text, embedding, metadata)
    def search(query, k=10)  # Returns top-k similar memories
    def update(memory_id, new_text, new_embedding)
    def delete(memory_id)
```

**Migration Path:**
1. Read all existing FAISS memories
2. Convert to Qdrant/Weaviate format
3. Keep backward compatibility layer

---

### **2. Knowledge Graph (`memory/knowledge_graph.py`)**

**Purpose:** Extract and connect entities from conversations

**Key Functions:**
```python
class KnowledgeGraph:
    def extract_entities(text)  # Returns: [Person, Company, Date, ...]
    def add_relationship(entity1, relation, entity2)
    def query(pattern)  # GraphQL or Cypher queries
    def visualize()  # For frontend display
```

**Example:**
```python
# From conversation: "I met John at Google last week"
entities = extract_entities(text)
# Returns: [Person("John"), Company("Google"), Date("last week")]

add_relationship("user", "met", "John")
add_relationship("John", "works_at", "Google")
```

---

### **3. Spaces Manager (`memory/spaces.py`)**

**Purpose:** Organize memories into collections

**Key Functions:**
```python
class SpacesManager:
    def create_space(name, type="personal")
    def add_to_space(memory_id, space_id)
    def suggest_space(memory_text)  # AI suggests which space
    def search_in_space(query, space_id)
```

---

### **4. Sync Engine (`memory/sync.py`)**

**Purpose:** Sync memories across devices

**Key Functions:**
```python
class SyncEngine:
    def sync_to_cloud(space_id)
    def sync_from_cloud(device_id)
    def resolve_conflict(local, remote)  # CRDT merge
    def get_sync_status()
```

---

### **5. Lifecycle Manager (`memory/lifecycle.py`)**

**Purpose:** Manage memory importance and archival

**Key Functions:**
```python
class LifecycleManager:
    def score_importance(memory_id)  # Based on access frequency
    def archive_low_importance()
    def detect_contradiction(new_memory, existing_memories)
    def set_privacy(memory_id, level="private")
```

---

## 📋 Implementation Checklist

### **Week 1-2: Foundation**
- [ ] Set up Qdrant/Weaviate instance (local or cloud)
- [ ] Create `memory/vector_store.py` with basic CRUD
- [ ] Migrate existing FAISS data
- [ ] Write tests for vector operations
- [ ] Ensure backward compatibility with `episodic_memory.py`

### **Week 3-5: Knowledge Graph**
- [ ] Set up Neo4j or NetworkX
- [ ] Implement entity extraction (using LLM or NER)
- [ ] Build relationship extraction
- [ ] Create graph query interface
- [ ] Add visualization endpoint for frontend

### **Week 6-7: Spaces**
- [ ] Design space schema
- [ ] Implement space CRUD operations
- [ ] Build auto-categorization logic
- [ ] Create frontend UI for spaces
- [ ] Add space templates

### **Week 8-10: Sync**
- [ ] Research and implement CRDT library
- [ ] Build sync protocol
- [ ] Handle offline scenarios
- [ ] Add conflict resolution
- [ ] Test multi-device scenarios

### **Week 11+: Lifecycle**
- [ ] Implement importance scoring algorithm
- [ ] Build archival system
- [ ] Add contradiction detection
- [ ] Create privacy controls
- [ ] Add UI for memory management

---

## 🧪 Testing Requirements

The project charter specifies **mandatory test gates**:

### **Acceptance Tests** (`tests/acceptance/p11_mnemo/test_memory_influences_planner_output.py`)
Must have at least 8 test cases covering:
- ✅ Happy-path: Memory retrieval works end-to-end
- ✅ Invalid input handling
- ✅ Memory ingestion
- ✅ Retrieval ranking
- ✅ Contradiction handling
- ✅ Lifecycle archival

### **Integration Tests** (`tests/integration/test_mnemo_oracle_cross_project_retrieval.py`)
Must have at least 5 scenarios covering:
- ✅ Memory affects Planner behavior BEFORE plan generation
- ✅ Cross-project retrieval (finding memories from other projects)
- ✅ Failure propagation (graceful degradation)

### **CI Requirements**
- All acceptance tests pass
- All integration tests pass
- Baseline regression suite passes
- Lint/typecheck passes
- **Performance:** < 250ms for top-k retrieval

---

## 🎯 Key Success Metrics

1. **Performance:** < 250ms retrieval latency (P95)
2. **Backward Compatibility:** Existing `episodic_memory.py` code still works
3. **Test Coverage:** All mandatory tests pass
4. **User Experience:** Can create spaces, see knowledge graph, sync across devices

---

## 🤔 Common Questions

**Q: Why not just improve FAISS?**
A: FAISS is great for local use, but doesn't support multi-tenancy, cloud sync, or advanced features like hybrid search out of the box.

**Q: Do we need to rewrite everything?**
A: No! We maintain backward compatibility. Existing code using `episodic_memory.py` will continue to work.

**Q: What if Qdrant/Weaviate is down?**
A: The system should gracefully degrade - fall back to local storage or cached results.

**Q: How do we handle privacy?**
A: Per-memory privacy levels, and some spaces can be marked as local-only (never synced).

---

## 📖 Learning Resources

- **Vector Databases:** [Qdrant Docs](https://qdrant.tech/documentation/), [Weaviate Docs](https://weaviate.io/developers/weaviate)
- **Knowledge Graphs:** [Neo4j Tutorial](https://neo4j.com/developer/get-started/), [NetworkX Guide](https://networkx.org/documentation/stable/tutorial.html)
- **CRDTs:** [CRDT Explained](https://crdt.tech/)
- **FAISS Migration:** [FAISS to Qdrant Migration Guide](https://qdrant.tech/articles/migrate-from-faiss/)

---

## 🚀 Getting Started

1. **Read the project charter** (`P11_mnemo_real_time_memory_knowledge_graph.md`)
2. **Understand current system** - Review `core/episodic_memory.py` and `remme/store.py`
3. **Set up development environment** - Install Qdrant/Weaviate locally
4. **Start with Phase 1** - Build the vector store adapter
5. **Write tests first** - Follow TDD approach
6. **Iterate** - Build incrementally, test frequently

---

**Remember:** This is a big project, but it's broken down into manageable phases. Focus on one phase at a time, and don't try to build everything at once. Good luck! 🎓

