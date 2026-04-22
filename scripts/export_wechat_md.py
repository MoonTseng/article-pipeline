#!/usr/bin/env python3
"""
公众号文章导出工具 — 从 articles JSON 挑选文章 → 生成公众号风格 Markdown → Typora 打开审阅

用法:
  # 交互选择文章
  python scripts/export_wechat_md.py

  # 直接指定序号(逗号分隔)
  python scripts/export_wechat_md.py --pick 1,3,5

  # 导出全部
  python scripts/export_wechat_md.py --all
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output" / "wechat"
ARTICLES_DIR = PROJECT_ROOT / "output" / "articles"

# === 品牌素材路径 ===
BRAND_DIR = PROJECT_ROOT / "brand"

# 公众号「极话」的 Markdown 模板 — 品牌化版本
TEMPLATE = """\
<!-- 极话 · JIHUA — 科技前沿 · AI洞察 · 深度解读 -->

![极话 · 头图](header_image)

# {title}

> 💡 {summary}

<p style="text-align:center;color:#00D4FF;font-size:12px;">━━━━━━  极话 · JIHUA  ━━━━━━</p>

{body}

<p style="text-align:center;color:#00D4FF;font-size:12px;">━━━━━━  ━━━━━━  ━━━━━━</p>

📌 **来源**: {source}
🔗 **原文**: [{source_url_short}]({source_url})
🏷️ **标签**: {tags}

---

<div style="background:#0D1B2A;padding:20px;border-radius:8px;text-align:center;margin:20px 0;">
<p style="color:#FFFFFF;font-size:24px;font-weight:bold;margin:0;">极话</p>
<p style="color:#00D4FF;font-size:14px;margin:5px 0;">科技前沿 · AI洞察 · 深度解读</p>
<p style="color:#A0AAB4;font-size:12px;margin:5px 0;">每天 get 最前沿的科技资讯</p>
<p style="color:#F0F0F0;font-size:16px;margin:10px 0;">⭐ 关注「极话」不迷路</p>
</div>
"""


def load_articles(date_str: str = None) -> list[dict]:
    """加载指定日期的文章（自动去重）"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    path = ARTICLES_DIR / f"articles_{date_str}.json"
    if not path.exists():
        print(f"❌ 文件不存在: {path}")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        articles = json.load(f)

    # 过滤掉 status != "processed" 的（如果有 status 字段）
    processed = [a for a in articles if a.get("status") in ("processed", None)]

    # 去重：同一 source_url 只保留 body 最长的
    seen = {}
    for a in processed:
        url = a.get("source_url", "")
        body_len = len(a.get("body", ""))
        if url not in seen or body_len > len(seen[url].get("body", "")):
            seen[url] = a
    deduped = list(seen.values())

    # 过滤掉内容过短的废品（< 500 字）
    quality = [a for a in deduped if len(a.get("body", "")) >= 500]

    if len(quality) < len(processed):
        print(f"  🔄 去重: {len(processed)} → {len(deduped)} 篇 | 过滤短文: {len(deduped)} → {len(quality)} 篇")

    return quality


def show_menu(articles: list[dict]):
    """显示文章列表供用户选择"""
    print(f"\n📰 共 {len(articles)} 篇文章:\n")
    for i, a in enumerate(articles, 1):
        tags = ", ".join(a.get("tags", [])[:3])
        score = a.get("score", "?")
        print(f"  [{i:2d}] [{score}分] {a['title'][:50]}")
        print(f"       {tags} | {a.get('source', '')}")
    print()


def resolve_image_placeholders(body: str) -> str:
    """将 ![描述](img:关键词) 替换为 Pexels 高质量配图（本地缓存）"""
    img_cache_dir = OUTPUT_DIR / "images"
    img_cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Pexels API — 免费、高质量、支持中文搜索
    PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")
    used_images = set()  # 同一篇文章内去重
    
    def fetch_pexels(keyword: str, idx: int) -> str | None:
        """从 Pexels 搜索并下载配图，返回本地路径"""
        if not PEXELS_API_KEY:
            return None
        
        # 缓存：同关键词不重复下载
        safe_kw = re.sub(r'[^a-zA-Z0-9_-]', '_', keyword)[:50]
        cached = img_cache_dir / f"pexels_{safe_kw}.jpg"
        if cached.exists() and cached.stat().st_size > 5000:
            return str(cached)
        
        try:
            import httpx
            resp = httpx.get(
                "https://api.pexels.com/v1/search",
                params={"query": keyword, "per_page": 5, "orientation": "landscape"},
                headers={"Authorization": PEXELS_API_KEY},
                timeout=15,
                proxy=os.environ.get("https_proxy"),
            )
            resp.raise_for_status()
            photos = resp.json().get("photos", [])
            
            # 去重：跳过已使用的图
            for photo in photos:
                photo_id = photo["id"]
                if photo_id not in used_images:
                    img_url = photo["src"]["large"]  # 940px 宽，适合公众号
                    used_images.add(photo_id)
                    
                    # 下载
                    img_resp = httpx.get(img_url, timeout=20, proxy=os.environ.get("https_proxy"))
                    if img_resp.status_code == 200 and len(img_resp.content) > 5000:
                        cached.write_bytes(img_resp.content)
                        return str(cached)
            
        except Exception as e:
            print(f"  ⚠️ Pexels配图失败({keyword}): {e}")
        
        return None
    
    img_counter = [0]
    
    def replace_img(match):
        alt = match.group(1)
        keyword = match.group(2)
        img_counter[0] += 1
        
        # 1. 尝试 Pexels API
        local_path = fetch_pexels(keyword, img_counter[0])
        if local_path:
            print(f"  📷 配图{img_counter[0]}: {alt} → Pexels({keyword})")
            return f"![{alt}]({local_path})"
        
        # 2. Fallback: Unsplash source（不稳定但免费无需key）
        query = urllib.parse.quote(keyword)
        fallback_url = f"https://source.unsplash.com/800x400/?{query}"
        print(f"  📷 配图{img_counter[0]}: {alt} → Unsplash fallback")
        return f"![{alt}]({fallback_url})"

    return re.sub(r'!\[([^\]]*)\]\(img:([^)]+)\)', replace_img, body)


