#!/usr/bin/env python3
"""每日精选一篇AI科技文章 — 采集热点 → LLM精选+生成 → 图片下载 → HTML输出"""
import sys, os, json, re, time, random, logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collector import collect_all, _load_config
from processor import _call_llm

logging.basicConfig(level=logging.INFO, format="%(asctime)s │ %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

# ── Pexels 图片库（按主题分类）─────────────────────────────
THEME_IMAGES = {
    'ai_general': [
        'https://images.pexels.com/photos/8849295/pexels-photo-8849295.jpeg',
        'https://images.pexels.com/photos/8566526/pexels-photo-8566526.jpeg',
        'https://images.pexels.com/photos/8294619/pexels-photo-8294619.jpeg',
        'https://images.pexels.com/photos/17483874/pexels-photo-17483874.jpeg',
        'https://images.pexels.com/photos/17483868/pexels-photo-17483868.jpeg',
        'https://images.pexels.com/photos/8386440/pexels-photo-8386440.jpeg',
        'https://images.pexels.com/photos/8438918/pexels-photo-8438918.jpeg',
        'https://images.pexels.com/photos/8728560/pexels-photo-8728560.jpeg',
    ],
    'coding': [
        'https://images.pexels.com/photos/546819/pexels-photo-546819.jpeg',
        'https://images.pexels.com/photos/574071/pexels-photo-574071.jpeg',
        'https://images.pexels.com/photos/1181671/pexels-photo-1181671.jpeg',
        'https://images.pexels.com/photos/1181675/pexels-photo-1181675.jpeg',
        'https://images.pexels.com/photos/4164418/pexels-photo-4164418.jpeg',
        'https://images.pexels.com/photos/3861969/pexels-photo-3861969.jpeg',
    ],
    'hardware': [
        'https://images.pexels.com/photos/699122/pexels-photo-699122.jpeg',
        'https://images.pexels.com/photos/1092644/pexels-photo-1092644.jpeg',
        'https://images.pexels.com/photos/1714208/pexels-photo-1714208.jpeg',
        'https://images.pexels.com/photos/325229/pexels-photo-325229.jpeg',
        'https://images.pexels.com/photos/2582937/pexels-photo-2582937.jpeg',
        'https://images.pexels.com/photos/1148820/pexels-photo-1148820.jpeg',
    ],
    'research': [
        'https://images.pexels.com/photos/3729557/pexels-photo-3729557.jpeg',
        'https://images.pexels.com/photos/6256065/pexels-photo-6256065.jpeg',
        'https://images.pexels.com/photos/3862130/pexels-photo-3862130.jpeg',
        'https://images.pexels.com/photos/5428012/pexels-photo-5428012.jpeg',
        'https://images.pexels.com/photos/6238120/pexels-photo-6238120.jpeg',
    ],
    'chatbot': [
        'https://images.pexels.com/photos/8438922/pexels-photo-8438922.jpeg',
        'https://images.pexels.com/photos/7567443/pexels-photo-7567443.jpeg',
        'https://images.pexels.com/photos/4050315/pexels-photo-4050315.jpeg',
        'https://images.pexels.com/photos/5474295/pexels-photo-5474295.jpeg',
        'https://images.pexels.com/photos/5473955/pexels-photo-5473955.jpeg',
    ],
    'business': [
        'https://images.pexels.com/photos/7413915/pexels-photo-7413915.jpeg',
        'https://images.pexels.com/photos/3184292/pexels-photo-3184292.jpeg',
        'https://images.pexels.com/photos/3183150/pexels-photo-3183150.jpeg',
        'https://images.pexels.com/photos/7688336/pexels-photo-7688336.jpeg',
        'https://images.pexels.com/photos/3184291/pexels-photo-3184291.jpeg',
    ],
    'design': [
        'https://images.pexels.com/photos/196644/pexels-photo-196644.jpeg',
        'https://images.pexels.com/photos/326503/pexels-photo-326503.jpeg',
        'https://images.pexels.com/photos/1779487/pexels-photo-1779487.jpeg',
        'https://images.pexels.com/photos/196645/pexels-photo-196645.jpeg',
        'https://images.pexels.com/photos/3153198/pexels-photo-3153198.jpeg',
    ],
}

# 全局 used tracker，避免同一篇文章重复用图
_theme_idx = {k: random.randint(0, len(v)-1) for k, v in THEME_IMAGES.items()}

def get_theme_image(theme):
    """获取下一个主题图片URL"""
    if theme not in THEME_IMAGES:
        theme = 'ai_general'
    imgs = THEME_IMAGES[theme]
    idx = _theme_idx.get(theme, 0) % len(imgs)
    _theme_idx[theme] = idx + 1
    return imgs[idx] + '?auto=compress&cs=tinysrgb&fit=crop&h=400&w=800'

def download_image(url, path):
    """通过代理下载图片"""
    import urllib.request
    proxy = urllib.request.ProxyHandler({'http': 'http://127.0.0.1:7890', 'https': 'http://127.0.0.1:7890'})
    opener = urllib.request.build_opener(proxy)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    resp = opener.open(req, timeout=20)
    data = resp.read()
    with open(path, 'wb') as f:
        f.write(data)
    return len(data)


# ── 历史记录（防重复选题）─────────────────────────────────
HISTORY_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "history.json")

