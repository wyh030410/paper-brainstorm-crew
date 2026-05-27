"""
Paper Brainstorm Crew — Gradio UI
==================================

A web UI wrapper around the AutoGen brainstorm session.
Run:  python ui.py
Then open http://localhost:7860 in your browser.
"""

import os
import sys
import json
import threading
import queue
import time
from datetime import datetime

import gradio as gr

# ── 重用 brainstorm.py 里的所有组件 ──────────────────────────
# 先把 brainstorm 模块当脚本的 __main__ 守卫绕过
# 我们只需要它的 agent 定义、工具、记忆等
sys.modules.pop("brainstorm", None)

import brainstorm as bs

# ── 线程间通信队列 ──────────────────────────────────────────
human_input_queue: queue.Queue[str] = queue.Queue()
agent_output_queue: queue.Queue[dict] = queue.Queue()

# 全局状态
_chat_thread: threading.Thread | None = None
_session_active = False


# ── 拦截 AutoGen 的人类输入 ──────────────────────────────────
# 把 UserProxyAgent 的 get_human_input 替换成从队列读取
_original_get_human_input = bs.user.get_human_input


def _ui_get_human_input(prompt: str = "") -> str:
    """从 UI 队列获取人类输入，替代 stdin。"""
    # 通知 UI 该你说话了
    agent_output_queue.put({
        "role": "system",
        "name": "system",
        "content": "💬 **轮到你了** — 输入你的想法，或按发送（空内容）让 agents 继续讨论。",
    })
    # 阻塞等待 UI 端的输入
    text = human_input_queue.get()
    return text


bs.user.get_human_input = _ui_get_human_input


# ── 拦截 agent 发言，推送到 UI ────────────────────────────────
# Monkey-patch GroupChatManager 的 run_chat 不太方便，
# 改为轮询 groupchat.messages 检测新消息

AGENT_STYLES = {
    "senior_explorer":    ("Explorer",    "#4CAF50"),
    "literature_expert":  ("LitExpert",   "#2196F3"),
    "harsh_critic":       ("Critic",      "#f44336"),
    "practical_mentor":   ("Mentor",      "#FF9800"),
    "venue_expert":       ("Venue",       "#9C27B0"),
    "proposal_writer":    ("Proposal",    "#00BCD4"),
    "related_work_drafter": ("RelWork",   "#795548"),
    "researcher_you":     ("You",         "#607D8B"),
    "chat_manager":       ("Chair",       "#757575"),
}


def _format_agent_msg(name: str, content: str) -> str:
    """给 agent 消息加上彩色标签。"""
    style = AGENT_STYLES.get(name, (name, "#999"))
    label, color = style
    # Gradio Chatbot markdown 支持 HTML
    header = f'<span style="color:{color};font-weight:bold;">[{label}]</span>'
    return f"{header}\n\n{content}"


def _run_session(initial_prompt: str):
    """在后台线程跑 AutoGen session。"""
    global _session_active
    _session_active = True

    try:
        # 重置 groupchat
        bs.groupchat.messages.clear()

        # 设置人类输入模式
        bs.user.human_input_mode = "ALWAYS"
        bs.user.max_consecutive_auto_reply = 0

        # 启动聊天（阻塞，在子线程运行）
        bs.user.initiate_chat(bs.manager, message=initial_prompt)

        # 聊天结束
        bs.cost_tracker.update_from_messages(bs.groupchat.messages)
        model = bs.config_list[0].get("model", "claude-opus-4-5")
        cost = bs.cost_tracker.get_cost(model)

        # 导出 session
        filepath = bs.export_session(bs.groupchat.messages)
        bs.update_memory_from_session(bs.groupchat.messages)

        agent_output_queue.put({
            "role": "system",
            "name": "system",
            "content": (
                f"**Session 结束**\n\n"
                f"- 总轮数: {len(bs.groupchat.messages)}\n"
                f"- 估算费用: ${cost:.4f}\n"
                f"- 记录已保存: `{filepath}`"
            ),
        })
    except Exception as e:
        agent_output_queue.put({
            "role": "system",
            "name": "system",
            "content": f"**错误**: {e}",
        })
    finally:
        _session_active = False


# ── 消息轮询线程 ─────────────────────────────────────────────
_seen_msg_count = 0


def _poll_messages():
    """持续检查 groupchat.messages 有没有新消息，推送到 UI 队列。"""
    global _seen_msg_count
    while _session_active or not agent_output_queue.empty():
        msgs = bs.groupchat.messages
        while _seen_msg_count < len(msgs):
            msg = msgs[_seen_msg_count]
            _seen_msg_count += 1
            name = msg.get("name", msg.get("role", "unknown"))
            content = msg.get("content", "")
            if not content:
                continue
            # 跳过人类消息（已在 UI 显示）
            if name == "researcher_you":
                continue
            agent_output_queue.put({
                "role": "assistant",
                "name": name,
                "content": content,
            })
        time.sleep(0.3)


