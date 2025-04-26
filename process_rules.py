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
        content = response.text
        
        # 打印内容的前几行用于调试
        print("      下载的内容预览 (前5行):")
        preview_lines = content.splitlines()[:5]
        for i, line in enumerate(preview_lines):
            print(f"        {i+1}: {line}")
        
        return content
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
    '''
    解析 .yaml 文件内容，提取 payload 下的规则。
    更健壮的实现，能处理各种 YAML 格式变种。
    '''
    rules = set()
    lines = content.splitlines()
    payload_found = False
    
    # 首先查找 payload: 行
    for i, line in enumerate(lines):
        if line.strip() == 'payload:':
            payload_found = True
            print(f"      找到 payload: 在第 {i+1} 行")
            
            # 从 payload: 的下一行开始处理
            for j in range(i + 1, len(lines)):
                line = lines[j]
                stripped = line.strip()
                
                # 空行或注释行跳过
                if not stripped or stripped.startswith('#'):
                    continue
                
                # 如果不是以 - 开头，可能 payload 部分已经结束
                if not stripped.startswith('-'):
                    print(f"      在第 {j+1} 行离开 payload 部分: '{stripped}'")
                    break
                
                # 移除 - 前缀和多余空格
                rule = stripped[1:].strip()
                
                # 添加非空规则
                if rule:
                    print(f"      提取规则: '{rule}'")
                    rules.add(rule)
            
            # 找到并处理完 payload 部分后跳出循环
            break
    
    # 如果没有找到正确的 payload 结构或未提取到规则，尝试备用方法
    if not payload_found or len(rules) == 0:
        print("      未找到标准 payload 结构或未提取到规则，尝试备用解析方法...")
        
        # 尝试查找任何可能的规则行
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # 跳过空行、注释和 payload: 行
            if not stripped or stripped.startswith('#') or stripped == 'payload:':
                continue
            
            # 如果行以 - 开头，尝试提取规则
            if stripped.startswith('-'):
                rule = stripped[1:].strip()
                if rule:
                    print(f"      备用方法提取规则 (行 {i+1}): '{rule}'")
                    rules.add(rule)
    
    # 创建最终的规则列表，确保没有遗漏的前缀
    cleaned_rules = set()
    for rule in rules:
        # 递归移除可能的多重 - 前缀
        while rule.startswith('-'):
            print(f"      清理剩余 '-' 前缀: '{rule}' -> '{rule[1:].strip()}'")
            rule = rule[1:].strip()
        cleaned_rules.add(rule)
    
    return cleaned_rules

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