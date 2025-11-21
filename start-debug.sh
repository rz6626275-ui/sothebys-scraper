#!/bin/bash

# 苏富比抓取工具启动脚本 (调试模式)
# 前台运行,显示实时日志

echo "=========================================="
echo "  苏富比抓取工具 (调试模式)"
echo "=========================================="
echo ""

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 python3"
    echo "请先安装 Python 3"
    exit 1
fi

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 检查端口是否被占用
if lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  端口 5001 已被占用"
    echo "正在尝试终止占用进程..."
    lsof -ti:5001 | xargs kill -9 2>/dev/null
    sleep 1
fi

echo "🚀 正在启动后端服务 (前台模式)..."
echo "=========================================="
echo ""

# 延迟打开浏览器
(sleep 3 && open http://localhost:5001) &

# 前台运行服务,显示所有日志
echo "💡 提示: 按 Ctrl+C 停止服务"
echo ""
python3 app.py

# 服务停止后的清理
echo ""
echo "=========================================="
echo "✅ 服务已停止"
echo "=========================================="
