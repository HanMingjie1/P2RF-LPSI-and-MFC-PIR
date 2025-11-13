import spu
import secretflow as sf
import numpy as np
import random
import time
import sys
from io import StringIO

# -------------------------- 临时重定向stdout用于捕获SPU日志 --------------------------
class Capturing:
    def __enter__(self):
        self._old_stdout = sys.stdout
        sys.stdout = self._stringio = StringIO()
        return self

    def __exit__(self, *args):
        self.output = self._stringio.getvalue()
        sys.stdout = self._old_stdout

# -------------------------- 初始化与配置 --------------------------
sf.init(['sender', 'receiver'], address='local')

cheetah_config = sf.utils.testing.cluster_def(
    parties=['sender', 'receiver'],
    runtime_config={
        'protocol': "SEMI2K",
        'field': "FM64",
        'enable_pphlo_profile': True,
        'enable_hal_profile': True,  # 关键：启用通信日志
    },
)

spu_device2 = sf.SPU(cheetah_config)
sender, receiver = sf.PYU('sender'), sf.PYU('receiver')

# -------------------------- 数据生成 --------------------------
start_data_gen = time.perf_counter()
#n = 1 << 16  # 65536行
n=1<<20
dnum = 1   # 维度数

ops = {
    ">": [0, 2, -1],
    ">=": [1, 0.5, -0.5],
    "<": [0, -0.5, 0.5],
    "<=": [1, -2, 1],
    "=": [1, -1.5, 0.5],
    "/": [1, 0, 0]
} 

symbols = [">", "<", "=", ">=", "<=", "/"]
opsshare = {"AND": [0, 1], "OR": [1, -1]}
conops = ["AND", "OR"]

op_list = [random.choice(symbols) for _ in range(dnum)]
con_list = [random.choice(conops) for _ in range(dnum-1)]

predicate_num = np.random.randint(
    np.iinfo(np.int32).min, 
    np.iinfo(np.int32).max, 
    size=dnum, 
    dtype=np.int32
)
predicate_matrix = np.tile(predicate_num, (n, 1))
sender_features = np.random.randint(
    np.iinfo(np.int32).min, 
    np.iinfo(np.int32).max, 
    size=(n, dnum), 
    dtype=np.int32
)
end_data_gen = time.perf_counter()
time_data_gen = end_data_gen - start_data_gen

# -------------------------- 计算函数 --------------------------
def greater(x, y):
    return (x > y)

def smaller(x, y):
    return (x < y)

def compare(x, y):
    return x.astype(int) + (y.astype(int) << 1)

def sub(x, y):
    return x - y

def poly(x, i, op):
    return op[0] + op[1] * x[:, i] + op[2] * x[:, i] ** 2

def im(x, y, op):
    return op[0] * (x + y) + op[1] * (x * y)

def COMPARE():
    x = sf.to(sender, sender_features)
    y = sf.to(receiver, predicate_matrix)
    op_greater = spu_device2(greater)(x, y)
    op_smaller = spu_device2(smaller)(x, y)
    res = spu_device2(compare)(op_greater, op_smaller)
    return res 

def PPT(res):
    ppts = []
    for i in range(dnum):
        if op_list[i] == ">":
            ss_ops = sf.to(receiver, ops[">"])
        elif op_list[i] == ">=":
            ss_ops = sf.to(receiver, ops[">="])
        elif op_list[i] == "<":
            ss_ops = sf.to(receiver, ops["<"])
        elif op_list[i] == "<=":
            ss_ops = sf.to(receiver, ops["<="])
        elif op_list[i] == "=":
            ss_ops = sf.to(receiver, ops["="])
        else:
            ss_ops = sf.to(receiver, ops["/"])
        ppt = spu_device2(poly)(res, i, ss_ops)
        ppts.append(ppt)
    return ppts

def IM(ppts):
    srres = ppts[0]
    for i in range(1, dnum):
        if con_list[i-1] == "AND":
            ss_ops = sf.to(receiver, opsshare["AND"])
        else:
            ss_ops = sf.to(receiver, opsshare["OR"])
        srres = spu_device2(im)(srres, ppts[i], ss_ops)
    return srres

