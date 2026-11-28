# HaijunBot vs OpenViking: Mechanism Comparison Analysis Report

## Document Information

- **Analysis date**: 2026-09-29
- **Analysis Goals**: Compare the design and trade-offs of HaijunBot and OpenViking in the Mechanisms related to "context / memory / knowledge reuse"
- **Analysis scope**: Focus on the similarities and differences between the two at the Mechanism level, including **context organization, memory storage and retrieval, knowledge/track reuse, session distillation, and shared collaboration**
- **Reference materials**:
  - HaijunBot: source code (`src/haijunbot/haijunbot_memory_organizer/`, `src/haijunbot/haijunbot_agent/memory_manager.py`, `src/haijunbot/haijunbot_tools/memory.py`, `src/haijunbot/haijunbot_tools/methodology.py`, `src/haijunbot/haijunbot_agent/rules_manager.py`, `src/haijunbot/haijunbot_rules_index/core.py`) and the actual Data directory at `~/.haijunbot/`
  - OpenViking: official docs (docs.openviking.ai / docs.openviking.net), GitHub repository `volcengine/OpenViking`

> Note: All Conclusions on the HaijunBot side are based on the **current source code**, and do not rely on possibly outdated Description documents.

---

## Executive Abstract

### One-Sentence Summary

- **HaijunBot**: a **collaborative AI development platform** for developers, whose "context/memory" Mechanisms are **a set of capabilities inside the platform** (memory + rules + Methodology + tracks), emphasizing **lightweight, local, vector-free, and on-demand loading**.
- **OpenViking**: a **general-purpose context Database (Context Database)** for AI Agents, which abstracts context into **independent storage infrastructure**, emphasizing **a virtual file system, semantic retrieval, and progressive loading**.

### Core Conclusions

1. **Different positioning**: HaijunBot's Mechanisms are "platform built-in capabilities" that serve its own development workflow; OpenViking is an "independent Data layer that any Agent can connect to", serving all Agent applications.
2. **Different organization paradigm**: HaijunBot adopts **layering + classification** (memory layering / rules / Methodology / tracks each independent); OpenViking adopts a **unified virtual file system** (Resource/Memory/Track uniformly addressed under `viking://`).
3. **Different retrieval approach**: HaijunBot uses **vector-free lightweight retrieval** (tags + BM25 + time/frequency weighting); OpenViking uses **vector semantic retrieval + directory awareness + Rerank**.
4. **Similar loading strategy**: both emphasize "**look at the Abstract first, then read the full content**" to save tokens — HaijunBot implements it through on-demand rule loading and memory-tag hints, while OpenViking implements it through the L0/L1/L2 three layers.
5. **Different sharing Mechanism emphases**: HaijunBot uses a **central Git repository** to share rules/Methodology; OpenViking uses **a server + multi-tenancy + ACL** to share context.

### High-Level Overview Comparison Table

| Dimension | HaijunBot | OpenViking |
| --- | --- | --- |
| Project role | Collaborative AI development platform | AI Agent context Database |
| Context Mechanism positioning | Platform built-in capabilities (memory/rules/Methodology/tracks) | Independent storage infrastructure (connectable by any Agent) |
| Organization Model | Layering + classification, each independent | Unified `viking://` virtual file system |
| Storage form | Local JSON / Markdown files | Server-side AGFS + vector index |
| Retrieval method | Tag + BM25 weighting, **vector-free** | Vector semantic retrieval + directory awareness + Rerank |
| Content loading | On-demand rule loading, memory-tag hints | L0/L1/L2 progressive loading |
| Memory types | 3 types (short-term / project long-term / global long-term) | 9+ built-in memory types |
| Sharing method | Central Git repository | Server multi-tenancy + ACL |
| Tech stack | Python 3.12 (primary) | Python / Rust / TypeScript |
| Deployment form | Local CLI / Web / SDK | Standalone server + SDK / HTTP API |

---

## 1. Positioning and Form Comparison

### 1.1 Project Positioning

| Dimension | HaijunBot | OpenViking |
| --- | --- | --- |
| **Positioning** | A collaborative AI development platform covering "human × Agent" four-quadrant collaboration | A Database providing unified context management for AI Agents |
| **Core Scenarios** | Code development, review, Validation, Security analysis, C→Rust migration | Agent cross-session memory, knowledge RAG, track management |
| **Form** | CLI + Web + Python SDK | Standalone server (`openviking-server`) + CLI (`ov`) + SDK |
| **License** | MIT | AGPL-3.0 (primary) / Apache-2.0 (some Components) |

