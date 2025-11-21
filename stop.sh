#!/bin/bash

# 苏富比抓取工具停止脚本
# 停止后端服务

echo "=========================================="
echo "  停止苏富比抓取工具"
echo "=========================================="
echo ""

# 查找占用5001端口的进程
PID=$(lsof -ti:5001 2>/dev/null)

if [ -z "$PID" ]; then
    echo "ℹ️  没有发现运行中的服务"
    exit 0
fi

echo "🔍 发现进程: $PID"
echo "🛑 正在停止服务..."

# 终止进程
kill $PID 2>/dev/null

# 等待进程结束
sleep 1

# 检查是否成功停止
if lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  进程未响应,强制终止..."
    kill -9 $PID 2>/dev/null
    sleep 1
fi

# 再次检查
if lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "❌ 停止失败"
    exit 1
else
    echo "✅ 服务已停止"
fi

echo ""
