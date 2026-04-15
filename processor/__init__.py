"""文章处理器 — LLM 翻译/改写 + 去AI味 + 自动生成标题/标签"""

import json
import logging
import os
import re
import time

import httpx
import yaml

logger = logging.getLogger(__name__)


def _load_config(config_path: str = None) -> dict:
    if config_path is None:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _call_llm(prompt: str, config: dict, max_tokens: int = 4000, task: str = "default") -> str:
    """调用 LLM（支持 ollama 本地 + openai 小米/DeepSeek，自动降级）
    
    task 参数用于决定用哪个后端:
      - summarize / tags / categorize / filter → 本地 ollama（省token）
      - rewrite / default → 小米API（高质量），失败自动切 DeepSeek
    """
    llm_cfg = config.get("llm", {})
    
    # 检查是否该任务走本地模型
    local_cfg = llm_cfg.get("local", {})
    use_for = local_cfg.get("use_for", [])
    use_local = task in use_for
    
    if use_local and local_cfg:
        # 本地 Ollama
        ollama_cfg = local_cfg.get("ollama", {})
        base_url = ollama_cfg.get("base_url", "http://127.0.0.1:11434")
        model = ollama_cfg.get("model", "qwen2.5:7b")
        
        resp = httpx.post(
            f"{base_url}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    
    # 构建后端列表：主后端 + 备用后端
    backends = []
    primary = llm_cfg.get("backend", "openai")
    backends.append(("主后端", llm_cfg.get(primary, {}), primary) if primary == "openai" 
                    else ("主后端", llm_cfg.get(primary, {}), primary))
    
    fallback = llm_cfg.get("fallback", {})
    if fallback:
        fb_backend = fallback.get("backend", "openai")
        backends.append(("备用(DeepSeek)", fallback.get(fb_backend, {}), fb_backend))
    
    last_error = None
    for name, bk_cfg, bk_type in backends:
        try:
            if bk_type == "bedrock_proxy":
                url = f"{bk_cfg['base_url']}/model/{bk_cfg['model']}/invoke"
                headers = {}
                if bk_cfg.get("auth_token"):
                    headers["Authorization"] = f"Bearer {bk_cfg['auth_token']}"
                resp = httpx.post(url, headers=headers, json={
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                }, timeout=60)
                resp.raise_for_status()
                return resp.json().get("content", [{}])[0].get("text", "")
            
            elif bk_type == "openai":
                from openai import OpenAI
                api_key = bk_cfg.get("api_key") or os.getenv("XIAOMI_API_KEY", "")
                base_url = bk_cfg.get("base_url", "")
                model = bk_cfg.get("model", "mimo-v2-pro")
                client = OpenAI(api_key=api_key, base_url=base_url)
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                )
                return resp.choices[0].message.content
            
        except Exception as e:
            logger.warning(f"⚠️ {name} 调用失败: {e}，尝试下一个后端...")
            last_error = e
            continue
    
    raise RuntimeError(f"所有LLM后端均失败: {last_error}")


# ── 文章改写 ──────────────────────────────────────────────

