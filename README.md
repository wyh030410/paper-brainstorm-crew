# Paper Brainstorm Crew

一个基于 AutoGen 的多智能体"研究组会"，帮你打磨能投顶会（CVPR / NeurIPS / CoRL 等）的论文 idea。

A multi-agent "research group meeting" powered by AutoGen, helping you
refine a paper idea worthy of top-tier venues (CVPR / NeurIPS / CoRL).

---

## 项目特点

### 多智能体对抗式辩论，不是单 LLM 陪聊

单个 LLM 太爱迎合你（"这是个不错的 idea！"），不会真正挑刺。本项目用 AutoGen 的 `GroupChat` 模拟一个**真实实验室组会**，7 个 AI agent 各司其职，围绕一个 idea 反复辩论、挑战、迭代：

| Agent | 角色 | 干什么 |
|-------|------|--------|
| **Explorer** | 资深研究员 | 提出大胆具体的 idea，被挑战后迭代改进而非推倒重来 |
| **LitExpert** | 文献专家 | 调用 Semantic Scholar 搜真实论文，验证 idea 是否真的新 |
| **Critic** | 顶会审稿人 | 只问 1-2 个最致命的问题（"这只是个工程优化，novelty 在哪？"） |
| **Mentor** | 实际导师 | 基于 1x4090 + 4-6 个月的现实约束评估可行性 |
| **VenueExpert** | 投稿顾问 | 判断 idea 该投 CVPR 还是 CoRL，怎么 frame |
| **ProposalWriter** | 提案撰写 | idea 锁定后自动生成 1 页结构化 proposal 并保存文件 |
| **RelatedWorkDrafter** | 文献综述 | 从讨论中提取所有引用，自动起草 Related Work 段落 |

Manager（会议主席）通过 `speaker_selection_method="auto"` 柔性调度发言顺序——不是固定流水线，而是像真实组会一样根据上下文决定谁该发言。

### 真实文献验证，禁止编造引用

LitExpert 配备 `search_papers()` 工具，直接调 Semantic Scholar API 搜索真实论文。不确定的论文必须标注不确定，**绝不允许编造引用**。搜索结果本地缓存，429 限流自动退避重试。

### Idea 自动收敛成可投稿的 Proposal

讨论不是无限发散。当 idea 经过多轮挑战后收敛，Explorer 说出 **"IDEA LOCKED"**，系统自动触发：
1. ProposalWriter 生成包含 Abstract / Method / Experiments / Timeline / Risks 的 1 页 proposal
2. RelatedWorkDrafter 从讨论中收集所有引用，按主题分组写 300-500 词 Related Work
3. 输出保存到 `proposals/` 目录，可直接用于投稿准备

### PDF 论文导入，构建私有知识库

把你读过的论文 PDF 丢进 `docs/`，启动时自动用 Claude Sonnet 读全文生成结构化摘要，注入 LitExpert 的知识库。LitExpert 不只靠训练数据记忆，还能基于**你实际读过的论文**做新颖性判断。

### 跨 Session 记忆，不走回头路

`memory.json` 自动记录锁定的 idea、被否决的方向、上次讨论概要。下次启动时注入 Explorer 的 system message，避免重复提出已经被否决的方向。

### 并行探索多个方向

`--parallel 3` 从不同角度（quantization+LoRA / inference scheduling / training efficiency）同时跑多个全自动 session，比较哪个方向最有潜力。

### Web UI 支持

`python ui.py` 启动 Gradio Web 界面，支持：
- 浏览器中实时对话，agent 发言彩色标签区分
- 上传 PDF 论文
- 查看跨 session 记忆和已生成 proposals

### 设计哲学

- **只要一个 Explorer** — 瓶颈不是"更多 idea"，而是"把一个 idea 磨好"
- **Critic 和 Mentor 分开** — 审稿视角（是否新颖）和导师视角（是否可行）是不同的思维模式
- **VenueExpert 独立** — 好 idea 投错会议照样被拒，framing 是独立技能
- **AutoGen 而非 CrewAI** — 需要自由辩论的 GroupChat，不是固定流水线
- **temperature=0.7** — 0.5 太保守，0.9 太发散，0.7 是大胆但落地的平衡点

---

## 快速开始

```bash
# 1. 安装依赖
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. 配置 API key
cp .env.example .env
# 编辑 .env，填入你的 ANTHROPIC_API_KEY

# 3. 启动头脑风暴
python brainstorm.py
```

会话是交互式的——每轮 AI 讨论后，会停下来让你输入引导，按回车继续即可。

---

## 功能详解

### 1. 文献检索（Semantic Scholar）

LitExpert 可以调用 `search_papers` 工具，搜索 Semantic Scholar 上的**真实论文**，不再靠 LLM 记忆瞎编引用。

- 免费 API，不需要额外 key
- 支持年份过滤（如 2024-2026）
- 搜索结果本地缓存（`.paper_cache.json`），避免重复请求
- 429 限流自动退避重试

LitExpert 会在判断 idea 新颖性时自动调用，无需手动操作。

---

### 2. PDF 论文导入 + AI 总结

把你读过的论文 PDF 丢进 `docs/` 文件夹，启动时会自动：
1. 扫描 `docs/` 中的新 PDF
2. 调用 Claude Sonnet 读**全文**并生成结构化摘要
3. 保存到 `docs/summaries/<论文名>.md`

