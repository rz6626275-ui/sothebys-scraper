from flask import Flask, render_template, request, jsonify, Response
import threading
import queue
import os
import time
from list_scraper import scrape_sothebys_list
from image_extractor import ImageDownloader

app = Flask(__name__)

# 全局状态管理
class TaskManager:
    def __init__(self):
        self.scrape_thread = None
        self.download_thread = None
        self.stop_flag = threading.Event()
        self.log_queue = queue.Queue()
        self.status = {
            'scraping': False,
            'downloading': False,
            'scrape_progress': '',
            'download_progress': ''
        }
        self.lock = threading.Lock()
    
    def log(self, message):
        """添加日志消息"""
        timestamp = time.strftime('%H:%M:%S')
        log_msg = f"[{timestamp}] {message}"
        self.log_queue.put(log_msg)
        print(log_msg)
    
    def update_status(self, **kwargs):
        """更新状态"""
        with self.lock:
            self.status.update(kwargs)

task_manager = TaskManager()

def scrape_with_stop(url, output_file, stop_flag, log_callback):
    """支持停止的抓取函数"""
    log_callback("启动列表抓取器...")
    log_callback(f"目标 URL: {url}")
    
    # 清空urls.txt并写入文件头
    log_callback(f"初始化 {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# Source: {url}\n")
        f.write(f"# Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# 每页抓取完成后实时写入\n\n")
    
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            log_callback("正在加载页面...")
            page.goto(url, timeout=60000)
            page.wait_for_load_state("networkidle")
            
            # 处理 Cookie Banner
            log_callback("检查 Cookie Banner...")
            try:
                cookie_btn = page.locator("#onetrust-accept-btn-handler, #onetrust-reject-all-handler, button:has-text('Accept All'), button:has-text('Reject All')").first
                if cookie_btn.is_visible():
                    log_callback("发现 Cookie Banner，尝试关闭/接受...")
                    cookie_btn.click()
                    time.sleep(2)
                    page.wait_for_load_state("networkidle")
            except Exception as e:
                log_callback(f"处理 Cookie Banner 时出错 (非致命): {e}")
            
            total_items = 0
            seen_urls = set()
            page_num = 1
            
            while not stop_flag.is_set():
                log_callback(f"--- 正在处理第 {page_num} 页 ---")
                task_manager.update_status(scrape_progress=f"第 {page_num} 页")
                
                # 滚动到底部
                log_callback("滚动到底部...")
                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(3)
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(2)
                except Exception as e:
                    log_callback(f"滚动时发生错误: {e}")
                    time.sleep(2)

                # 提取商品信息
                log_callback("正在提取本页商品信息...")
                links = page.locator("a[href*='/buy/auction/']").all()
                
                page_items = []  # 当前页的商品
                for link in links:
                    if stop_flag.is_set():
                        log_callback("收到停止信号，中断抓取...")
                        break
                        
                    try:
                        href = link.get_attribute("href")
                        if not href: continue
                        
                        if href.startswith("/"):
                            full_url = "https://www.sothebys.com" + href
                        else:
                            full_url = href
                            
                        if full_url in seen_urls: continue
                        if full_url == url: continue
                        
                        title = link.inner_text().strip()
                        if not title:
                            h_tag = link.locator("h3, h4, p, div[class*='title']").first
                            if h_tag.count() > 0:
                                title = h_tag.inner_text().strip()
                        
                        title = title.replace("\n", " ").replace("\r", "")
                        
                        if full_url not in seen_urls:
                            is_product = False
                            if "/buy/auction/" in full_url:
                                if full_url.split("?")[0] != url.split("?")[0]:
                                    is_product = True
                            
                            if is_product:
                                seen_urls.add(full_url)
                                page_items.append({"title": title, "url": full_url})

                    except Exception:
                        pass
                
                # 立即写入本页数据
                if page_items:
                    log_callback(f"第 {page_num} 页提取到 {len(page_items)} 个新商品，正在写入文件...")
                    with open(output_file, 'a', encoding='utf-8') as f:
                        for item in page_items:
                            line = f"{item['url']} # {item['title']}\n"
                            f.write(line)
                    total_items += len(page_items)
                    log_callback(f"✓ 已写入，累计 {total_items} 个商品")
                else:
                    log_callback(f"第 {page_num} 页未提取到新商品。")

                if stop_flag.is_set():
                    break

                # 翻页逻辑
                log_callback("正在检查分页...")
                next_button = page.locator("button[aria-label='Go to next page.']").first
                
                is_visible = next_button.is_visible()
                is_enabled = next_button.is_enabled()
                
                if is_visible and is_enabled:
                    log_callback("发现 'Next' 按钮，准备点击下一页...")
                    try:
                        next_button.scroll_into_view_if_needed()
                        time.sleep(1)
                        next_button.click()
                        
                        try:
                            page.wait_for_load_state("networkidle", timeout=10000)
                        except:
                            pass
                        
                        page_num += 1
                        time.sleep(5)
                        
                    except Exception as e:
                        log_callback(f"点击下一页时出错: {e}")
                        break
                else:
                    log_callback("未发现可见的 'Next' 按钮或按钮不可用，已到达最后一页。")
                    break
            
            if stop_flag.is_set():
                log_callback(f"抓取已停止，共提取到 {total_items} 个商品。")
            else:
                log_callback(f"抓取结束，共提取到 {total_items} 个商品。")
            
            # 更新文件头的总数
            if total_items > 0:
                log_callback("更新文件统计信息...")
                with open(output_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # 在第二行后插入总数
                lines.insert(2, f"# Total Items: {total_items}\n")
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                log_callback("文件更新完成！")
            else:
                log_callback("警告：未提取到任何商品。")

        except Exception as e:
            log_callback(f"发生严重错误: {e}")
        finally:
            browser.close()
            task_manager.update_status(scraping=False, scrape_progress='')

def download_with_stop(stop_flag, log_callback):
    """支持停止的下载函数"""
    log_callback("启动批量下载器...")
    
    urls_file = "urls.txt"
    if not os.path.exists(urls_file):
        log_callback(f"错误: {urls_file} 不存在")
        return
    
    # 读取任务
    tasks = []
    with open(urls_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            
            parts = line.split('#', 1)
            url = parts[0].strip()
            title = parts[1].strip() if len(parts) > 1 else None
            
            if url:
                tasks.append((url, title))
    
    log_callback(f"共读取到 {len(tasks)} 个任务。")
    
    # 创建下载器
    downloader = ImageDownloader(
        min_width=3840,
        min_height=2160,
        headless=True,
        base_dir="下载",
        stop_flag=stop_flag  # 传递停止标志
    )
    
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        for i, (url, title) in enumerate(tasks):
            if stop_flag.is_set():
                log_callback("收到停止信号，中断下载...")
                break
            
            log_callback(f"\n{'='*20} 正在执行任务 [{i+1}/{len(tasks)}] {'='*20}")
            task_manager.update_status(download_progress=f"{i+1}/{len(tasks)}")
            
            try:
                context = browser.new_context()
                page = context.new_page()
                
                fetched_title = downloader._scan_page(page, url)
                
                # 使用title(如果有),否则使用fetched_title,不添加序号
                if title:
                    final_title = title
                else:
                    final_title = fetched_title
                
                save_dir = downloader.sanitize_filename(final_title)
                log_callback(f"保存目录: {save_dir}")
                
                context.close()
                
                # 下载图片
                downloader._download_images(save_dir)
                
            except Exception as e:
                log_callback(f"❌ 任务失败: {url}\n原因: {e}")
        
        browser.close()
    
    task_manager.update_status(downloading=False, download_progress='')
    log_callback("下载任务完成！")

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/api/scrape', methods=['POST'])
def start_scrape():
    """启动抓取任务"""
    data = request.json
    url = data.get('url')
    
    if not url:
        return jsonify({'success': False, 'message': '请提供URL'})
    
    if task_manager.status['scraping']:
        return jsonify({'success': False, 'message': '抓取任务正在进行中'})
    
    # 重置停止标志
    task_manager.stop_flag.clear()
    task_manager.update_status(scraping=True, scrape_progress='准备中...')
    
    # 启动抓取线程
    task_manager.scrape_thread = threading.Thread(
        target=scrape_with_stop,
        args=(url, "urls.txt", task_manager.stop_flag, task_manager.log)
    )
    task_manager.scrape_thread.start()
    
    return jsonify({'success': True, 'message': '抓取任务已启动'})

@app.route('/api/download', methods=['POST'])
def start_download():
    """启动下载任务"""
    if task_manager.status['downloading']:
        return jsonify({'success': False, 'message': '下载任务正在进行中'})
    
    # 重置停止标志
    task_manager.stop_flag.clear()
    task_manager.update_status(downloading=True, download_progress='准备中...')
    
    # 启动下载线程
    task_manager.download_thread = threading.Thread(
        target=download_with_stop,
        args=(task_manager.stop_flag, task_manager.log)
    )
    task_manager.download_thread.start()
    
    return jsonify({'success': True, 'message': '下载任务已启动'})

@app.route('/api/stop', methods=['POST'])
def stop_task():
    """停止当前任务"""
    task_manager.stop_flag.set()
    task_manager.log("正在停止任务...")
    return jsonify({'success': True, 'message': '停止信号已发送'})

@app.route('/api/status', methods=['GET'])
def get_status():
    """获取当前状态"""
    return jsonify(task_manager.status)

@app.route('/api/logs')
def stream_logs():
    """SSE日志流"""
    def generate():
        while True:
            try:
                log = task_manager.log_queue.get(timeout=1)
                yield f"data: {log}\n\n"
            except queue.Empty:
                yield f"data: \n\n"  # 心跳
    
    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    # 确保下载目录存在
    os.makedirs('下载', exist_ok=True)
    
    print("=" * 50)
    print("苏富比抓取工具 Web 服务")
    print("=" * 50)
    print("访问地址: http://localhost:5001")
    print("=" * 50)
    
    app.run(debug=False, host='0.0.0.0', port=5001, threaded=True)