### 1.2 Mechanism Positioning Differences

- **HaijunBot**: context Mechanisms are **part of the platform's own capabilities**. Although memory, rules, Methodology, and tracks have complete Mechanisms, they are all **bound within the HaijunBot platform**, driven through tools (`memory`, `methodology`, `load_rule`) and event hooks.
- **OpenViking**: context Mechanisms are **abstracted into independent infrastructure**. It does not produce content itself, but provides **any Agent** (Haijun, Codex, Cursor, LangChain, etc.) with a unified "read/write context" capability, accessed through MCP / SDK / HTTP APIs.

> **One-sentence takeaway**: HaijunBot's Mechanisms are "**for self-use**", while OpenViking's Mechanisms are "**general-purpose**".

---

## 2. Context Organization Model Comparison

### 2.1 HaijunBot: Layering + Classification, Each Independent

HaijunBot's "context" consists of several **mutually independent** subsystems, each with its own storage directories and tools:

| Subsystem | Storage location | Organization | Corresponding tool |
| --- | --- | --- | --- |
| **Memory** | `.haijunbot/memory/` (project), `~/.haijunbot/memory/` (global) | Layered by type, one JSON file per memory | `memory` |
| **Rules** | `builtin/rules/`, `.haijunbot/rules/`, `~/.haijunbot/rules/`, central library | Organized by source directory, Markdown + YAML front matter | `load_rule`, `auto_select_rule` |
| **Methodology** | `~/.haijunbot/methodologies/`, `.haijunbot/methodologies/` | By problem type, MD5-named JSON files | `methodology` |
| **Tracks** | `~/.haijunbot/rules/tracks/` | Reuses the rule system's extensions | Through rules/input processors |

### 2.2 OpenViking: Unified Virtual File System

OpenViking **unifies** the three types of context under the `viking://` virtual file system, addressed with the **same URI scheme**:

```
viking://
├── resources/              # Resources: project documents, code repositories, web pages, etc.
│   └── my_project/
│       ├── docs/
│       └── src/
└── user/{user_id}/
    ├── memories/           # Memories: preferences, entities, events, experiences, etc.
    │   └── preferences/
    ├── resources/          # User-private resources
    ├── tracks/             # Tracks
    └── peers/{peer_id}/    # Peer-level context
```

| Context type | Purpose | Lifecycle | Initiator |
| --- | --- | --- | --- |
| **Resource** | Knowledge and rules (documents, code repositories) | Long-term, relatively static | Added by the user |
| **Memory** | The Agent's cognition (preferences, entities, events, experiences) | Long-term, dynamically updated | Recorded by the Agent |
| **Track** | Declarable, invocable capability Configuration | Long-term, static | Added by the user or system |

### 2.3 Key Differences

| Comparison point | HaijunBot | OpenViking |
| --- | --- | --- |
| Organization paradigm | Layering + classification, subsystems independent | Unified file system, three context types addressed uniformly |
| Addressing | File paths + tool Parameters | Unified `viking://` URI |
| Browsability | Must view each directory separately | Can `ls` / `tree` / `grep` like a file system |
| Extensibility | New subsystems require new directories and tools | New types just add directories; addressing stays the same |

---

## 3. Memory Mechanism Comparison (Focus)

### 3.1 Storage Structure

**HaijunBot**: memories are **one JSON file each**, with a fixed field structure:

```json
{
  "id": "20260914_165026_146930",
  "type": "project_long_term",
  "tags": ["CPU limit", "cgroup", "systemd", "user resource limit"],
  "content": "User CPU limit plan for the server (16 cores, Ubuntu 20.04, cgroup v1):...",
  "created_at": "2026-09-14T16:50:26.146957",
  "updated_at": "2026-09-14T16:50:26.146961"
}
```

- Layering: `short_term` (in memory), `project_long_term` (`.haijunbot/memory/`), `global_long_term` (`~/.haijunbot/memory/global_long_term/`)
- Organization: **tags** are the core indexing dimension

**OpenViking**: memories are **Markdown files** organized into directories by **semantic type**:

