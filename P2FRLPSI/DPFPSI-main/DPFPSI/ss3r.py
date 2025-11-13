import os
import glob
import re
from pathlib import Path
import time

def read_all_files_in_directory(directory_path):
    """
    读取指定目录中的所有文件
    
    Args:
        directory_path (str): 目标目录路径
    
    Returns:
        dict: 文件名到文件内容的映射
    """
    files_content = {}
    
    # 检查目录是否存在
    if not os.path.exists(directory_path):
        print(f"目录不存在: {directory_path}")
        return files_content
    
    # 使用glob递归获取所有文件
    pattern = os.path.join(directory_path, "**", "*")
    all_files = glob.glob(pattern, recursive=True)
    
    # 过滤出文件（排除目录）
    files_only = [f for f in all_files if os.path.isfile(f)]
    
    print(f"找到 {len(files_only)} 个文件")
    
    for file_path in files_only:
        try:
            # 获取相对路径作为键
            relative_path = os.path.relpath(file_path, directory_path)
            
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                files_content[relative_path] = content
                # print(f"已读取: {relative_path} ({len(content)} 字符)")
                
        except Exception as e:
            print(f"读取文件失败 {file_path}: {e}")
            files_content[relative_path] = f"读取失败: {e}"
    
    return files_content

def list_files_in_directory(directory_path):
    """
    列出指定目录中的所有文件（不读取内容）
    
    Args:
        directory_path (str): 目标目录路径
    
    Returns:
        list: 文件路径列表
    """
    files_list = []
    
    if not os.path.exists(directory_path):
        print(f"目录不存在: {directory_path}")
        return files_list
    
    # 使用os.walk递归遍历目录
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, directory_path)
            files_list.append(relative_path)
    
    return files_list

def process_receivershare_to_binary(receivershare_content):
    """
    处理receivershare文件内容，将每行的数值转换为10位二进制字符串并串连，然后转换为字节
    
    Args:
        receivershare_content (str): receivershare文件内容
    
    Returns:
        list: 每行对应的(二进制字符串, 字节数据)元组列表
    """
    import numpy as np
    
    print("开始处理receivershare数据...")
    
    # 按行分割数据
    lines = receivershare_content.strip().split('\n')
    # print(f"总行数: {len(lines)}")
    
    binary_lines = []
    
    for i, line in enumerate(lines):
        # if i % 1000 == 0:  # 每1000行显示进度
        #     print(f"处理进度: {i}/{len(lines)}")
        
        # 按空格分割每行的数值
        values = line.strip().split()
        line_binary_strings = []
        
        for value_str in values:
            try:
                # 转换为整数并取绝对值
                value = abs(int(value_str))
                
                # 转换为10位二进制字符串
                binary_str = format(value, '010b')
                line_binary_strings.append(binary_str)
                
            except ValueError as e:
                print(f"警告: 无法转换值 '{value_str}': {e}")
                continue
        
        # 将当前行的所有二进制字符串连接起来
        line_binary = ''.join(line_binary_strings)
        
        # 填充到能被8整除的长度
        original_length = len(line_binary)
        remainder = original_length % 8
        if remainder != 0:
            padding_length = 8 - remainder
            line_binary += '0' * padding_length
        
        # 计算字节数
        byte_count = len(line_binary) // 8
        
        # 将二进制字符串转换为字节
        line_bytes = int(line_binary, 2).to_bytes(byte_count, byteorder='big')
        
        binary_lines.append((line_binary, line_bytes))
        
        # print(f"第{i+1}行: 原始长度={original_length}位, 填充后长度={len(line_binary)}位, 字节数={byte_count}")
    
    print(f"处理完成!")
    print(f"总行数: {len(binary_lines)}")
    
    # 计算总字节数
    # total_bytes = sum(len(line) // 8 for line, _ in binary_lines)
    # print(f"总字节数: {total_bytes}")
    
    return binary_lines

def update_param_h_dynamic(byte_count):
    """
    动态更新param.h中的Item_byte_size值
    
    Args:
        byte_count (int): 从ss3r.py计算得到的byte_count值
    
    Returns:
        bool: 更新是否成功
    """
    param_file = "/home/hmj/P2FRLPSI/DPFPSI-main/DPFPSI/src/psi/param.h"
    
    if not os.path.exists(param_file):
        print(f"❌ param.h文件不存在: {param_file}")
        return False
    
    # 计算新的Item_byte_size
    new_item_byte_size = 16 + byte_count
    
    try:
        # 读取文件内容
        with open(param_file, 'r') as f:
            content = f.read()
        
        # 查找并替换Item_byte_size
        pattern = r'constexpr size_t Item_byte_size = \d+;'
        replacement = f'constexpr size_t Item_byte_size = {new_item_byte_size};'
        
        if re.search(pattern, content):
            new_content = re.sub(pattern, replacement, content)
            
            # 写回文件
            with open(param_file, 'w') as f:
                f.write(new_content)
            
            print(f"✅ 成功更新param.h: Item_byte_size = 16 + {byte_count} = {new_item_byte_size}")
            return True
        else:
            print("❌ 未找到Item_byte_size定义")
            return False
    except Exception as e:
        print(f"❌ 更新param.h时出错: {e}")
        return False