**LitExpert 的知识库只从 `docs/summaries/` 读取。**

```
docs/
├── QLoRA.pdf              ← 放 PDF 原文
├── QuantVLA.pdf
├── StreamingVLA.pdf
└── summaries/             ← AI 生成的摘要（知识库）
    ├── QLoRA.md           ← 可手动编辑
    ├── QuantVLA.md
    └── StreamingVLA.md
```

**使用方式：**

```bash
# 正常启动（新 PDF 自动总结，已有摘要的跳过）
python brainstorm.py

# 查看所有摘要内容
python brainstorm.py --show-summaries

# 强制重新总结所有论文（比如觉得摘要不准确）
python brainstorm.py --resummarize
```

**管理论文：**
- 加论文：把 PDF 放进 `docs/`，下次启动自动总结
- 删论文：删 `docs/summaries/` 里对应的 `.md`
- 改摘要：直接编辑 `.md` 文件
- 论文太多时会自动警告，删掉不相关的 `.md` 即可

---

### 3. 会话记录导出

每次 brainstorm 结束后，完整对话自动保存为 Markdown：

```
sessions/
└── 20260527-1430.md
```

- 包含所有 agent 的发言记录
- 如果讨论中出现了 "IDEA LOCKED"，会在文件末尾单独提取为 **LOCKED IDEAS** 章节
- 方便回顾和下次 session 参考

---

### 4. Proposal 自动生成

当一个 idea 收敛（Explorer 说 "IDEA LOCKED" 或你说 "lock this idea"），**ProposalWriter** 自动接管，生成 1 页结构化 proposal 并保存：

```
proposals/
└── quantized-vla-lora.md
```

Proposal 格式：
- **Abstract** — 150 词摘要
- **Problem Statement** — 具体 gap
- **Proposed Method** — 技术方案步骤
- **Experiments** — 数据集、基线、指标、headline experiment、消融实验
- **Expected Results** — 预期结果
- **Timeline** — 4 个月计划
- **Risks & Mitigations** — 风险与应对

---

### 5. Related Work 自动起草

ProposalWriter 写完后，**RelatedWorkDrafter** 自动接力：

- 从讨论中收集所有引用过的论文
- 按主题分组（VLA Models、Quantization、Efficient Fine-tuning 等）
- 写一段 300-500 词的 Related Work，可直接放进论文
- 保存到 `proposals/<idea-name>-related-work.md`

---

### 6. API 费用追踪

每次 session 结束后自动打印费用估算：

```
==================================================
SESSION COST ESTIMATE
==================================================
  Rounds:        25
  Input tokens:  ~120,000
  Output tokens: ~15,000
  Model:         claude-opus-4-5
  Est. cost:     $2.9250
==================================================
```

支持 Claude Opus、Sonnet、GPT-4o 的定价。

---

### 7. 多轮并行 Brainstorm

用不同的切入角度同时跑多个 session，比较哪个方向更好：

```bash
# 跑 3 个 session，每个角度不同（自动模式，无需人工输入）
python brainstorm.py --parallel 3
```

- Session 1: 默认 prompt
- Session 2: 聚焦 quantization + LoRA co-design
- Session 3: 聚焦 inference scheduling for real-time VLA
- 每个 session 都有独立的 transcript 保存到 `sessions/`

---

### 8. 跨 Session 记忆

系统会自动记住之前的讨论（保存在 `memory.json`）：

- **之前锁定的 idea** — 避免重复讨论
- **被否决的方向** — Explorer 不会再走老路
- **上次讨论概要** — 新 session 有上下文

记忆自动注入 Explorer 的 system message，无需手动操作。

---

## 项目结构

```
paper_brainstorm_crew/
├── brainstorm.py          # 主程序：8 个 agent + 群聊 + 工具
├── ui.py                  # Gradio Web UI
├── requirements.txt       # 依赖
├── .env.example           # API key 模板
├── .env                   # 你的 API key（gitignored）
├── docs/                  # 论文 PDF + AI 摘要
│   ├── *.pdf              # 放论文原文
│   └── summaries/         # AI 生成的摘要（知识库）
│       └── *.md
├── sessions/              # 会话记录（自动生成）
│   └── YYYYMMDD-HHMM.md
├── proposals/             # 锁定 idea 的 proposal + related work
│   ├── <idea-name>.md
│   └── <idea-name>-related-work.md
├── memory.json            # 跨 session 记忆（自动维护）
├── README.md              # 本文件
└── CLAUDE.md              # 给 Claude Code 看的项目说明
```

---

## CLI 参数

| 命令 | 作用 |
|------|------|
| `python brainstorm.py` | 启动终端交互式 brainstorm |
| `python brainstorm.py --show-summaries` | 启动时打印所有论文摘要的完整内容 |
| `python brainstorm.py --resummarize` | 清除所有摘要缓存，强制重新总结 |
| `python brainstorm.py --parallel N` | 并行跑 N 个 session（1-5），自动模式无需人工输入 |
| `python ui.py` | 启动 Gradio Web UI（http://localhost:7860） |

---

## 想让 Claude Code 帮你扩展？

读 `CLAUDE.md`——里面写好了完整的项目上下文、TODO 列表、风格指南。直接：

```bash
claude  # 在项目目录里启动 Claude Code
> 读一下 CLAUDE.md，然后帮我实现下一个 TODO
```

---

## License

This project is licensed under the [MIT License](LICENSE).
