#!/usr/bin/env python3
"""Generate article about Claude Opus 4.7"""
import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from processor import _call_llm
from collector import _load_config

config = _load_config()

prompt = """你是一位资深科技自媒体编辑。请根据以下信息，写一篇适合微信公众号发布的中文科技文章。

## 信息
- 事件: Anthropic 即将发布 Claude Opus 4.7 模型和一个全新的 AI 设计工具
- 时间: 预计本周内发布
- 来源: The Information 独家报道
- Reddit 热度: 573 赞, 88 条评论 (r/singularity 热帖)
- 背景:
  - Claude Opus 4 是 Anthropic 目前最强的模型
  - Claude Code 是 Anthropic 的编程助手产品，最近非常火爆
  - Anthropic 与 OpenAI、Google 在 AI 领域竞争激烈
  - Opus 4.7 可能在推理能力、编程能力上有显著提升
  - AI 设计工具是 Anthropic 的新产品线，可能与 Figma、Canva 竞争

## 要求
1. 标题: 20字以内，抓眼球
2. 摘要: 一句话概括，50字以内
3. 正文: 1200-1800字
   - 开头直接切入，不要"在当今"
   - 介绍 Claude Opus 4.7 可能的新特性
   - 分析 Anthropic 的产品策略
   - 对比 OpenAI GPT-5、Google Gemini
   - AI 设计工具的市场分析
   - 结尾给出你的观点和预测
4. 标签: 5个

## 风格
- 科技媒体风格，专业但有趣
- 去AI味，像真人编辑写的
- 适当加入吐槽和观点
- 技术术语保留英文

## 输出格式 (严格JSON)
{"title": "标题", "summary": "一句话摘要", "body": "正文内容", "tags": ["标签1", "标签2"]}

只输出JSON，不要其他内容。"""

result = _call_llm(prompt, config, max_tokens=6000)

# Parse and pretty-print
try:
    json_str = result.strip()
    if json_str.startswith("```"):
        import re
        json_str = re.sub(r'^```(?:json)?\\s*', '', json_str)
        json_str = re.sub(r'\\s*```$', '', json_str)
    parsed = json.loads(json_str)
    print(json.dumps(parsed, ensure_ascii=False, indent=2))
except Exception as e:
    print(f"PARSE_ERROR: {e}")
    print("RAW:", result[:2000])
