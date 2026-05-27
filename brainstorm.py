"""
Paper Brainstorm Crew — AutoGen Demo
====================================

A multi-agent research group meeting that helps you develop and refine
a research idea targeting top-tier CV / robotics venues
(CVPR, ICCV, NeurIPS, CoRL, ICML, ICLR).

Agents:
  - Explorer:     Proposes ideas, iterates based on feedback
  - LitExpert:    Checks novelty against recent literature (2024-2026)
  - Critic:       Top-tier reviewer who challenges every idea
  - Mentor:       Practical feasibility advisor for grad students
  - VenueExpert:  Helps shape the idea for a specific venue
  - User (You):   Human-in-the-loop, can steer the discussion anytime

Usage:
  1. pip install -r requirements.txt
  2. cp .env.example .env  &&  fill in your API keys
  3. python brainstorm.py
"""

import os
import json
import hashlib
import glob
import urllib.request
import urllib.parse
from typing import Annotated
from dotenv import load_dotenv
import autogen

load_dotenv()


# ============================================================
# PDF Paper Ingestion (AI-summarized)
# ============================================================
# Reads PDFs from docs/, uses Claude to summarize each paper's
# key points, and caches summaries in docs/.summaries.json.
# The condensed summaries are injected into literature_expert's
# system message — much more token-efficient than raw text.

DOCS_DIR = os.path.join(os.path.dirname(__file__), "docs")
SUMMARY_CACHE = os.path.join(DOCS_DIR, ".summaries.json") if os.path.isdir(
    os.path.join(os.path.dirname(__file__), "docs")
) else ""


