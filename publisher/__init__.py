"""发布器 — 微信公众号 + 头条号"""

import json
import logging
import os
import time
from datetime import datetime

import httpx
import yaml

logger = logging.getLogger(__name__)


def _load_config(config_path: str = None) -> dict:
    if config_path is None:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ══════════════════════════════════════════════════════════
#  微信公众号
# ══════════════════════════════════════════════════════════

class WeChatPublisher:
    """微信公众号发布（通过公众号平台 API）"""

    BASE_URL = "https://api.weixin.qq.com"

    def __init__(self, config: dict):
        pub_cfg = config.get("publisher", {}).get("wechat", {})
        self.app_id = pub_cfg.get("app_id", "")
        self.app_secret = pub_cfg.get("app_secret", "")
        self._access_token = None
        self._token_expires = 0

    def _get_access_token(self) -> str:
        """获取 access_token"""
        if self._access_token and time.time() < self._token_expires:
            return self._access_token

        resp = httpx.get(
            f"{self.BASE_URL}/cgi-bin/token",
            params={
                "grant_type": "client_credential",
                "appid": self.app_id,
                "secret": self.app_secret,
            },
            timeout=10,
        )
        data = resp.json()
        if "access_token" not in data:
            raise RuntimeError(f"获取 access_token 失败: {data}")

        self._access_token = data["access_token"]
        self._token_expires = time.time() + data.get("expires_in", 7200) - 300
        return self._access_token

    def upload_draft(self, article: dict) -> dict:
        """上传草稿"""
        token = self._get_access_token()

        # 构建图文内容
        content = self._build_wechat_content(article)

        payload = {
            "articles": [{
                "title": article["title"],
                "author": "AI科技日报",
                "content": content,
                "content_source_url": article.get("source_url", ""),
                "digest": article.get("summary", "")[:120],
                "show_cover_pic": 0,
                "need_open_comment": 1,
                "only_fans_can_comment": 0,
            }]
        }

        resp = httpx.post(
            f"{self.BASE_URL}/cgi-bin/draft/add",
            params={"access_token": token},
            json=payload,
            timeout=30,
        )
        result = resp.json()

        if "media_id" in result:
            logger.info(f"   📤 公众号草稿上传成功: media_id={result['media_id']}")
            return {"success": True, "media_id": result["media_id"]}
        else:
            logger.error(f"   ❌ 公众号上传失败: {result}")
            return {"success": False, "error": result}

    def publish(self, media_id: str) -> dict:
        """发布草稿"""
        token = self._get_access_token()
        resp = httpx.post(
            f"{self.BASE_URL}/cgi-bin/freepublish/submit",
            params={"access_token": token},
            json={"media_id": media_id},
            timeout=30,
        )
        result = resp.json()

        if result.get("errcode", 0) == 0:
            logger.info(f"   🎉 公众号发布成功! publish_id={result.get('publish_id')}")
            return {"success": True, "publish_id": result.get("publish_id")}
        else:
            logger.error(f"   ❌ 公众号发布失败: {result}")
            return {"success": False, "error": result}

    def _build_wechat_content(self, article: dict) -> str:
        """构建公众号 HTML 内容"""
        body = article.get("body", "")

        # 简单 markdown → HTML 转换
        body = body.replace("\n\n", "</p><p>")
        body = body.replace("\n", "<br>")
        body = f"<p>{body}</p>"

        # 添加来源信息
        footer = f"""
<br><br>
<hr>
<p style="color: #888; font-size: 12px;">
📌 来源：{article.get('source', 'AI科技日报')}<br>
🔗 原文：<a href="{article.get('source_url', '#')}">{article.get('source_url', '')}</a><br>
📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}
</p>"""

        return body + footer

    def is_configured(self) -> bool:
        return bool(self.app_id and self.app_secret)


# ══════════════════════════════════════════════════════════
#  头条号 (今日头条)
# ══════════════════════════════════════════════════════════

