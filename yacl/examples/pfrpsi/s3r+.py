import spu
import secretflow as sf
import numpy as np
import random
import time
import sys
from io import StringIO  # 用于捕获SPU日志

# -------------------------- 临时重定向stdout，捕获SPU通信日志 --------------------------
class Capturing:
    def __enter__(self):
        self._old_stdout = sys.stdout
        sys.stdout = self._stringio = StringIO()
        return self

    def __exit__(self, *args):
        self.output = self._stringio.getvalue()  # 保存日志内容
        sys.stdout = self._old_stdout  # 恢复标准输出

# -------------------------- 移除所有种子代码（恢复无种子状态）--------------------------
sf.init(['sender', 'receiver'], address='local')

cheetah_config = sf.utils.testing.cluster_def(
    parties=['sender', 'receiver'],
    runtime_config={
        'protocol': "SEMI2K",
        'field': "FM64",
        'enable_pphlo_profile': True,
        'enable_hal_profile': True,  # 关键：开启通信日志输出
    },
)

spu_device2 = sf.SPU(cheetah_config)
sender, receiver = sf.PYU('sender'), sf.PYU('receiver')

# -------------------------- 数据生成（恢复原无种子随机逻辑）--------------------------
n= 1 << 14  # 1024行（可改为1<<20开启百万级数据）
#n=4 # 小样本量，方便测试
dnum =1 #维度数，可按需调整

ops = {
    ">": [0, 2, -1],
    ">=": [1, 0.5, -0.5],
    "<": [0, -0.5, 0.5],
    "<=": [1, -2, 1],
    "=": [1, -1.5, 0.5],
    "/": [1, 0, 0]
} 

symbols = [">", "<", "=", ">=", "<=", "/"]
opsshare = {"AND": [0, 1], "OR": [1, -1]}  # 保留定义
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
# ------------------------------------------------------------------------

# -------------------------- 定义计算函数（保留原compare编码逻辑）--------------------------
def greater(x, y):
    return (x > y)

def smaller(x, y):
    return (x < y)

def compare(x, y):
    return x.astype(int) * 1 + y.astype(int) * 2  

def sub(x, y):
    return x - y

def poly(x, i, op):
    return op[0] + op[1] * x[:, i] + op[2] * x[:, i] ** 2

def im(x, y, op):  # 保留定义（不调用）
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
        ss_ops = sf.to(receiver, ops[op_list[i]])
        ppt = spu_device2(poly)(res, i, ss_ops)
        ppts.append(ppt)
    return ppts
# ------------------------------------------------------------------------

# -------------------------- 核心：计时+捕获通信日志 --------------------------
with Capturing() as capture:  # 捕获SPU运行时的通信日志
    # 1. 测量 COMPARE 时间 + 计算
    start_compare = time.perf_counter()
    res = COMPARE()
    compare_result = sf.reveal(res)
    end_compare = time.perf_counter()
    time_compare = end_compare - start_compare

    # 2. 测量 PPT 时间 + 计算
    start_ppt = time.perf_counter()
    ppts = PPT(res)
    sf.reveal(ppts)
    end_ppt = time.perf_counter()
    time_ppt = end_ppt - start_ppt

    # 3. 测量后续处理时间 + 计算
    start_post = time.perf_counter()
    ones_vector = np.ones(n, dtype=np.int32)
    sendershare_list = []
    receivershare_list = []

    for i in range(dnum):
        receivershare = np.random.randint(0, 1023, size=n, dtype=np.int32)
        spu_receivershare = sf.to(receiver, receivershare)
        spu_sendershare = spu_device2(sub)(ppts[i], spu_receivershare)
        sendershare = sf.reveal(spu_sendershare).astype(int)
        receivershare = ones_vector - receivershare
        sendershare_list.append(sendershare)
        receivershare_list.append(receivershare)

    end_post = time.perf_counter()
    time_post = end_post - start_post

# -------------------------- 解析日志，计算总通信量（MB） --------------------------
total_send_bytes = 0
total_recv_bytes = 0
log_lines = capture.output.split('\n')  # 按行拆分日志

