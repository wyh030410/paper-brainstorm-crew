# Paper Brainstorm Crew 🧠

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
- **你**（人类）随时介入、引导方向

---

## 快速开始

```bash
# 1. 安装依赖
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. 配置 API key
cp .env.example .env
# 编辑 .env，填入你的 ANTHROPIC_API_KEY

# 3. 启动头脑风暴
python brainstorm.py
```

会话是交互式的——每轮 AI 讨论后，会停下来让你输入引导，按回车继续即可。

---

## 输出示例

收敛时 Explorer 会输出一个标准化的 idea 卡片：

```
## IDEA LOCKED: <一句话标题>

**Pitch:** <审稿人看到的第一段>
**核心贡献:** ...
**Why new:** ...
**Headline experiment:** ...
**Target venue:** CVPR
**Timeline (4 个月):** ...
**风险与缓解:** ...
```

把这张卡片直接拿去写 abstract 和 intro 就行。

---

## 想让 Claude Code 帮你扩展？

读 `CLAUDE.md`——里面写好了完整的项目上下文、TODO 列表、风格指南。直接：

```bash
claude  # 在项目目录里启动 Claude Code
> 读一下 CLAUDE.md，然后帮我实现 TODO 6.1.1（接入 arXiv API）
```

---

## 项目结构

```
paper_brainstorm_crew/
├── brainstorm.py       # 主程序：定义 6 个 agent + 群聊
├── requirements.txt    # 依赖
├── .env.example        # API key 模板
├── README.md           # 本文件
└── CLAUDE.md           # 给 Claude Code 看的项目说明
```

---

## License

MIT — 随便用。
