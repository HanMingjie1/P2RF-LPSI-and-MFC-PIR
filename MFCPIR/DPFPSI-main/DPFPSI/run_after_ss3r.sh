#!/bin/bash

# 在ss3r.py手动执行后，运行三方协作DPF协议
# 前提：ss3r.py已经生成了Q_result_*.txt文件

# 定义构建目录和可执行文件路径
BUILD_DIR="/home/hmj/MFCPIR/DPFPSI-main/DPFPSI/build"
AIDSERVER_CLI="$BUILD_DIR/bin/AidServer_cli"
SERVER_CLI="$BUILD_DIR/bin/Server_cli"
CLIENT_CLI="$BUILD_DIR/bin/Client_cli"

# 协议参数
THREADS=8
LOG_SET_SIZE=20

echo "=== 三方协作DPF协议执行 ==="
echo "前提：ss3r.py已手动执行并生成Q文件"
echo ""

# 清理环境
echo "=== 清理环境 ==="
pkill -f "AidServer_cli\|Server_cli\|Client_cli" 2>/dev/null || true
rm -f "$BUILD_DIR/../cli/server_data.txt" "$BUILD_DIR/../cli/client_result.txt" "$BUILD_DIR/../cli/time.txt"
sleep 2

# 查找最新的Q文件
echo "=== 查找ss3r.py生成的Q文件 ==="
LATEST_Q_FILE=$(find "$BUILD_DIR/.." -name "Q_result_*.txt" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)

if [ -n "$LATEST_Q_FILE" ] && [ -f "$LATEST_Q_FILE" ]; then
    echo "找到Q文件: $(basename "$LATEST_Q_FILE")"
    echo "Q文件路径: $LATEST_Q_FILE"
    echo "Q文件内容预览:"
    head -10 "$LATEST_Q_FILE"
    echo ""
else
    echo "错误: 未找到ss3r.py生成的Q文件"
    echo "请先手动执行ss3r.py生成Q文件"
    exit 1
fi

# 在运行三方前，根据 -l 修改 DPF 参数并重新编译（运行时分派：支持 10,12,14,16,18,20）
echo "=== 配置 DPF 参数并构建（运行时分派） ==="
ALLOWED_BITS=(10 12 14 16 18 20)
is_allowed=false
for v in "${ALLOWED_BITS[@]}"; do
    if [ "$v" = "$LOG_SET_SIZE" ]; then is_allowed=true; break; fi
done

if [ "$is_allowed" != true ]; then
    echo "错误: -l 仅支持 {10,12,14,16,18,20}，当前为 $LOG_SET_SIZE"
    exit 1
fi

PARAM_H_PATH="$BUILD_DIR/../src/psi/param.h"
if [ ! -f "$PARAM_H_PATH" ]; then
    echo "错误: 未找到 $PARAM_H_PATH"
    exit 1
fi