def _load_summary_cache() -> dict:
    if SUMMARY_CACHE and os.path.exists(SUMMARY_CACHE):
        with open(SUMMARY_CACHE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_summary_cache(cache: dict):
    if SUMMARY_CACHE:
        with open(SUMMARY_CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)


def _summarize_with_llm(paper_text: str, filename: str) -> str:
    """调用 Claude API 生成论文结构化摘要。"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return f"[No API key — raw excerpt]\n{paper_text[:2000]}"

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-5-20250514",  # 用 sonnet 总结，省钱
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": f"""Summarize this academic paper in a structured format.
Be concise but cover ALL key technical details. Output in English.

Format:
**Title:** ...
**Authors:** ...
**Problem:** What problem does this paper solve? (1-2 sentences)
**Method:** Core technical approach (3-5 bullets)
**Key Results:** Main experimental findings (2-3 bullets)
**Limitations/Gaps:** What this paper does NOT solve (1-2 bullets)

Paper text from {filename}:
{paper_text[:12000]}"""
            }]
        )
        return response.content[0].text
    except Exception as e:
        print(f"[WARNING] LLM summary failed for {filename}: {e}")
        return f"[Summary failed — raw excerpt]\n{paper_text[:2000]}"


def load_reference_papers() -> str:
    """读取 docs/ 下所有 PDF，用 AI 总结后返回。结果缓存到本地。"""
    if not os.path.isdir(DOCS_DIR):
        return ""

    pdf_files = glob.glob(os.path.join(DOCS_DIR, "*.pdf"))
    if not pdf_files:
        return ""

    try:
        import pypdf
    except ImportError:
        print("[WARNING] pypdf not installed — skipping PDF ingestion. "
              "Run: pip install pypdf")
        return ""

    cache = _load_summary_cache()
    summaries = []
    updated = False

    for pdf_path in sorted(pdf_files):
        filename = os.path.basename(pdf_path)
        # 用文件大小+文件名作为缓存 key，文件变了就重新总结
        file_size = os.path.getsize(pdf_path)
        cache_key = f"{filename}|{file_size}"

        if cache_key in cache:
            summaries.append(f"### {filename}\n{cache[cache_key]}\n")
            continue

        # 需要新总结
        try:
            reader = pypdf.PdfReader(pdf_path)
            pages_text = []
            for page in reader.pages[:8]:  # 读前 8 页给 LLM 足够上下文
                text = page.extract_text()
                if text:
                    pages_text.append(text.strip())

            if not pages_text:
                continue

            full_text = "\n".join(pages_text)
            print(f"[PDF] Summarizing {filename} with AI...")
            summary = _summarize_with_llm(full_text, filename)
            cache[cache_key] = summary
            updated = True
            summaries.append(f"### {filename}\n{summary}\n")
        except Exception as e:
            print(f"[WARNING] Failed to read {filename}: {e}")

    if updated:
        _save_summary_cache(cache)

    if not summaries:
        return ""

    return (
        "\n\n--- REFERENCE PAPERS (AI-summarized from docs/ folder) ---\n"
        "You have structured summaries of the user's reference papers below. "
        "Use this knowledge when checking novelty — these are ground truth.\n\n"
        + "\n---\n".join(summaries)
    )


# 支持 --resummarize 参数强制重新总结
import sys
if "--resummarize" in sys.argv:
    if SUMMARY_CACHE and os.path.exists(SUMMARY_CACHE):
        os.remove(SUMMARY_CACHE)
        print("[PDF] Cleared summary cache — will re-summarize all papers.")

# Load reference papers at startup
_reference_papers = load_reference_papers()

# 启动时打印摘要，方便 review
if _reference_papers:
    print("=" * 60)
    print("LOADED REFERENCE PAPER SUMMARIES")
    print("=" * 60)
    print(_reference_papers)
    print("=" * 60)
    print("(If summaries look wrong, re-run with: python brainstorm.py --resummarize)\n")


# ============================================================
# Semantic Scholar Literature Search Tool
# ============================================================
# Gives literature_expert access to real paper search via the
# Semantic Scholar API (free, no key required).
# Results are cached locally in .paper_cache.json to avoid
# repeated requests.

CACHE_FILE = os.path.join(os.path.dirname(__file__), ".paper_cache.json")


def _load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def search_papers(
    query: Annotated[str, "Search query, e.g. 'quantization VLA model'"],
    max_results: Annotated[int, "Number of papers to return (1-10)"] = 5,
    year_range: Annotated[str, "Year filter, e.g. '2024-2026'"] = "",
) -> str:
    """Search Semantic Scholar for real academic papers.

    Returns titles, authors, year, citation count, and abstract snippet
    for each matching paper. Use this to verify novelty claims and find
    related work — never fabricate citations.
    """
    max_results = max(1, min(10, max_results))

    # 构建缓存 key
    cache_key = hashlib.md5(
        f"{query}|{max_results}|{year_range}".encode()
    ).hexdigest()
    cache = _load_cache()
    if cache_key in cache:
        return cache[cache_key]

    # 调 Semantic Scholar API
    params = {
        "query": query,
        "limit": max_results,
        "fields": "title,authors,year,citationCount,abstract,url",
    }
    if year_range and "-" in year_range:
        parts = year_range.split("-")
        params["year"] = f"{parts[0].strip()}-{parts[1].strip()}"

    url = "https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(params)

    import time
    data = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PaperBrainstormCrew/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(2 * (attempt + 1))  # 退避重试: 2s, 4s
                continue
            return f"[Search failed: HTTP {e.code}] — fall back to your training knowledge, but flag uncertainty."
        except Exception as e:
            return f"[Search failed: {e}] — fall back to your training knowledge, but flag uncertainty."

    papers = data.get("data", [])
    if not papers:
        return f"No papers found for query: '{query}'. Try different keywords."

    # 格式化结果
    lines = [f"Found {len(papers)} papers for '{query}':\n"]
    for i, p in enumerate(papers, 1):
        authors = ", ".join(a["name"] for a in (p.get("authors") or [])[:3])
        if len(p.get("authors") or []) > 3:
            authors += " et al."
        abstract = (p.get("abstract") or "No abstract")[:200]
        lines.append(
            f"{i}. **{p.get('title', 'Untitled')}**\n"
            f"   Authors: {authors}\n"
            f"   Year: {p.get('year', '?')} | Citations: {p.get('citationCount', '?')}\n"
            f"   URL: {p.get('url', 'N/A')}\n"
            f"   Abstract: {abstract}...\n"
        )

    result = "\n".join(lines)
    # 缓存结果
    cache[cache_key] = result
    _save_cache(cache)
    return result

# ============================================================
# LLM Configuration
# ============================================================
# We use Anthropic's Claude as the default. AutoGen supports
# OpenAI, Anthropic, Azure, local models, etc.
# Swap config_list if you prefer GPT-4 / DeepSeek / Qwen.

config_list = [
    {
        "model": "claude-opus-4-5",
        "api_key": os.getenv("ANTHROPIC_API_KEY"),
        "api_type": "anthropic",
    }
]

llm_config = {
    "config_list": config_list,
    "temperature": 0.7,
    "timeout": 120,
}


# ============================================================
# Agent Definitions
# ============================================================

# ---- You (Human in the loop) ----
user = autogen.UserProxyAgent(
    name="researcher_you",
    human_input_mode="ALWAYS",          # Prompt you between rounds
    max_consecutive_auto_reply=0,
    code_execution_config=False,
    system_message=(
        "You are the human researcher driving this brainstorm. "
        "You can steer the discussion, accept an idea, or pivot at any time."
    ),
)

# ---- Senior Explorer ----
explorer = autogen.AssistantAgent(
    name="senior_explorer",
    llm_config=llm_config,
    system_message="""You are a senior research scientist specializing in
embodied AI, vision-language-action models, model compression, and efficient
inference.

Your job is to propose and iteratively REFINE concrete paper ideas — NOT to
brainstorm vaguely.

Rules:
1. Propose ONE idea at a time, with: (a) one-sentence pitch, (b) the core
   technical contribution, (c) why it's NEW vs prior work, (d) the minimum
   experiment that would convince a reviewer.
2. After receiving feedback (from LitExpert, Critic, Mentor, VenueExpert,
   or the User), iterate the idea — don't restart from scratch.
3. Look for cross-pollination: combine quantization + LoRA + inference
   scheduling + RL + flow matching, etc. The best CVPR/NeurIPS papers
   combine 2-3 ideas in a non-obvious way.
4. NEVER propose pure engineering ("we built X for Y"). Every idea must
   have a clear scientific question or technical insight.
5. When an idea has converged (Critic says OK, Mentor says feasible,
   LitExpert finds a real gap), say "IDEA LOCKED" and write a 1-page
   structured proposal.
""",
)

# ---- Literature Expert ----
lit_expert = autogen.AssistantAgent(
    name="literature_expert",
    llm_config=llm_config,
    system_message="""You are a literature expert in VLA models, model
compression (quantization, pruning, distillation), parameter-efficient
fine-tuning (LoRA, QLoRA, adapters), diffusion policies, flow matching,
and efficient inference for foundation models. You know the 2024-2026
landscape well.

Rules:
1. Whenever Explorer proposes an idea, immediately check:
   - Has someone already done this? Name 2-3 representative papers.
   - What's the specific GAP that remains?
   - Is the proposed novelty REAL or just a re-skin?
2. Be concrete. Cite paper names you're confident about (OpenVLA, π0/π0.5,
   GR00T N1.5, QuantVLA, QLoRA, StreamingVLA, SmolVLA, RDT-1B, FAST,
   DuQuant, SmoothQuant, Diffusion Policy, etc.). If you're uncertain
   about a paper, SAY SO — do not fabricate citations.
