# 拍卖图片批量下载工具集

这是一个专为拍卖网站设计的图片批量下载工具集，包含列表抓取器和高清图片下载器两个核心模块。

## 📦 项目组成

### 1. 列表抓取器 (`list_scraper.py`)
自动抓取拍卖列表页面，提取所有商品链接和标题，支持自动翻页。

### 2. 图片下载器 (`image_extractor.py`)
批量下载商品详情页的高清图片，支持 4K 及以上分辨率筛选。

## ✨ 核心功能

### 列表抓取器特性
*   **自动翻页**：智能识别 Next 按钮，自动遍历所有页面
*   **Cookie 处理**：自动处理 Cookie Banner，避免点击拦截
*   **结构化输出**：生成 `URL # 标题` 格式的列表文件
*   **详细日志**：实时显示抓取进度和状态

### 图片下载器特性
*   **深度扫描**：支持 Next.js `__NEXT_DATA__` 数据提取，获取隐藏的高清原图
*   **智能原图解析**：自动去除 URL 参数，还原 CDN 缩略图背后的原始大图
*   **多维度抓取**：结合网络嗅探、DOM 扫描、srcset 解析、背景图提取
*   **灵活筛选**：支持横向/竖向 4K，以及长边优先模式
*   **批量优化**：复用浏览器实例，大幅提升批量任务效率
*   **极速下载**：多线程并发下载（默认 10 线程）
*   **自动归档**：使用商品标题作为文件夹名，自动整理

## 🛠️ 环境准备

确保你的电脑上安装了 Python 3。

1.  **安装依赖库**：
    ```bash
    pip install playwright requests Pillow
    ```

2.  **安装浏览器驱动** (Playwright)：
    ```bash
    playwright install chromium
    ```

## 🚀 使用指南

### 完整工作流程

#### 第一步：抓取商品列表

```bash
python3 list_scraper.py "https://www.sothebys.com/en/buy/auction/2024/china-5000-years?locale=zh-Hant"
```

这会生成 `urls.txt` 文件，包含所有商品链接和标题：
```text
# Source: https://www.sothebys.com/en/buy/auction/2024/china-5000-years?locale=zh-Hant
# Total Items: 99
# Date: 2025-11-19 09:41:31

https://www.sothebys.com/en/buy/.../item1 # 201. A yellow-ground green and aubergine-enamelled 'dragon' dish...
https://www.sothebys.com/en/buy/.../item2 # 202. Two green-enamelled 'dragon' dishes...
```

#### 第二步：批量下载图片

```bash
python3 image_extractor.py urls.txt
```

脚本会：
1. 读取 `urls.txt` 中的所有商品链接
2. 使用标题作为文件夹名
3. 自动下载每个商品的所有 4K 高清图片
4. 保存到对应的文件夹中

### 单个商品下载

```bash
python3 image_extractor.py "https://www.sothebys.com/en/buy/auction/2024/china-5000-years/item-url"
```

### 自定义筛选尺寸

**下载 1920x1080 (1080P) 及以上的图片**
```bash
python3 image_extractor.py urls.txt --width 1920 --height 1080
```

### 调试模式

```bash
python3 image_extractor.py urls.txt --no-headless
```

## 📝 参数说明

### list_scraper.py

| 参数 | 说明 |
| :--- | :--- |
| `url` | 列表页 URL（必填） |
| `--output` | 输出文件路径（默认: urls.txt） |

### image_extractor.py

| 参数 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `input` | 必填 | 目标 URL 或包含 `URL # Title` 格式的文本文件 |
| `--width` | 3840 | 最小图片宽度 |
| `--height` | 2160 | 最小图片高度 |
| `--no-headless` | False | 显示浏览器窗口 |

## 🎯 尺寸筛选逻辑

脚本采用灵活的筛选策略，满足以下任一条件即可下载：

1. **标准 4K**：宽 ≥ 3840 且 高 ≥ 2160
2. **竖向 4K**：高 ≥ 3840 且 宽 ≥ 2160
3. **长边优先**：max(宽, 高) ≥ 3840（适用于全景图或超长竖图）

## 📂 输出结构

