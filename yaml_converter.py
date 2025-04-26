'''
将特定格式的 YAML 规则文件转换为列表格式。
'''

import argparse
import sys

def convert_yaml_to_list(input_filepath, output_filepath=None):
    '''
    读取 YAML 文件，提取 payload 下的规则，并转换为列表格式。

    Args:
        input_filepath (str): 输入的 YAML 文件路径。
        output_filepath (str, optional): 输出文件路径。如果为 None，则打印到标准输出。

    Returns:
        list: 包含转换后规则的列表。
    '''
    rules = []
    in_payload_section = False
    try:
        with open(input_filepath, 'r', encoding='utf-8') as infile:
            for line in infile:
                stripped_line = line.strip()

                if stripped_line == 'payload:':
                    in_payload_section = True
                    continue

                # 只处理 payload 部分的规则行
                if in_payload_section:
                    # 检查是否是规则行（以 '  - ' 开头）
                    if line.startswith('  - '):
                        # 移除前缀 '  - '
                        rule = line.strip().lstrip('- ')
                        rules.append(rule)
                    # 如果遇到非规则行（比如空行或其他缩进不符的），认为payload结束
                    # 或者可以更严格，只接受 '  - ' 开头的行
                    # elif stripped_line: # 如果需要更宽松，可以取消注释这行
                    #    in_payload_section = False # 如果 payload 后还有其他内容

    except FileNotFoundError:
        print(f"错误：输入文件未找到: {input_filepath}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"处理文件时发生错误: {e}", file=sys.stderr)
        sys.exit(1)

    # 输出结果
    if output_filepath:
        try:
            with open(output_filepath, 'w', encoding='utf-8') as outfile:
                for rule in rules:
                    outfile.write(rule + '\n')
            print(f"转换完成，结果已保存至: {output_filepath}")
        except Exception as e:
            print(f"写入输出文件时发生错误: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # 如果没有指定输出文件，则打印到控制台
        for rule in rules:
            print(rule)

    return rules

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='将 Clash 规则 YAML 文件中的 payload 转换为列表格式。')
    parser.add_argument('input_file', help='输入的 YAML 文件路径')
    parser.add_argument('-o', '--output', help='输出文件路径 (可选, 默认打印到控制台)')

    args = parser.parse_args()

    convert_yaml_to_list(args.input_file, args.output) 