REWRITE_PROMPT = """你是一位资深科技媒体编辑，擅长把英文科技资讯改写成中文深度文章。

## 原文信息
- 标题: {title}
- 来源: {source}
- 摘要/正文: {summary}
- 原文链接: {url}

## 任务
根据以上信息，写一篇中文科技短文，要求：

1. **标题**：吸引眼球，15-25字，用数字或疑问句更佳（如「OpenAI又放大招，这次真的不一样」）
2. **正文**：800-1500字
   - 先用一句话概括核心信息
   - 然后展开细节（技术原理、背景、影响）
   - 最后加入你的点评/观点（犀利一点没关系）
3. **标签**：3-5个中文标签

## 风格要求
- 像 36氪 / 量子位 的风格：专业但不枯燥
- 适当加入口语化表达和网络用语
- 可以有自己的观点和吐槽
- 技术术语保留英文原文 + 中文解释

## 去AI味规则（严格遵守）
### 禁用开头词/句式（直接删掉，换成有信息量的开头）
"在当今", "随着...的发展", "众所周知", "不可否认", "值得注意的是", "事实上", "毫无疑问",
"近年来", "伴随着", "不难发现"

### 禁用连接词堆砌
"此外", "与此同时", "不仅如此", "综上所述", "总而言之", "进而", "由此可见"

### 禁用假大空表达
"具有重要意义", "发挥着关键作用", "引发了广泛关注", "开启了新篇章",
"为...提供了新思路", "展现了...的决心", "标志着...的到来"

### 禁用AI高频英文词（如果出现请替换）
pivotal→关键的, landmark→里程碑式的, delve→研究, foster→推动,
underscore→说明, multifaceted→多方面的, nuanced→细致的,
"stands as"→"就是", "serves as"→"就是"

### 必须做到
- 句子长短交替（不要每段4句话齐整整的）
- 有态度有观点，不要四平八稳
- 敢用反问、吐槽、类比
- 数字、对比、具体细节 > 空洞形容词
- 开头直接说事，不要铺垫

## 输出格式（严格JSON）
```json
{{
  "title": "文章标题",
  "summary": "一句话摘要（50字以内）",
  "body": "正文内容（支持markdown格式）",
  "tags": ["标签1", "标签2", "标签3"]
}}
```

只输出JSON，不要其他内容。"""


HUMANIZE_PROMPT = """你是一个去AI味审查员。检查下面这篇中文科技文章，找出所有AI写作痕迹并修正。

## 审查清单
1. 开头是否用了"在当今"、"随着"、"众所周知"等套话？→ 换成直接说事
2. 是否有"此外"、"与此同时"、"综上所述"等连接词堆砌？→ 删掉或换成口语
3. 是否有"具有重要意义"、"引发广泛关注"等假大空？→ 用具体数据或事实替代
4. 段落长度是否太均匀（每段都是3-4句）？→ 打乱节奏
5. 是否缺少作者态度/观点？→ 加入点评、吐槽或类比
6. 句式是否太整齐？→ 长短句交替

## 待审查文章
标题: {title}
正文:
{body}

## 要求
- 直接输出修改后的完整文章
- 只改AI味问题，不要改变事实内容
- 输出纯JSON格式：{{"title": "...", "body": "..."}}
- 只输出JSON，不要其他内容"""


def process_article(article: dict, config: dict) -> dict:
    """用 LLM 改写单篇文章（含去AI味二次审查）"""
    prompt = REWRITE_PROMPT.format(
        title=article["title"],
        source=article["source_name"],
        summary=article.get("summary", "(无摘要)"),
        url=article["external_url"],
    )

    try:
        result = _call_llm(prompt, config, max_tokens=4000, task="rewrite")

        # 解析 JSON（处理 markdown code block）
        json_str = result.strip()
        if json_str.startswith("```"):
            json_str = re.sub(r'^```(?:json)?\s*', '', json_str)
            json_str = re.sub(r'\s*```$', '', json_str)

        parsed = json.loads(json_str)

        # ── 第二步：去AI味审查 ──────────────────────────
        humanize_enabled = config.get("processor", {}).get("humanize", True)
        if humanize_enabled and parsed.get("body"):
            try:
                h_prompt = HUMANIZE_PROMPT.format(
                    title=parsed.get("title", ""),
                    body=parsed.get("body", ""),
                )
                h_result = _call_llm(h_prompt, config, max_tokens=4000)
                h_json = h_result.strip()
                if h_json.startswith("```"):
                    h_json = re.sub(r'^```(?:json)?\s*', '', h_json)
                    h_json = re.sub(r'\s*```$', '', h_json)
                h_parsed = json.loads(h_json)
                if h_parsed.get("body"):
                    parsed["title"] = h_parsed.get("title", parsed["title"])
                    parsed["body"] = h_parsed["body"]
                    logger.info("   🧹 去AI味审查完成")
            except Exception as e:
                logger.warning(f"   ⚠️ 去AI味审查失败(跳过): {e}")

        return {
            "original_title": article["title"],
            "source": article["source_name"],
            "source_url": article["external_url"],
            "title": parsed.get("title", article["title"]),
            "summary": parsed.get("summary", ""),
            "body": parsed.get("body", ""),
            "tags": parsed.get("tags", []),
            "collected_at": article.get("created_at", ""),
            "score": article.get("score", 0),
            "status": "processed",
        }

    except json.JSONDecodeError as e:
        logger.warning(f"   ⚠️ JSON 解析失败: {e}")
        # fallback：直接用原文信息
        return {
            "original_title": article["title"],
            "source": article["source_name"],
            "source_url": article["external_url"],
            "title": article["title"],
            "summary": article.get("summary", "")[:100],
            "body": f"原文摘要：{article.get('summary', '无')}\n\n🔗 原文链接：{article['external_url']}",
            "tags": ["AI", "科技资讯"],
            "collected_at": article.get("created_at", ""),
            "score": article.get("score", 0),
            "status": "fallback",
        }
    except Exception as e:
        logger.warning(f"   ⚠️ LLM 改写失败: {e}")
        return None