def generate_header_image(title: str, index: int) -> Path:
    """为文章动态生成品牌化头图"""
    try:
        # 导入品牌生成模块
        sys.path.insert(0, str(BRAND_DIR))
        from generate_brand import create_article_header_gen
        from datetime import datetime as dt

        img = create_article_header_gen(
            title=title,
            subtitle="极话 · 科技前沿",
            date=dt.now().strftime("%Y.%m.%d"),
        )
        img_dir = OUTPUT_DIR / "images"
        img_dir.mkdir(parents=True, exist_ok=True)
        img_path = img_dir / f"header_{index:02d}.png"
        img.save(str(img_path), "PNG")
        return img_path
    except Exception as e:
        print(f"  ⚠️  头图生成失败: {e}")
        # fallback: 使用静态模板
        static = BRAND_DIR / "article_header_template.png"
        if static.exists():
            return static
        return None


def export_article(article: dict, index: int) -> Path:
    """导出单篇文章为 Markdown（品牌化版本）"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    title = article["title"]
    body = article.get("body", "")
    summary = article.get("summary", "")
    source = article.get("source", "")
    source_url = article.get("source_url", "")
    tags = " ".join(f"#{t}" for t in article.get("tags", []))

    # 处理图片占位符 → Unsplash 真实图片
    body = resolve_image_placeholders(body)

    # 截断 URL 用于显示
    source_url_short = source_url[:60] + "..." if len(source_url) > 60 else source_url

    # 生成品牌化头图
    header_img = generate_header_image(title, index)
    header_ref = str(header_img) if header_img else ""

    md = TEMPLATE.format(
        title=title,
        summary=summary,
        body=body,
        source=source,
        source_url=source_url,
        source_url_short=source_url_short,
        tags=tags,
    )
    # 替换头图占位符
    if header_ref:
        md = md.replace("![极话 · 头图](header_image)", f"![极话 · 头图]({header_ref})")
    else:
        md = md.replace("![极话 · 头图](header_image)\n\n", "")

    # 文件名: 序号_标题前15字
    safe_title = "".join(c for c in title[:15] if c.isalnum() or c in "- ").strip()
    filename = f"{index:02d}_{safe_title}.md"
    path = OUTPUT_DIR / filename

    with open(path, "w", encoding="utf-8") as f:
        f.write(md)

    return path


def open_in_typora(paths: list[Path]):
    """用 Typora 打开 Markdown 文件"""
    for p in paths:
        try:
            subprocess.Popen(["open", "-a", "Typora", str(p)])
            print(f"  📝 Typora 打开: {p.name}")
        except FileNotFoundError:
            # fallback: 直接 open
            subprocess.Popen(["open", str(p)])
            print(f"  📝 已打开: {p.name}")


def main():
    parser = argparse.ArgumentParser(description="公众号文章导出工具")
    parser.add_argument("--date", help="日期 YYYY-MM-DD (默认今天)")
    parser.add_argument("--pick", help="文章序号，逗号分隔 (如 1,3,5)")
    parser.add_argument("--all", action="store_true", help="导出全部")
    parser.add_argument("--top", type=int, help="导出得分最高的 N 篇")
    parser.add_argument("--no-open", action="store_true", help="不自动打开 Typora")
    args = parser.parse_args()

    articles = load_articles(args.date)
    if not articles:
        print("❌ 没有可导出的文章")
        sys.exit(1)

    # 确定要导出的文章
    if args.all:
        selected = list(range(len(articles)))
    elif args.top:
        # 按 score 排序取 top N
        scored = sorted(enumerate(articles), key=lambda x: x[1].get("score", 0), reverse=True)
        selected = [i for i, _ in scored[:args.top]]
    elif args.pick:
        selected = [int(x.strip()) - 1 for x in args.pick.split(",")]
    else:
        # 交互模式
        show_menu(articles)
        raw = input("选择要导出的文章序号 (逗号分隔, 如 1,3,5 / all / top5): ").strip()
        if raw.lower() == "all":
            selected = list(range(len(articles)))
        elif raw.lower().startswith("top"):
            n = int(raw[3:]) if len(raw) > 3 else 5
            scored = sorted(enumerate(articles), key=lambda x: x[1].get("score", 0), reverse=True)
            selected = [i for i, _ in scored[:n]]
        else:
            selected = [int(x.strip()) - 1 for x in raw.split(",")]

    # 导出
    exported = []
    print(f"\n📤 导出 {len(selected)} 篇文章到 {OUTPUT_DIR}/\n")
    for idx in selected:
        if 0 <= idx < len(articles):
            path = export_article(articles[idx], idx + 1)
            exported.append(path)
            print(f"  ✅ [{idx+1}] {articles[idx]['title'][:40]}...")

    # 打开 Typora
    if exported and not args.no_open:
        print()
        open_in_typora(exported)

    print(f"\n✨ 完成! 共导出 {len(exported)} 篇")
    print(f"   审阅后在公众号后台 → 新建图文 → 粘贴 Markdown 内容即可")


if __name__ == "__main__":
    main()