def get_byte_count_from_output(binary_lines):
    """
    从binary_lines中计算平均byte_count
    
    Args:
        binary_lines (list): (二进制字符串, 字节数据)元组列表
    
    Returns:
        int: 平均byte_count值
    """
    if not binary_lines:
        return 3  # 默认值
    
    byte_counts = []
    for line_binary, line_bytes in binary_lines:
        byte_count = len(line_bytes)
        byte_counts.append(byte_count)
    
    if byte_counts:
        avg_byte_count = sum(byte_counts) / len(byte_counts)
        return int(avg_byte_count)
    else:
        return 3  # 默认值

def main():
    """主函数"""
    target_directory = "/home/hmj/yacl/bazel-bin/examples/pfrpsi"
    
    print(f"目标目录: {target_directory}")
    print("=" * 50)
    
    # 方法1: 列出所有文件
    print("1. 列出所有文件:")
    files_list = list_files_in_directory(target_directory)
    for i, file_path in enumerate(files_list, 1):
        print(f"{i:3d}. {file_path}")
    
    # print(f"\n总共找到 {len(files_list)} 个文件")
    # print("=" * 50)
    
    # 方法2: 读取所有文件内容
    # print("2. 读取所有文件内容:")
    files_content = read_all_files_in_directory(target_directory)
    
    # 显示文件内容统计
    # print("\n文件内容统计:")
    # for file_path, content in files_content.items():
    #     print(f"{file_path}: {len(content)} 字符")
    
    # 处理receivershare文件
    receivershare_binary_lines = None
    conv_time_ms_total = 0.0

    if 'receivershare_all' in files_content:
        print("\n" + "=" * 50)
        # print("3. 处理receivershare数据:")
        t0 = time.perf_counter()
        receivershare_binary_lines = process_receivershare_to_binary(files_content['receivershare_all'])
        t1 = time.perf_counter()
        conv_time_ms_total += (t1 - t0) * 1000.0
        
        # 保存结果到文件，每行包含二进制字符串和对应的字节
        output_file_with_bytes = "/home/hmj/P2FRLPSI/DPFPSI-main/DPFPSI/receivershare_binary_with_bytes.txt"
        with open(output_file_with_bytes, 'w') as f:
            for line_binary, line_bytes in receivershare_binary_lines:
                # 将字节转换为十六进制字符串显示
                hex_bytes = line_bytes.hex()
                f.write(f"{line_binary} {hex_bytes}\n")
        print(f"二进制和字节结果已保存到: {output_file_with_bytes}")
    
    # 处理sendershare文件
    sendershare_binary_lines = None
    if 'sendershare_all' in files_content:
        print("\n" + "=" * 50)
        # print("4. 处理sendershare数据:")
        t0 = time.perf_counter()
        sendershare_binary_lines = process_receivershare_to_binary(files_content['sendershare_all'])
        t1 = time.perf_counter()
        conv_time_ms_total += (t1 - t0) * 1000.0
        
        # 保存结果到文件，每行包含二进制字符串和对应的字节
        output_file_with_bytes = "/home/hmj/P2FRLPSI/DPFPSI-main/DPFPSI/sendershare_binary_with_bytes.txt"
        with open(output_file_with_bytes, 'w') as f:
            for line_binary, line_bytes in sendershare_binary_lines:
                # 将字节转换为十六进制字符串显示
                hex_bytes = line_bytes.hex()
                f.write(f"{line_binary} {hex_bytes}\n")
        print(f"二进制和字节结果已保存到: {output_file_with_bytes}")
    
    # 将仅转换耗时写入文件（供协议结束后汇总到intersection_results.txt）
    try:
        conv_time_path = "/home/hmj/P2FRLPSI/DPFPSI-main/DPFPSI/conv_time_ms.txt"
        with open(conv_time_path, 'w') as f:
            f.write(f"{conv_time_ms_total:.6f}\n")
        print(f"转换耗时(仅转换，不含I/O)：{conv_time_ms_total:.6f} ms 已写入 {conv_time_path}")
    except Exception as e:
        print(f"写入转换耗时失败: {e}")

    # 动态更新param.h中的Item_byte_size
    print("\n" + "=" * 50)
    print("🔄 动态更新param.h中的Item_byte_size...")
    
    # 选择用于计算byte_count的数据源（优先使用receivershare）
    binary_lines_for_update = receivershare_binary_lines or sendershare_binary_lines
    
    if binary_lines_for_update:
        # 计算byte_count
        byte_count = get_byte_count_from_output(binary_lines_for_update)
        print(f"📊 计算得到byte_count: {byte_count}")
        
        # 更新param.h
        success = update_param_h_dynamic(byte_count)
        if success:
            print("🎉 param.h更新完成！")
        else:
            print("💥 param.h更新失败！")
    else:
        print("❌ 没有可用的数据来更新param.h")
    
    return files_content

if __name__ == "__main__":
    files_data = main()
