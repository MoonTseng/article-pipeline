#!/usr/bin/env python3
"""Generate and save WeChat article using Xiaomi LLM"""
import sys, json, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from processor import _call_llm
from collector import _load_config

config = _load_config()

prompt = """你是一位资深科技自媒体编辑。请写一篇微信公众号科技文章。

## 信息
Anthropic预计本周发布Claude Opus 4.7模型和全新AI设计工具。The Information独家报道。Reddit热度573赞88评论。Claude Opus 4是Anthropic最强模型，Claude Code编程助手最近爆火。Anthropic与OpenAI(GPT-5)、Google(Gemini)竞争激烈。

## 要求
1. 标题: 20字以内抓眼球
2. 摘要: 50字以内
3. 正文: 1200-1800字，去AI味，像真人编辑写的，有观点有吐槽
4. 标签: 5个中文标签

输出纯JSON: {"title":"","summary":"","body":"","tags":[]}"""

result = _call_llm(prompt, config, max_tokens=8000)

json_str = result.strip()
if json_str.startswith("```"):
    json_str = re.sub(r'^```(?:json)?\s*', '', json_str)
    json_str = re.sub(r'\s*```$', '', json_str)

parsed = json.loads(json_str)

# Build WeChat HTML
body_html = ""
for para in parsed["body"].split("\n\n"):
    para = para.replace("\n", "<br>")
    if para.strip():
        body_html += f"<p>{para}</p>\n"

tags_html = "".join(f'<span class="tag">#{t}</span>' for t in parsed["tags"])

html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body {{ font-family: -apple-system, PingFang SC, sans-serif; line-height: 1.9; color: #333; padding: 0 15px; }}
p {{ margin: 1.2em 0; }}
strong {{ color: #07c160; }}
.tags {{ text-align: center; margin: 2em 0; }}
.tag {{ display: inline-block; background: #f0f7f0; color: #07c160; padding: 4px 14px; border-radius: 20px; margin: 4px; font-size: 13px; }}
.footer {{ color: #aaa; font-size: 12px; text-align: center; margin-top: 3em; border-top: 1px solid #eee; padding: 1.5em 0; }}
</style></head><body>
<h1 style="text-align:center; font-size:1.4em;">{parsed["title"]}</h1>
<p style="text-align:center; color:#888; font-size:14px;">{parsed["summary"]}</p>
{body_html}
<div class="tags">{tags_html}</div>
<div class="footer">极话 · AI 科技日报<br>来源: The Information, Reddit r/singularity<br>2026-04-15</div>
</body></html>"""

out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "articles", "wechat_claude_opus_47.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)

print(f"TITLE: {parsed['title']}")
print(f"TAGS: {', '.join(parsed['tags'])}")
print(f"BODY_LEN: {len(parsed['body'])} chars")
print(f"SAVED: {out}")