| Built-in memory type | Default location | Description |
| --- | --- | --- |
| profile | `~/memories/profile.md` | User basic information |
| preferences | `~/memories/preferences/` | User preferences organized by topic |
| entities | `~/memories/entities/` | Knowledge about entities such as people, projects, and organizations |
| events | `~/memories/events/` | Records of events such as decisions and milestones |
| identity | `~/memories/identity.md` | Assistant name, persona, and tone |
| soul | `~/memories/soul.md` | Assistant principles, boundaries, and style |
| cases | `~/memories/cases/` | Task cases |
| trajectories | `~/memories/trajectories/` | Reusable task execution trajectories |
| experiences | `~/memories/experiences/` | Reusable experiences distilled from execution results |

### 3.2 Memory Writing

| Comparison point | HaijunBot | OpenViking |
| --- | --- | --- |
| Trigger | Event hooks (`TASK_STARTED`/`TASK_COMPLETED`/`BEFORE_HISTORY_CLEAR`) + the LLM's autonomous judgment | **Asynchronous** extraction after session submission (`session.commit()`) |
| Writer | The LLM proactively saves by calling the `memory` tool | The system automatically extracts according to memory policies |
| Classification granularity | 3 types (short-term/project long-term/global long-term) | 9+ semantic types |
| Deduplication/organization | `MemoryOrganizer` merges by **tag overlap** | LLM-driven deduplication (Compressor) |

### 3.3 Memory Retrieval

**HaijunBot**: `smart_search` uses **vector-free weighted scoring** (verified in the `smart_retrieval.py` source):

```
Total score = content similarity (BM25) × 0.4
     + tag match × 0.3
     + time freshness × 0.15
     + usage frequency × 0.15
```

- Tokenization: `jieba` (Chinese word segmentation)
- Similarity: **BM25** (non-vector)
- Candidates: first filtered by expanded tags, then scored and ranked
- Note: the `~/.haijunbot/embeddings/` directory is empty, **confirming that HaijunBot memory retrieval does not depend on vector embeddings**

**OpenViking**: uses **vector semantic retrieval + directory awareness**:

```
Query → intent analysis → layered retrieval (directory-level recursion) → Rerank → result
```

- Retrieval methods: `find` (no session context) / `search` (with session context)
- Core: **directory-scoped retrieval** (can be limited to a project/memory subtree rather than scanning the entire vector pool)
- Fine ranking: scalar filtering + Model Rerank

### 3.4 Key Differences

| Comparison point | HaijunBot | OpenViking |
| --- | --- | --- |
| Retrieval basis | Tags + BM25 (**lexical**) | Vectors (**semantic**) |
| Retrieval scope | Filtered by type/tag | Directory scope + whole library |
| Fine ranking | Weighted scoring | Model Rerank |
| Dependencies | No external Model/index | Requires an embedding Model + vector index |
| Strengths | Lightweight, offline, zero dependencies | Strong semantic understanding, good cross-language/synonym recall |
| Costs | Weak semantic generalization (depends on tag quality) | Must maintain a vector index and Model service |

---

## 4. Progressive Loading / Token Optimization Comparison

Both emphasize "**look at the Abstract first, then read the full content**", but differ in Implementation Path:

| Comparison point | HaijunBot | OpenViking |
| --- | --- | --- |
| Core mechanism | On-demand rule loading (`load_rule`/`auto_select_rule`), memory-tag hints | L0/L1/L2 three-layer progressive loading |
| Abstract generation | Rules carry a YAML `description` | Directories automatically generate `.abstract.md` (L0) / `.overview.md` (L1) |
| Loading granularity | Rule-level (whole rule), memory-level (whole memory) | Directory-level + file-level |
| Token control | Rule body length limits (`_limit_rule_body`), memory count caps | L0 about 256 characters, L1 about 4000 characters, L2 on demand |

**OpenViking's three-layer Model**:

| Layer | Content | Default limit |
| --- | --- | --- |
| L0 | One-sentence Abstract for quick relevance judgment | 256 characters |
| L1 | Overview for navigation | 4000 characters |
| L2 | Full original text, read on demand | No unified limit |

> **Shared point**: both recognize that "stuffing everything into the context" is unsustainable, and both adopt a "**metadata first, expand on demand**" strategy.
> **Difference**: HaijunBot's Abstracts depend on **manual/rule writing**, while OpenViking's Abstracts are **automatically generated by the system** (during the semantic processing Phase).

---

## 5. Knowledge and Track Reuse Comparison

### 5.1 HaijunBot: Rule System + Methodology + Tracks

