#!/usr/bin/env python3
"""
AI 科技文章发布流水线
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
用法:
  python main.py collect                  # 只采集，不处理不发布
  python main.py process                  # 处理已采集的文章
  python main.py publish                  # 发布已处理的文章
  python main.py run                      # 采集 + 处理 + 发布（完整流程）
  python main.py run --no-publish         # 采集 + 处理，不发布
  python main.py run -p wechat            # 只发公众号
  python main.py run -p toutiao           # 只发头条
  python main.py run -p wechat,toutiao    # 两个都发
  python main.py status                   # 查看待处理/已发布状态
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

import yaml

# ── 路径 ──────────────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
sys.path.insert(0, BASE_DIR)

from collector import collect_all
from processor import process_all, save_articles
from publisher import publish_articles, generate_report

# ── 日志 ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_config(path: str = None) -> dict:
    if path is None:
        path = os.path.join(BASE_DIR, "config.yaml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── 命令 ──────────────────────────────────────────────────

def cmd_collect(config: dict):
    """只采集"""
    articles = collect_all(config)
    # 保存原始采集数据
    output_dir = os.path.join(BASE_DIR, "runs")
    os.makedirs(output_dir, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"collected_{today}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    logger.info(f"💾 原始数据保存到 {path}")
    return articles


def cmd_process(config: dict, articles: list[dict] = None):
    """处理文章（LLM 改写）"""
    if articles is None:
        # 从最近的采集文件加载
        runs_dir = os.path.join(BASE_DIR, "runs")
        files = sorted([f for f in os.listdir(runs_dir) if f.startswith("collected_")])
        if not files:
            logger.error("❌ 没有找到采集数据，请先运行 collect")
            return []
        latest = os.path.join(runs_dir, files[-1])
        with open(latest, encoding="utf-8") as f:
            articles = json.load(f)
        logger.info(f"📂 从 {files[-1]} 加载 {len(articles)} 篇文章")

    processed = process_all(articles, config)
    save_articles(processed)
    return processed


def cmd_publish(config: dict, platforms: list[str], articles: list[dict] = None):
    """发布文章"""
    if articles is None:
        # 从今天的处理结果加载
        today = datetime.now().strftime("%Y-%m-%d")
        path = os.path.join(BASE_DIR, "output", "articles", f"articles_{today}.json")
        if not os.path.exists(path):
            logger.error(f"❌ 没有找到今天的文章: {path}")
            return {}
        with open(path, encoding="utf-8") as f:
            articles = json.load(f)
        # 只发布状态为 processed 的
        articles = [a for a in articles if a.get("status") == "processed"]
        logger.info(f"📂 加载 {len(articles)} 篇已处理文章")

    results = publish_articles(articles, config, platforms)

    # 生成报告
    report = generate_report(results)
    report_path = os.path.join(BASE_DIR, "output", f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    logger.info(f"📊 报告保存到 {report_path}")

    return results


def cmd_run(config: dict, platforms: list[str], no_publish: bool = False):
    """完整流水线: 采集 → 处理 → 发布"""
    logger.info("=" * 50)
    logger.info("🚀 AI 科技文章发布流水线")
    logger.info(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    logger.info(f"   平台: {', '.join(platforms)}")
    logger.info("=" * 50)

    # Step 1: 采集
    logger.info("\n📡 Step 1: 采集文章")
    articles = cmd_collect(config)
    if not articles:
        logger.warning("⚠️ 没有采集到文章，流水线结束")
        return

    # Step 2: 处理
    logger.info("\n✍️ Step 2: LLM 改写")
    processed = cmd_process(config, articles)
    if not processed:
        logger.warning("⚠️ 没有成功处理的文章，流水线结束")
        return

    # Step 3: 发布
    if no_publish:
        logger.info("\n⏭️ Step 3: 跳过发布 (--no-publish)")
        logger.info(f"✅ 完成！共处理 {len(processed)} 篇文章")
        return

    logger.info("\n📤 Step 3: 发布文章")
    results = cmd_publish(config, platforms, processed)

    # 总结
    success = sum(1 for r in results.values() if any(v.get("success") for v in r.values()))
    logger.info("\n" + "=" * 50)
    logger.info(f"✅ 流水线完成！")
    logger.info(f"   采集: {len(articles)} 篇")
    logger.info(f"   处理: {len(processed)} 篇")
    logger.info(f"   发布: {success}/{len(results)} 篇")
    logger.info("=" * 50)


def cmd_status(config: dict):
    """查看状态"""
    logger.info("📊 流水线状态")
    logger.info("=" * 40)

    # 采集数据
    runs_dir = os.path.join(BASE_DIR, "runs")
    if os.path.exists(runs_dir):
        collected = [f for f in os.listdir(runs_dir) if f.startswith("collected_")]
        logger.info(f"\n📡 采集数据: {len(collected)} 份")
        for f in sorted(collected)[-3:]:
            path = os.path.join(runs_dir, f)
            with open(path) as fh:
                count = len(json.load(fh))
            logger.info(f"   {f} ({count} 篇)")

    # 处理结果
    articles_dir = os.path.join(BASE_DIR, "output", "articles")
    if os.path.exists(articles_dir):
        processed = [f for f in os.listdir(articles_dir) if f.startswith("articles_")]
        logger.info(f"\n✍️ 处理结果: {len(processed)} 份")
        for f in sorted(processed)[-3:]:
            path = os.path.join(articles_dir, f)
            with open(path) as fh:
                articles = json.load(fh)
            done = len([a for a in articles if a.get("status") == "processed"])
            logger.info(f"   {f} ({done} 篇已处理)")

    # 发布器状态
    from publisher import WeChatPublisher, ToutiaoPublisher
    wp = WeChatPublisher(config)
    tp = ToutiaoPublisher(config)
    logger.info(f"\n📤 发布器状态:")
    logger.info(f"   公众号: {'✅ 已配置' if wp.is_configured() else '❌ 未配置 (需要 app_id + app_secret)'}")
    logger.info(f"   头条号: {'✅ 已配置' if tp.is_configured() else '❌ 未配置 (需要 cookies 文件)'}")


# ── CLI ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="AI 科技文章发布流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("command", choices=["collect", "process", "publish", "run", "status"],
                        help="要执行的命令")
    parser.add_argument("-p", "--platforms", default="wechat,toutiao",
                        help="发布平台，逗号分隔: wechat,toutiao (默认全部)")
    parser.add_argument("--no-publish", action="store_true",
                        help="只采集+处理，不发布")
    parser.add_argument("--config", default=None,
                        help="配置文件路径")

    args = parser.parse_args()
    config = load_config(args.config)
    platforms = [p.strip() for p in args.platforms.split(",")]

    if args.command == "collect":
        cmd_collect(config)
    elif args.command == "process":
        cmd_process(config)
    elif args.command == "publish":
        cmd_publish(config, platforms)
    elif args.command == "run":
        cmd_run(config, platforms, no_publish=args.no_publish)
    elif args.command == "status":
        cmd_status(config)


if __name__ == "__main__":
    main()
