# Paper Brainstorm Crew

一个多智能体"研究组会"，帮你打磨能投顶会（CVPR / NeurIPS / CoRL 等）的论文 idea。

A multi-agent "research group meeting" that helps you refine a paper idea
worthy of top-tier venues (CVPR / NeurIPS / CoRL).

---

## 为什么不用 ChatGPT 直接聊？

单个 LLM 太爱迎合你（"这是个不错的 idea！"），不会真正挑刺。这个项目模拟一个**真实研究组会**：

- **Explorer** 大胆提 idea
- **LitExpert** 查文献，告诉你"这个 X 论文已经做过了"
- **Critic** 像顶会审稿人一样砸刺（"这只是个工程优化，novelty 在哪？"）
- **Mentor** 检查可行性（"你 4 个月做不完，砍成 7B + LIBERO 吧"）
- **VenueExpert** 告诉你这个 idea 投 CVPR 还是 CoRL 更合适
- **ProposalWriter** idea 锁定后自动生成 1 页 CVPR 风格 proposal
- **你**（人类）随时介入、引导方向

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

## 项目结构

```
paper_brainstorm_crew/
├── brainstorm.py          # 主程序：7 个 agent + 群聊 + 工具
├── requirements.txt       # 依赖
├── .env.example           # API key 模板
├── .env                   # 你的 API key（gitignored）
├── docs/                  # 论文 PDF + AI 摘要
│   ├── *.pdf              # 放论文原文
│   └── summaries/         # AI 生成的摘要（知识库）
│       └── *.md
├── sessions/              # 会话记录（自动生成）
│   └── YYYYMMDD-HHMM.md
├── proposals/             # 锁定 idea 的 proposal（自动生成）
│   └── <idea-name>.md
├── README.md              # 本文件
└── CLAUDE.md              # 给 Claude Code 看的项目说明
```

---

## CLI 参数

| 参数 | 作用 |
|------|------|
| `--show-summaries` | 启动时打印所有论文摘要的完整内容 |
| `--resummarize` | 清除所有摘要缓存，强制重新总结 |

---

## 想让 Claude Code 帮你扩展？

读 `CLAUDE.md`——里面写好了完整的项目上下文、TODO 列表、风格指南。直接：

```bash
claude  # 在项目目录里启动 Claude Code
> 读一下 CLAUDE.md，然后帮我实现下一个 TODO
```

---

## License

MIT — 随便用。
