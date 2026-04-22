"""AI科技文章采集器 — Reddit / HN / arXiv / RSS + 原文正文抓取"""

import json
import logging
import os
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
import yaml

logger = logging.getLogger(__name__)


# ── 原文正文抓取 ─────────────────────────────────────────
def _fetch_full_text(url: str, proxy: str = None, max_chars: int = 5000) -> str:
    """抓取原文正文（readability 提取）
    
    给 LLM 提供真实事实素材，避免凭空捏造。
    跳过 Reddit/HN 讨论页（这些走各自的 selftext/comment 抓取）。
    失败时静默返回空字符串，不影响采集流程。
    """
    if not url:
        return ""
    # 讨论帖页面不走 readability — Reddit selftext 在 collect_reddit 里直接处理
    if url.startswith("https://www.reddit.com") or url.startswith("https://news.ycombinator.com"):
        return ""
    
    # 浏览器级 UA + 常见 Accept 头，降低 403 概率
    _HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    # 最多重试 2 次（首次 + 1 次重试），应对瞬时网络抖动
    for attempt in range(2):
        try:
            from readability import Document
            import lxml.html
            
            resp = httpx.get(url, timeout=20, proxy=proxy, follow_redirects=True,
                             headers=_HEADERS)
            resp.raise_for_status()
            
            # readability 提取正文
            doc = Document(resp.text)
            content_html = doc.summary()
            
            # HTML → 纯文本
            tree = lxml.html.fromstring(content_html)
            text = tree.text_content().strip()
            
            # 清理：去掉连续空行、多余空白
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r'[ \t]+', ' ', text)
            
            if len(text) < 100:
                return ""  # 太短说明提取失败
            
            return text[:max_chars]
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 429) and attempt == 0:
                time.sleep(2)  # 等一下再试
                continue
            logger.debug(f"   原文抓取失败 HTTP {e.response.status_code} ({url[:60]})")
            return ""
        except Exception as e:
            logger.debug(f"   原文抓取失败({url[:60]}): {e}")
            return ""
    return ""

# ── 代理 ─────────────────────────────────────────────────

def _get_proxy(config: dict) -> str | None:
    """从配置或环境变量获取代理"""
    proxy = config.get("collector", {}).get("proxy")
    if proxy:
        return proxy
    # 从环境变量自动检测
    for env in ("https_proxy", "HTTPS_PROXY", "http_proxy", "HTTP_PROXY"):
        val = os.environ.get(env)
        if val:
            return val
    return None

# ── 通用 ─────────────────────────────────────────────────

def _load_config(config_path: str = None) -> dict:
    if config_path is None:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _is_ai_related(text: str, keywords: list[str] = None) -> bool:
    """检查文本是否与 AI 相关"""
    if keywords is None:
        keywords = [
            "AI", "LLM", "GPT", "Claude", "agent", "machine learning",
            "neural network", "transformer", "openai", "anthropic",
            "deepmind", "mistral", "stable diffusion", "fine-tun",
            "RAG", "embedding", "multimodal", "diffusion model",
            "large language model", "artificial intelligence",
            "chatbot", "copilot", "whisper", "dall-e", "midjourney",
            "hugging face", "langchain", "autogen", "crewai",
        ]
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


# ── Reddit ────────────────────────────────────────────────