# ── Gradio UI ────────────────────────────────────────────────

def start_session(initial_prompt, chatbot, status):
    """点击开始按钮后启动 session。"""
    global _chat_thread, _seen_msg_count

    if _session_active:
        yield chatbot, "Session 正在运行中..."
        return

    if not initial_prompt.strip():
        initial_prompt = bs.INITIAL_PROMPT

    # 清空状态
    _seen_msg_count = 0
    chatbot = []

    # 在 UI 显示初始 prompt
    chatbot.append({"role": "user", "content": initial_prompt})
    yield chatbot, "🟢 Session 已启动，等待 agents 回复..."

    # 启动后台线程
    chat_t = threading.Thread(target=_run_session, args=(initial_prompt,), daemon=True)
    poll_t = threading.Thread(target=_poll_messages, daemon=True)
    _chat_thread = chat_t
    chat_t.start()
    poll_t.start()

    # 持续从队列读取新消息并更新 UI
    while _session_active or not agent_output_queue.empty():
        try:
            msg = agent_output_queue.get(timeout=0.5)
            name = msg["name"]
            content = msg["content"]

            if msg["role"] == "system":
                chatbot.append({
                    "role": "assistant",
                    "content": content,
                })
            else:
                chatbot.append({
                    "role": "assistant",
                    "content": _format_agent_msg(name, content),
                })
            yield chatbot, f"🟢 运行中 — 第 {_seen_msg_count} 轮"
        except queue.Empty:
            continue

    yield chatbot, "🔴 Session 已结束"


def send_human_input(user_msg, chatbot):
    """用户发送消息。"""
    if not _session_active:
        chatbot.append({"role": "assistant", "content": "Session 未在运行。请先点击「开始 Brainstorm」。"})
        return "", chatbot

    # 空消息 = 让 agents 继续
    display_msg = user_msg if user_msg.strip() else "(继续)"
    chatbot.append({"role": "user", "content": display_msg})

    # 发送到 AutoGen
    human_input_queue.put(user_msg)

    return "", chatbot


def upload_pdf(files):
    """上传 PDF 到 docs/ 目录。"""
    if not files:
        return "没有选择文件"

    os.makedirs(bs.DOCS_DIR, exist_ok=True)
    results = []
    for f in files:
        filename = os.path.basename(f)
        dest = os.path.join(bs.DOCS_DIR, filename)
        # gradio 给的是临时路径，复制过去
        import shutil
        shutil.copy2(f, dest)
        results.append(f"  ✓ {filename}")

    # 重新处理 PDF
    bs._process_new_pdfs()
    new_refs = bs.load_reference_papers()
    paper_count = len([f for f in os.listdir(bs.SUMMARIES_DIR) if f.endswith(".md")]) if os.path.isdir(bs.SUMMARIES_DIR) else 0

    return f"已上传 {len(results)} 个文件:\n" + "\n".join(results) + f"\n\n知识库现有 {paper_count} 篇论文摘要"


def get_memory_info():
    """显示跨 session 记忆。"""
    memory = bs.load_memory()
    lines = []

    if memory.get("locked_ideas"):
        lines.append(f"### 已锁定 Ideas ({len(memory['locked_ideas'])})")
        for i, idea in enumerate(memory["locked_ideas"], 1):
            preview = idea.strip().split("\n")[0][:120]
            lines.append(f"{i}. {preview}")

    if memory.get("rejected_directions"):
        lines.append(f"\n### 被否决的方向 ({len(memory['rejected_directions'])})")
        for d in memory["rejected_directions"][-5:]:
            lines.append(f"- {d[:100]}")

    if memory.get("sessions"):
        lines.append(f"\n### 历史 Sessions ({len(memory['sessions'])})")
        for s in memory["sessions"][-5:]:
            locked_tag = " 🔒" if s.get("locked") else ""
            lines.append(f"- {s['date']} — {s['rounds']} 轮{locked_tag}")

    return "\n".join(lines) if lines else "暂无记忆记录"


def list_proposals():
    """列出已生成的 proposals。"""
    proposals_dir = os.path.join(os.path.dirname(bs.__file__), "proposals")
    if not os.path.isdir(proposals_dir):
        return "暂无 proposal"

    files = sorted(os.listdir(proposals_dir))
    if not files:
        return "暂无 proposal"

    lines = []
    for f in files:
        path = os.path.join(proposals_dir, f)
        size = os.path.getsize(path)
        lines.append(f"- **{f}** ({size} bytes)")
    return "\n".join(lines)


