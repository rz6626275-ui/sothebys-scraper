#!/bin/bash

# 苏富比抓取工具启动脚本
# 自动启动后端服务并打开浏览器

echo "=========================================="
echo "  苏富比抓取工具"
echo "=========================================="
echo ""

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 python3"
    echo "请先安装 Python 3"
    exit 1
fi

# 检查依赖是否安装
if [ ! -d ".venv" ] && [ ! -f "requirements.txt" ]; then
    echo "⚠️  警告: 未找到虚拟环境或依赖文件"
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

# 启动后端服务(后台运行)
echo "🚀 正在启动后端服务..."
python3 app.py > /dev/null 2>&1 &
BACKEND_PID=$!

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 3

# 检查服务是否成功启动
if ! ps -p $BACKEND_PID > /dev/null 2>&1; then
    echo "❌ 后端服务启动失败"
    echo "请手动运行: python3 app.py"
    exit 1
fi

# 打开浏览器
echo "🌐 正在打开浏览器..."
open http://localhost:5001

echo ""
echo "✅ 启动成功!"
echo "=========================================="
echo "  访问地址: http://localhost:5001"
echo "  后端进程 PID: $BACKEND_PID"
echo "=========================================="
echo ""
echo "💡 提示:"
echo "  - 关闭此终端窗口不会停止服务"
echo "  - 要停止服务,请运行: kill $BACKEND_PID"
echo "  - 或者在浏览器中关闭标签页后运行: lsof -ti:5001 | xargs kill"
echo ""
