// API 基础 URL
const API_BASE = '';

// DOM 元素
const scrapeBtn = document.getElementById('scrape-btn');
const scrapeStopBtn = document.getElementById('scrape-stop-btn');
const downloadBtn = document.getElementById('download-btn');
const downloadStopBtn = document.getElementById('download-stop-btn');
const urlInput = document.getElementById('url-input');
const scrapeStatus = document.getElementById('scrape-status');
const downloadStatus = document.getElementById('download-status');
const scrapeProgress = document.getElementById('scrape-progress');
const downloadProgress = document.getElementById('download-progress');
const logContent = document.getElementById('log-content');
const clearLogBtn = document.getElementById('clear-log-btn');

// 状态管理
let eventSource = null;

// 初始化
function init() {
    // 绑定事件
    scrapeBtn.addEventListener('click', startScrape);
    scrapeStopBtn.addEventListener('click', stopTask);
    downloadBtn.addEventListener('click', startDownload);
    downloadStopBtn.addEventListener('click', stopTask);
    clearLogBtn.addEventListener('click', clearLog);

    // 启动日志流
    connectLogStream();

    // 定期更新状态
    setInterval(updateStatus, 1000);
}

// 连接日志流
function connectLogStream() {
    if (eventSource) {
        eventSource.close();
    }

    eventSource = new EventSource('/api/logs');

    eventSource.onmessage = function (event) {
        if (event.data.trim()) {
            addLog(event.data);
        }
    };

    eventSource.onerror = function () {
        console.error('日志流连接错误，5秒后重连...');
        setTimeout(connectLogStream, 5000);
    };
}

// 添加日志
function addLog(message) {
    // 移除占位符
    const placeholder = logContent.querySelector('.log-placeholder');
    if (placeholder) {
        placeholder.remove();
    }

    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.textContent = message;
    logContent.appendChild(entry);

    // 自动滚动到底部
    logContent.scrollTop = logContent.scrollHeight;

    // 限制日志条数
    const entries = logContent.querySelectorAll('.log-entry');
    if (entries.length > 500) {
        entries[0].remove();
    }
}

// 清空日志
function clearLog() {
    logContent.innerHTML = '<div class="log-placeholder">日志已清空</div>';
}

// 更新状态
async function updateStatus() {
    try {
        const response = await fetch('/api/status');
        const status = await response.json();

        // 更新抓取状态
        if (status.scraping) {
            setStatus(scrapeStatus, 'active', '运行中');
            scrapeBtn.disabled = true;
            scrapeStopBtn.disabled = false;
            scrapeProgress.textContent = status.scrape_progress || '处理中...';
        } else {
            setStatus(scrapeStatus, '', '就绪');
            scrapeBtn.disabled = false;
            scrapeStopBtn.disabled = true;
            scrapeProgress.textContent = '';
        }

        // 更新下载状态
        if (status.downloading) {
            setStatus(downloadStatus, 'active', '运行中');
            downloadBtn.disabled = true;
            downloadStopBtn.disabled = false;
            downloadProgress.textContent = status.download_progress || '处理中...';
        } else {
            setStatus(downloadStatus, '', '就绪');
            downloadBtn.disabled = false;
            downloadStopBtn.disabled = true;
            downloadProgress.textContent = '';
        }
    } catch (error) {
        console.error('更新状态失败:', error);
    }
}

// 设置状态指示器
function setStatus(element, className, text) {
    element.className = 'status-indicator ' + className;
    element.querySelector('.text').textContent = text;
}

// 开始抓取
async function startScrape() {
    const url = urlInput.value.trim();

    if (!url) {
        alert('请输入URL');
        return;
    }

    if (!url.startsWith('http')) {
        alert('请输入有效的URL');
        return;
    }

    try {
        const response = await fetch('/api/scrape', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url })
        });

        const result = await response.json();

        if (result.success) {
            addLog('✅ ' + result.message);
        } else {
            addLog('❌ ' + result.message);
            alert(result.message);
        }
    } catch (error) {
        addLog('❌ 请求失败: ' + error.message);
        alert('请求失败: ' + error.message);
    }
}

// 开始下载
async function startDownload() {
    try {
        const response = await fetch('/api/download', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const result = await response.json();

        if (result.success) {
            addLog('✅ ' + result.message);
        } else {
            addLog('❌ ' + result.message);
            alert(result.message);
        }
    } catch (error) {
        addLog('❌ 请求失败: ' + error.message);
        alert('请求失败: ' + error.message);
    }
}

// 停止任务
async function stopTask(event) {
    // 阻止事件冒泡
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }

    try {
        const response = await fetch('/api/stop', {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            addLog('⚠️ ' + result.message);
        } else {
            addLog('❌ ' + result.message);
        }
    } catch (error) {
        addLog('❌ 请求失败: ' + error.message);
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', init);
