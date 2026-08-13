# 📚 novel-agent

> 多 Agent 小说创作系统 — 章节生成 + 封面设计 + 发布规则查询 + 内容审核一条龙。

## ✨ 特性

- 🤖 **多 Agent 协作**：大纲 Agent / 章节 Agent / 封面 Agent / 审核 Agent 流水线
- 📖 **章节管理**：自动生成、续写、改写、合并
- 🎨 **封面生成**：调用 Agnes / SD 等生图模型
- 📋 **平台规则**：内置番茄小说/起点等平台发布规则
- 🔍 **去 AI 味**：基于 tokenizer 的句式变换 + 人工抽检
- 📤 **一键发布**：自动推送草稿到番茄作家助手

## 📁 项目结构

```
novel-agent/
├── agents/                # Agent 定义
│   ├── outline_agent.py   # 大纲生成
│   ├── chapter_agent.py   # 章节写作
│   ├── cover_agent.py     # 封面设计
│   └── review_agent.py    # 内容审核
├── chapter*.txt           # 章节草稿
├── chapter*.json          # 结构化章节
└── cover_bg*.png          # 封面背景图
```

## 🚀 快速开始

```bash
git clone https://github.com/itr-del/novel-agent.git
cd novel-agent
pip install -r requirements.txt  # 如有
python3 -m agents.outline_agent --genre 玄幻 --words 100万
```

## 📜 License

MIT

## 🙏 致谢

Anthropic Claude、Agnes 生图、番茄小说平台规则。