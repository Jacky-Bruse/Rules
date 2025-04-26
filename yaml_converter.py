'''
将特定格式的 YAML 规则文件转换为列表格式。
'''

import argparse
import sys

def convert_yaml_to_list(input_filepath, output_filepath=None, verbose=False):
    '''
    读取 YAML 文件，提取 payload 下的规则，并转换为列表格式。
    使用更健壮的解析方法，能够处理各种 YAML 格式变种。

    Args:
        input_filepath (str): 输入的 YAML 文件路径。
        output_filepath (str, optional): 输出文件路径。如果为 None，则打印到标准输出。
        verbose (bool): 是否显示详细的调试信息。

    Returns:
        list: 包含转换后规则的列表。
    '''
    # 读取 YAML 文件
    try:
        with open(input_filepath, 'r', encoding='utf-8') as infile:
            content = infile.read()
    except FileNotFoundError:
        print(f"错误：输入文件未找到: {input_filepath}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"读取文件时发生错误: {e}", file=sys.stderr)
        sys.exit(1)

    # 解析 YAML 内容
    rules = []
    lines = content.splitlines()
    payload_found = False
    
    if verbose:
        print(f"处理文件: {input_filepath}")
        print(f"总行数: {len(lines)}")
    
    # 首先查找 payload: 行
    for i, line in enumerate(lines):
        if line.strip() == 'payload:':
            payload_found = True
            if verbose:
                print(f"找到 payload: 在第 {i+1} 行")
            
            # 从 payload: 的下一行开始处理
            for j in range(i + 1, len(lines)):
                line = lines[j]
                stripped = line.strip()
                
                # 空行或注释行跳过
                if not stripped or stripped.startswith('#'):
                    continue
                
                # 如果不是以 - 开头，可能 payload 部分已经结束
                if not stripped.startswith('-'):
                    if verbose:
                        print(f"在第 {j+1} 行离开 payload 部分: '{stripped}'")
                    break
                
                # 移除 - 前缀和多余空格
                rule = stripped[1:].strip()
                
                # 添加非空规则
                if rule:
                    if verbose:
                        print(f"提取规则: '{rule}'")
                    rules.append(rule)
            
            # 找到并处理完 payload 部分后跳出循环
            break
    
    # 如果没有找到标准 payload 结构，尝试备用方法
    if not payload_found or len(rules) == 0:
        if verbose:
            print("未找到标准 payload 结构或未提取到规则，尝试备用解析方法...")
        
        # 遍历所有行
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # 跳过空行、注释和 payload:
            if not stripped or stripped.startswith('#') or stripped == 'payload:':
                continue
            
            # 如果行以 - 开头，尝试提取规则
            if stripped.startswith('-'):
                rule = stripped[1:].strip()
                if rule:
                    if verbose:
                        print(f"备用方法提取规则 (行 {i+1}): '{rule}'")
                    rules.append(rule)
    
    # 最终清理规则
    cleaned_rules = []
    for rule in rules:
        # 递归移除可能的多重 - 前缀
        while rule.startswith('-'):
            if verbose:
                print(f"清理剩余 '-' 前缀: '{rule}' -> '{rule[1:].strip()}'")
            rule = rule[1:].strip()
        cleaned_rules.append(rule)
    
    # 如果没有找到规则，报告错误
    if not cleaned_rules:
        print(f"警告: 未能从文件中提取任何规则: {input_filepath}", file=sys.stderr)
    elif verbose:
        print(f"成功提取 {len(cleaned_rules)} 条规则")
    
    # 输出结果
    if output_filepath:
        try:
            with open(output_filepath, 'w', encoding='utf-8') as outfile:
                for rule in cleaned_rules:
                    outfile.write(rule + '\n')
            print(f"转换完成，结果已保存至: {output_filepath}")
        except Exception as e:
            print(f"写入输出文件时发生错误: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # 如果没有指定输出文件，则打印到控制台
        for rule in cleaned_rules:
            print(rule)

    return cleaned_rules

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='将 Clash 规则 YAML 文件中的 payload 转换为列表格式。')
    parser.add_argument('input_file', help='输入的 YAML 文件路径')
    parser.add_argument('-o', '--output', help='输出文件路径 (可选, 默认打印到控制台)')
    parser.add_argument('-v', '--verbose', action='store_true', help='显示详细的处理信息')

    args = parser.parse_args()

    convert_yaml_to_list(args.input_file, args.output, args.verbose) 