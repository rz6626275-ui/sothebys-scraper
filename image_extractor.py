import time
import os
import requests
import re
import threading
import argparse
from io import BytesIO
from PIL import Image
from urllib.parse import unquote, urlparse, parse_qs
from playwright.sync_api import sync_playwright
from concurrent.futures import ThreadPoolExecutor

class ImageDownloader:
    def __init__(self, min_width=3840, min_height=2160, headless=True, max_workers=100, base_dir=None):
        self.min_width = min_width
        self.min_height = min_height
        self.headless = headless
        self.max_workers = max_workers
        self.base_dir = base_dir  # 根目录，所有商品文件夹都会创建在这里
        self.image_urls = set()
        self.counter_lock = threading.Lock()
        self.counter = [1]

    def sanitize_filename(self, name):
        """清理文件名中的非法字符"""
        cleaned = re.sub(r'[\\/*?:"<>|]', '_', name)
        return cleaned.strip()[:100]

    def _add_url(self, u):
        if not u: return
        # 1. 原始 URL
        self.image_urls.add(u)
        
        # 2. 尝试去除参数获取原图 (针对 .../image.jpg?width=800 这种)
        try:
            clean_url = u.split('?')[0]
            if clean_url != u:
                self.image_urls.add(clean_url)
        except:
            pass

        # 3. 尝试从 URL 参数中提取原图 (针对 CDN 缩略图嵌套)
        try:
            parsed = urlparse(u)
            qs = parse_qs(parsed.query)
            if 'url' in qs:
                original_url = unquote(qs['url'][0])
                if original_url.startswith('http'):
                    self.image_urls.add(original_url)
                    # 同样添加去除参数的版本
                    self.image_urls.add(original_url.split('?')[0])
        except:
            pass

    def _process_image(self, img_url, save_dir):
        """单个图片处理逻辑"""
        if img_url.startswith("data:"): return
        if img_url.endswith('.svg') or img_url.endswith('.ico'): return

        try:
            # 伪造 User-Agent 防止被拦截
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            resp = requests.get(img_url, headers=headers, timeout=15, stream=True)
            if resp.status_code != 200: return

            img_content = resp.content
            with Image.open(BytesIO(img_content)) as img:
                width, height = img.size
                
                # 尺寸过滤逻辑优化
                # 原逻辑: width >= 3840 and height >= 2160 (只支持横向 4K)
                # 新逻辑: 只要长边 >= 3840 (支持竖向 4K) 或者 满足横向 4K
                # 考虑到用户可能设置了自定义宽高，我们使用更灵活的判断:
                # 1. 严格匹配: 宽>=MW 且 高>=MH
                # 2. 旋转匹配: 高>=MW 且 宽>=MH (竖图)
                # 3. 只要长边足够大: max(w, h) >= MW (如果 MW 是主要标准)
                
                # 这里我们采用: 只要有一边达到 min_width (默认 3840)，或者 宽>=MW 且 高>=MH
                is_valid = False
                if width >= self.min_width and height >= self.min_height:
                    is_valid = True
                elif height >= self.min_width and width >= self.min_height: # 竖向 4K
                    is_valid = True
                elif max(width, height) >= self.min_width: # 只要长边够长 (比如全景图或超长竖图)
                    is_valid = True
                
                if is_valid:
                    with self.counter_lock:
                        idx = self.counter[0]
                        self.counter[0] += 1
                    
                    filename = f"{save_dir}/{idx:03d}_{width}x{height}.{img.format.lower()}"
                    with open(filename, "wb") as f:
                        f.write(img_content)
                    print(f"[✔ 捕获目标] {width}x{height} -> {os.path.basename(filename)}")
                else:
                    # 调试日志：显示被忽略的图片尺寸，方便排查
                    # 只显示稍微大一点的图，避免刷屏
                    if width > 1000 or height > 1000:
                        print(f"[跳过] {width}x{height} (不满足 {self.min_width}x{self.min_height}) - {img_url[-30:]}")
        except Exception:
            pass

    def _scan_page(self, page, url):
        """页面扫描逻辑"""
        print(f"目标 URL: {url}")
        self.image_urls.clear() # 清空上一页的记录
        
        # 1. 监听网络请求
        def handle_response(response):
            try:
                if response.request.resource_type == "image":
                    self._add_url(response.url)
                elif "image" in response.headers.get("content-type", ""):
                    self._add_url(response.url)
            except:
                pass
        
        # 移除旧的监听器 (如果有) - Playwright page 对象通常是新的，所以不需要
        page.on("response", handle_response)

        try:
            page.goto(url, timeout=60000)
        except Exception as e:
            print(f"页面加载警告: {e}")

        # 2. 获取标题 (如果需要外部调用者处理，这里可以返回)
        page_title = ""
        try:
            page_title = page.locator("h1").first.inner_text()
            if not page_title: page_title = page.title()
        except:
            page_title = page.title()

        # 3. 模拟滚动
        print("正在滚动页面以触发懒加载...")
        try:
            last_height = page.evaluate("document.body.scrollHeight")
            while True:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1.5)
                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
        except Exception as e:
            print(f"滚动时出错: {e}")

        # 4. DOM 扫描
        print("正在扫描 DOM 结构...")
        try:
            dom_images = page.evaluate("""() => {
                const urls = [];
                document.querySelectorAll('img').forEach(img => {
                    if (img.src) urls.push(img.src);
                    if (img.dataset.src) urls.push(img.dataset.src);
                    if (img.srcset) {
                        // 提取 srcset 中的最大图
                        const sources = img.srcset.split(',');
                        const lastSource = sources[sources.length - 1].trim().split(' ')[0];
                        if (lastSource) urls.push(lastSource);
                    }
                });
                document.querySelectorAll('*').forEach(el => {
                    const style = window.getComputedStyle(el);
                    const bg = style.backgroundImage;
                    if (bg && bg !== 'none') {
                        const match = bg.match(/url\\(['"]?(.*?)['"]?\\)/);
                        if (match) urls.push(match[1]);
                    }
                });
                return urls;
            }""")
            for u in dom_images:
                self._add_url(u)
        except Exception as e:
            print(f"DOM 扫描出错: {e}")

        # 5. 深度扫描 __NEXT_DATA__ (针对 Sotheby's 等 Next.js 站点)
        print("正在扫描 __NEXT_DATA__ 数据...")
        try:
            import json
            next_data = page.evaluate("""() => {
                const el = document.getElementById('__NEXT_DATA__');
                return el ? el.innerText : null;
            }""")
            
            if next_data:
                data = json.loads(next_data)
                
                # 递归查找所有 URL
                def find_urls(obj):
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if isinstance(v, str):
                                if v.startswith('http') and any(ext in v.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                                    self._add_url(v)
                            else:
                                find_urls(v)
                    elif isinstance(obj, list):
                        for item in obj:
                            find_urls(item)
                
                find_urls(data)
                print("已处理 __NEXT_DATA__ 中的潜在图片链接")
        except Exception as e:
            print(f"__NEXT_DATA__ 扫描出错: {e}")
            
        return page_title

    def _download_images(self, output_dir):
        """并发下载逻辑"""
        print(f"分析完成！共发现 {len(self.image_urls)} 个潜在资源。")
        
        # 如果设置了 base_dir，则在其下创建子文件夹
        if self.base_dir:
            final_dir = os.path.join(self.base_dir, output_dir)
        else:
            final_dir = output_dir
            
        if not os.path.exists(final_dir):
            os.makedirs(final_dir)
        
        print(f"开始并发下载 (线程数: {self.max_workers})...")
        # 重置计数器
        self.counter = [1]
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for img_url in list(self.image_urls): # 使用副本进行迭代
                executor.submit(self._process_image, img_url, final_dir)
        
        print(f"任务结束。请查看文件夹: {final_dir}")

    def run(self, url, output_dir=None):
        """执行单个下载任务"""
        print(f"启动下载器...")
        print(f"过滤标准: {self.min_width}x{self.min_height}")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context()
            page = context.new_page()
            
            fetched_title = self._scan_page(page, url)
            
            if not output_dir:
                output_dir = self.sanitize_filename(fetched_title)
            
            print(f"保存目录: {output_dir}")
            browser.close()
            
            self._download_images(output_dir)

    def run_batch(self, tasks):
        """批量执行任务，复用浏览器实例"""
        print(f"启动批量下载器...")
        print(f"任务数量: {len(tasks)}")
        print(f"过滤标准: {self.min_width}x{self.min_height}")
        
        with sync_playwright() as p:
            # 启动浏览器
            browser = p.chromium.launch(headless=self.headless)
            
            for i, (url, title) in enumerate(tasks):
                print(f"\n{'='*20} 正在执行任务 [{i+1}/{len(tasks)}] {'='*20}")
                
                try:
                    # 为每个任务创建新上下文，确保隔离
                    context = browser.new_context()
                    page = context.new_page()
                    
                    fetched_title = self._scan_page(page, url)
                    
                    # 确定输出目录
                    if title:
                        final_title = title
                    else:
                        final_title = fetched_title
                    
                    save_dir = self.sanitize_filename(final_title)
                    print(f"保存目录: {save_dir}")
                    
                    context.close() # 关闭上下文
                    
                    # 下载图片 (不需要浏览器)
                    self._download_images(save_dir)
                    
                except Exception as e:
                    print(f"❌ 任务失败: {url}\n原因: {e}")
            
            browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="通用高清图片下载器 (复刻 ImageAssistant 核心逻辑)")
    parser.add_argument("input", help="要抓取的网页 URL 或包含 URL 的文本文件路径 (.txt)")
    parser.add_argument("--width", type=int, default=3840, help="最小宽度 (默认: 3840)")
    parser.add_argument("--height", type=int, default=2160, help="最小高度 (默认: 2160)")
    parser.add_argument("--headless", action="store_true", default=True, help="是否使用无头模式 (默认: True)")
    parser.add_argument("--no-headless", action="store_false", dest="headless", help="关闭无头模式 (显示浏览器)")
    parser.add_argument("--base-dir", type=str, default=None, help="所有商品文件夹的根目录 (默认: 当前目录)")
    
    args = parser.parse_args()
    
    downloader = ImageDownloader(
        min_width=args.width, 
        min_height=args.height, 
        headless=args.headless,
        base_dir=args.base_dir
    )

    # 判断输入是文件还是 URL
    if os.path.isfile(args.input):
        print(f"检测到输入为文件: {args.input}")
        tasks = []
        with open(args.input, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'): continue
                
                # 解析 URL # Title 格式
                parts = line.split('#', 1)
                url = parts[0].strip()
                title = parts[1].strip() if len(parts) > 1 else None
                
                if url:
                    tasks.append((url, title))
        
        print(f"共读取到 {len(tasks)} 个任务。")
        
        # 使用批量模式执行
        downloader.run_batch(tasks)
            
    else:
        # 单个 URL 模式
        downloader.run(args.input)
