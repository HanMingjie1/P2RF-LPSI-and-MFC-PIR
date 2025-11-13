import spu
import secretflow as sf
import numpy as np
import random
import time
import sys
import os  # 用于路径处理
from io import StringIO

# -------------------------- 目标路径配置（确保存在且可写） --------------------------
TARGET_DIR = '/home/hmj/yacl/bazel-bin/examples/pfrpsi'
os.makedirs(TARGET_DIR, exist_ok=True)  # 确保目录存在

# -------------------------- 临时重定向stdout，捕获SPU通信日志 --------------------------
class Capturing:
    def __enter__(self):
        self._old_stdout = sys.stdout
        sys.stdout = self._stringio = StringIO()
        return self

    def __exit__(self, *args):
        self.output = self._stringio.getvalue()
        sys.stdout = self._old_stdout

# -------------------------- 初始化SPU --------------------------
sf.init(['sender', 'receiver'], address='local')

cheetah_config = sf.utils.testing.cluster_def(
    parties=['sender', 'receiver'],
    runtime_config={
        'protocol': "SEMI2K",
        'field': "FM64",
        'enable_pphlo_profile': True,
        'enable_hal_profile': True,  # 开启通信日志
    },
)

spu_device2 = sf.SPU(cheetah_config)
sender, receiver = sf.PYU('sender'), sf.PYU('receiver')

# -------------------------- 数据生成（仅保留COMPARE所需） --------------------------
n = 1 << 20  # 1024行（可调整）
dnum = 20  # 维度数

# 生成发送方和接收方数据（仅用于比较）
predicate_num = np.random.randint(
    np.iinfo(np.int32).min, 
    np.iinfo(np.int32).max, 
    size=dnum, 
    dtype=np.int32
)
predicate_matrix = np.tile(predicate_num, (n, 1))  # 接收方数据
sender_features = np.random.randint(
    np.iinfo(np.int32).min, 
    np.iinfo(np.int32).max, 
    size=(n, dnum), 
    dtype=np.int32
)  # 发送方数据

# -------------------------- COMPARE阶段核心函数 --------------------------
def greater(x, y):
    return (x > y)

def smaller(x, y):
    return (x < y)

def compare(x, y):
    # 编码规则：0=等于，1=大于，2=小于
    return x.astype(int) * 1 + y.astype(int) * 2  

def COMPARE():
    x = sf.to(sender, sender_features)  # 发送方数据传入SPU
    y = sf.to(receiver, predicate_matrix)  # 接收方数据传入SPU
    op_greater = spu_device2(greater)(x, y)  # 比较x>y
    op_smaller = spu_device2(smaller)(x, y)  # 比较x<y
    res = spu_device2(compare)(op_greater, op_smaller)  # 合并结果
    return res 

# -------------------------- 执行COMPARE阶段并捕获日志 --------------------------
with Capturing() as capture:
    # 仅记录COMPARE阶段的时间
    start_compare = time.perf_counter()
    res = COMPARE()
    compare_result = sf.reveal(res)  # 解密比较结果
    end_compare = time.perf_counter()
    time_compare = end_compare - start_compare  # COMPARE阶段耗时

# -------------------------- 解析COMPARE阶段的通信量 --------------------------
total_send_bytes = 0
total_recv_bytes = 0
log_lines = capture.output.split('\n')

# 提取COMPARE阶段的发送和接收字节数
for line in log_lines:
    if 'send bytes' in line and 'recv bytes' in line:
        parts = line.strip().split()
        try:
            send_idx = parts.index('send') + 2
            recv_idx = parts.index('recv') + 2
            total_send_bytes += int(parts[send_idx])
            total_recv_bytes += int(parts[recv_idx])
        except (ValueError, IndexError):
            continue

# 转换为MB
compare_comm_mb = (total_send_bytes + total_recv_bytes) / (1024 * 1024)

# -------------------------- 写入结果（仅保留必要文件） --------------------------
# 1. 写入COMPARE比较结果
compare_result_path = os.path.join(TARGET_DIR, 'compare_result.txt')
with open(compare_result_path, 'w') as f:
    for row in compare_result:
        f.write(' '.join(map(str, row)) + '\n')

# 2. 写入COMPARE阶段的时间和通信统计
stats_path = os.path.join(TARGET_DIR, 'compare_stats.txt')
with open(stats_path, 'w') as f:
    f.write(f"=== COMPARE阶段统计 ===\n")
    f.write(f"数据规模:        {n}行 × {dnum}维度\n")
    f.write(f"COMPARE耗时:     {time_compare:.9f} 秒\n")
    f.write("--------------------------\n")
    f.write(f"通信消耗:\n")
    f.write(f"   发送字节: {total_send_bytes:,} B\n")
    f.write(f"   接收字节: {total_recv_bytes:,} B\n")
    f.write(f"   总通信量: {compare_comm_mb:.2f} MB\n")

# -------------------------- 清理与提示 --------------------------
sf.shutdown()
print(f"执行完成！仅保留COMPARE阶段结果：")
print(f"比较结果文件: {compare_result_path}")
print(f"统计文件: {stats_path}")

