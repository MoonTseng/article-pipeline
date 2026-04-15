#!/usr/bin/env python3
"""
「极话」公众号品牌素材生成器
生成: 公众号头图, 文章头图模板, 文章尾部引导图

品牌定位: 科技前沿 · AI洞察 · 深度解读
配色: 深空蓝(#0D1B2A) + 电光蓝(#00D4FF) + 极光紫(#7B2FF7) + 亮白(#F0F0F0)
风格: 科技感 + 未来感 + 简洁有力
"""

import os
import math
from PIL import Image, ImageDraw, ImageFont

BRAND_DIR = os.path.dirname(os.path.abspath(__file__))

# === 配色方案 ===
DEEP_SPACE   = (13, 27, 42)      # 深空蓝
ELECTRIC_BLUE= (0, 212, 255)     # 电光蓝
AURORA_PURPLE= (123, 47, 247)    # 极光紫
BRIGHT_WHITE = (240, 240, 240)   # 亮白
SOFT_GRAY    = (160, 170, 180)   # 柔灰
ACCENT_CYAN  = (0, 255, 200)     # 点缀青


def get_font(size, bold=False):
    """获取字体"""
    font_paths = [
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except:
                continue
    return ImageFont.load_default()


def draw_circuit_lines(draw, width, height, color, count=15):
    """绘制电路板/数据流线条装饰"""
    import random
    random.seed(42)  # 固定种子保证一致
    for _ in range(count):
        x = random.randint(0, width)
        y = random.randint(0, height)
        length = random.randint(30, 150)
        direction = random.choice(['h', 'v'])
        alpha = random.randint(20, 80)
        c = (*color[:3], alpha) if len(color) == 4 else (*color, alpha)
        if direction == 'h':
            draw.line([(x, y), (x + length, y)], fill=c, width=1)
            # 节点
            draw.ellipse([x + length - 2, y - 2, x + length + 2, y + 2], fill=c)
        else:
            draw.line([(x, y), (x, y + length)], fill=c, width=1)
            draw.ellipse([x - 2, y + length - 2, x + 2, y + length + 2], fill=c)


def draw_gradient_bg(img, color1, color2, direction='vertical'):
    """绘制渐变背景"""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for i in range(h if direction == 'vertical' else w):
        ratio = i / (h if direction == 'vertical' else w)
        r = int(color1[0] + (color2[0] - color1[0]) * ratio)
        g = int(color1[1] + (color2[1] - color1[1]) * ratio)
        b = int(color1[2] + (color2[2] - color1[2]) * ratio)
        if direction == 'vertical':
            draw.line([(0, i), (w, i)], fill=(r, g, b))
        else:
            draw.line([(i, 0), (i, h)], fill=(r, g, b))


def create_profile_logo():
    """生成公众号头像 Logo (800x800)"""
    print("  [1/4] 生成公众号头像...")
    size = 800
    img = Image.new('RGBA', (size, size), (*DEEP_SPACE, 255))
    
    # 渐变背景
    bg = Image.new('RGB', (size, size))
    draw_gradient_bg(bg, DEEP_SPACE, (20, 35, 55))
    img.paste(bg)
    
    draw = ImageDraw.Draw(img, 'RGBA')
    
    # 电路线装饰
    draw_circuit_lines(draw, size, size, ELECTRIC_BLUE, count=20)
    
    # 中心: "极" 字大字
    font_big = get_font(320, bold=True)
    text = "极"
    bbox = draw.textbbox((0, 0), text, font=font_big)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    
    # 发光效果: 多层绘制
    for offset in range(8, 0, -2):
        alpha = 30
        draw.text((size//2 - tw//2 + offset//3, size//2 - th//2 - 40 + offset//3), 
                  text, fill=(*AURORA_PURPLE, alpha), font=font_big)
    draw.text((size//2 - tw//2, size//2 - th//2 - 40), text, fill=BRIGHT_WHITE, font=font_big)
    
    # "话" 字 - 电光蓝
    font_sub = get_font(120)
    text2 = "话"
    bbox2 = draw.textbbox((0, 0), text2, font=font_sub)
    tw2 = bbox2[2] - bbox2[0]
    draw.text((size//2 - tw2//2, size//2 + 150), text2, fill=ELECTRIC_BLUE, font=font_sub)
    
    # 底部标签
    font_tag = get_font(36)
    tag = "科技前沿 · AI洞察"
    bbox3 = draw.textbbox((0, 0), tag, font=font_tag)
    tw3 = bbox3[2] - bbox3[0]
    draw.text((size//2 - tw3//2, size - 100), tag, fill=(*SOFT_GRAY, 200), font=font_tag)
    
    # 顶部和底部渐变装饰线
    for x in range(size):
        ratio = x / size
        r = int(ELECTRIC_BLUE[0] + (AURORA_PURPLE[0] - ELECTRIC_BLUE[0]) * ratio)
        g = int(ELECTRIC_BLUE[1] + (AURORA_PURPLE[1] - ELECTRIC_BLUE[1]) * ratio)
        b = int(ELECTRIC_BLUE[2] + (AURORA_PURPLE[2] - ELECTRIC_BLUE[2]) * ratio)
        draw.line([(x, 0), (x, 3)], fill=(r, g, b, 200))
        draw.line([(x, size-3), (x, size)], fill=(r, g, b, 200))
    
    path = os.path.join(BRAND_DIR, "logo_jihua.png")
    img.save(path, "PNG")
    print(f"    -> {path}")
    return path


def create_article_header():
    """生成文章头图模板 (900x383 公众号标准)"""
    print("  [2/4] 生成文章头图模板...")
    w, h = 900, 383
    img = Image.new('RGB', (w, h))
    draw_gradient_bg(img, DEEP_SPACE, (15, 30, 50))
    
    draw = ImageDraw.Draw(img, 'RGBA')
    
    # 电路线装饰
    draw_circuit_lines(draw, w, h, ELECTRIC_BLUE, count=12)
    draw_circuit_lines(draw, w, h, AURORA_PURPLE, count=8)
    
    # 左上角 logo 标识
    font_logo = get_font(42, bold=True)
    draw.text((40, 30), "极话", fill=BRIGHT_WHITE, font=font_logo)
    font_tag = get_font(18)
    draw.text((40, 80), "JIHUA · 科技前沿", fill=(*ELECTRIC_BLUE, 180), font=font_tag)
    
    # 中间区域: 留白给标题 (用占位符)
    font_title = get_font(52, bold=True)
    draw.text((40, 150), "{title}", fill=BRIGHT_WHITE, font=font_title)
    font_subtitle = get_font(24)
    draw.text((40, 220), "{subtitle}", fill=(*SOFT_GRAY, 200), font=font_subtitle)
    
    # 右下角装饰
    font_date = get_font(20)
    draw.text((w - 200, h - 50), "{date}", fill=(*SOFT_GRAY, 150), font=font_date)
    
    # 底部渐变线
    for x in range(w):
        ratio = x / w
        r = int(ELECTRIC_BLUE[0] + (AURORA_PURPLE[0] - ELECTRIC_BLUE[0]) * ratio)
        g = int(ELECTRIC_BLUE[1] + (AURORA_PURPLE[1] - ELECTRIC_BLUE[1]) * ratio)
        b = int(ELECTRIC_BLUE[2] + (AURORA_PURPLE[2] - ELECTRIC_BLUE[2]) * ratio)
        draw.line([(x, h-3), (x, h)], fill=(r, g, b))
    
    path = os.path.join(BRAND_DIR, "article_header_template.png")
    img.save(path, "PNG")
    print(f"    -> {path}")
    return path


def create_article_header_gen(title, subtitle="", date=""):
    """
    根据文章标题动态生成头图 (可被其他脚本调用)
    """
    w, h = 900, 383
    img = Image.new('RGB', (w, h))
    draw_gradient_bg(img, DEEP_SPACE, (15, 30, 50))
    
    draw = ImageDraw.Draw(img, 'RGBA')
    draw_circuit_lines(draw, w, h, ELECTRIC_BLUE, count=12)
    draw_circuit_lines(draw, w, h, AURORA_PURPLE, count=8)
    
    # 左上角 logo
    font_logo = get_font(42, bold=True)
    draw.text((40, 30), "极话", fill=BRIGHT_WHITE, font=font_logo)
    font_tag = get_font(18)
    draw.text((40, 80), "JIHUA · 科技前沿", fill=(*ELECTRIC_BLUE, 180), font=font_tag)
    
    # 标题 (自动换行)
    font_title = get_font(46, bold=True)
    max_width = w - 80
    lines = []
    current = ""
    for ch in title:
        test = current + ch
        bbox = draw.textbbox((0, 0), test, font=font_title)
        if bbox[2] - bbox[0] > max_width:
            lines.append(current)
            current = ch
        else:
            current = test
    if current:
        lines.append(current)
    
    y_start = 140
    for i, line in enumerate(lines[:3]):  # 最多3行
        draw.text((40, y_start + i * 55), line, fill=BRIGHT_WHITE, font=font_title)
    
    # 副标题
    if subtitle:
        font_sub = get_font(22)
        sub_y = y_start + len(lines[:3]) * 55 + 10
        draw.text((40, sub_y), subtitle, fill=(*SOFT_GRAY, 200), font=font_sub)
    
    # 日期
    if date:
        font_date = get_font(18)
        draw.text((w - 180, h - 45), date, fill=(*SOFT_GRAY, 150), font=font_date)
    
    # 底部渐变线
    for x in range(w):
        ratio = x / w
        r = int(ELECTRIC_BLUE[0] + (AURORA_PURPLE[0] - ELECTRIC_BLUE[0]) * ratio)
        g = int(ELECTRIC_BLUE[1] + (AURORA_PURPLE[1] - ELECTRIC_BLUE[1]) * ratio)
        b = int(ELECTRIC_BLUE[2] + (AURORA_PURPLE[2] - ELECTRIC_BLUE[2]) * ratio)
        draw.line([(x, h-3), (x, h)], fill=(r, g, b))
    
    return img


def create_footer_banner():
    """生成文章尾部关注引导图 (900x200)"""
    print("  [3/4] 生成文章尾部引导图...")
    w, h = 900, 200
    img = Image.new('RGB', (w, h))
    draw_gradient_bg(img, (10, 20, 35), DEEP_SPACE)
    
    draw = ImageDraw.Draw(img, 'RGBA')
    
    # 顶部渐变线
    for x in range(w):
        ratio = x / w
        r = int(ELECTRIC_BLUE[0] + (AURORA_PURPLE[0] - ELECTRIC_BLUE[0]) * ratio)
        g = int(ELECTRIC_BLUE[1] + (AURORA_PURPLE[1] - ELECTRIC_BLUE[1]) * ratio)
        b = int(ELECTRIC_BLUE[2] + (AURORA_PURPLE[2] - ELECTRIC_BLUE[2]) * ratio)
        draw.line([(x, 0), (x, 2)], fill=(r, g, b))
    
    # 电路装饰
    draw_circuit_lines(draw, w, h, ELECTRIC_BLUE, count=6)
    
    # 左侧: "极话" logo
    font_logo = get_font(56, bold=True)
    draw.text((50, 40), "极话", fill=BRIGHT_WHITE, font=font_logo)
    
    # 中间: slogan
    font_slogan = get_font(24)
    draw.text((50, 110), "科技前沿 · AI洞察 · 深度解读", fill=ELECTRIC_BLUE, font=font_slogan)
    draw.text((50, 145), "每天 get 最前沿的科技资讯", fill=(*SOFT_GRAY, 180), font=get_font(18))
    
    # 右侧: 关注引导
    font_cta = get_font(28, bold=True)
    draw.text((w - 250, 55), "👆 长按关注", fill=BRIGHT_WHITE, font=font_cta)
    font_hint = get_font(18)
    draw.text((w - 250, 100), "扫码关注公众号", fill=(*SOFT_GRAY, 150), font=font_hint)
    
    # 右侧装饰框 (二维码占位)
    box_x, box_y = w - 130, 35
    box_s = 130
    draw.rounded_rectangle([box_x, box_y, box_x + box_s, box_y + box_s], 
                           radius=8, outline=(*ELECTRIC_BLUE, 100), width=2)
    font_qr = get_font(14)
    draw.text((box_x + 25, box_y + 55), "二维码", fill=(*SOFT_GRAY, 100), font=font_qr)
    
    path = os.path.join(BRAND_DIR, "footer_banner.png")
    img.save(path, "PNG")
    print(f"    -> {path}")
    return path


def create_separator():
    """生成分割线图 (900x40)"""
    print("  [4/4] 生成分割线...")
    w, h = 900, 40
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 中间位置的渐变线
    y = h // 2
    for x in range(w):
        ratio = x / w
        # 两端淡出
        edge_alpha = 1.0 - abs(x - w/2) / (w/2) * 0.8
        r = int(ELECTRIC_BLUE[0] + (AURORA_PURPLE[0] - ELECTRIC_BLUE[0]) * ratio)
        g = int(ELECTRIC_BLUE[1] + (AURORA_PURPLE[1] - ELECTRIC_BLUE[1]) * ratio)
        b = int(ELECTRIC_BLUE[2] + (AURORA_PURPLE[2] - ELECTRIC_BLUE[2]) * ratio)
        alpha = int(180 * edge_alpha)
        draw.line([(x, y), (x, y+1)], fill=(r, g, b, alpha))
    
    path = os.path.join(BRAND_DIR, "separator.png")
    img.save(path, "PNG")
    print(f"    -> {path}")
    return path


def main():
    print("=" * 50)
    print("  ⚡ 极话 — 公众号品牌素材生成")
    print("=" * 50)
    
    create_profile_logo()
    create_article_header()
    create_footer_banner()
    create_separator()
    
    print(f"\n{'='*50}")
    print("  ✅ 品牌素材生成完成!")
    print(f"{'='*50}")
    print(f"  配色方案:")
    print(f"    深空蓝:  #0D1B2A (背景)")
    print(f"    电光蓝:  #00D4FF (强调)")
    print(f"    极光紫:  #7B2FF7 (点缀)")
    print(f"    亮白:    #F0F0F0 (文字)")


if __name__ == "__main__":
    main()
