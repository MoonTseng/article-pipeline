#!/usr/bin/env python3
"""Generate article about Claude Opus 4.7 — rich Markdown with images & tables"""
import sys, json, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from processor import _call_llm
from collector import _load_config

config = _load_config()

prompt = """你是一位资深科技自媒体编辑，为微信公众号「极话」写文章。

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
3. 正文: 1500-2200字，**Markdown 格式**
4. 标签: 5个

## 正文格式要求（非常重要）
正文必须是丰富的 Markdown，包含以下元素：

### 图片
在正文中插入 3-5 张图片占位符，格式：
![图片描述](img:english_keyword)

例如：
![Claude模型对比](img:artificial+intelligence+comparison)
![AI设计工具界面](img:design+tool+interface)

图片要放在相关段落之间，不要堆在一起。关键词用英文。

### 表格
至少包含 1 个对比表格，比如：
| 模型 | 公司 | 特点 | 评分 |
|------|------|------|------|
| Claude Opus 4.7 | Anthropic | 推理王者 | ⭐⭐⭐⭐⭐ |

### 排版元素
- 用 **加粗** 突出关键信息
- 用 `代码样式` 标注技术术语
- 用 > 引用框放重要观点或数据
- 用 ### 三级标题分段
- 适当用 emoji 增加可读性（但不要过度）
- 用有序/无序列表整理要点

## 风格
- 科技媒体风格，专业但有趣
- 去AI味，像真人编辑写的，偶尔吐槽
- 开头直接切入，不要"在当今""随着"
- 技术术语保留英文

## 输出格式 (严格JSON)
{"title": "标题", "summary": "一句话摘要", "body": "Markdown正文（含图片表格）", "tags": ["标签1", "标签2"]}

只输出JSON，不要其他内容。"""

result = _call_llm(prompt, config, max_tokens=16000)

# Parse and pretty-print
try:
    json_str = result.strip()
    if json_str.startswith("```"):
        json_str = re.sub(r'^```(?:json)?\s*', '', json_str)
        json_str = re.sub(r'\s*```$', '', json_str)
    parsed = json.loads(json_str)
    
    # Save as Markdown for Typora preview
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "wechat")
    os.makedirs(output_dir, exist_ok=True)
    
    # Replace img: placeholders — download related images to local
    import urllib.parse, urllib.request
    body = parsed["body"]
    img_dir = os.path.join(output_dir, "images")
    os.makedirs(img_dir, exist_ok=True)
    
    img_counter = [0]
    def replace_img(m):
        alt = m.group(1)
        kw = m.group(2)
        img_counter[0] += 1
        local_path = os.path.join(img_dir, f"img_{img_counter[0]:02d}.jpg")
        query = urllib.parse.quote(kw)
        
        # 按关键词搜索相关图片
        urls = [
            f"https://source.unsplash.com/800x400/?{query}",
            f"https://loremflickr.com/800/400/{query}",
        ]
        
        downloaded = False
        for url in urls:
            try:
                proxy = urllib.request.ProxyHandler({
                    'http': 'http://127.0.0.1:7890',
                    'https': 'http://127.0.0.1:7890',
                })
                opener = urllib.request.build_opener(proxy)
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                resp = opener.open(req, timeout=15)
                data = resp.read()
                # 确保是有效图片（至少10KB）
                if len(data) > 10000:
                    with open(local_path, 'wb') as f:
                        f.write(data)
                    downloaded = True
                    print(f"  📷 下载图片 {img_counter[0]}: {alt} (关键词: {kw})")
                    break
            except Exception as e:
                continue
        
        if downloaded:
            return f"![{alt}]({local_path})"
        else:
            print(f"  ⚠️  图片 {img_counter[0]} 下载失败: {alt}")
            return f"<!-- 图片下载失败: {alt} -->"
    
    body = re.sub(r'!\[([^\]]*)\]\(img:([^)]+)\)', replace_img, body)
    
    # Build full Markdown
    tags_str = " ".join(f"#{t}" for t in parsed["tags"])
    md = f"""<!-- 极话 · JIHUA — 科技前沿 · AI洞察 · 深度解读 -->

# {parsed["title"]}

> 💡 {parsed["summary"]}

<p style="text-align:center;color:#00D4FF;font-size:12px;">━━━━━━  极话 · JIHUA  ━━━━━━</p>

{body}

<p style="text-align:center;color:#00D4FF;font-size:12px;">━━━━━━  ━━━━━━  ━━━━━━</p>

🏷️ {tags_str}

---

<div style="background:#0D1B2A;padding:20px;border-radius:8px;text-align:center;margin:20px 0;">
<p style="color:#FFFFFF;font-size:24px;font-weight:bold;margin:0;">极话</p>
<p style="color:#00D4FF;font-size:14px;margin:5px 0;">科技前沿 · AI洞察 · 深度解读</p>
<p style="color:#A0AAB4;font-size:12px;margin:5px 0;">每天 get 最前沿的科技资讯</p>
<p style="color:#F0F0F0;font-size:16px;margin:10px 0;">⭐ 关注「极话」不迷路</p>
</div>
"""
    
    safe_title = "".join(c for c in parsed["title"][:15] if c.isalnum() or c in "- ").strip()
    md_path = os.path.join(output_dir, f"01_{safe_title}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    
    print(f"TITLE: {parsed['title']}")
    print(f"TAGS: {', '.join(parsed['tags'])}")
    print(f"BODY_LEN: {len(parsed['body'])} chars")
    print(f"SAVED: {md_path}")
    
except Exception as e:
    print(f"PARSE_ERROR: {e}")
    print("RAW:", result[:2000])
