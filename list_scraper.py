import time
import argparse
from playwright.sync_api import sync_playwright

def scrape_sothebys_list(url, output_file="urls.txt"):
    print(f"启动列表抓取器...")
    print(f"目标 URL: {url}")
    
    with sync_playwright() as p:
        # 启动浏览器 (无头模式)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            print("正在加载页面...")
            page.goto(url, timeout=60000)
            
            # 等待页面初步加载
            page.wait_for_load_state("networkidle")
            
            # --- 处理 Cookie Banner ---
            print("检查 Cookie Banner...")
            try:
                # 常见的 OneTrust 按钮 ID
                cookie_btn = page.locator("#onetrust-accept-btn-handler, #onetrust-reject-all-handler, button:has-text('Accept All'), button:has-text('Reject All')").first
                if cookie_btn.is_visible():
                    print("发现 Cookie Banner，尝试关闭/接受...")
                    cookie_btn.click()
                    time.sleep(2)
                    page.wait_for_load_state("networkidle") # 等待可能发生的刷新
                else:
                    print("未发现明显的 Cookie Banner。")
            except Exception as e:
                print(f"处理 Cookie Banner 时出错 (非致命): {e}")
            
            items = []
            seen_urls = set()
            page_num = 1
            
            while True:
                print(f"--- 正在处理第 {page_num} 页 ---")
                
                # 1. 滚动到底部确保所有元素加载 (Sotheby's 页面较长)
                print("滚动到底部...")
                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(3) # 等待滚动后的懒加载
                    
                    # 再次滚动以防万一 (有些页面需要多次滚动)
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(2)
                except Exception as e:
                    print(f"滚动时发生错误 (可能是页面刷新): {e}")
                    time.sleep(2)
                    # 尝试重新获取上下文或忽略，继续尝试提取

                # --- 数据提取逻辑 ---
                print("正在提取本页商品信息...")
                
                # 获取页面上所有链接元素
                # 查找所有包含 /buy/auction/ 的链接
                links = page.locator("a[href*='/buy/auction/']").all()
                
                current_page_items = 0
                for link in links:
                    try:
                        href = link.get_attribute("href")
                        if not href: continue
                        
                        # 补全相对路径
                        if href.startswith("/"):
                            full_url = "https://www.sothebys.com" + href
                        else:
                            full_url = href
                            
                        # 去重
                        if full_url in seen_urls: continue
                        
                        # 简单的 URL 过滤
                        if full_url == url: continue
                        
                        # 移除错误的 locale 过滤，因为商品链接也可能包含 locale
                        # if "locale=" in full_url and "lot" not in full_url: continue 

                        # 提取标题
                        title = link.inner_text().strip()
                        if not title:
                            # 尝试找内部的 h3, h4, p
                            h_tag = link.locator("h3, h4, p, div[class*='title']").first
                            if h_tag.count() > 0:
                                title = h_tag.inner_text().strip()
                        
                        # 清理标题换行
                        title = title.replace("\n", " ").replace("\r", "")
                        
                        if full_url not in seen_urls:
                            # 只有当 URL 看起来像商品时才添加
                            # 只要包含 auction 且不是当前列表页即可，或者包含 china-5000-years
                            # 排除一些显然不是商品的链接 (如 /buy/auction/2024/china-5000-years 自身)
                            
                            is_product = False
                            if "/buy/auction/" in full_url:
                                # 排除列表页自身 (简单判断长度或特定后缀)
                                if full_url.split("?")[0] != url.split("?")[0]:
                                    is_product = True
                            
                            if is_product:
                                seen_urls.add(full_url)
                                items.append({"title": title, "url": full_url})
                                current_page_items += 1
                                # print(f"发现: {title[:30]}... -> {full_url[-30:]}")

                    except Exception as e:
                        pass
                
                print(f"第 {page_num} 页提取到 {current_page_items} 个新商品。")

                # --- 翻页逻辑 ---
                print(f"[{time.strftime('%H:%M:%S')}] 正在检查分页...")
                
                # 查找 "Next" 按钮
                # Selector identified: button[aria-label='Go to next page.']
                next_button = page.locator("button[aria-label='Go to next page.']").first
                
                # 检查按钮状态
                is_visible = next_button.is_visible()
                is_enabled = next_button.is_enabled()
                print(f"[{time.strftime('%H:%M:%S')}] Next 按钮状态: 可见={is_visible}, 可用={is_enabled}")
                
                if is_visible and is_enabled:
                    print(f"[{time.strftime('%H:%M:%S')}] 发现 'Next' 按钮，准备点击下一页...")
                    
                    # 尝试点击并等待导航
                    try:
                        # 确保按钮在视图中
                        next_button.scroll_into_view_if_needed()
                        time.sleep(1)
                        
                        # 记录当前 URL
                        current_url = page.url
                        
                        # 点击
                        print(f"[{time.strftime('%H:%M:%S')}] 点击 Next 按钮...")
                        next_button.click()
                        
                        # 等待 URL 变化或网络空闲
                        # 有时候点击不会立即触发 URL 变化，而是 AJAX 加载
                        # 但 Sotheby's 分页通常是 URL 变化 (page=2) 或 pushState
                        try:
                            page.wait_for_load_state("networkidle", timeout=10000)
                        except:
                            print(f"[{time.strftime('%H:%M:%S')}] 等待 networkidle 超时，继续...")
                        
                        # 检查 URL 是否变化
                        new_url = page.url
                        if new_url != current_url:
                             print(f"[{time.strftime('%H:%M:%S')}] 页面 URL 已更新: {new_url}")
                        else:
                             print(f"[{time.strftime('%H:%M:%S')}] 页面 URL 未变化，可能是 AJAX 加载或翻页失败。")
                        
                        page_num += 1
                        time.sleep(5) # 额外等待渲染
                        
                    except Exception as e:
                        print(f"[{time.strftime('%H:%M:%S')}] 点击下一页时出错: {e}")
                        # 尝试强制点击
                        try:
                            print(f"[{time.strftime('%H:%M:%S')}] 尝试强制点击...")
                            next_button.click(force=True)
                            time.sleep(5)
                            page_num += 1
                        except Exception as e2:
                            print(f"[{time.strftime('%H:%M:%S')}] 强制点击也失败: {e2}")
                            print("无法翻页，停止。")
                            break
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] 未发现可见的 'Next' 按钮或按钮不可用，已到达最后一页。")
                    break
            
            print(f"抓取结束，共提取到 {len(items)} 个商品。")
            
            # --- 写入文件 ---
            if items:
                print(f"正在写入 {output_file} ...")
                # 读取现有内容以避免重复 (可选，但这里我们覆盖或追加)
                # 用户希望有条理地写入
                with open(output_file, "w", encoding="utf-8") as f: # 使用 'w' 覆盖，保证是最新的完整列表
                    f.write(f"# Source: {url}\n")
                    f.write(f"# Total Items: {len(items)}\n")
                    f.write(f"# Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    for item in items:
                        line = f"{item['url']} # {item['title']}\n"
                        f.write(line)
                print("写入完成！")
            else:
                print("警告：未提取到任何商品。")

        except Exception as e:
            print(f"发生严重错误: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sotheby's 列表页抓取器")
    parser.add_argument("url", help="列表页 URL")
    parser.add_argument("--output", default="urls.txt", help="输出文件路径 (默认: urls.txt)")
    
    args = parser.parse_args()
    
    scrape_sothebys_list(args.url, args.output)