def load_history():
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, encoding='utf-8') as f:
            return json.load(f)
    return []

def save_history(history):
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# ── LLM 精选 ──────────────────────────────────────────────

SELECT_PROMPT = """你是公众号「极话」的主编。从以下候选热点中，选出1篇最适合今天发布的文章。

## 选题标准
1. 话题新鲜度：优先当天/近两天的热点
2. 读者吸引力：有争议性、颠覆性、或实用性的优先
3. 可写性：信息量足够撑起一篇深度文章
4. 避免重复：以下话题最近已经发过，不要再选
{history_str}

## 候选热点
{candidates}

## 输出格式（严格JSON）
{{"index": 0, "reason": "选择理由（一句话）"}}

index 是候选列表的序号（从0开始）。只输出JSON。"""


def select_best_article(articles, config, history):
    """用 LLM 从候选中精选1篇"""
    # 格式化候选
    candidates = []
    for i, a in enumerate(articles):
        candidates.append(f"{i}. [{a['source_name']}] {a['title']} (⬆️{a.get('score',0)} 💬{a.get('comments',0)})\n   摘要: {a.get('summary','')[:150]}")
    
    # 历史记录
    recent = history[-20:] if history else []
    history_str = "\n".join(f"  - {h.get('title','')}" for h in recent) if recent else "  (无历史记录)"
    
    prompt = SELECT_PROMPT.format(
        candidates="\n".join(candidates),
        history_str=history_str,
    )
    
    result = _call_llm(prompt, config, max_tokens=200)
    
    # 解析
    json_str = result.strip()
    if json_str.startswith("```"):
        json_str = re.sub(r'^```(?:json)?\s*', '', json_str)
        json_str = re.sub(r'\s*```$', '', json_str)
    
    parsed = json.loads(json_str)
    idx = int(parsed["index"])
    reason = parsed.get("reason", "")
    
    if 0 <= idx < len(articles):
        logger.info(f"🎯 精选: [{idx}] {articles[idx]['title'][:50]}")
        logger.info(f"   理由: {reason}")
        return articles[idx]
    
    # fallback
    return articles[0]


# ── 图片关键词→主题映射 ───────────────────────────────────

KEYWORD_THEME_MAP = {
    'ai': 'ai_general', 'artificial+intelligence': 'ai_general', 'robot': 'ai_general',
    'machine+learning': 'ai_general', 'neural': 'ai_general', 'brain': 'ai_general',
    'code': 'coding', 'programming': 'coding', 'developer': 'coding', 'software': 'coding',
    'terminal': 'coding', 'coding': 'coding', 'github': 'coding',
    'chip': 'hardware', 'hardware': 'hardware', 'server': 'hardware', 'gpu': 'hardware',
    'phone': 'hardware', 'circuit': 'hardware', 'device': 'hardware',
    'math': 'research', 'research': 'research', 'paper': 'research', 'science': 'research',
    'equation': 'research', 'academic': 'research',
    'chat': 'chatbot', 'conversation': 'chatbot', 'assistant': 'chatbot', 'bot': 'chatbot',
    'business': 'business', 'company': 'business', 'market': 'business', 'competition': 'business',
    'team': 'business', 'office': 'business', 'strategy': 'business',
    'design': 'design', 'creative': 'design', 'ui': 'design', 'art': 'design',
}