class ToutiaoPublisher:
    """头条号发布（通过头条开放平台 API）"""

    BASE_URL = "https://open.toutiao.com"

    def __init__(self, config: dict):
        pub_cfg = config.get("publisher", {}).get("toutiao", {})
        self.cookie_file = pub_cfg.get("cookie_file", "toutiao_cookies.txt")
        self.default_category = pub_cfg.get("default_category", "科技")
        self._cookies = {}

    def _load_cookies(self) -> dict:
        """从文件加载 cookies"""
        cookie_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            self.cookie_file
        )
        if not os.path.exists(cookie_path):
            logger.warning(f"   ⚠️ 头条 cookies 文件不存在: {cookie_path}")
            return {}

        cookies = {}
        with open(cookie_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, _, val = line.partition("=")
                    cookies[key.strip()] = val.strip()
        self._cookies = cookies
        return cookies

    def publish(self, article: dict) -> dict:
        """发布文章到头条"""
        # 头条号目前主要通过 Web API 或第三方工具发布
        # 这里提供一个基于 HTTP 的框架

        cookies = self._load_cookies()
        if not cookies:
            return {"success": False, "error": "缺少 cookies 配置"}

        # 构建发布数据
        content = article.get("body", "")
        title = article.get("title", "")

        # 头条文章分类 ID（科技）
        category_map = {
            "科技": "62cd8bc2d63f9e542f3e97ba",
            "数码": "62cd8bc2d63f9e542f3e97bb",
        }

        payload = {
            "title": title,
            "content": content,
            "category": category_map.get(self.default_category, "62cd8bc2d63f9e542f3e97ba"),
            "tags": ",".join(article.get("tags", [])),
            "source": article.get("source", ""),
            "source_url": article.get("source_url", ""),
            "type": 0,  # 0=文章, 1=图集, 2=视频
        }

        logger.info(f"   📤 头条发布: {title[:40]}...")
        logger.info(f"   ℹ️  头条号需要配置 cookies 或使用 Web 手动发布")

        # 保存为草稿文件，方便手动发布
        draft_path = self._save_draft(article)
        return {
            "success": True,
            "draft_file": draft_path,
            "note": "已保存为草稿文件，请在头条号后台手动发布",
        }

    def _save_draft(self, article: dict) -> str:
        """保存为草稿 HTML 文件"""
        draft_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "output", "articles"
        )
        os.makedirs(draft_dir, exist_ok=True)

        today = datetime.now().strftime("%Y%m%d")
        safe_title = "".join(c for c in article["title"][:20] if c.isalnum() or c in "中文-").strip()
        filename = f"toutiao_{today}_{safe_title}.html"
        path = os.path.join(draft_dir, filename)

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{article['title']}</title>
    <style>
        body {{ max-width: 800px; margin: 40px auto; padding: 0 20px; font-family: -apple-system, sans-serif; }}
        .meta {{ color: #888; font-size: 14px; margin-bottom: 20px; }}
        .tags {{ margin: 20px 0; }}
        .tag {{ display: inline-block; background: #f0f0f0; padding: 4px 12px; border-radius: 14px; margin-right: 8px; font-size: 13px; }}
    </style>
</head>
<body>
    <h1>{article['title']}</h1>
    <div class="meta">
        来源: {article.get('source', '')} | 
        原文: <a href="{article.get('source_url', '#')}">{article.get('source_url', '')}</a>
    </div>
    <div class="tags">
        {''.join(f'<span class="tag">{t}</span>' for t in article.get('tags', []))}
    </div>
    <div class="content">
        {article.get('body', '').replace(chr(10), '<br>')}
    </div>
</body>
</html>"""

        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info(f"   💾 草稿已保存: {path}")
        return path

    def is_configured(self) -> bool:
        cookie_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            self.cookie_file
        )
        return os.path.exists(cookie_path)


# ══════════════════════════════════════════════════════════
#  统一发布入口
# ══════════════════════════════════════════════════════════

def publish_articles(articles: list[dict], config: dict = None,
                     platforms: list[str] = None) -> dict:
    """发布文章到指定平台"""
    if config is None:
        config = _load_config()

    if platforms is None:
        platforms = ["wechat", "toutiao"]

    pub_cfg = config.get("publisher", {})
    cooldown = pub_cfg.get("cooldown_seconds", 300)

    results = {}

    # 初始化发布器
    publishers = {}
    if "wechat" in platforms:
        publishers["wechat"] = WeChatPublisher(config)
    if "toutiao" in platforms:
        publishers["toutiao"] = ToutiaoPublisher(config)

    for i, article in enumerate(articles):
        logger.info(f"\n📤 发布 [{i+1}/{len(articles)}]: {article['title'][:40]}...")

        article_results = {}

        for name, pub in publishers.items():
            if not pub.is_configured():
                logger.warning(f"   ⚠️ {name} 未配置，跳过")
                article_results[name] = {"success": False, "error": "未配置"}
                continue

            try:
                if name == "wechat":
                    result = pub.upload_draft(article)
                    article_results[name] = result
                elif name == "toutiao":
                    result = pub.publish(article)
                    article_results[name] = result
            except Exception as e:
                logger.error(f"   ❌ {name} 发布异常: {e}")
                article_results[name] = {"success": False, "error": str(e)}

        results[article["title"]] = article_results

        # 发布间隔
        if i < len(articles) - 1:
            logger.info(f"   ⏳ 等待 {cooldown}s 后继续...")
            time.sleep(cooldown)

    return results


# ── 发布报告 ──────────────────────────────────────────────

def generate_report(results: dict) -> str:
    """生成发布报告"""
    lines = ["# 📊 发布报告", "", f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]

    total = len(results)
    success = sum(1 for r in results.values()
                  if any(v.get("success") for v in r.values()))

    lines.append(f"**总计**: {total} 篇 | **成功**: {success} 篇 | **失败**: {total - success} 篇")
    lines.append("")

    for title, platforms in results.items():
        lines.append(f"### {title}")
        for platform, result in platforms.items():
            status = "✅" if result.get("success") else "❌"
            note = result.get("error", result.get("note", ""))
            lines.append(f"- {status} {platform}: {note}")
        lines.append("")

    return "\n".join(lines)
