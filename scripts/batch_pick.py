#!/usr/bin/env python3
"""批量生成5篇AI科技文章 — 采集热点 → LLM精选5篇 → 逐篇生成 → 图片下载 → HTML输出"""
import sys, os, json, re, time, random, logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collector import collect_all, _load_config
from processor import _call_llm, process_article

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
    'security': [
        'https://images.pexels.com/photos/60504/security-protection-anti-virus-software-60504.jpeg',
        'https://images.pexels.com/photos/5380642/pexels-photo-5380642.jpeg',
        'https://images.pexels.com/photos/5240547/pexels-photo-5240547.jpeg',
        'https://images.pexels.com/photos/5952651/pexels-photo-5952651.jpeg',
    ],
}

_theme_idx = {k: random.randint(0, len(v)-1) for k, v in THEME_IMAGES.items()}

KEYWORD_THEME_MAP = {
    'ai': 'ai_general', 'artificial+intelligence': 'ai_general', 'robot': 'ai_general',
    'machine+learning': 'ai_general', 'neural': 'ai_general', 'brain': 'ai_general',
    'code': 'coding', 'programming': 'coding', 'developer': 'coding', 'software': 'coding',
    'terminal': 'coding', 'coding': 'coding', 'github': 'coding',
    'chip': 'hardware', 'hardware': 'hardware', 'server': 'hardware', 'gpu': 'hardware',
    'phone': 'hardware', 'circuit': 'hardware', 'device': 'hardware',
    'math': 'research', 'research': 'research', 'paper': 'research', 'science': 'research',
    'chat': 'chatbot', 'conversation': 'chatbot', 'assistant': 'chatbot', 'bot': 'chatbot',
    'business': 'business', 'company': 'business', 'market': 'business', 'competition': 'business',
    'team': 'business', 'office': 'business', 'strategy': 'business',
    'design': 'design', 'creative': 'design', 'ui': 'design', 'art': 'design',
    'security': 'security', 'privacy': 'security', 'hack': 'security',
}

def get_theme_image(theme):
    if theme not in THEME_IMAGES:
        theme = 'ai_general'
    imgs = THEME_IMAGES[theme]
    idx = _theme_idx.get(theme, 0) % len(imgs)
    _theme_idx[theme] = idx + 1
    return imgs[idx] + '?auto=compress&cs=tinysrgb&fit=crop&h=400&w=800'

def keyword_to_theme(keyword):
    kw = keyword.lower().replace('-', '+').replace('_', '+')
    for k, theme in KEYWORD_THEME_MAP.items():
        if k in kw:
            return theme
    return 'ai_general'

def download_image(url, path):
    import urllib.request
    proxy = urllib.request.ProxyHandler({'http': 'http://127.0.0.1:7890', 'https': 'http://127.0.0.1:7890'})
    opener = urllib.request.build_opener(proxy)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    resp = opener.open(req, timeout=20)
    data = resp.read()
    if len(data) > 5000:
        with open(path, 'wb') as f:
            f.write(data)
        return len(data)
    return 0


# ── 历史记录 ─────────────────────────────────────────────
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


# ── LLM 精选 5 篇 ────────────────────────────────────────

SELECT_PROMPT = """你是公众号「极话」的主编。从以下候选热点中，选出5篇最适合今天发布的文章。

## 选题标准
1. 话题新鲜度：优先当天/近两天的热点
2. 读者吸引力：有争议性、颠覆性、或实用性的优先
3. 可写性：信息量足够撑起一篇深度文章
4. 多样性：5篇文章话题不要太重复，覆盖不同领域（产品/技术/行业/应用/研究）
5. 避免重复：以下话题最近已经发过，不要再选
{history_str}

## 候选热点
{candidates}

## 输出格式（严格JSON数组）
[{{"index": 0, "reason": "选择理由"}}, {{"index": 3, "reason": "选择理由"}}, ...]

index 是候选列表的序号（从0开始），选5篇。只输出JSON数组。"""


def select_top5(articles, config, history):
    candidates = []
    for i, a in enumerate(articles):
        candidates.append(f"{i}. [{a['source_name']}] {a['title']} (⬆️{a.get('score',0)} 💬{a.get('comments',0)})\n   摘要: {a.get('summary','')[:150]}")
    
    recent = history[-20:] if history else []
    history_str = "\n".join(f"  - {h.get('title','')}" for h in recent) if recent else "  (无历史记录)"
    
    prompt = SELECT_PROMPT.format(
        candidates="\n".join(candidates),
        history_str=history_str,
    )
    
    result = _call_llm(prompt, config, max_tokens=500)
    
    json_str = result.strip()
    if json_str.startswith("```"):
        json_str = re.sub(r'^```(?:json)?\s*', '', json_str)
        json_str = re.sub(r'\s*```$', '', json_str)
    
    parsed = json.loads(json_str)
    selected = []
    for item in parsed[:5]:
        idx = int(item["index"])
        if 0 <= idx < len(articles):
            logger.info(f"🎯 精选 [{idx}] {articles[idx]['title'][:50]}")
            logger.info(f"   理由: {item.get('reason', '')}")
            selected.append(articles[idx])
    
    return selected