def collect_reddit(config: dict) -> list[dict]:
    """从 Reddit 采集 AI 相关热帖"""
    reddit_cfg = config.get("collector", {}).get("sources", {}).get("reddit", {})
    if not reddit_cfg.get("enabled", True):
        return []

    subreddits = reddit_cfg.get("subreddits", ["artificial", "MachineLearning"])
    sort = reddit_cfg.get("sort", "hot")
    limit = reddit_cfg.get("limit", 10)
    max_age = config.get("collector", {}).get("max_age_hours", 24) * 3600

    articles = []
    cutoff = time.time() - max_age

    headers = {"User-Agent": "ArticlePipeline/1.0 (research bot)"}
    proxy = _get_proxy(config)

    for sub in subreddits:
        try:
            url = f"https://www.reddit.com/r/{sub}/{sort}.json?limit={limit}&t=day"
            resp = httpx.get(url, headers=headers, timeout=15, proxy=proxy)
            resp.raise_for_status()
            data = resp.json()

            for post in data.get("data", {}).get("children", []):
                pd = post.get("data", {})
                created = pd.get("created_utc", 0)
                if created < cutoff:
                    continue

                title = pd.get("title", "")
                selftext = pd.get("selftext", "")[:500]
                url_val = pd.get("url", "")
                permalink = f"https://reddit.com{pd.get('permalink', '')}"
                score = pd.get("score", 0)
                num_comments = pd.get("num_comments", 0)

                # 只保留 AI 相关
                if not _is_ai_related(title + " " + selftext):
                    continue

                # 判断是否是链接帖
                is_link = not url_val.startswith("https://www.reddit.com")

                # Reddit selftext 就是讨论帖的"正文"，直接作为 full_text 素材
                full_selftext = pd.get("selftext", "")
                # 有些帖子 selftext 很长（几千字），截取给 LLM
                full_text = full_selftext.strip()[:5000] if len(full_selftext.strip()) >= 100 else ""

                article_data = {
                    "source": "reddit",
                    "source_name": f"r/{sub}",
                    "title": title,
                    "summary": selftext[:300],
                    "url": permalink,
                    "external_url": url_val if is_link else permalink,
                    "score": score,
                    "comments": num_comments,
                    "created_at": datetime.fromtimestamp(created, tz=timezone.utc).isoformat(),
                    "raw_data": pd,
                }
                if full_text:
                    article_data["full_text"] = full_text
                articles.append(article_data)

            logger.info(f"   📡 r/{sub}: 找到 {len([a for a in articles if a['source_name'] == f'r/{sub}'])} 篇 AI 相关")
        except Exception as e:
            logger.warning(f"   ⚠️ Reddit r/{sub} 采集失败: {e}")

    return articles


# ── Hacker News ───────────────────────────────────────────

def collect_hackernews(config: dict) -> list[dict]:
    """从 HN 采集 AI 相关热帖"""
    hn_cfg = config.get("collector", {}).get("sources", {}).get("hackernews", {})
    if not hn_cfg.get("enabled", True):
        return []

    limit = hn_cfg.get("limit", 30)
    keywords = hn_cfg.get("keywords", ["AI", "LLM", "GPT"])

    articles = []

    try:
        proxy = _get_proxy(config)
        # 获取 top stories
        resp = httpx.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10, proxy=proxy)
        story_ids = resp.json()[:limit]

        for sid in story_ids:
            try:
                item = httpx.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=10, proxy=proxy).json()
                if not item:
                    continue

                title = item.get("title", "")
                url = item.get("url", f"https://news.ycombinator.com/item?id={sid}")
                score = item.get("score", 0)
                descendants = item.get("descendants", 0)
                by = item.get("by", "")
                timestamp = item.get("time", 0)
                # Ask HN / Show HN 帖子有 text 字段（类似 Reddit selftext）
                hn_text = item.get("text", "")

                # AI 相关过滤
                if not _is_ai_related(title, keywords):
                    continue

                article_data = {
                    "source": "hackernews",
                    "source_name": "Hacker News",
                    "title": title,
                    "summary": f"by {by} | {descendants} comments",
                    "url": f"https://news.ycombinator.com/item?id={sid}",
                    "external_url": url,
                    "score": score,
                    "comments": descendants,
                    "created_at": datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(),
                    "raw_data": item,
                }
                # Ask HN / Show HN 帖子的 text 作为 full_text
                if hn_text and len(hn_text) >= 50:
                    # HN text 是 HTML，简单清理
                    clean_text = re.sub(r'<[^>]+>', ' ', hn_text)
                    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                    if len(clean_text) >= 50:
                        article_data["full_text"] = clean_text[:5000]
                articles.append(article_data)
            except Exception:
                continue

        logger.info(f"   📡 Hacker News: 找到 {len(articles)} 篇 AI 相关")
    except Exception as e:
        logger.warning(f"   ⚠️ HN 采集失败: {e}")

    return articles