def process_all(articles: list[dict], config: dict) -> list[dict]:
    """批量处理所有文章"""
    logger.info(f"✍️ 开始处理 {len(articles)} 篇文章...")

    processed = []
    for i, article in enumerate(articles, 1):
        logger.info(f"   [{i}/{len(articles)}] {article['title'][:50]}...")
        result = process_article(article, config)
        if result:
            processed.append(result)
            logger.info(f"   ✅ {result['title'][:40]}")
        # 避免 rate limit
        time.sleep(1)

    logger.info(f"✅ 处理完成: {len(processed)}/{len(articles)} 篇")
    return processed


# ── 本地模型：文章过滤 ───────────────────────────────────

FILTER_PROMPT = """判断以下AI科技文章是否值得改写发布到中文科技公众号。

文章标题: {title}
来源: {source}
摘要: {summary}

判断标准:
- ✅ 值得: 有实质技术内容、新产品发布、行业重大变化、有讨论价值
- ❌ 跳过: 纯广告、水文、过于专业冷门、与AI/科技无关

只回答 "YES" 或 "NO"，不要解释。"""


def filter_articles_local(articles: list[dict], config: dict) -> list[dict]:
    """用本地模型预过滤文章，筛掉不值得改写的，节省API token"""
    logger.info(f"🔍 本地模型过滤 {len(articles)} 篇文章...")
    
    filtered = []
    for i, article in enumerate(articles, 1):
        prompt = FILTER_PROMPT.format(
            title=article["title"],
            source=article.get("source_name", ""),
            summary=article.get("summary", "")[:300],
        )
        try:
            result = _call_llm(prompt, config, max_tokens=10, task="filter")
            if result and result.strip().upper().startswith("YES"):
                filtered.append(article)
                logger.info(f"   [{i}] ✅ {article['title'][:50]}")
            else:
                logger.info(f"   [{i}] ⏭️  跳过: {article['title'][:50]}")
        except Exception as e:
            logger.warning(f"   [{i}] ⚠️ 过滤失败，保留: {e}")
            filtered.append(article)  # 失败就保留
    
    logger.info(f"🔍 过滤后: {len(filtered)}/{len(articles)} 篇保留")
    return filtered


# ── 保存 ──────────────────────────────────────────────────

def save_articles(articles: list[dict], output_dir: str = None) -> str:
    """保存处理后的文章到 JSON"""
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "articles")

    os.makedirs(output_dir, exist_ok=True)

    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(output_dir, f"articles_{today}.json")

    # 如果已存在，合并
    existing = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            existing = json.load(f)

    # 用 title 去重
    seen = {a["title"] for a in existing}
    for a in articles:
        if a["title"] not in seen:
            existing.append(a)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    logger.info(f"💾 保存 {len(existing)} 篇文章到 {path}")
    return path
