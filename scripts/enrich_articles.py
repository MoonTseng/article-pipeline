#!/usr/bin/env python3
"""批量优化 wechat 目录下的文章 — 添加图片、表格、丰富排版"""
import sys, json, os, re, glob, urllib.parse, urllib.request, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from processor import _call_llm
from collector import _load_config

config = _load_config()
wechat_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "wechat")
img_dir = os.path.join(wechat_dir, "images")
os.makedirs(img_dir, exist_ok=True)

# 要优化的文章
targets = [
    "19_Anthropic本周发布Cl.md",
    "02_ChatGPT成瘾性使用报告.md",
    "01_小米12 Pro改造AI服务器.md",
    "04_GPT-54 Pro攻克埃尔.md",
    "03_Claude推出Code Ro.md",
    "01_Claude 47突然杀到.md",
]

def download_img(kw, idx, article_idx):
    """按关键词下载图片到本地"""
    local_path = os.path.join(img_dir, f"art{article_idx:02d}_img{idx:02d}.jpg")
    query = urllib.parse.quote(kw)
    urls = [
        f"https://source.unsplash.com/800x400/?{query}",
        f"https://loremflickr.com/800/400/{query}",
    ]
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
            if len(data) > 10000:
                with open(local_path, 'wb') as f:
                    f.write(data)
                return local_path
        except:
            continue
    return None

def enrich_article(filepath, article_idx):
    """读取文章，LLM 重写为富 Markdown"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 提取标题
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    title = title_match.group(1) if title_match else os.path.basename(filepath)
    
    # 去掉 HTML 装饰和旧的图片引用，提取纯文本
    plain = re.sub(r'<[^>]+>', '', content)
    plain = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', plain)
    plain = re.sub(r'<!--.*?-->', '', plain, flags=re.DOTALL)
    plain = plain.strip()
    
    prompt = f"""你是资深科技自媒体编辑，为微信公众号「极话」优化文章。

## 原文
{plain[:3000]}

## 优化要求
1. 保持原文主题和核心信息不变
2. 篇幅扩充到 1500-2500 字
3. 语言自然有趣，去AI味，像真人编辑写的
4. 开头直接切入，不要"在当今""随着"这类套话

## 必须包含的富媒体元素

### 图片（3-5张）
在正文中插入图片占位符，格式：
![图片描述](img:english_keyword)
关键词要跟文章主题高度相关！比如写AI就用ai+robot，写手机就用smartphone+technology

### 表格（至少1个）
用 Markdown 表格做对比、数据展示

### 排版元素
- **加粗** 突出关键信息
- `代码样式` 标注技术术语
- > 引用框放重要观点或数据
- ### 三级标题分段
- 适当用 emoji（不过度）
- 有序/无序列表整理要点

## 输出格式（严格JSON）
{{"title": "优化后的标题（20字以内）", "summary": "一句话摘要（50字以内）", "body": "Markdown正文（含图片表格）", "tags": ["标签1", "标签2", "标签3", "标签4", "标签5"]}}

只输出JSON。"""

    result = _call_llm(prompt, config, max_tokens=16000)
    
    # Parse
    json_str = result.strip()
    if json_str.startswith("```"):
        json_str = re.sub(r'^```(?:json)?\s*', '', json_str)
        json_str = re.sub(r'\s*```$', '', json_str)
    
    parsed = json.loads(json_str)
    body = parsed["body"]
    
    # 下载图片
    img_counter = [0]
    def replace_img(m):
        alt = m.group(1)
        kw = m.group(2)
        img_counter[0] += 1
        local = download_img(kw, img_counter[0], article_idx)
        if local:
            print(f"    📷 图片{img_counter[0]}: {alt} (kw: {kw})")
            return f"![{alt}]({local})"
        else:
            print(f"    ⚠️  图片{img_counter[0]}失败: {alt}")
            return f"<!-- 图片下载失败: {alt} -->"
    
    body = re.sub(r'!\[([^\]]*)\]\(img:([^)]+)\)', replace_img, body)
    
    # 构建完整 Markdown
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
    
    # 覆盖原文件
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(md)
    
    return parsed["title"], len(parsed["body"])


# 主循环
print(f"🔄 批量优化 {len(targets)} 篇文章...\n")
for i, fname in enumerate(targets):
    fpath = os.path.join(wechat_dir, fname)
    if not os.path.exists(fpath):
        print(f"  ⚠️  文件不存在: {fname}")
        continue
    
    print(f"[{i+1}/{len(targets)}] 优化: {fname}")
    try:
        new_title, body_len = enrich_article(fpath, i+1)
        print(f"  ✅ {new_title} ({body_len}字)\n")
    except Exception as e:
        print(f"  ❌ 失败: {e}\n")
    
    # 避免API限流
    if i < len(targets) - 1:
        time.sleep(2)

print("🎉 全部完成！")