# 计算输入字节数 = ceil(bits/8)
if command -v python3 >/dev/null 2>&1; then
    DPF_INPUT_BYTE_SIZE=$(python3 - <<PY
bits=$LOG_SET_SIZE
print((bits+7)//8)
PY
)
else
    # 备用：纯 bash 计算
    bits=$LOG_SET_SIZE
    DPF_INPUT_BYTE_SIZE=$(( (bits + 7) / 8 ))
fi

echo "设置 DPF_INPUT_BIT_SIZE=$LOG_SET_SIZE, DPF_INPUT_BYTE_SIZE=$DPF_INPUT_BYTE_SIZE"

# 就地修改 param.h 中的常量定义
sed -i -E "s/(constexpr size_t DPF_INPUT_BIT_SIZE = )[0-9]+;/\1$LOG_SET_SIZE;/" "$PARAM_H_PATH"
sed -i -E "s/(constexpr size_t DPF_INPUT_BYTE_SIZE = )[0-9]+;/\1$DPF_INPUT_BYTE_SIZE;/" "$PARAM_H_PATH"

# 重新编译
cmake -S "$BUILD_DIR/.." -B "$BUILD_DIR" >/dev/null
cmake --build "$BUILD_DIR" -j "$THREADS"
BUILD_STATUS=$?
if [ $BUILD_STATUS -ne 0 ]; then
    echo "错误: 构建失败"
    exit 1
fi

# 启动Server (生成随机数据和label)
echo "=== 启动Server (生成数据和label) ==="
echo "Server cmd: $SERVER_CLI -t $THREADS -l $LOG_SET_SIZE"
"$SERVER_CLI" -t "$THREADS" -l "$LOG_SET_SIZE" &
SERVER_PID=$!
echo "Server PID: $SERVER_PID"
sleep 6

# 启动AidServer (辅助DPF协议执行)
echo "=== 启动AidServer (辅助DPF协议) ==="
echo "AidServer cmd: $AIDSERVER_CLI -t $THREADS -l $LOG_SET_SIZE"
"$AIDSERVER_CLI" -t "$THREADS" -l "$LOG_SET_SIZE" &
AidServer_PID=$!
echo "AidServer PID: $AidServer_PID"
sleep 3

# 启动Client (使用ss3r.py生成的Q)
echo "=== 启动Client (使用ss3r.py的Q) ==="
echo "使用Q文件: $(basename "$LATEST_Q_FILE")"
"$CLIENT_CLI" -t "$THREADS" -f "$LATEST_Q_FILE"
CLIENT_EXIT_CODE=$?

# 等待所有后台进程结束
echo "=== 等待协议完成 ==="
wait $AidServer_PID
wait $SERVER_PID

echo ""
echo "=== 协议执行完成 ==="
echo "Client退出码: $CLIENT_EXIT_CODE"

# 显示结果
echo ""
echo "=== Server生成的数据 ==="
if [ -f "$BUILD_DIR/../cli/server_data.txt" ]; then
    cat "$BUILD_DIR/../cli/server_data.txt"
else
    echo "Server数据文件未找到"
fi

echo ""
echo "=== Client查询结果 ==="
if [ -f "$BUILD_DIR/../cli/client_result.txt" ]; then
    cat "$BUILD_DIR/../cli/client_result.txt"
else
    echo "Client结果文件未找到"
fi

echo ""
echo "=== 性能统计 ==="
if [ -f "$BUILD_DIR/../cli/time.txt" ]; then
    cat "$BUILD_DIR/../cli/time.txt"
else
    echo "时间统计文件未找到"
fi

echo ""
echo "=== 协议总结 ==="
echo "✓ AidServer: 辅助DPF协议执行"
echo "✓ Server: 生成随机数据和对应label"
echo "✓ Client: 使用ss3r.py生成的Q进行查询"
echo "✓ Q文件: $(basename "$LATEST_Q_FILE")"
echo "✓ 协议目标: 通过DPF安全获取Q中行号对应的label"

# 计算三方总在线时间和总通信消耗
TIME_FILE="$BUILD_DIR/../cli/time.txt"
if [ -f "$TIME_FILE" ]; then
    echo ""
    echo "=== 计算总统计信息 ==="

    AIDSERVER_ONLINE=$(grep -A 5 "简化DPFPSI AidServer" "$TIME_FILE" | grep "在线处理时间:" | awk '{print $2}' | sed 's/ms//' | tail -n 1)
    SERVER_ONLINE=$(grep -A 5 "简化DPFPSI Server" "$TIME_FILE" | grep "在线处理时间:" | awk '{print $2}' | sed 's/ms//' | tail -n 1)
    CLIENT_ONLINE=$(grep -A 5 "简化DPFPSI Client" "$TIME_FILE" | grep "在线处理时间:" | awk '{print $2}' | sed 's/ms//' | tail -n 1)
    COMMUNICATION_MB=$(grep -A 5 "简化DPFPSI Client" "$TIME_FILE" | grep "通信消耗:" | awk '{print $2}' | sed 's/MB//' | tail -n 1)

    if [ -n "$AIDSERVER_ONLINE" ] && [ -n "$SERVER_ONLINE" ] && [ -n "$CLIENT_ONLINE" ]; then
        TOTAL_ONLINE_MS=$(echo "$AIDSERVER_ONLINE + $SERVER_ONLINE + $CLIENT_ONLINE" | bc)
        TOTAL_ONLINE_S=$(echo "scale=3; $TOTAL_ONLINE_MS / 1000" | bc)

        {
            echo ""
            echo "=== 协议总统计 ==="
            echo "三方总在线时间: $TOTAL_ONLINE_S s"
            if [ -n "$COMMUNICATION_MB" ]; then
                echo "总通信消耗: $COMMUNICATION_MB MB"
            else
                echo "总通信消耗: 0 MB"
            fi
            echo "----------------------------------------"
        } >> "$TIME_FILE"

        echo "✓ 三方总在线时间: $TOTAL_ONLINE_S 秒"
        if [ -n "$COMMUNICATION_MB" ]; then
            echo "✓ 总通信消耗: $COMMUNICATION_MB MB"
        else
            echo "✓ 总通信消耗: 0 MB"
        fi
    else
        echo "警告: 无法从time.txt中提取完整的统计信息"
    fi
fi


exit $CLIENT_EXIT_CODE