3. If the idea is already done, propose the closest open variant.
4. Keep responses tight: a few bullets, not a literature review.
5. You have a search_papers tool — USE IT to verify claims instead of
   guessing. Search before making novelty judgments.
""" + _reference_papers,
)

# Register the search tool so literature_expert can call it
# and user proxy can execute it
lit_expert.register_for_llm(
    name="search_papers",
    description="Search Semantic Scholar for real academic papers to verify novelty and find related work.",
)(search_papers)

user.register_for_execution(name="search_papers")(search_papers)

# ---- Harsh Reviewer / Critic ----
critic = autogen.AssistantAgent(
    name="harsh_critic",
    llm_config=llm_config,
    system_message="""You are a senior reviewer for CVPR, ICCV, NeurIPS,
ICLR, and CoRL. You have rejected hundreds of papers. You are skeptical
but fair.

Rules:
1. After each idea iteration, ask 1-2 SHARP questions — not 10.
   Focus on the questions that will likely come up in actual review:
   - What's the scientific question? Is it a 'so what?' paper?
   - Is the contribution incremental or a real insight?
   - What's the strongest baseline? Why beat it?
   - Could this be done with a 1-line trick? Then it's not a paper.
   - Are the experiments convincing enough for the claimed contribution?
2. If the idea is clearly weak, say so directly: "This is an arxiv
   tech report, not a CVPR paper, because X."
3. If the idea is strong, say "I have no further objections — this
   could be a strong submission."
4. Don't be cruel for sport. Your job is to make the idea stronger.
""",
)

# ---- Practical Mentor ----
mentor = autogen.AssistantAgent(
    name="practical_mentor",
    llm_config=llm_config,
    system_message="""You are a hands-on advisor for graduate students.
You know the realistic constraints of a CS Master's student:
  - 1-2 consumer GPUs (RTX 4090 / A100 access if lucky)
  - 4-6 months of focused work
  - Limited engineering time, must reuse open-source code
  - LIBERO, CALVIN, RoboCasa, Open-X for VLA datasets
  - OpenPI, OpenVLA, LeRobot, HuggingFace for codebases