# ── arXiv ─────────────────────────────────────────────────

def collect_arxiv(config: dict) -> list[dict]:
    """从 arXiv 采集最新 AI 论文"""
    arxiv_cfg = config.get("collector", {}).get("sources", {}).get("arxiv", {})
    if not arxiv_cfg.get("enabled", True):
        return []

    categories = arxiv_cfg.get("categories", ["cs.AI", "cs.CL"])
    max_results = arxiv_cfg.get("max_results", 10)

    articles = []

    try:
        proxy = _get_proxy(config)
        cat_query = "+OR+".join(f"cat:{c}" for c in categories)
        url = (
            f"https://export.arxiv.org/api/query?"
            f"search_query={cat_query}"
            f"&sortBy=submittedDate&sortOrder=descending"
            f"&max_results={max_results}"
        )
        resp = httpx.get(url, timeout=30, follow_redirects=True, proxy=proxy)
        resp.raise_for_status()

        # 简单 XML 解析（不引入额外依赖）
        import re
        entries = re.findall(r'<entry>(.*?)</entry>', resp.text, re.DOTALL)

        for entry in entries:
            title = re.search(r'<title>(.*?)</title>', entry, re.DOTALL)
            summary = re.search(r'<summary>(.*?)</summary>', entry, re.DOTALL)
            link = re.search(r'<id>(.*?)</id>', entry)
            published = re.search(r'<published>(.*?)</published>', entry)
            authors = re.findall(r'<name>(.*?)</name>', entry)

            if not title or not link:
                continue

            title_text = title.group(1).strip().replace("\n", " ")
            summary_text = summary.group(1).strip().replace("\n", " ")[:300] if summary else ""
            author_str = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")

            articles.append({
                "source": "arxiv",
                "source_name": "arXiv",
                "title": title_text,
                "summary": summary_text,
                "url": link.group(1),
                "external_url": link.group(1),
                "score": 0,
                "comments": 0,
                "created_at": published.group(1) if published else "",
                "authors": author_str,
                "raw_data": {"entry": entry[:500]},
            })

        logger.info(f"   📡 arXiv: 找到 {len(articles)} 篇最新论文")
    except Exception as e:
        logger.warning(f"   ⚠️ arXiv 采集失败: {e}")

    return articles


# ── RSS ───────────────────────────────────────────────────

def collect_rss(config: dict) -> list[dict]:
    """从 RSS feeds 采集 AI 文章"""
    rss_cfg = config.get("collector", {}).get("sources", {}).get("rss", {})
    if not rss_cfg.get("enabled", True):
        return []

    feeds = rss_cfg.get("feeds", [])
    max_age = config.get("collector", {}).get("max_age_hours", 24) * 3600
    cutoff = time.time() - max_age

    articles = []

    try:
        import feedparser

        for feed_info in feeds:
            name = feed_info.get("name", "Unknown")
            url = feed_info.get("url", "")
            if not url:
                continue

            try:
                feed = feedparser.parse(url)
                count = 0
                for entry in feed.entries[:10]:
                    # 检查时间
                    published = entry.get("published_parsed") or entry.get("updated_parsed")
                    if published:
                        ts = time.mktime(published)
                        if ts < cutoff:
                            continue

                    title = entry.get("title", "")
                    summary = entry.get("summary", "")[:300]
                    link = entry.get("link", "")

                    # AI 相关过滤
                    if not _is_ai_related(title + " " + summary):
                        continue

                    articles.append({
                        "source": "rss",
                        "source_name": name,
                        "title": title,
                        "summary": summary,
                        "url": link,
                        "external_url": link,
                        "score": 0,
                        "comments": 0,
                        "created_at": entry.get("published", entry.get("updated", "")),
                        "raw_data": {"feed": name},
                    })
                    count += 1

                logger.info(f"   📡 {name}: 找到 {count} 篇 AI 相关")
            except Exception as e:
                logger.warning(f"   ⚠️ RSS {name} 失败: {e}")

    except ImportError:
        logger.warning("   ⚠️ feedparser 未安装，跳过 RSS 采集")

    return articles