def keyword_to_theme(keyword):
    """将图片关键词映射到主题"""
    kw = keyword.lower().replace('-', '+').replace('_', '+')
    for k, theme in KEYWORD_THEME_MAP.items():
        if k in kw:
            return theme
    return 'ai_general'


# ── 主流程 ────────────────────────────────────────────────

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    logger.info(f"📰 极话每日精选 — {today}")
    
    config = _load_config()
    
    # 1. 采集热点
    logger.info("🔍 采集热点...")
    articles = collect_all(config)
    if not articles:
        logger.error("❌ 没有采集到任何文章")
        sys.exit(1)
    logger.info(f"   找到 {len(articles)} 篇候选")
    
    # 2. LLM 精选
    history = load_history()
    selected = select_best_article(articles, config, history)
    
    # 3. LLM 生成深度文章
    logger.info("✍️ 生成深度文章...")
    from processor import process_article
    result = process_article(selected, config)
    if not result or not result.get("body"):
        logger.error("❌ 文章生成失败")
        sys.exit(1)
    
    body = result["body"]
    title = result["title"]
    summary = result.get("summary", "")
    tags = result.get("tags", [])
    
    logger.info(f"   标题: {title}")
    logger.info(f"   字数: {len(body)}")
    
    # 4. 下载图片
    logger.info("🖼️ 下载配图...")
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "wechat")
    img_dir = os.path.join(output_dir, "images")
    os.makedirs(img_dir, exist_ok=True)
    
    img_counter = [0]
    def replace_img(m):
        alt = m.group(1)
        kw = m.group(2)
        img_counter[0] += 1
        
        theme = keyword_to_theme(kw)
        url = get_theme_image(theme)
        local_name = f"daily_{today.replace('-','')}_{img_counter[0]:02d}.jpg"
        local_path = os.path.join(img_dir, local_name)
        
        try:
            size = download_image(url, local_path)
            logger.info(f"   📷 {img_counter[0]}: {alt[:30]} [{theme}] ({size//1024}KB)")
            return f"![{alt}]({local_path})"
        except Exception as e:
            logger.warning(f"   ⚠️ 图片下载失败: {e}")
            return f"<!-- 图片: {alt} -->"
    
    body = re.sub(r'!\[([^\]]*)\]\(img:([^)]+)\)', replace_img, body)
    
    # 5. 保存 Markdown
    tags_str = " ".join(f"#{t}" for t in tags)
    md = f"""<!-- 极话 · JIHUA — 科技前沿 · AI洞察 · 深度解读 -->

# {title}

> 💡 {summary}

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
    
    safe_title = "".join(c for c in title[:15] if c.isalnum() or c in "- ").strip()
    md_name = f"{today}_{safe_title}.md"
    md_path = os.path.join(output_dir, md_name)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    logger.info(f"📝 MD 保存: {md_path}")
    
    # 6. 转 HTML
    logger.info("🔄 转换为公众号 HTML...")
    import subprocess
    script_dir = os.path.dirname(os.path.abspath(__file__))
    subprocess.run([sys.executable, os.path.join(script_dir, "md_to_wechat.py")], check=True)
    
    html_name = md_name.replace('.md', '.html')
    html_path = os.path.join(output_dir, "html", html_name)
    
    # 7. 记录历史
    history.append({
        "date": today,
        "title": title,
        "source": selected.get("source_name", ""),
        "original_title": selected.get("title", ""),
        "tags": tags,
    })
    save_history(history)
    
    logger.info(f"\n{'='*50}")
    logger.info(f"✅ 今日精选完成！")
    logger.info(f"   📄 标题: {title}")
    logger.info(f"   📊 字数: {len(body)}")
    logger.info(f"   🏷️ 标签: {', '.join(tags)}")
    logger.info(f"   📝 MD: {md_path}")
    logger.info(f"   🌐 HTML: {html_path}")
    logger.info(f"\n💡 打开 HTML → 复制标题 → 复制正文 → 粘贴到公众号发布")


if __name__ == "__main__":
    main()