Rules:
1. For each idea, evaluate:
   - Data: is a public dataset sufficient? Or does it need new collection?
   - Compute: rough GPU-hours needed for training + ablations?
   - Codebase: is there a starter repo to fork?
   - Risk: what's the most likely thing that kills the project?
2. If too ambitious, propose a SCOPED-DOWN version that's still
   publishable (e.g., "do it on 7B not 65B, on LIBERO not real robot").
3. Be honest. If something will take 12 months, say so.
""",
)

# ---- Venue Expert ----
venue_expert = autogen.AssistantAgent(
    name="venue_expert",
    llm_config=llm_config,
    system_message="""You are an expert on top CV/ML/robotics venues:
CVPR, ICCV, ECCV, NeurIPS, ICML, ICLR, CoRL, RSS, ICRA.

You know each venue's culture:
  - CVPR/ICCV/ECCV: vision-centric, loves new tasks, strong benchmarks,
    visual results. Robotics work needs strong vision contribution.
  - NeurIPS/ICML/ICLR: ML methodology, theory or rigorous empirical
    insight, less tolerant of pure engineering.
  - CoRL: robotics-first, real-robot results highly valued, ML
    sophistication appreciated but not required.
  - RSS: theoretical rigor in robotics, smaller and selective.
  - ICRA: more applied, broader robotics scope.

Rules:
1. Once an idea takes shape, advise on the BEST venue fit and why.
2. Tell Explorer how to FRAME the idea for that venue's reviewers:
   - For CVPR: emphasize visual contributions, benchmark gains
   - For NeurIPS: emphasize methodology, theoretical motivation
   - For CoRL: emphasize robot capability, real deployment
3. Flag deadlines if relevant (CVPR ~Nov, NeurIPS ~May, ICLR ~Sep,
   CoRL ~June). Do not invent specific years/dates if uncertain.
""",
)


# ============================================================
# Group Chat Setup
# ============================================================

groupchat = autogen.GroupChat(
    agents=[user, explorer, lit_expert, critic, mentor, venue_expert],
    messages=[],
    max_round=40,
    speaker_selection_method="auto",
    allow_repeat_speaker=False,
)

manager = autogen.GroupChatManager(
    groupchat=groupchat,
    llm_config=llm_config,
    system_message="""You are the meeting chair for a research group
brainstorm. Manage the discussion flow so it converges efficiently
toward 1-3 strong, venue-ready paper ideas.

Recommended flow per idea cycle:
  1. Explorer proposes idea
  2. LitExpert checks novelty
  3. Critic challenges
  4. Explorer iterates
  5. Critic & Mentor evaluate the revised idea
  6. If solid, VenueExpert advises framing & venue fit
  7. Invite the User to react / steer / accept

Rules:
- Do NOT let the same agent speak 3 times in a row.
- After 5-6 rounds on one idea without convergence, pivot to a new
  direction (suggest Explorer try another angle).
- Periodically (every ~6 rounds) check in with the User.
- When the User says "lock this idea" or "I'm happy", instruct
  Explorer to produce the final 1-page proposal and end the session.
""",
)


# ============================================================
# Kickoff
# ============================================================

INITIAL_PROMPT = """\
Hello team. I'm a CS Master's student at Stevens Institute of Technology
working in efficient embodied AI. I want to develop a paper idea that I
can submit to a top-tier venue (CVPR / NeurIPS / CoRL preferred).

My background:
  - Strong full-stack + systems background (Spring Boot, distributed sys)
  - Currently working through VLA model literature: QLoRA, QuantVLA,
    StreamingVLA, OpenVLA, π0.5
  - Interested in the intersection of: quantization + LoRA-style
    fine-tuning + inference scheduling for VLA models
  - Have access to 1x RTX 4090 and limited A100 time
  - 4-6 month timeline

Target venue: CVPR (preferred) or CoRL, depending on the angle.

Goal of this session: develop ONE concrete, novel paper idea that:
  1. Has a real gap not covered by QuantVLA / StreamingVLA / QLoRA
  2. Is feasible on my compute budget
  3. Frames well for CVPR or CoRL reviewers
  4. Has a clear "headline experiment" that would carry the paper

Let's start. Senior Explorer, propose your first idea — but ONE idea,
not a list. Make it specific and bold.
"""

if __name__ == "__main__":
    user.initiate_chat(
        manager,
        message=INITIAL_PROMPT,
    )