# ── X/Twitter (需要 x-cli) ────────────────────────────────

def collect_x(config: dict) -> list[dict]:
    """从 X 搜索 AI 相关推文（需要 x-cli + API 凭证）"""
    import shutil
    if not shutil.which("x-cli"):
        return []

    articles = []
    queries = [
        "AI new release",
        "LLM announcement",
        "GPT Claude Gemini new",
        "AI agent framework",
    ]

    try:
        for q in queries[:2]:
            result = os.popen(f'x-cli -j tweet search "{q}" --max 5 2>/dev/null').read()
            if not result:
                continue
            tweets = json.loads(result)
            for tweet in tweets:
                text = tweet.get("text", tweet.get("body", ""))
                if not _is_ai_related(text):
                    continue
                articles.append({
                    "source": "x",
                    "source_name": "X/Twitter",
                    "title": text[:100],
                    "summary": text[:300],
                    "url": f"https://x.com/i/status/{tweet.get('id', '')}",
                    "external_url": f"https://x.com/i/status/{tweet.get('id', '')}",
                    "score": tweet.get("metrics", {}).get("likes", 0),
                    "comments": tweet.get("metrics", {}).get("replies", 0),
                    "created_at": tweet.get("created_at", ""),
                    "raw_data": tweet,
                })
        logger.info(f"   📡 X/Twitter: 找到 {len(articles)} 篇 AI 相关")
    except Exception as e:
        logger.warning(f"   ⚠️ X 采集失败: {e}")

    return articles


# ── 去重 & 排序 ──────────────────────────────────────────

def deduplicate(articles: list[dict]) -> list[dict]:
    """去重（精确标题 + 相似话题聚合）
    
    两层过滤:
    1. 精确去重：标准化标题完全相同
    2. 话题聚合：标题词袋相似度 > 0.55 的视为同一话题，只保留热度最高的
    """
    # ── 第一层：精确标题去重 ──
    seen = set()
    unique = []
    for a in articles:
        key = re.sub(r'\s+', ' ', a["title"].lower().strip())
        if key in seen:
            continue
        seen.add(key)
        unique.append(a)
    
    # ── 第二层：相似话题聚合 ──
    def _title_words(title: str) -> set:
        """提取标题中的有效词（英文单词 + 中文字）"""
        # 英文转小写、提取词
        words = set(re.findall(r'[a-z][a-z0-9.+-]+', title.lower()))
        # 去掉太短和停用词
        stops = {'the', 'a', 'an', 'is', 'are', 'was', 'for', 'and', 'or', 'to', 'in', 'on',
                 'of', 'by', 'at', 'its', 'it', 'how', 'why', 'what', 'with', 'from', 'has', 'new'}
        words = {w for w in words if w not in stops and len(w) > 1}
        return words
    
    def _similarity(w1: set, w2: set) -> float:
        """Jaccard 相似度"""
        if not w1 or not w2:
            return 0.0
        return len(w1 & w2) / len(w1 | w2)
    
    def _score(a: dict) -> int:
        """计算文章热度（用于聚合时保留最热的）"""
        s = a.get("score", 0)
        c = a.get("comments", 0)
        has_text = 1 if a.get("full_text") else 0
        return s + c * 2 + has_text * 20  # 有正文的优先
    
    # 预计算每篇标题的词集
    word_sets = [_title_words(a["title"]) for a in unique]
    
    # 贪心聚合：遍历每篇，如果和已有簇的代表相似则合并
    clusters = []  # [(代表文章idx, [成员idx...])]
    assigned = set()
    
    for i in range(len(unique)):
        if i in assigned:
            continue
        cluster = [i]
        assigned.add(i)
        for j in range(i + 1, len(unique)):
            if j in assigned:
                continue
            if _similarity(word_sets[i], word_sets[j]) > 0.55:
                cluster.append(j)
                assigned.add(j)
        clusters.append(cluster)
    
    # 每个簇保留热度最高的
    result = []
    merged_count = 0
    for cluster in clusters:
        if len(cluster) == 1:
            result.append(unique[cluster[0]])
        else:
            # 按热度排序，取第一个
            best_idx = max(cluster, key=lambda idx: _score(unique[idx]))
            result.append(unique[best_idx])
            merged_count += len(cluster) - 1
            if len(cluster) > 1:
                titles = [unique[idx]["title"][:40] for idx in cluster]
                logger.info(f"   🔗 合并相似话题({len(cluster)}篇): {titles[0]}...")
    
    if merged_count:
        logger.info(f"   🔗 话题聚合: 合并了 {merged_count} 篇相似文章")
    
    return result


