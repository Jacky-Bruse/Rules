'''
处理 sources 文件夹下 text 文件中的 URL 规则列表。
从 URL 下载内容，区分处理 .list 和 .yaml 文件，合并去重后输出到 output 文件夹。
'''

import os
import sys
import requests
import argparse

# --- 配置 --- (可以根据需要修改)
DEFAULT_SOURCE_DIR = 'sources'
DEFAULT_OUTPUT_DIR = 'output'
DEFAULT_OUTPUT_FILE = 'merged_rules.list'
REQUEST_TIMEOUT = 10 # seconds
# ------------- 

def download_content(url):
    '''尝试从 URL 下载文本内容。'''
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status() # 如果请求失败则抛出 HTTPError
        response.encoding = response.apparent_encoding # 尝试自动检测编码
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"警告: 下载 {url} 时出错: {e}", file=sys.stderr)
        return None

def parse_list_content(content):
    '''解析 .list 文件内容。'''
    rules = set()
    for line in content.splitlines():
        rule = line.strip()
        # 忽略空行和注释
        if rule and not rule.startswith('#'):
            rules.add(rule)
    return rules

def parse_yaml_content(content):
    '''解析 .yaml 文件内容，提取 payload 下的规则。'''
    rules = set()
    in_payload_section = False
    for line in content.splitlines():
        stripped_line = line.strip()
        
        # 忽略空行、注释行和 payload: 行
        if not stripped_line or stripped_line.startswith('#') or stripped_line == 'payload:':
            # 如果找到 payload: 行，标记开始处理规则
            if stripped_line == 'payload:':
                in_payload_section = True
            continue

        if in_payload_section:
            # 检查是否是规则行（以 '-' 或 '- ' 开头）
            if stripped_line.startswith('-'):
                # 移除前缀 '-' 和可能的空格
                rule = stripped_line[1:].strip()
                # 确保提取出的规则不是空的
                if rule:
                    rules.add(rule)
            # 如果遇到其他非规则行，认为 payload 结束
            elif not stripped_line.startswith('-'):
                # 如果不以连字符开头且不为空，可能 payload 部分已结束
                in_payload_section = False

    return rules

def process_source_files(source_dir, output_dir, output_filename):
    '''主处理函数。'''
    all_rules = set()

    if not os.path.isdir(source_dir):
        print(f"错误: 源目录 '{source_dir}' 不存在或不是一个目录。", file=sys.stderr)
        sys.exit(1)

    print(f"开始处理源目录: {source_dir}")

    # 遍历源目录下的 .txt 文件
    for filename in os.listdir(source_dir):
        if filename.lower().endswith('.txt'):
            filepath = os.path.join(source_dir, filename)
            print(f"  读取文件: {filename}")
            try:
                with open(filepath, 'r', encoding='utf-8') as infile:
                    for line_num, url in enumerate(infile, 1):
                        url = url.strip()
                        if not url or url.startswith('#'): # 忽略空行和注释URL
                            continue

                        print(f"    处理 URL: {url}")
                        content = download_content(url)
                        if content is None:
                            continue # 下载失败，跳过

                        # 根据 URL 后缀判断类型并处理
                        if url.lower().endswith('.yaml') or url.lower().endswith('.yml'):
                            print("      类型: YAML，进行解析...")
                            yaml_rules = parse_yaml_content(content)
                            print(f"      提取到 {len(yaml_rules)} 条 YAML 规则")
                            all_rules.update(yaml_rules)
                        elif url.lower().endswith('.list'):
                            print("      类型: List，进行解析...")
                            list_rules = parse_list_content(content)
                            print(f"      提取到 {len(list_rules)} 条 List 规则")
                            all_rules.update(list_rules)
                        else:
                            # 尝试作为 list 处理未知后缀
                            print(f"      类型: 未知 (尝试按 List 处理)...")
                            list_rules = parse_list_content(content)
                            print(f"      提取到 {len(list_rules)} 条规则")
                            all_rules.update(list_rules)
                            # 或者可以选择忽略未知类型:
                            # print(f"    跳过未知类型文件: {url}", file=sys.stderr)

            except Exception as e:
                print(f"处理文件 {filename} 时发生错误: {e}", file=sys.stderr)
                continue # 继续处理下一个文件

    # 创建输出目录
    if not os.path.exists(output_dir):
        print(f"创建输出目录: {output_dir}")
        try:
            os.makedirs(output_dir)
        except OSError as e:
            print(f"错误: 无法创建输出目录 '{output_dir}': {e}", file=sys.stderr)
            sys.exit(1)

    # 对规则进行排序
    sorted_rules = sorted(list(all_rules))

    # 写入输出文件
    output_filepath = os.path.join(output_dir, output_filename)
    print(f"合并去重后共 {len(sorted_rules)} 条规则，准备写入到: {output_filepath}")
    try:
        with open(output_filepath, 'w', encoding='utf-8') as outfile:
            for rule in sorted_rules:
                outfile.write(rule + '\n')
        print("处理完成！")
    except Exception as e:
        print(f"写入输出文件时发生错误: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='处理 sources 文件夹下的规则文件 URL，合并去重后输出。')
    parser.add_argument('-s', '--source', default=DEFAULT_SOURCE_DIR,
                        help=f'包含 URL 列表的源目录 (默认: {DEFAULT_SOURCE_DIR})')
    parser.add_argument('-o', '--output-dir', default=DEFAULT_OUTPUT_DIR,
                        help=f'存放合并结果的输出目录 (默认: {DEFAULT_OUTPUT_DIR})')
    parser.add_argument('-f', '--output-file', default=DEFAULT_OUTPUT_FILE,
                        help=f'输出文件名 (默认: {DEFAULT_OUTPUT_FILE})')

    args = parser.parse_args()

    process_source_files(args.source, args.output_dir, args.output_file) 