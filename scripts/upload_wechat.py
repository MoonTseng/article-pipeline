#!/usr/bin/env python3
"""Upload article to WeChat draft"""
import httpx, json

app_id = "wxd05598e68dd59b8e"
app_secret = "5dfb61acabfbe294c684d7eb4edcabda"

# Get access token
resp = httpx.get("https://api.weixin.qq.com/cgi-bin/token",
    params={"grant_type": "client_credential", "appid": app_id, "secret": app_secret},
    timeout=10)
token = resp.json()["access_token"]
print(f"✅ Token OK")

title = "Anthropic 偷袭 AI 战场：Claude Opus 4.7 和设计工具本周亮相"

content = (
    "<p>AI 圈又炸了。</p>"
    "<p>据 The Information 独家报道，<strong>Anthropic 预计将在本周发布 Claude Opus 4.7 模型</strong>，同时还有一款全新的 AI 设计工具。消息一出，Reddit 上相关帖子直接飙到 500 多赞，评论区讨论热度堪比当年 GPT-4 发布。</p>"
    "<p>要知道，上一次 AI 圈这么兴奋，还是因为 Claude Code 在编程领域大杀四方的时候。这次 Anthropic 显然不满足于只做最好的编程 AI——他们要搞事情了。</p>"
    "<p><strong>Opus 4.7：不只是版本号的跳跃</strong></p>"
    "<p>从 Opus 4 到 Opus 4.7，看起来只是小版本迭代，但了解 Anthropic 风格的人都知道——他们从来不随便发模型。这次可能在推理能力、编程能力上都有显著提升，同时还有一个全新的 AI 设计工具。</p>"
    "<p><strong>AI 设计工具：Anthropic 的新战场</strong></p>"
    "<p>比模型更新更让人意外的是——Anthropic 居然要做设计工具了。目前 AI 设计市场基本是 Canva 和 Figma 两家独大，如果 Anthropic 出品的工具能做到理解自然语言描述直接生成设计稿，那整个行业都得重新洗牌。</p>"
    "<p><strong>三巨头混战</strong></p>"
    "<p>OpenAI 想做 AI 界的苹果，Google 想做 AI 界的安卓，而 Anthropic 想做 AI 界的瑞士军刀——不一定最大众，但一定最好用。</p>"
    "<p>你觉得 Anthropic 的 AI 设计工具能打败 Canva 和 Figma 吗？评论区聊聊。</p>"
)

payload = {
    "articles": [{
        "title": title,
        "author": "极话",
        "content": content,
        "content_source_url": "https://www.bilibili.com/video/BV1c4QLBrET8",
        "digest": "Anthropic预计本周发布Claude Opus 4.7模型及全新AI设计工具，AI三巨头混战再升级",
        "show_cover_pic": 0,
    }]
}

resp = httpx.post("https://api.weixin.qq.com/cgi-bin/draft/add",
    params={"access_token": token},
    json=payload,
    timeout=30)
result = resp.json()

if "media_id" in result:
    print(f"✅ 草稿上传成功!")
    print(f"   media_id: {result['media_id']}")
    print(f"   登录公众号后台 → 草稿箱 即可查看和发布")
else:
    print(f"❌ 失败: {json.dumps(result, ensure_ascii=False)}")