def clean_body_duplication(body, title, summary):
    """清除 body 中与模板重复的元素"""
    # 去掉 body 开头重复的标题和摘要
    body = re.sub(r'^\s*\n#\s+[^\n]+\n+>\s*💡[^\n]*\n*', '\n', body, count=1)
    # 去掉 body 中的极话分隔线
    body = re.sub(r'^━━━━━━\s*极话\s*·\s*JIHUA\s*━━━━━━\s*$', '', body, flags=re.MULTILINE)
    # 去掉 body 尾部的品牌块
    body = re.sub(r'\n---\s*\n+\*?\*?极话\*?\*?\s*[\|｜]?\s*科技前沿.*?(?:关注「极话」不迷路|每天.*?资讯.*?⭐)\s*\n*', '', body, flags=re.DOTALL)
    body = re.sub(r'\n\*?\*?极话\*?\*?\s*\n\s*科技前沿.*?关注「极话」不迷路\s*\n*', '', body, flags=re.DOTALL)
    body = re.sub(r'\n---\s*\n+\*关注「极话」.*?\*\s*\n*', '', body, flags=re.DOTALL)
    # 最后清理残余
    body = re.sub(r'关注「极话」不迷路', '', body)
    return body.strip()


# ── 主流程 ────────────────────────────────────────────────

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    logger.info(f"📰 极话批量精选 — {today} — 目标5篇")
    
    config = _load_config()
    
    # 1. 采集热点
    logger.info("🔍 采集热点...")
    articles = collect_all(config)
    if not articles:
        logger.error("❌ 没有采集到任何文章")
        sys.exit(1)
    logger.info(f"   找到 {len(articles)} 篇候选")
    
    # 2. LLM 精选 5 篇
    history = load_history()
    selected = select_top5(articles, config, history)
    if not selected:
        logger.error("❌ LLM 选题失败")
        sys.exit(1)
    logger.info(f"\n{'='*50}")
    logger.info(f"📋 已选 {len(selected)} 篇，开始逐篇生成...")
    logger.info(f"{'='*50}\n")
    
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "wechat")
    img_dir = os.path.join(output_dir, "images")
    os.makedirs(img_dir, exist_ok=True)
    
    results = []
    
    for art_idx, article in enumerate(selected, 1):
        logger.info(f"\n{'─'*40}")
        logger.info(f"📝 [{art_idx}/5] 生成: {article['title'][:50]}...")
        
        try:
            # 3. LLM 生成深度文章（含去AI味）
            result = process_article(article, config)
            if not result or not result.get("body"):
                logger.warning(f"   ⚠️ 文章 {art_idx} 生成失败，跳过")
                continue
            
            body = result["body"]
            title = result["title"]
            summary = result.get("summary", "")
            tags = result.get("tags", [])
            
            logger.info(f"   标题: {title}")
            logger.info(f"   字数: {len(body)}")
            
            # 4. 下载图片
            logger.info(f"   🖼️ 下载配图...")
            img_counter = [0]
            def replace_img(m, _art_idx=art_idx, _counter=img_counter):
                alt = m.group(1)
                kw = m.group(2)
                _counter[0] += 1
                
                theme = keyword_to_theme(kw)
                url = get_theme_image(theme)
                local_name = f"batch_{today.replace('-','')}_{_art_idx:02d}_{_counter[0]:02d}.jpg"
                local_path = os.path.join(img_dir, local_name)
                
                try:
                    size = download_image(url, local_path)
                    if size > 0:
                        logger.info(f"      📷 {_counter[0]}: {alt[:25]} [{theme}] ({size//1024}KB)")
                        return f"![{alt}](images/{local_name})"
                    else:
                        return f"<!-- 图片: {alt} -->"
                except Exception as e:
                    logger.warning(f"      ⚠️ 图片下载失败: {e}")
                    return f"<!-- 图片: {alt} -->"
            
            body = re.sub(r'!\[([^\]]*)\]\(img:([^)]+)\)', replace_img, body)
            
            # 清除重复元素
            body = clean_body_duplication(body, title, summary)
            
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
            md_name = f"{art_idx:02d}_{safe_title}.md"
            md_path = os.path.join(output_dir, md_name)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md)
            logger.info(f"   📝 MD: {md_name}")
            
            results.append({
                "idx": art_idx,
                "title": title,
                "body_len": len(body),
                "tags": tags,
                "md_path": md_path,
                "md_name": md_name,
            })
            
            # 记录历史
            history.append({
                "date": today,
                "title": title,
                "source": article.get("source_name", ""),
                "original_title": article.get("title", ""),
                "tags": tags,
            })
            
        except Exception as e:
            logger.error(f"   ❌ 文章 {art_idx} 处理异常: {e}")
            import traceback
            traceback.print_exc()
            continue
        
        # 避免 rate limit
        if art_idx < len(selected):
            logger.info("   ⏳ 等待2秒...")
            time.sleep(2)
    
    # 保存历史
    save_history(history)
    
    # 6. 批量转 HTML
    if results:
        logger.info(f"\n{'='*50}")
        logger.info("🔄 批量转换为公众号 HTML...")
        import subprocess
        script_dir = os.path.dirname(os.path.abspath(__file__))
        subprocess.run([sys.executable, os.path.join(script_dir, "md_to_wechat.py")], check=True)
    
    # 汇总
    logger.info(f"\n{'='*50}")
    logger.info(f"✅ 批量生成完成！共 {len(results)}/5 篇")
    logger.info(f"{'='*50}")
    for r in results:
        logger.info(f"   {r['idx']}. {r['title']} ({r['body_len']}字) 🏷️{', '.join(r['tags'][:3])}")
    
    logger.info(f"\n📁 输出目录: {output_dir}")
    logger.info(f"💡 打开 HTML → 复制标题 → 复制正文 → 粘贴到公众号发布")


if __name__ == "__main__":
    main()
