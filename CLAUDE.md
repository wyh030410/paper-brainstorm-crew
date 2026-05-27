# CLAUDE.md

> **Hand-off document for Claude Code.**
> This file gives Claude Code everything it needs to understand, extend,
> debug, and improve this project. Read top-to-bottom before making changes.

---

## 1. Project Overview

**Name:** `paper_brainstorm_crew`

**Goal:** A multi-agent AutoGen-based "research group meeting" that helps a
CS Master's student develop and refine a research idea targeting **top-tier
CV / ML / robotics conferences** (CVPR, ICCV, NeurIPS, ICLR, ICML, CoRL).

**Why this exists:** Single-agent LLM chats are too sycophantic for paper
ideation — they don't push back, don't check literature critically, and
don't simulate the kind of adversarial review an actual submission faces.
This crew simulates a real lab meeting where ideas are challenged, refined,
and grounded in feasibility before being locked in.

**Domain context (important — the user's actual research area):**
- Vision-Language-Action (VLA) models for embodied AI
- Efficient deployment: quantization (QuantVLA), parameter-efficient
  fine-tuning (LoRA, QLoRA), inference scheduling (StreamingVLA)
- The user has read: QLoRA (Dettmers 2023), QuantVLA (Zhang 2026),
  StreamingVLA (Shi 2026), and is familiar with π0.5, OpenVLA, GR00T N1.5

---

## 2. Architecture

### 2.1 Framework

**AutoGen** (Microsoft) — chosen specifically over CrewAI because the user
wants real *brainstorming* (multi-turn agent-to-agent debate), not a fixed
pipeline. AutoGen's `GroupChat` lets agents speak in any order based on
context, which mirrors how real lab meetings work.

### 2.2 Agents (6 total)

| Agent              | Role                              | Key trait                            |
| ------------------ | --------------------------------- | ------------------------------------ |
| `researcher_you`   | The human user (HITL)             | Steers the discussion any time       |
| `senior_explorer`  | Proposes & iterates ideas         | Specific, bold, NOT a list-maker     |
| `literature_expert`| Novelty check against 2024-2026   | Cites real papers; refuses to fabricate |
| `harsh_critic`     | CVPR/NeurIPS reviewer simulator   | 1-2 sharp questions, not 10          |
| `practical_mentor` | Feasibility advisor               | Aware of 1x4090 + 4-6 month budget   |
| `venue_expert`     | Venue selection & framing         | Knows each venue's culture           |
| `manager`          | Meeting chair (group chat manager)| Controls flow, avoids dead-ends      |

### 2.3 Discussion Flow (designed, not hard-coded)

```
Explorer → LitExpert → Critic → Explorer (iterate)
                                    ↓
                            Critic + Mentor evaluate
                                    ↓
                            VenueExpert framing advice
                                    ↓
                            User checks in / steers
                                    ↓
                  (loop until "IDEA LOCKED" or pivot)
```

The `manager` agent orchestrates this softly via its system message;
agents are free to deviate based on context. `speaker_selection_method`
is `"auto"` so the LLM picks the next speaker.

---

## 3. File Layout

```
paper_brainstorm_crew/
├── brainstorm.py          # Main entry point — agents + group chat
├── requirements.txt       # Pinned deps
├── .env.example           # Template for API keys
├── .env                   # (you create this; gitignored)
├── README.md              # User-facing quick start
└── CLAUDE.md              # ← this file
```

---

## 4. How to Run (for the User)

```bash
# 1. Set up environment
python -m venv .venv
source .venv/bin/activate     # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure API keys
cp .env.example .env
# Edit .env and add ANTHROPIC_API_KEY

# 3. Run the brainstorm session
python brainstorm.py
```

The session is interactive. The user (you) will be prompted between
agent turns. Type your steering input, or press Enter to let the agents
continue. Type `exit` to end the session.

---

## 5. Configuration Knobs

All in `brainstorm.py`:

| Knob                              | Where               | Effect                                |
| --------------------------------- | ------------------- | ------------------------------------- |
| `config_list` model               | top of file         | Swap Claude ↔ GPT-4 ↔ local models    |
| `temperature` (default 0.7)       | `llm_config`        | Higher = more divergent ideas         |
| `max_round` (default 40)          | `GroupChat(...)`    | Hard cap on total turns               |
| `human_input_mode` (default ALWAYS) | `user = UserProxy…` | `NEVER` for fully autonomous runs    |
| `INITIAL_PROMPT`                  | bottom of file      | The opening message; edit to refocus  |

---

## 6. Extension Roadmap (TODO for Claude Code)

Listed in priority order. The user wants these added incrementally.

### 6.1 High priority — sharpen the brainstorm

1. **Real literature search tool** for `literature_expert`.
   - Currently `literature_expert` relies on the LLM's training knowledge,
     which can lead to fabricated citations.
   - Add a tool that hits arXiv API or Semantic Scholar API.
   - Use AutoGen's `register_for_llm` / `register_for_execution` pattern.
   - Cache results in a local JSON to avoid re-querying.

2. **PDF ingestion for the user's reference papers.**
   - User has PDFs of QLoRA, QuantVLA, StreamingVLA on disk.
   - Build a `docs/` folder, parse PDFs with `pypdf` or `pymupdf`.
   - Inject summarized content into `literature_expert`'s system message
     at startup so it has *direct* knowledge of these works.

3. **Session transcript export.**
   - At session end, write the full chat to `sessions/YYYYMMDD-HHMM.md`.
   - Include a final "Locked Idea" section if the user said "lock this".
   - Useful for the user to review and to feed back into next session.

### 6.2 Medium priority — better collaboration

4. **Add a `proposal_writer` agent.**
   - Triggered only when `senior_explorer` says "IDEA LOCKED".
   - Produces a 1-page CVPR-style proposal: Abstract, Problem, Method,
     Experiments, Expected Results, Risks.
   - Writes to `proposals/{idea_slug}.md`.

5. **Add a `related_work_drafter` agent.**
   - After IDEA LOCKED, drafts a Related Work paragraph for the paper.
   - Pulls from the literature_expert's citations during the session.

### 6.3 Low priority — quality of life

6. **Cost tracking.** Print estimated API spend per session.
7. **Multiple parallel brainstorms.** Run 3 sessions concurrently with
   different starting prompts, compare the locked ideas.
8. **Persistent memory across sessions** using a simple JSON file —
   so the explorer remembers what was tried last week.

---

## 7. Known Quirks / Gotchas

### 7.1 AutoGen API drift

AutoGen has split into multiple packages:
- `pyautogen` (the v0.2 stable line — what this project uses)
- `autogen-agentchat` + `autogen-core` (v0.4+ rewrite, different API)

**Do NOT upgrade past 0.2.x without rewriting agents.** The 0.4 API
replaces `AssistantAgent`/`GroupChat` with a message-passing model.
Pin in `requirements.txt`.

### 7.2 Anthropic API in AutoGen

AutoGen's Anthropic integration uses `api_type: "anthropic"`. If the
user hits "unsupported api_type" errors, they may need a newer
`pyautogen` version OR fall back to OpenAI for the LLM config.

Alternative model strings if Claude Opus 4.5 is unavailable:
  - `claude-sonnet-4-5`
  - `claude-opus-4-1`
  - `gpt-4o` (with `api_type: "openai"`)

### 7.3 Speaker selection sometimes loops

If two agents start ping-ponging, lower `max_round` or set
`allow_repeat_speaker=False` (already done). For pathological loops,
you can also use `speaker_selection_method="round_robin"` to force order.

### 7.4 Human input timeout

`UserProxyAgent` blocks waiting for stdin. If running in a notebook,
set `human_input_mode="TERMINATE"` and provide input via the notebook
cell. For CLI use (the default here), stdin is fine.

---

## 8. Design Decisions — *Why* This Setup

These are deliberate choices, not accidents. Please preserve them
unless the user asks otherwise.

1. **Only ONE Explorer.** Multiple explorers would just produce more
   ideas, not better ones. The bottleneck for paper ideation isn't
   *more ideas*, it's *refining one idea*.

2. **Critic is separate from Mentor.** Reviewer concerns ("is this
   novel?") and advisor concerns ("can you actually do this?") are
   different lenses. Conflating them produces wishy-washy feedback.

3. **VenueExpert is separate from Critic.** Framing is a distinct skill
   from technical evaluation. A great idea framed for the wrong venue
   gets rejected.

4. **No web-search tool by default.** Tempting to add, but it
   encourages the literature_expert to dump search results instead
   of synthesizing. Better to add focused arXiv API later (TODO 6.1).

5. **`temperature=0.7`** is the sweet spot we tested:
   - 0.3-0.5: ideas are too safe, just rehash known work
   - 0.7-0.9: ideas are bold but still grounded
   - >0.9: ideas drift into sci-fi, lose feasibility

6. **`max_round=40`** because a real brainstorm converges in 15-25
   meaningful turns. 40 leaves headroom for iteration without runaway.

---

## 9. Target Output

A successful session ends with a markdown block like this in the
transcript (Explorer emits this when "IDEA LOCKED" is reached):

```
## IDEA LOCKED: <one-sentence title>

**Pitch:** <one paragraph, what a reviewer reads first>

**Core technical contribution:**
  - <bullet 1>
  - <bullet 2>
  - <bullet 3>

**Why it's new:**
  - Closest prior work: <papers>
  - Specific gap we fill: <gap>

**Headline experiment:**
  - Dataset: <e.g., LIBERO Spatial + Object + Goal + Long>
  - Model: <e.g., π0.5-base, 7B>
  - Metric: <e.g., success rate, latency, memory>
  - Baseline to beat: <e.g., QuantVLA W4A8>

**Target venue:** <CVPR | CoRL | NeurIPS> — <one-line rationale>

**Timeline (4 months):**
  - Month 1: <…>
  - Month 2: <…>
  - Month 3: <…>
  - Month 4: <…>

**Top risks & mitigations:**
  - <risk>: <mitigation>
```

If a session ends without this block, the brainstorm did not converge.
That's OK — pivot the initial prompt and try again.

---

## 10. Style Guide for Future Edits

When Claude Code edits files in this repo:

1. **Preserve agent personalities.** System messages are tuned. Don't
   rewrite them wholesale; surgical edits only.
2. **Keep `brainstorm.py` as the single source of truth.** Resist
   splitting into many files until there's a real reason. A flat
   200-line script is easier to iterate on than a 6-file package.
3. **Comments in English, but feel free to add Chinese comments**
   inline near tricky logic — the user is bilingual (CN/EN) and
   appreciates 说人话 explanations.
4. **Pin dependencies.** Add to `requirements.txt` with `>=` minimums.
5. **No new top-level dependencies without listing them in section 6.**

---

## 11. Quick Reference — Common Tasks

**"Add a new agent."**
1. Define an `AssistantAgent` in `brainstorm.py` with a focused
   system message (under 200 words).
2. Add it to `GroupChat(agents=[...])`.
3. Mention it in the `manager`'s system message so the chair knows
   when to call on it.
4. Update section 2.2 of this file.

**"Make it run without human input."**
Set `human_input_mode="NEVER"` on the `user` agent. The session will
run to `max_round` or until agents naturally stop. Useful for
overnight runs.

**"Use a different LLM."**
Replace `config_list`:
```python
config_list = [{"model": "gpt-4o", "api_key": os.getenv("OPENAI_API_KEY"),
                "api_type": "openai"}]
```

**"Export the chat."**
After the session ends, the full message history is in
`groupchat.messages`. Add at the end of `brainstorm.py`:
```python
import json
from datetime import datetime
fname = f"sessions/{datetime.now():%Y%m%d-%H%M}.json"
os.makedirs("sessions", exist_ok=True)
with open(fname, "w") as f:
    json.dump(groupchat.messages, f, indent=2, ensure_ascii=False)
print(f"Saved to {fname}")
```

---

## 12. Contact / Context for Claude Code

The user is `wyh` — a CS Master's student at Stevens (NJ). They:
- Speak Chinese natively, English fluently
- Prefer 说人话 (plain language) explanations over jargon
- Are juggling coursework (CS 501, 570, 583, 556) + this research
- Want this tool to actually produce something they can submit
- Have access to limited compute and time, so feasibility matters
- Are likely to ask follow-up "how does X work?" questions, treat
  them as opportunities to teach, not just fix code

When in doubt: ask the user before refactoring. Don't silently
restructure the project.
