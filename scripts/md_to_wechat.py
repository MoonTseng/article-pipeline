#!/usr/bin/env python3
"""将 Markdown 文章转为微信公众号兼容的 HTML — 浏览器打开后全选复制，粘贴到公众号编辑器即可"""
import os, re, sys, glob
import markdown

def md_to_wechat_html(md_content, title="极话"):
    """Markdown → 微信公众号风格 HTML"""
    
    # 先处理图片：微信不支持本地图片，转成 base64 内嵌
    import base64
    def embed_image(m):
        alt = m.group(1)
        path = m.group(2)
        if os.path.exists(path):
            with open(path, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode()
            return f'![{alt}](data:image/jpeg;base64,{b64})'
        return m.group(0)
    
    md_content = re.sub(r'!\[([^\]]*)\]\((/[^)]+)\)', embed_image, md_content)
    
    # 去掉 HTML 注释
    md_content = re.sub(r'<!--.*?-->', '', md_content, flags=re.DOTALL)
    
    # 提取标题（用于顶部显示，方便复制到公众号标题栏）
    title_match = re.search(r'^#\s+(.+)$', md_content, re.MULTILINE)
    article_title = title_match.group(1) if title_match else title
    
    # 去掉 h1 标题（公众号标题单独填，正文不需要）
    md_content = re.sub(r'^#\s+[^\n]+\n+', '', md_content.strip(), count=1)
    
    # 预处理：手动将 Markdown 表格转为带内联样式的 HTML
    # （markdown 库对表格前无空行的情况解析不稳定，且微信对 table 支持差）
    def convert_md_tables(text):
        lines = text.split('\n')
        result = []
        i = 0
        while i < len(lines):
            # 检测表格起始：| xxx | xxx |
            if re.match(r'^\s*\|.+\|', lines[i]):
                # 收集连续的表格行
                table_lines = []
                while i < len(lines) and re.match(r'^\s*\|.+\|', lines[i]):
                    table_lines.append(lines[i])
                    i += 1
                
                if len(table_lines) >= 3:  # 至少 header + separator + 1 row
                    # 解析表头
                    headers = [c.strip() for c in table_lines[0].strip('|').split('|')]
                    # 跳过分隔行 (|---|---|)
                    rows = []
                    for tl in table_lines[2:]:
                        cells = [c.strip() for c in tl.strip('|').split('|')]
                        rows.append(cells)
                    
                    # 生成 HTML 表格
                    html = '<table style="width:100%;border-collapse:collapse;margin:15px 0;font-size:14px;border:1px solid #e0e0e0;">\n'
                    html += '<thead><tr>'
                    for h in headers:
                        html += f'<th style="background:#0D1B2A;color:#fff;padding:10px 12px;text-align:center;font-size:13px;border:1px solid #333;">{h}</th>'
                    html += '</tr></thead>\n<tbody>'
                    for ri, row in enumerate(rows):
                        bg = '#f9f9f9' if ri % 2 == 0 else '#fff'
                        html += f'<tr style="background:{bg};">'
                        for cell in row:
                            html += f'<td style="padding:8px 12px;border:1px solid #e0e0e0;text-align:center;font-size:13px;">{cell}</td>'
                        html += '</tr>'
                    html += '</tbody></table>\n'
                    result.append(html)
                else:
                    result.extend(table_lines)
            else:
                result.append(lines[i])
                i += 1
        return '\n'.join(result)
    
    md_content = convert_md_tables(md_content)
    
    # 提取并暂存内嵌 HTML（分隔线、品牌块、表格等），避免被 markdown 库和后续正则破坏
    html_blocks = {}
    block_counter = [0]
    def stash_html(m):
        block_counter[0] += 1
        key = f'XHTMLBLOCKX{block_counter[0]}X'
        html_blocks[key] = m.group(0)
        return key
    md_content = re.sub(r'<(?:p|div|table)\s[^>]*>.*?</(?:p|div|table)>', stash_html, md_content, flags=re.DOTALL)
    
    # 转 HTML
    html_body = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])
    
    # 恢复内嵌 HTML — 清除 markdown 可能包裹的标签
    for key, val in html_blocks.items():
        # 可能被包在 <p><strong> 等标签里
        html_body = re.sub(rf'<[^>]*>{key}</[^>]*>', val, html_body)
        html_body = html_body.replace(key, val)
    
    # 微信公众号兼容样式（内联样式，微信不支持 <style> 标签）
    # 标题
    html_body = re.sub(
        r'<h1>(.*?)</h1>',
        r'<h1 style="font-size:22px;font-weight:bold;color:#1a1a1a;text-align:center;margin:20px 0 10px;line-height:1.4;">\1</h1>',
        html_body
    )
    html_body = re.sub(
        r'<h2>(.*?)</h2>',
        r'<h2 style="font-size:18px;font-weight:bold;color:#1a1a1a;margin:25px 0 10px;padding-left:10px;border-left:4px solid #00D4FF;line-height:1.4;">\1</h2>',
        html_body
    )
    html_body = re.sub(
        r'<h3>(.*?)</h3>',
        r'<h3 style="font-size:16px;font-weight:bold;color:#333;margin:20px 0 8px;line-height:1.4;">\1</h3>',
        html_body
    )
    
    # 段落
    html_body = re.sub(
        r'<p(?:\s[^>]*)?>(.*?)</p>',
        lambda m: f'<p style="font-size:15px;color:#333;line-height:1.8;margin:10px 0;text-align:justify;">{m.group(1)}</p>',
        html_body, flags=re.DOTALL
    )
    
    # 引用块
    html_body = re.sub(
        r'<blockquote>\s*<p[^>]*>(.*?)</p>\s*</blockquote>',
        r'<blockquote style="margin:15px 0;padding:12px 15px;background:#f7f7f7;border-left:4px solid #00D4FF;border-radius:0 4px 4px 0;"><p style="font-size:14px;color:#666;line-height:1.8;margin:0;">\1</p></blockquote>',
        html_body, flags=re.DOTALL
    )
    
    # 无序列表
    html_body = html_body.replace('<ul>', '<ul style="margin:10px 0;padding-left:20px;">')
    html_body = re.sub(
        r'<li>(.*?)</li>',
        r'<li style="font-size:14px;color:#333;line-height:1.8;margin:4px 0;">\1</li>',
        html_body
    )
    
    # 有序列表
    html_body = html_body.replace('<ol>', '<ol style="margin:10px 0;padding-left:20px;">')
    
    # 行内代码
    html_body = re.sub(
        r'<code>(.*?)</code>',
        r'<code style="background:#f0f0f0;color:#d14;padding:2px 6px;border-radius:3px;font-size:13px;">\1</code>',
        html_body
    )
    
    # 图片居中 + 圆角
    html_body = re.sub(
        r'<img([^>]*)/>',
        r'<img\1 style="max-width:100%;border-radius:8px;margin:10px auto;display:block;"/>',
        html_body
    )
    # 有些img不是自闭合的
    html_body = re.sub(
        r'<img([^>]*)>',
        r'<img\1 style="max-width:100%;border-radius:8px;margin:10px auto;display:block;">',
        html_body
    )
    
    # 加粗高亮
    html_body = re.sub(
        r'<strong>(.*?)</strong>',
        r'<strong style="color:#1a1a1a;font-weight:bold;">\1</strong>',
        html_body
    )
    
    # 分割线
    html_body = html_body.replace('<hr>', '<hr style="border:none;border-top:1px solid #eee;margin:20px 0;">')
    html_body = html_body.replace('<hr/>', '<hr style="border:none;border-top:1px solid #eee;margin:20px 0;">')
    
    # 完整 HTML（用于浏览器预览+复制）
    full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{
    max-width: 580px;
    margin: 0 auto;
    padding: 20px;
    font-family: -apple-system, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
    background: #fff;
  }}
  /* 复制提示 */
  .copy-hint {{
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    background: #00D4FF;
    color: #fff;
    text-align: center;
    padding: 10px;
    font-size: 14px;
    z-index: 999;
    cursor: pointer;
  }}
  .copy-hint:hover {{ background: #00b8d9; }}
  #content {{ margin-top: 50px; }}
  .title-bar {{
    position: fixed;
    top: 40px;
    left: 0;
    right: 0;
    background: #fff;
    border-bottom: 1px solid #eee;
    padding: 8px 20px;
    z-index: 998;
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  .title-bar input {{
    flex: 1;
    font-size: 14px;
    padding: 6px 10px;
    border: 1px solid #ddd;
    border-radius: 4px;
    color: #333;
  }}
  .title-bar button {{
    background: #00D4FF;
    color: #fff;
    border: none;
    padding: 6px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
  }}
  .title-bar button:hover {{ background: #00b8d9; }}
  #content {{ margin-top: 90px; }}
</style>
<script>
function copyContent() {{
  var content = document.getElementById('content');
  var range = document.createRange();
  range.selectNodeContents(content);
  var sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
  document.execCommand('copy');
  document.querySelector('.copy-hint').textContent = '✅ 已复制正文！去公众号编辑器粘贴';
  setTimeout(() => {{
    document.querySelector('.copy-hint').textContent = '👆 点击复制正文 → 粘贴到公众号编辑器';
  }}, 2000);
}}
function copyTitle() {{
  var input = document.getElementById('titleInput');
  input.select();
  document.execCommand('copy');
  document.querySelector('.title-bar button').textContent = '✅ 已复制';
  setTimeout(() => {{
    document.querySelector('.title-bar button').textContent = '复制标题';
  }}, 1500);
}}
</script>
</head>
<body>
<div class="copy-hint" onclick="copyContent()">👆 点击复制正文 → 粘贴到公众号编辑器</div>
<div class="title-bar">
  <span style="font-size:13px;color:#999;">标题:</span>
  <input id="titleInput" value="{article_title}" readonly onclick="this.select()">
  <button onclick="copyTitle()">复制标题</button>
</div>
<div id="content">
{html_body}
</div>
</body>
</html>"""
    return full_html


if __name__ == '__main__':
    wechat_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "wechat")
    html_dir = os.path.join(wechat_dir, "html")
    os.makedirs(html_dir, exist_ok=True)
    
    md_files = sorted(glob.glob(os.path.join(wechat_dir, "*.md")))
    
    if not md_files:
        print("没找到 .md 文件")
        sys.exit(1)
    
    for md_path in md_files:
        fname = os.path.basename(md_path)
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        html = md_to_wechat_html(content, title=fname.replace('.md', ''))
        
        html_name = fname.replace('.md', '.html')
        html_path = os.path.join(html_dir, html_name)
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"✅ {fname} → html/{html_name}")
    
    print(f"\n🎉 共转换 {len(md_files)} 篇文章")
    print(f"📂 输出目录: {html_dir}")
    print(f"\n使用方法:")
    print(f"  1. 浏览器打开 HTML 文件")
    print(f"  2. 点击顶部「一键复制全文」")
    print(f"  3. 到公众号编辑器 Ctrl+V 粘贴")
    print(f"  4. 检查排版，发布！")