# -------------------------- 执行核心步骤并捕获通信日志 --------------------------
with Capturing() as capture:  # 捕获SPU输出的通信日志
    # 1. COMPARE步骤
    start_compare = time.perf_counter()
    res = COMPARE()
    sf.reveal(res)
    end_compare = time.perf_counter()
    time_compare = end_compare - start_compare

    # 2. PPT步骤
    start_ppt = time.perf_counter()
    ppts = PPT(res)
    sf.reveal(ppts)
    end_ppt = time.perf_counter()
    time_ppt = end_ppt - start_ppt

    # 3. IM步骤
    start_im = time.perf_counter()
    srres = IM(ppts)
    sf.reveal(srres)
    end_im = time.perf_counter()
    time_im = end_im - start_im

    # 4. 后续处理步骤
    start_post = time.perf_counter()
    receivershare = np.random.randint(0, 65536, size=n, dtype=np.int32)
    ones_vector = np.ones(n, dtype=np.int32)
    spu_receivershare = sf.to(receiver, receivershare)
    spu_sendershare = spu_device2(sub)(srres, spu_receivershare)
    sendershare = sf.reveal(spu_sendershare).astype(int)
    receivershare = ones_vector - receivershare
    end_post = time.perf_counter()
    time_post = end_post - start_post

# -------------------------- 解析日志计算总通信量（MB） --------------------------
total_send_bytes = 0
total_recv_bytes = 0
log_lines = capture.output.split('\n')

# 从日志中提取send bytes和recv bytes（匹配SPU日志格式）
for line in log_lines:
    if 'send bytes' in line and 'recv bytes' in line:
        # 提取数字部分（例如："send bytes 587202560 recv bytes 587202560"）
        parts = line.split()
        send_idx = parts.index('send') + 2  # 'send'后第2个是字节数
        recv_idx = parts.index('recv') + 2  # 'recv'后第2个是字节数
        try:
            total_send_bytes += int(parts[send_idx])
            total_recv_bytes += int(parts[recv_idx])
        except (ValueError, IndexError):
            continue

# 转换为MB（1 MB = 1024*1024字节）
total_comm_mb = (total_send_bytes + total_recv_bytes) / (1024 * 1024)

# -------------------------- 计算时间占比 --------------------------
total_time = time_data_gen + time_compare + time_ppt + time_im + time_post

if total_time == 0:
    pct_data_gen = pct_compare = pct_ppt = pct_im = pct_post = 0.0
else:
    pct_data_gen = (time_data_gen / total_time) * 100
    pct_compare = (time_compare / total_time) * 100
    pct_ppt = (time_ppt / total_time) * 100
    pct_im = (time_im / total_time) * 100
    pct_post = (time_post / total_time) * 100

# -------------------------- 写入结果（含通信消耗） --------------------------
with open('../../bazel-bin/examples/pfrpsi/receivershare', 'w') as file:
    for value in receivershare:
        file.write(f"{value}\n")

with open('../../bazel-bin/examples/pfrpsi/sendershare', 'w') as file:
    for value in sendershare:
        file.write(f"{value}\n")

with open('../../bazel-bin/examples/pfrpsi/s3r_timings.txt', 'w') as f:
    f.write("=== 各步骤时间统计（含数据生成） ===\n")
    f.write(f"0. 数据生成时间: {time_data_gen:.9f} 秒 (占比: {pct_data_gen:.2f}%)\n")
    f.write(f"1. COMPARE 时间: {time_compare:.9f} 秒 (占比: {pct_compare:.2f}%)\n")
    f.write(f"2. PPT 时间:     {time_ppt:.9f} 秒 (占比: {pct_ppt:.2f}%)\n")
    f.write(f"3. IM 时间:      {time_im:.9f} 秒 (占比: {pct_im:.2f}%)\n")
    f.write(f"4. 后续处理时间: {time_post:.9f} 秒 (占比: {pct_post:.2f}%)\n")
    f.write("--------------------------\n")
    f.write(f"总耗时:          {total_time:.9f} 秒 (100.00%)\n")
    f.write(f"数据规模:        n={n}（{n//1024}K行）, dnum={dnum}（维度）\n")
    # 新增通信消耗统计
    f.write("--------------------------\n")
    f.write(f"通信消耗统计:     总发送字节={total_send_bytes} B, 总接收字节={total_recv_bytes} B\n")
    f.write(f"总通信量:        {total_comm_mb:.2f} MB\n")

sf.shutdown()