```
/Users/zhangran/Downloads/app/0000/
├── 201. A yellow-ground green and aubergine-enamelled.../
│   ├── 001_4096x4096.jpeg
│   ├── 002_4096x4096.jpeg
│   └── ...
├── 202. Two green-enamelled 'dragon' dishes.../
│   ├── 001_4096x4096.jpeg
│   └── ...
└── urls.txt
```

## 🔧 高级特性

### __NEXT_DATA__ 深度扫描

针对 Next.js 网站（如 Sotheby's），脚本会：
1. 提取页面中的 `<script id="__NEXT_DATA__">` 数据
2. 递归解析 JSON 结构
3. 提取所有隐藏的高清图片链接
4. 这些链接通常是 4096x4096 的原图，普通扫描无法获取

### 批量处理优化

使用 `run_batch()` 方法时：
- 复用同一个浏览器实例
- 为每个任务创建独立上下文（确保隔离）
- 避免重复启动浏览器，速度提升 3-5 倍

### URL 清理策略

自动尝试多种 URL 变体：
```python
# 原始 URL
https://example.com/image.jpg?width=800

# 自动添加的变体
https://example.com/image.jpg              # 去除参数
https://example.com/original.jpg           # 从嵌套参数提取
```

## 💻 Python 代码调用

```python
from image_extractor import ImageDownloader

# 批量任务
downloader = ImageDownloader(min_width=3840, min_height=2160)
tasks = [
    ("https://example.com/item1", "Item 1 Title"),
    ("https://example.com/item2", "Item 2 Title"),
]
downloader.run_batch(tasks)

# 单个任务
downloader.run("https://example.com/item", output_dir="Custom Folder Name")
```

## 📊 日志示例

```
启动批量下载器...
任务数量: 99
过滤标准: 3840x2160

==================== 正在执行任务 [1/99] ====================
目标 URL: https://www.sothebys.com/en/buy/auction/2024/china-5000-years/item1
正在滚动页面以触发懒加载...
正在扫描 DOM 结构...
正在扫描 __NEXT_DATA__ 数据...
已处理 __NEXT_DATA__ 中的潜在图片链接
保存目录: 201. A yellow-ground green and aubergine-enamelled...
分析完成！共发现 64 个潜在资源。
开始并发下载 (线程数: 10)...
[✔ 捕获目标] 4096x4096 -> 001_4096x4096.jpeg
[✔ 捕获目标] 4096x4096 -> 002_4096x4096.jpeg
[跳过] 2048x2048 (不满足 3840x2160) - ...
任务结束。请查看文件夹: 201. A yellow-ground green and aubergine-enamelled...
```

## 🎓 适用场景

- 拍卖网站商品图片批量下载
- 艺术品高清图片收集
- 博物馆藏品图片归档
- 任何需要批量下载高清图片的场景

## ⚡ 性能调优

### 并发数设置

脚本默认使用 **100 线程并发下载**，可通过修改代码调整：

```python
# 在 image_extractor.py 第 14 行
def __init__(self, min_width=3840, min_height=2160, headless=True, max_workers=100, base_dir=None):
```

**推荐配置：**

| 任务规模 | 推荐并发数 | 说明 |
|---------|-----------|------|
| 小批量（<50 个商品） | 10-20 | 稳定可靠，便于调试 |
| 中批量（50-200 个） | 30-50 | **推荐配置**，平衡速度和稳定性 |
| 大批量（>200 个） | 30-50 | 避免触发服务器限制 |
| 测试/极限 | 100+ | 仅用于测试，可能被限流 |

### 并发数过高的潜在问题

1. **服务器限制**
   - IP 可能被临时封禁（403/429 错误）
   - CDN 连接数限制
   - 触发反爬虫机制

2. **系统资源**
   - 文件描述符耗尽（macOS 默认限制 256-1024）
   - 内存占用增加（100 线程约 100-800MB）
   - CPU 线程切换开销

3. **下载质量**
   - 部分请求可能超时失败
   - 网络带宽瓶颈导致速度无法进一步提升

### 性能监控

运行时可通过以下方式监控：

```bash
# 查看系统资源占用
top -pid $(pgrep -f image_extractor)

# 查看网络连接数
lsof -i -n | grep Python | wc -l
```

**优化建议：**
- 如果看到大量 `[跳过]` 或超时，降低并发数
- 如果 CPU 使用率 > 80%，降低并发数
- 如果下载速度没有明显提升，说明已达带宽上限