- **Rule system**: Markdown + YAML front matter, supports multiple sources (built-in/project/global/central library/Configuration directory), supports Jinja2 template rendering, and loads **on demand**. The rule system is a "**meta-Mechanism**" that Scales out to capabilities such as track and spec.
- **Methodology**: codifies "solutions that successfully solved problems" into a reusable library, indexed by **problem type** (MD5-named), supports project-level/global-level, and can be shared through a **central Git repository**.
- **Tracks**: extended through the rule system, with support for installing from a Git repository or a local path.

### 5.2 OpenViking: Track as a First-Class Context

- **Track** is one of the three context types, **on equal footing** with Resource and Memory, all addressed uniformly with `viking://`.
- Standardized storage structure: `TRACK.md` (definition) + `.abstract.md`/`.overview.md` (Abstract) + `scripts` (implementation).
- Scope: user-private (`viking://~/tracks/`) or globally shared (`viking://agent/tracks/`).
- Extension direction: Track belongs to `AgentDefinedContextType`, and the same class also plans subtypes such as Endpoint / Tool / Payment.

### 5.3 Key Differences

| Comparison point | HaijunBot | OpenViking |
| --- | --- | --- |
| Knowledge reuse vehicle | Rules + Methodology (two independent systems) | Resource + Track (unified context) |
| Track status | An extension of the rule system | A first-class context type |
| Sharing method | Central Git repository | Server multi-tenancy + scoped URI |
| Metadata | YAML front matter (manually written) | Automatically generated L0/L1 Abstracts |

---

## 6. Session Distillation and Memory Extraction Comparison

| Comparison point | HaijunBot | OpenViking |
| --- | --- | --- |
| Session carrier | Dialog history (`~/.haijunbot/history`, `dialogues`) | Session (managed server-side) |
| Distillation trigger | Event hooks on task start/completion/history clearing | Explicit `session.commit()` submission |
| Extraction method | The LLM judges, then calls the `memory` tool | Background tasks extract asynchronously (status can be polled) |
| Extraction output | JSON memory entries | Markdown memory files (organized by type into directories) |
| Observability | Memory files can be viewed directly | Memory files can be viewed/edited directly, and `ov compile` can organize them into a wiki/knowledge graph |

> **Shared point**: both support converting "sessions" into "reusable long-term memory", and the output is **human-readable files**.
> **Difference**: HaijunBot is **event-driven + Model-autonomous**, while OpenViking is **explicit submission + asynchronous pipeline**.

---

## 7. Sharing and Collaboration Mechanism Comparison

| Comparison point | HaijunBot | OpenViking |
| --- | --- | --- |
| Sharing unit | Rules, Methodology | All context (Resource/Memory/Track) |
| Sharing method | Central Git repository (`central_rules_repo`, etc.) | Server multi-tenancy + scoped URI |
| Permission Model | Multi-user authentication (JWT) + group permissions + ACL | Account/user isolation + optional resource ACL |
| Isolation dimension | Project-level / global-level | User-level / Peer-level / Agent-level |
| Conflict handling | The central repository has the highest priority | Uniformly managed by the server |

> **Fundamental Difference**: HaijunBot's sharing is a decentralized "**files + Git**" model; OpenViking's sharing is a centralized "**server + Database**" model.

---

## 8. Tech Stack and Deployment Comparison

| Comparison point | HaijunBot | OpenViking |
| --- | --- | --- |
| Main language | Python 3.12 | Python 74.8% / Rust 12.4% / TypeScript 8.7% |
| Runtime form | Local CLI / Web / SDK | Standalone server + SDK / HTTP API |
| Data storage | Local files (JSON/Markdown) | AGFS (content) + vector index |
| External dependencies | No vector dependencies, LLM optional | Requires an embedding Model + VLM |
| Deployment complexity | Low (runs locally) | Medium (requires Deploying a server and Models) |
| Offline capability | Strong (local files suffice) | Requires a local Model or network access |

---

## 9. Comprehensive Comparison and Complementarity Analysis

### 9.1 Mechanism Comparison Summary Table

| Mechanism dimension | HaijunBot | OpenViking | Relationship |
| --- | --- | --- | --- |
| Context organization | Layering + classification, each independent | Unified virtual file system | Complementary |
| Memory storage | JSON files, tag-indexed | Markdown files, organized by type | Similar (both file-based) |
| Memory retrieval | Tags + BM25, vector-free | Vectors + directory awareness + Rerank | Complementary |
| Progressive loading | On-demand rule loading | L0/L1/L2 three layers | Similar |
| Knowledge reuse | Rules + Methodology | Resource + Track | Complementary |
| Session distillation | Event-driven + Model-autonomous | Explicit submission + async extraction | Similar |
| Sharing/collaboration | Central Git repository | Server multi-tenancy + ACL | Complementary |
| Deployment form | Lightweight local | Server + Model | Complementary |

