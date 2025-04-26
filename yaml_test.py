'''
YAML 解析测试脚本 - 帮助诊断规则提取问题
'''

import argparse
import sys

def print_banner(text):
    '''打印分隔标题'''
    width = 60
    print('\n' + '=' * width)
    print(text.center(width))
    print('=' * width)

def parse_yaml_content(content, verbose=True):
    '''
    解析 YAML 内容并提取规则。
    Args:
        content (str): YAML 文件内容
        verbose (bool): 是否打印详细调试信息
    Returns:
        list: 提取到的规则列表
    '''
    rules = set()
    lines = content.splitlines()
    payload_found = False
    
    if verbose:
        print(f"总行数: {len(lines)}")
    
    # 查找 payload: 行
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
                        print(f"提取规则 #{len(rules)+1}: '{rule}'")
                    rules.add(rule)
            
            # 找到并处理完 payload 部分后跳出循环
            break
    
    # 如果没有找到标准 payload 结构，尝试备用方法
    if not payload_found or len(rules) == 0:
        if verbose:
            print_banner("使用备用解析方法")
        
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
                        print(f"备用方法提取规则 #{len(rules)+1} (行 {i+1}): '{rule}'")
                    rules.add(rule)
    
    # 最终清理规则
    cleaned_rules = []
    for rule in rules:
        # 递归移除可能的多重 - 前缀
        while rule.startswith('-'):
            rule = rule[1:].strip()
        cleaned_rules.append(rule)
    
    # 排序，以便输出一致
    cleaned_rules.sort()
    
    if verbose:
        print_banner("统计")
        print(f"初始规则集合大小: {len(rules)}")
        print(f"清理后规则列表大小: {len(cleaned_rules)}")
    
    return cleaned_rules

def test_yaml_string():
    '''测试一个示例 YAML 字符串'''
    print_banner("测试样例 YAML 字符串")
    
    yaml_str = '''# NAME: Telegram
# UPDATED: 2024-12-08 02:12:03
# DOMAIN: 2
# TOTAL: 44
payload:
  - DOMAIN,api.imem.app
  - DOMAIN-SUFFIX,cdn-telegram.org
  - IP-CIDR,109.239.140.0/24
  - PROCESS-NAME,org.telegram.messenger
  - IP-ASN,211157'''
    
    print("输入 YAML 字符串:")
    print("-" * 40)
    print(yaml_str)
    print("-" * 40)
    
    rules = parse_yaml_content(yaml_str)
    
    print_banner("解析结果")
    for i, rule in enumerate(rules):
        print(f"{i+1}. '{rule}'")

def test_yaml_file(filepath):
    '''测试 YAML 文件解析'''
    print_banner(f"解析文件: {filepath}")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"文件大小: {len(content)} 字节")
        
        # 显示文件前10行
        print("文件前10行:")
        print("-" * 40)
        for i, line in enumerate(content.splitlines()[:10]):
            print(f"{i+1}. {line}")
        print("-" * 40)
        
        rules = parse_yaml_content(content)
        
        print_banner("解析结果")
        print(f"共提取出 {len(rules)} 条规则")
        
        # 显示前10条规则
        for i, rule in enumerate(rules[:10]):
            print(f"{i+1}. '{rule}'")
        
        if len(rules) > 10:
            print(f"... 还有 {len(rules) - 10} 条规则未显示")
        
        # 写入输出文件
        output_filename = filepath + ".extracted.txt"
        with open(output_filename, 'w', encoding='utf-8') as outfile:
            for rule in rules:
                outfile.write(rule + '\n')
        
        print(f"\n提取的规则已保存到: {output_filename}")
        
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='测试 YAML 规则文件解析')
    parser.add_argument('-f', '--file', help='要解析的 YAML 文件路径')
    
    args = parser.parse_args()
    
    if args.file:
        test_yaml_file(args.file)
    else:
        test_yaml_string()
        print("\n提示: 您可以使用 -f 参数指定 YAML 文件进行测试") 