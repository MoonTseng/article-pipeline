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
            if bk_type == "anthropic_proxy":
                base_url = bk_cfg.get("base_url", "").rstrip("/")
                url = f"{base_url}/v1/messages"
                resp = httpx.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": bk_cfg.get("api_key", ""),
                        "anthropic-version": "2023-06-01",
                    },
                    json={
                        "model": bk_cfg.get("model", "claude-opus-4-6"),
                        "max_tokens": max_tokens,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                    timeout=120,
                )
                resp.raise_for_status()
                return resp.json().get("content", [{}])[0].get("text", "")

            elif bk_type == "bedrock_proxy":
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

REWRITE_PROMPT = """你是「极话」公众号的资深科技编辑，擅长把前沿技术讲透、讲深。你的读者是对 AI/科技有浓厚兴趣的人，他们不满足于"发生了什么"，更想知道"为什么""怎么做到的""意味着什么"。

## 核心原则
1. **有据可依**：素材中的事实、数据、引用必须准确引用，标注来源（据 {source} 报道）。**严禁捏造**数据、百分比、金额、日期。
2. **深度优先**：对素材涉及的技术概念，你必须用自己的专业知识做深入解释。例如素材提到"RAG"，你要解释 RAG 的原理（检索增强生成：先从知识库检索相关文档，再喂给 LLM 生成回答）、它解决了什么问题、目前的局限性。
3. **禁止注水**：如果一个段落删掉后不影响读者理解，就不该写。每句话要么传递事实，要么传递洞察。

## 原始素材
- **标题**: {title}
- **来源**: {source}
- **原文链接**: {url}
- **摘要**: {summary}
{full_text_section}

## 写作要求

### 标题
15-25字，有信息量，不标题党。好标题 = 核心信息 + 吸引力。
✅「Claude 4 发布：编程能力超 GPT-4，API 价格砍半」
❌「AI界又炸了！这个模型太强了吧」

### 正文结构（必须包含以下四层）

**第一层：新闻事实（1-2段）**
- 直接说发生了什么，谁做了什么，关键数据是什么
- 不要铺垫，第一句话就是最重要的信息

**第二层：技术深度解析（这是文章灵魂，至少3-5段）**
- 涉及的核心技术是什么？用通俗语言讲清原理，给类比
- 这项技术和已有方案相比有什么不同？优劣各在哪？
- 关键技术术语必须解释：保留英文 + 括号中文解释 + 1-2句原理说明
- 如果有技术指标（benchmark分数、参数量、推理速度等），做对比表格
- 举具体应用场景让读者感受到"这和我有什么关系"

**第三层：行业背景与竞争格局（2-3段）**
- 这件事放在行业大背景下看，处于什么位置？
- 主要竞争对手的方案是什么？列出具体产品/公司/数据做对比
- 引用素材中的社区讨论观点（如果有），呈现不同立场

**第四层：前瞻分析（1-2段）**
- 基于事实的推断，明确标注"笔者认为"
- 对普通用户/开发者/行业分别意味着什么
- 短期（3-6个月）和中期（1-2年）可能的影响

### 字数要求
- 素材充足（有 full_text）：1500-2500 字，往深度写
- 素材有限（只有摘要）：1000-1500 字，用你的专业知识补充技术背景和行业分析，但要明确区分"素材中的事实"和"编辑的专业补充"

### 深度写作技巧
- **解释原理时用类比**：如"Transformer 的注意力机制就像一个高效的图书管理员，能在海量书架中精准找到你需要的那几本"
- **用具体数字说话**：不说"性能大幅提升"，而说"推理速度从 50 tokens/s 提升到 120 tokens/s"
- **对比才有感知**：不说"参数量很大"，而说"参数量达到 700B，是 GPT-3 的 4 倍"
- **给出应用场景**：不说"可用于多个领域"，而说"一个直接的应用：开发者可以用它在 5 分钟内搭建一个能回答公司内部文档问题的 chatbot"

### 排版
- ## 二级标题分段（标题要有信息量，不要"技术分析""市场影响"这种废话标题）
- 有数据对比时用 Markdown 表格
- 关键数据/金句用 > 引用块
- **加粗** 关键信息，`代码块` 标技术术语
- 每篇插入 2-3 个图片占位：![描述](img:english-keyword)

## 去AI味（严格遵守）
禁止：「在当今」「随着...的发展」「众所周知」「此外」「综上所述」「具有重要意义」「引发广泛关注」「不容忽视」「值得注意的是」「总的来说」「毫无疑问」
必须：句子长短交替、有态度有观点、敢吐槽、用具体数据而非空洞形容词、用口语化的过渡而非书面连接词

## 输出格式

===TITLE===
文章标题
===SUMMARY===
一句话摘要（50字以内）
===TAGS===
标签1, 标签2, 标签3
===BODY===
正文（Markdown格式，不要包裹在代码块里）"""


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
- 按以下分隔符格式输出：

===TITLE===
修改后的标题
===BODY===
修改后的正文

严格按分隔符格式，不要用JSON。"""


def _parse_delimited_output(text: str) -> dict:
    """解析分隔符格式的 LLM 输出"""
    result = {}
    # 支持的分隔符
    sections = re.split(r'===(\w+)===', text)
    # sections: ['前导文字', 'TITLE', '标题内容', 'SUMMARY', '摘要内容', ...]
    for i in range(1, len(sections) - 1, 2):
        key = sections[i].strip().lower()
        value = sections[i + 1].strip()
        result[key] = value

    if 'tags' in result:
        # "标签1, 标签2, 标签3" -> ["标签1", "标签2", "标签3"]
        result['tags'] = [t.strip() for t in result['tags'].split(',') if t.strip()]

    return result


def process_article(article: dict, config: dict) -> dict:
    """用 LLM 改写单篇文章（含去AI味二次审查）"""
    
    # 构建原文正文段落 — 有原文就给 LLM 真实素材
    full_text = article.get("full_text", "")
    if full_text:
        full_text_section = f"\n- **原文正文**（以下是从原文抓取的完整内容，请基于此写作）:\n\n{full_text}"
    else:
        full_text_section = "\n（⚠️ 未能获取原文正文，仅有标题和摘要。请基于有限素材简短写作，不要凭空补充细节）"
    
    prompt = REWRITE_PROMPT.format(
        title=article["title"],
        source=article["source_name"],
        summary=article.get("summary", "(无摘要)"),
        url=article["external_url"],
        full_text_section=full_text_section,
    )

    try:
        result = _call_llm(prompt, config, max_tokens=8000, task="rewrite")

        # 解析分隔符格式
        parsed = _parse_delimited_output(result)

        if not parsed.get("body"):
            raise ValueError("未找到 ===BODY=== 分隔符，输出格式异常")

        # ── 第二步：去AI味审查 ──────────────────────────
        humanize_enabled = config.get("processor", {}).get("humanize", True)
        if humanize_enabled and parsed.get("body"):
            try:
                h_prompt = HUMANIZE_PROMPT.format(
                    title=parsed.get("title", ""),
                    body=parsed.get("body", ""),
                )
                h_result = _call_llm(h_prompt, config, max_tokens=4000)
                h_parsed = _parse_delimited_output(h_result)
                if h_parsed.get("body"):
                    parsed["title"] = h_parsed.get("title", parsed.get("title", ""))
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

    except Exception as e:
        logger.warning(f"   ⚠️ LLM 改写失败: {e}")
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