### 9.2 Each Side's Advantages and Boundaries

**HaijunBot's Advantages**:
- Lightweight, local, zero vector dependencies, usable offline
- Deeply bound to the development workflow (rules/Methodology directly serve coding tasks)
- Memory/rule/Methodology outputs are all human-readable files, transparent and controllable

**HaijunBot's Boundaries**:
- Retrieval is primarily lexical (BM25), with limited semantic generalization and strong dependence on tag quality
- Context Mechanisms are for platform self-use, hard for external Agents to reuse directly
- Sharing depends on Git, lacking server-level permissions and multi-tenancy

**OpenViking's Advantages**:
- Strong semantic retrieval with good cross-language/synonym recall
- Unified file system + directory-aware retrieval, integrating organization and retrieval
- Server-based, naturally supporting multi-tenancy, ACL, and cross-language access

**OpenViking's Boundaries**:
- Requires Deploying a server and embedding/VLM Models, with heavier dependencies
- It is a general-purpose Data layer and does not directly provide development workflow capabilities
- The primary license is AGPL-3.0; commercial use requires attention to licensing

### 9.3 Complementarity and Takeaways

1. **Complementary retrieval capabilities**: if HaijunBot introduces vector retrieval (or integrates with OpenViking-like services), it can improve the semantic recall of memory/Methodology.
2. **Progressive loading is worth borrowing**: OpenViking's L0/L1/L2 automatic Abstract Mechanism can auto-generate Abstracts for HaijunBot's memories/rules, reducing manual maintenance costs.
3. **Unified addressing is worth borrowing**: OpenViking's unified `viking://` URI can provide a unified addressing paradigm for HaijunBot's scattered subsystems.
4. **Complementary sharing Mechanisms**: HaijunBot's central Git repository suits offline/decentralized Scenarios, while OpenViking's server model suits online team collaboration.
5. **Different positioning, not substitutes**: HaijunBot is a "development platform" and OpenViking is "context infrastructure"; the two can work together at different levels.

---

## 10. Conclusion

1. **They are not at the same level**: HaijunBot's context Mechanisms are **platform built-in capabilities**, while OpenViking is **general-purpose context infrastructure**, an "application" vs. "foundation" relationship.
2. **Very different organization paradigms**: HaijunBot uses "layering + classification", while OpenViking uses a "unified virtual file system".
3. **Divergent retrieval paths**: HaijunBot follows a **lightweight, vector-free lexical path**, while OpenViking follows a **vector-semantic + directory-aware path**, each with its own trade-offs.
4. **Shared loading philosophy**: both emphasize "Abstract first, expand on demand", a common choice for coping with context bloat.
5. **Complementarity outweighs competition**: in areas such as retrieval enhancement, automatic Abstracts, unified addressing, and shared collaboration, HaijunBot can draw on OpenViking's design.

---

## Appendix: Information Sources

### HaijunBot (verified from source code)

| Mechanism | Key source/Data location |
| --- | --- |
| Memory tool | `src/haijunbot/haijunbot_tools/memory.py` |
| Memory management | `src/haijunbot/haijunbot_agent/memory_manager.py` |
| Memory organization | `src/haijunbot/haijunbot_memory_organizer/memory_organizer.py` |
| Smart retrieval | `src/haijunbot/haijunbot_memory_organizer/smart_retrieval.py` |
| Methodology tool | `src/haijunbot/haijunbot_tools/methodology.py` |
| Rule management | `src/haijunbot/haijunbot_agent/rules_manager.py` |
| Rule index | `src/haijunbot/haijunbot_rules_index/core.py` |
| Memory Data | `~/.haijunbot/memory/global_long_term/*.json` |
| Methodology Data | `~/.haijunbot/methodologies/*.json` |

### OpenViking (official materials)

- Website: <https://www.openviking.ai/>
- Docs: <https://docs.openviking.ai/>
- GitHub: <https://github.com/volcengine/OpenViking>
- Architecture docs: Architecture Overview / Context Types / Context Layers / Sessions

---

*This report is compiled from the source code and official documents as of 2026-09-29; Conclusions on the HaijunBot side are based on the current source code.*
