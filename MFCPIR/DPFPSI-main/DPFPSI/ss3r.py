import os
import sys
import re
from typing import List, Set, Dict
from datetime import datetime


COMPARE_RESULT_PATH = "/home/hmj/yacl/bazel-bin/examples/pfrpsi/compare_result.txt"
OUTPUT_DIR = "/home/hmj/MFCPIR/DPFPSI-main/DPFPSI"


def read_compare_result(path: str = COMPARE_RESULT_PATH) -> List[str]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    lines = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            lines.append(line.rstrip("\n"))
    return lines


def parse_data(lines: List[str]) -> List[List[str]]:
    """解析数据，返回二维列表"""
    data = []
    for line in lines:
        if line.strip():  # 跳过空行
            # 按空格或制表符分割
            row = re.split(r'\s+', line.strip())
            data.append(row)
    return data


def get_column_count(data: List[List[str]]) -> int:
    """获取列数"""
    if not data:
        return 0
    return len(data[0])


def select_rows_by_multiple_conditions(data: List[List[str]], column_conditions: Dict[int, str]) -> Set[int]:
    """
    根据多列条件选择行号集合
    column_conditions: {列索引: 目标值} 的字典
    返回满足所有条件的行号集合Q
    """
    Q = set()
    
    for row_index, row in enumerate(data):
        # 检查该行是否满足所有条件
        match_all = True
        
        for column_index, target_value in column_conditions.items():
            if column_index >= len(row) or row[column_index] != target_value:
                match_all = False
                break
        
        if match_all:
            Q.add(row_index)
    
    return Q