# 提取所有含“send bytes”和“recv bytes”的日志行，累加通信量
for line in log_lines:
    if 'send bytes' in line and 'recv bytes' in line:
        # 日志格式示例："send bytes 587202560 recv bytes 587202560"
        parts = line.strip().split()
        try:
            # 定位发送/接收字节数的位置
            send_idx = parts.index('send') + 2
            recv_idx = parts.index('recv') + 2
            total_send_bytes += int(parts[send_idx])
            total_recv_bytes += int(parts[recv_idx])
        except (ValueError, IndexError):
            continue  # 跳过格式异常的日志行

# 转换为MB（1 MB = 1024 * 1024 字节）
total_comm_mb = (total_send_bytes + total_recv_bytes) / (1024 * 1024)

# -------------------------- 拼接+写入共享数据文件（不变）--------------------------
sendershare_2d = np.hstack([arr.reshape(-1, 1) for arr in sendershare_list])
receivershare_2d = np.hstack([arr.reshape(-1, 1) for arr in receivershare_list])

with open('../../bazel-bin/examples/pfrpsi/sendershare_all', 'w') as file:
    for row in sendershare_2d:
        file.write(' '.join(map(str, row)) + '\n')

with open('../../bazel-bin/examples/pfrpsi/receivershare_all', 'w') as file:
    for row in receivershare_2d:
        file.write(' '.join(map(str, row)) + '\n')

# -------------------------- 写入COMPARE结果（不变）--------------------------
compare_result_path = '/home/hmj/yacl/bazel-bin/examples/pfrpsi/compare_result.txt'
with open(compare_result_path, 'w') as f:
    for row in compare_result:
        f.write(' '.join(map(str, row)) + '\n')

# -------------------------- 计算总时间和百分比 + 写入时间+通信统计 --------------------------
total_time = time_compare + time_ppt + time_post

if total_time == 0:
    pct_compare = pct_ppt = pct_post = 0.0
else:
    pct_compare = (time_compare / total_time) * 100
    pct_ppt = (time_ppt / total_time) * 100
    pct_post = (time_post / total_time) * 100

# 写入时间统计+通信消耗
with open('../../bazel-bin/examples/pfrpsi/s3r+_timings.txt', 'w') as f:
    #f.write(f"=== 各核心计算步骤时间统计（{dnum}维，无IM步骤） ===\n")
    f.write(f"1. COMPARE 阶段（生成{n}×{dnum}维比较结果）: {time_compare:.9f} 秒 (占比: {pct_compare:.2f}%)\n")
    #f.write(f"   - COMPARE结果已保存至：{compare_result_path}\n")
    #f.write(f"   - 结果编码规则：0=等于（x==y），1=大于（x>y），2=小于（x<y）\n")
    f.write(f"2. PPT 阶段（生成{n}×{dnum}维多项式结果）:     {time_ppt:.9f} 秒 (占比: {pct_ppt:.2f}%)\n")
    f.write(f"3. 共享数据生成（{dnum}维SPU计算+reveal）:     {time_post:.9f} 秒 (占比: {pct_post:.2f}%)\n")
    f.write("--------------------------\n")
    f.write(f"总核心计算时间（不含拼接+写入）:              {total_time:.9f} 秒 (100.00%)\n")
    # 新增通信消耗统计
    f.write("--------------------------\n")
    f.write(f"通信消耗统计（COMPARE+PPT+共享数据生成）:\n")
    f.write(f"   - 总发送字节: {total_send_bytes:,} B\n")
    f.write(f"   - 总接收字节: {total_recv_bytes:,} B\n")
    f.write(f"   - 总通信量:   {total_comm_mb:.2f} MB\n")
    f.write("--------------------------\n")
    f.write(f"排除项说明：\n")
    f.write(f"- 数组拼接（np.hstack）耗时未计入\n")
    f.write(f"- 文件写入（sendershare_all/receivershare_all/compare_result.txt）耗时未计入\n")

sf.shutdown()
print(f"执行完成！时间统计+通信消耗已保存至 s3r+_timings.txt")
