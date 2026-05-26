# AI Curriculum Builder

An autonomous, multi-agent orchestration system that transforms a user's target goals into fully realized, personalized educational pathways. Built on top of the **Google Agent Development Kit (ADK)** and powered by **Gemini 2.0**, this system automates the complete pipeline from initial intake assessment to highly detailed syllabus drafting, rigorous peer review, and structural lesson page generation.

---

## 💡 Why We Made It

Standard online courses and textbook syllabi suffer from a fundamental problem: they are built for the average student, assuming uniform prior knowledge and a single learning pace. When an individual wants to learn a niche modern skill (like implementing a custom SLAM pipeline or training behavioral reinforcement learning models), they are forced to piece together scattered resources themselves.

We built the **AI Curriculum Builder** to serve as an agentic tutor that does the heavy lifting of instructional design. By leveraging cooperative multi-agent dynamics, the system ensures that educational material is technically precise, pedagogically structured, and tailored to an individual’s exact learning archetype.

---

## 🏗️ Architecture & How It Works

The system abandons a single linear prompt pipeline in favor of a **hierarchical multi-agent graph**, implementing a specialized "divide-and-conquer" approach to handling large educational contexts.

```
                  ┌────────────────────────┐
                  │       Root Agent       │ (Router / Orchestrator)
                  └───────────┬────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Interviewer Agt │  │ Director/Writer │  │  Critic/Reviewer│
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              ▼
                ┌────────────────────────────┐
                │ Long-Term Memory Component │ (JSON Profiles & MD Assets)
                └────────────────────────────┘

```

### 1. Central Routing (`tt/agent.py`)

A master **Root Agent** serves as the system's central nervous system and coordinator. Instead of exposing individual specialized sub-agents to raw user state mutations, the Root Agent manages the active context, tracks progression milestones, and dynamically routes state to the appropriate specialized worker.

### 2. Specialized Multi-Agent Roles (`tt/prompts.py`)

* **The Interviewer:** Rather than working off static text inputs, this agent engages in an active intake interview. It systematically probes for technical comfort levels, discovers hidden gaps in prerequisite knowledge, and assesses whether the learner favors highly empirical/practical exercises over theoretical frameworks.
* **The Curriculum Director & Writer:** Takes the finalized profile context and architecturally scopes the educational pathway. It structures logical module dependencies, prevents scope creep, and drafts concrete, actionable lesson units.
* **The Critic / Reviewer:** Evaluates draft outputs against strict pedagogy benchmarks. It verifies module prerequisites, checks that complex technical definitions aren't skipped, and rejects or refines material before it reaches long-term persistence.

### 3. Data Integrity & Validation Layers (`tt/schemas.py`)

Multi-agent systems often break down due to unstructured text drift. To enforce deterministic, typed inputs and outputs between edge agent handoffs, the framework utilizes rigorous **Pydantic** validation models:

* `UserProfile`: Safely tracks assessed skill levels, objective scopes, and target user milestones.
* `SyllabusOutline`: Standardizes the structural nesting of learning units, goals, and content paths.
* `CurriculumBundle`: Validates the structural completeness of content blocks before compiling down to disk.

### 4. Long-Term Storage & State Persistence (`long_term_memory/`)

To prevent stateless reset loops during multi-day learning sessions, a decoupled file-system abstraction acts as the system's persistent memory bank. Generated learner profiles, real-time evaluation tokens, and written curricula are compiled down into human-readable Markdown and structured schema objects. This enables seamless resumption, delta-patching, and iterative progression tracking over long timelines.

---

## 🛠️ Tech Stack

* **Core Orchestration Framework:** [Google Agent Development Kit (ADK)](https://www.google.com/search?q=https://github.com/google-gemini/adk)
* **Foundation LLM:** Gemini 2.0 (via `google-genai`)
* **Data Validation & Type Engineering:** Pydantic
* **Asynchronous Processing:** `aiohttp` / `asyncio`

---

## 📂 Repository Layout

```text
├── tt/                        # Core Application Engine
│   ├── agent.py               # Orchestration graph, Router, & Agent initializations
│   ├── prompts.py             # System profiles, role matrices, & instructions
│   ├── schemas.py             # Pydantic state machine & data-transfer constraints
│   ├── tools.py               # Native capabilities (Search execution, file system drivers)
│   └── guardrails.py          # Intent sanitization, validation rules, & exit logic
├── long_term_memory/          # File-system database tracking profiles & markdown artifacts
├── requirements.txt           # Project runtime dependencies
└── .gitignore                 # Environment and environment safety exclusions

```

---

## 🚦 Quick Start

### 1. Prerequisites

Ensure you have Python 3.10+ installed and a valid Google Gemini API key exported into your active shell environment.

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/nochapman/AI-Curriculum-Builder.git
cd AI-Curriculum-Builder

# Install project dependencies
pip install -r requirements.txt

```

### 3. Execution

```bash
# Set your API environment variable
export GOOGLE_API_KEY="your-api-key-here"

# Initialize the Multi-Agent Environment
python tt/agent.py

```

---

Feel free to paste this right over your initial placeholder `README.md` file. Let me know if you want to dial up the detail on any particular file or feature!