def rank_articles(articles: list[dict], max_articles: int = 10) -> list[dict]:
    """按热度排序，取 top N"""
    def score(a):
        s = a.get("score", 0)
        c = a.get("comments", 0)
        # Reddit/HN 的热度加权
        if a["source"] in ("reddit", "hackernews"):
            return s + c * 2
        elif a["source"] == "arxiv":
            return s + 50  # arXiv 论文保底分
        else:
            return s + 10

    articles.sort(key=score, reverse=True)
    return articles[:max_articles]


# ── 主入口 ────────────────────────────────────────────────

def collect_all(config: dict = None, config_path: str = None) -> list[dict]:
    """采集所有源的 AI 文章，去重 + 排序后返回"""
    if config is None:
        config = _load_config(config_path)

    logger.info("🔍 开始采集 AI 科技文章...")

    all_articles = []

    # 并行采集各个源
    collectors = [
        ("Reddit", collect_reddit),
        ("Hacker News", collect_hackernews),
        ("arXiv", collect_arxiv),
        ("RSS", collect_rss),
        ("X/Twitter", collect_x),
    ]

    for name, fn in collectors:
        try:
            results = fn(config)
            all_articles.extend(results)
            logger.info(f"   ✅ {name}: {len(results)} 篇")
        except Exception as e:
            logger.warning(f"   ⚠️ {name} 采集异常: {e}")

    # 去重
    before = len(all_articles)
    all_articles = deduplicate(all_articles)
    logger.info(f"🔄 去重: {before} → {len(all_articles)}")

    # 排序 + 截取
    max_a = config.get("collector", {}).get("max_articles", 20)
    all_articles = rank_articles(all_articles, max_articles=max_a)

    # ── 抓取原文正文（给 LLM 真实素材）────────────────────
    proxy = _get_proxy(config)
    enrich_count = 0
    for i, article in enumerate(all_articles):
        # 已经有 full_text 的（Reddit selftext / HN text）跳过抓取
        if article.get("full_text"):
            enrich_count += 1
            logger.info(f"   📄 [{i+1}] 自带正文 {len(article['full_text'])} 字: {article['title'][:40]}")
            continue
        
        ext_url = article.get("external_url", "")
        # 对有 external_url 的尝试抓取（包括 HN 链接帖的外链）
        if ext_url and ext_url != article.get("url", ""):
            full_text = _fetch_full_text(ext_url, proxy=proxy)
            if full_text:
                article["full_text"] = full_text
                enrich_count += 1
                logger.info(f"   📄 [{i+1}] 抓到原文 {len(full_text)} 字: {article['title'][:40]}")
            time.sleep(0.5)  # 礼貌爬虫

    logger.info(f"📄 原文抓取: {enrich_count}/{len(all_articles)} 篇成功")
    logger.info(f"✅ 采集完成，共 {len(all_articles)} 篇待处理")
    return all_articles


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    articles = collect_all()
    for i, a in enumerate(articles, 1):
        print(f"\n{i}. [{a['source_name']}] {a['title']}")
        print(f"   🔗 {a['url']}")
        print(f"   ⬆️ {a['score']} | 💬 {a['comments']}")