def save_Q_to_file(Q: Set[int], column_conditions: Dict[int, str], data: List[List[str]]) -> str:
    """
    将集合Q保存到txt文件
    返回保存的文件路径
    """
    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 生成文件名（包含时间戳）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Q_result_{timestamp}.txt"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        # 写入文件头信息
        f.write(f"# Q集合结果文件\n")
        f.write(f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# 匹配条件: {column_conditions}\n")
        f.write(f"# 匹配行数: {len(Q)}\n")
        f.write(f"# 总行数: {len(data)}\n")
        f.write("# " + "="*50 + "\n\n")
        
        # 写入行号集合
        f.write("行号集合Q:\n")
        if Q:
            sorted_Q = sorted(Q)
            f.write(f"{{{', '.join(map(str, sorted_Q))}}}\n\n")
            
            # 写入匹配的完整行内容
            f.write("匹配的完整行内容:\n")
            f.write("-" * 50 + "\n")
            for row_idx in sorted_Q:
                f.write(f"行 {row_idx}: {' '.join(data[row_idx])}\n")
        else:
            f.write("{} (空集合)\n")
    
    return filepath


def interactive_multi_column_selection(data: List[List[str]]) -> None:
    """交互式多列条件选择"""
    if not data:
        print("No data to process.")
        return
    
    column_count = get_column_count(data)
    print(f"Data has {column_count} columns.")
    print("Available columns: 0 to", column_count - 1)
    
    while True:
        try:
            print("\n" + "="*60)
            print("Multi-Column Selection Menu:")
            print("1. Set conditions for multiple columns")
            print("2. Show data preview")
            print("3. Exit")
            
            choice = input("Enter your choice (1-3): ").strip()
            
            if choice == "1":
                # 多列条件设置
                column_conditions = {}
                
                print(f"\nSetting conditions for columns (0-{column_count-1}):")
                print("方式1: 一次性输入多个条件")
                print("      格式1（推荐）: '列索引1:值1, 列索引2:值2, ...'")
                print("      格式2: '列索引1 值1, 列索引2 值2, ...'")
                print("      例如: '0:1, 2:3' 或 '0 1, 2 3' 表示列0=1且列2=3（列1任意）")
                print("方式2: 逐个输入，格式: '列索引 值'，输入'done'结束")
                print("      例如: '0 1' 表示列0=1")
                print("\n提示: 只设置部分列条件时，未设置的列可以是任意值")
                print("请选择输入方式:")
                input_mode = input("输入'multi'使用一次性输入，输入'single'或直接回车使用逐个输入: ").strip().lower()
                
                if input_mode == 'multi':
                    # 一次性输入多个条件
                    print("\n请一次性输入所有列条件:")
                    print("格式: '列索引1:值1, 列索引2:值2, ...' 或 '列索引1 值1, 列索引2 值2, ...'")
                    print("示例: '0:1, 2:3' 或 '0 1, 2 3' （只设置列0和列2的条件，其他列任意）")
                    multi_input = input("输入条件: ").strip()
                    
                    try:
                        # 分割多个条件（以逗号分隔）
                        conditions = [c.strip() for c in multi_input.split(',')]
                        
                        for condition in conditions:
                            if not condition:
                                continue
                            
                            # 支持两种格式: "列索引:值" 或 "列索引 值"
                            if ':' in condition:
                                parts = [p.strip() for p in condition.split(':', 1)]
                            else:
                                parts = condition.split()
                            
                            if len(parts) != 2:
                                print(f"警告: 条件格式错误 '{condition}'，已跳过")
                                continue
                            
                            column_index = int(parts[0])
                            target_value = parts[1]
                            
                            if column_index < 0 or column_index >= column_count:
                                print(f"警告: 列索引 {column_index} 超出范围(0-{column_count-1})，已跳过")
                                continue
                            
                            column_conditions[column_index] = target_value
                            print(f"添加条件: 列{column_index} = '{target_value}'")
                        
                        if not column_conditions:
                            print("错误: 没有成功解析任何条件")
                            continue
                            
                    except ValueError as e:
                        print(f"输入格式错误: {e}")
                        print("请使用格式: '列索引1:值1, 列索引2:值2, ...'")
                        continue
                else:
                    # 逐个输入条件（原有方式）
                    print("\n逐个输入模式（输入'done'结束）:")
                    while True:
                        condition_input = input("输入 '列索引 值' 或 'done': ").strip()
                        
                        if condition_input.lower() == 'done':
                            break
                        
                        try:
                            parts = condition_input.split()
                            if len(parts) != 2:
                                print("格式错误。请使用: '列索引 值'")
                                continue
                            
                            column_index = int(parts[0])
                            target_value = parts[1]
                            
                            if column_index < 0 or column_index >= column_count:
                                print(f"列索引错误。必须在 0 到 {column_count-1} 之间")
                                continue
                            
                            column_conditions[column_index] = target_value
                            print(f"已添加条件: 列{column_index} = '{target_value}'")
                            
                        except ValueError:
                            print("输入错误。列索引必须是数字。")
                            continue
                
                if not column_conditions:
                    print("No conditions set.")
                    continue
                
                # 执行多列选择
                Q = select_rows_by_multiple_conditions(data, column_conditions)
                
                print(f"\nConditions: {column_conditions}")
                print(f"Matching rows: {sorted(Q)}")
                print(f"Total matching rows: {len(Q)}")
                
                # 显示匹配的行
                if Q:
                    print("\nMatching rows:")
                    for row_idx in sorted(Q):
                        print(f"Row {row_idx}: {' '.join(data[row_idx])}")
                else:
                    print("No rows match all conditions.")
                
                # 询问是否保存到文件
                save_choice = input("\nSave Q set to file? (y/n): ").strip().lower()
                if save_choice in ['y', 'yes']:
                    try:
                        filepath = save_Q_to_file(Q, column_conditions, data)
                        print(f"Q set saved to: {filepath}")
                    except Exception as e:
                        print(f"Error saving file: {e}")
                else:
                    print("Q set not saved.")
                
            elif choice == "2":
                # 显示数据预览
                print(f"\nData preview (first 10 rows):")
                for i, row in enumerate(data[:10]):
                    print(f"Row {i}: {' '.join(row)}")
                if len(data) > 10:
                    print(f"... and {len(data) - 10} more rows")
                    
            elif choice == "3":
                print("Exiting...")
                break
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")
                
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")


def main() -> int:
    try:
        lines = read_compare_result()
        data = parse_data(lines)
        
        if not data:
            print("No data found in file.")
            return 0
            
        print(f"Loaded {len(data)} rows of data.")
        interactive_multi_column_selection(data)
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())


