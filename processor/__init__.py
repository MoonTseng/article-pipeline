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


def _call_llm(prompt: str, config: dict, max_tokens: int = 4000) -> str:
    """调用 LLM（支持 bedrock proxy 和 openai）"""
    llm_cfg = config.get("llm", {})
    backend = llm_cfg.get("backend", "bedrock_proxy")

    if backend == "bedrock_proxy":
        bp = llm_cfg.get("bedrock_proxy", {})
        url = f"{bp['base_url']}/model/{bp['model']}/invoke"
        headers = {}
        if bp.get("auth_token"):
            headers["Authorization"] = f"Bearer {bp['auth_token']}"

        resp = httpx.post(
            url,
            headers=headers,
            json={
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("content", [{}])[0].get("text", "")

    elif backend == "openai":
        from openai import OpenAI
        oa = llm_cfg.get("openai", {})
        api_key = oa.get("api_key") or os.getenv("XIAOMI_API_KEY", "")
        base_url = oa.get("base_url") or os.getenv("XIAOMI_BASE_URL", "")
        client = OpenAI(api_key=api_key, base_url=base_url)
        resp = client.chat.completions.create(
            model=oa.get("model", "mimo-v2-pro"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content

    else:
        raise ValueError(f"不支持的 LLM backend: {backend}")


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
- 不要用"在当今"、"随着...的发展"、"众所周知"等AI味表达
- 适当加入口语化表达和网络用语
- 可以有自己的观点和吐槽
- 技术术语保留英文原文 + 中文解释

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


def process_article(article: dict, config: dict) -> dict:
    """用 LLM 改写单篇文章"""
    prompt = REWRITE_PROMPT.format(
        title=article["title"],
        source=article["source_name"],
        summary=article.get("summary", "(无摘要)"),
        url=article["external_url"],
    )

    try:
        result = _call_llm(prompt, config, max_tokens=4000)

        # 解析 JSON（处理 markdown code block）
        json_str = result.strip()
        if json_str.startswith("```"):
            json_str = re.sub(r'^```(?:json)?\s*', '', json_str)
            json_str = re.sub(r'\s*```$', '', json_str)

        parsed = json.loads(json_str)

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
