# 📰 AI 科技文章发布流水线

全自动 AI 科技资讯采集 → LLM 改写 → 多平台发布的一站式流水线。

## ✨ 功能概览

```
Reddit / HN / arXiv / RSS / X
        ↓ 采集 & 去重
    LLM 翻译改写 (去AI味)
        ↓
  微信公众号 / 头条号 发布
```

- **多源采集**：Reddit (6个AI子版)、Hacker News、arXiv (cs.AI/CL/LG/CV)、RSS (OpenAI/Google/The Verge/TechCrunch)、X/Twitter
- **智能筛选**：AI 关键词过滤 + 热度排序 + 标题去重
- **LLM 改写**：自动翻译成中文科技资讯风格，去AI味，支持多 LLM 后端
- **多平台发布**：微信公众号 (草稿→发布)、头条号

## 🚀 快速开始

### 安装依赖

```bash
pip install httpx pyyaml openai feedparser
```

### 配置

复制并编辑 `config.yaml`：

```yaml
# LLM 后端 (二选一)
llm:
  backend: openai
  openai:
    api_key: ""          # 或设环境变量 XIAOMI_API_KEY
    base_url: https://token-plan-cn.xiaomimimo.com/v1
    model: mimo-v2-pro

# 发布平台
publisher:
  wechat:
    app_id: "your_app_id"
    app_secret: "your_secret"
  toutiao:
    cookie_file: "toutiao_cookies.txt"
```

### 使用

```bash
# 完整流程：采集 → 改写 → 发布
python main.py run

# 分步执行
python main.py collect                  # 只采集
python main.py process                  # 只改写
python main.py publish                  # 只发布

# 选择平台
python main.py run -p wechat            # 只发公众号
python main.py run -p toutiao           # 只发头条
python main.py run -p wechat,toutiao    # 两个都发

# 调试模式（不发布）
python main.py run --no-publish

# 查看状态
python main.py status
```

## 📁 项目结构

```
article-pipeline/
├── main.py              # CLI 入口 (collect/process/publish/run/status)
├── config.yaml          # 配置文件
├── collector/           # 采集器
│   └── __init__.py      # Reddit/HN/arXiv/RSS/X 多源采集 + 去重排序
├── processor/           # 处理器
│   └── __init__.py      # LLM 改写 (翻译/去AI味/自动标签)
├── publisher/           # 发布器
│   └── __init__.py      # 微信公众号 + 头条号
├── scripts/             # 辅助脚本
│   ├── gen_article.py   # 手动生成单篇文章
│   ├── gen_and_save.py  # 生成并保存为 HTML
│   └── upload_wechat.py # 手动上传到公众号
├── output/              # 输出目录 (gitignored)
│   ├── articles/        # 处理后的文章 JSON + HTML
│   └── images/          # 封面图
└── runs/                # 采集原始数据 (gitignored)
```

## 🔧 LLM 后端

| 后端 | 配置项 | 说明 |
|------|--------|------|
| OpenAI 兼容 | `backend: openai` | 支持任何 OpenAI 格式 API (小米 MiMo、DeepSeek、OpenRouter 等) |
| Bedrock Proxy | `backend: bedrock_proxy` | 公司 AWS Bedrock 代理 (需内网) |

## 📝 改写风格

- 36氪 / 量子位风格：专业但不枯燥
- 自动去除 "在当今"、"随着...的发展" 等 AI 味表达
- 适当加入口语化表达和网络用语
- 技术术语保留英文 + 中文解释
- 800-2000 字，自动生成标题和标签

## ⚠️ 注意事项

- **微信公众号**：未认证个人订阅号无法通过 API 发布，只能上传草稿后手动发布
- **头条号**：目前保存为草稿 HTML，需在后台手动发布
- **Reddit/HN**：需要代理才能访问
- **config.yaml** 包含密钥，已在 .gitignore 中（请勿提交）

## 📄 License

MIT