def read_proposal(filename):
    """读取一个 proposal 文件的内容。"""
    proposals_dir = os.path.join(os.path.dirname(bs.__file__), "proposals")
    path = os.path.join(proposals_dir, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "文件不存在"


# ── 构建 Gradio 界面 ─────────────────────────────────────────

CUSTOM_CSS = """
.agent-explorer { border-left: 3px solid #4CAF50; padding-left: 8px; }
.agent-critic { border-left: 3px solid #f44336; padding-left: 8px; }
footer { display: none !important; }
"""

with gr.Blocks(
    title="Paper Brainstorm Crew",
    css=CUSTOM_CSS,
    theme=gr.themes.Soft(),
) as app:

    gr.Markdown(
        "# Paper Brainstorm Crew\n"
        "多智能体研究组会 — 帮你打磨能投顶会的论文 idea"
    )

    with gr.Tabs():
        # ── Tab 1: Brainstorm 主界面 ──
        with gr.Tab("Brainstorm"):
            with gr.Row():
                with gr.Column(scale=3):
                    chatbot = gr.Chatbot(
                        label="讨论区",
                        height=520,
                        type="messages",
                        show_copy_button=True,
                    )
                    with gr.Row():
                        user_input = gr.Textbox(
                            label="你的输入",
                            placeholder="输入你的想法... 留空并发送 = 让 agents 继续讨论",
                            scale=5,
                            lines=2,
                        )
                        send_btn = gr.Button("发送", variant="primary", scale=1)

                with gr.Column(scale=1):
                    status_display = gr.Textbox(
                        label="状态",
                        value="🔴 未启动",
                        interactive=False,
                    )
                    initial_prompt = gr.Textbox(
                        label="起始 Prompt（可选，留空用默认）",
                        placeholder="留空 = 使用默认 VLA 研究方向",
                        lines=4,
                    )
                    start_btn = gr.Button("开始 Brainstorm", variant="primary")

                    gr.Markdown("---")
                    gr.Markdown("### Agent 角色说明")
                    gr.Markdown(
                        "- 🟢 **Explorer** — 提出 idea\n"
                        "- 🔵 **LitExpert** — 查文献验证\n"
                        "- 🔴 **Critic** — 审稿人挑刺\n"
                        "- 🟠 **Mentor** — 可行性评估\n"
                        "- 🟣 **Venue** — 投稿建议\n"
                        "- 🔵 **Proposal** — 写 proposal\n"
                        "- 🟤 **RelWork** — 写 related work"
                    )

            # 事件绑定
            start_btn.click(
                fn=start_session,
                inputs=[initial_prompt, chatbot, status_display],
                outputs=[chatbot, status_display],
            )
            send_btn.click(
                fn=send_human_input,
                inputs=[user_input, chatbot],
                outputs=[user_input, chatbot],
            )
            user_input.submit(
                fn=send_human_input,
                inputs=[user_input, chatbot],
                outputs=[user_input, chatbot],
            )

        # ── Tab 2: 论文管理 ──
        with gr.Tab("论文库"):
            gr.Markdown("### 上传参考论文 PDF\n放入 `docs/` 目录，AI 自动生成结构化摘要供 LitExpert 使用。")
            pdf_upload = gr.File(
                label="上传 PDF",
                file_count="multiple",
                file_types=[".pdf"],
            )
            upload_btn = gr.Button("上传并处理")
            upload_result = gr.Markdown()
            upload_btn.click(fn=upload_pdf, inputs=[pdf_upload], outputs=[upload_result])

        # ── Tab 3: 记忆与历史 ──
        with gr.Tab("记忆 & 历史"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### 跨 Session 记忆")
                    memory_display = gr.Markdown()
                    refresh_mem_btn = gr.Button("刷新记忆")
                    refresh_mem_btn.click(fn=get_memory_info, outputs=[memory_display])

                with gr.Column():
                    gr.Markdown("### 已生成 Proposals")
                    proposals_display = gr.Markdown()
                    refresh_prop_btn = gr.Button("刷新列表")
                    refresh_prop_btn.click(fn=list_proposals, outputs=[proposals_display])

            # 初始加载
            app.load(fn=get_memory_info, outputs=[memory_display])
            app.load(fn=list_proposals, outputs=[proposals_display])

    gr.Markdown(
        "---\n"
        "*Powered by [AutoGen](https://github.com/microsoft/autogen) + "
        "[Gradio](https://gradio.app) — MIT License*"
    )


if __name__ == "__main__":
    app.queue()      # 启用队列以支持 streaming/generator
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,     # 改为 True 可生成公网链接
    )
