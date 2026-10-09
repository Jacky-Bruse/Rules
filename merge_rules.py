import requests
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import re

# --- Configuration ---
# Directory containing the source URL lists
SOURCE_DIR = Path("sources")
# Directory to output the merged list
OUTPUT_DIR = Path("output")
# ASN specific directories
ASN_SOURCE_DIR = SOURCE_DIR / "ASN"
ASN_OUTPUT_DIR = OUTPUT_DIR / "ASN"
# Repository information
RULE_AUTHOR = "Jacky-Bruse"
REPO_URL = "https://github.com/Jacky-Bruse/Rules"
# Number of concurrent download threads
MAX_WORKERS = 10
# Request timeout in seconds
REQUEST_TIMEOUT = 15
# User-Agent for requests
# 使用 clash.meta 标识：部分规则源（如 kelee.one）会对普通浏览器 UA 返回 403，
# 仅对 clash 客户端 UA 放行；GitHub/ACL4SSR 等不校验 UA，统一使用此值无副作用。
USER_AGENT = "clash.meta"
# Retry attempts for failed downloads
MAX_RETRIES = 4
# Base delay between retries in seconds (exponential backoff: 2s, 4s, 8s)
RETRY_DELAY = 2

# 指向本仓库 main 分支的链接直接读取本地文件：Actions 已检出最新代码，
# 避免 raw.githubusercontent.com 的 CDN 缓存（约 5 分钟）导致刚推送的 Rules/ 改动读到旧内容
REPO_SLUG = re.escape(REPO_URL.removeprefix("https://github.com/"))
SELF_URL_PATTERN = re.compile(
    rf'^https://(?:raw\.githubusercontent\.com/{REPO_SLUG}|github\.com/{REPO_SLUG}/raw)/(?:refs/heads/)?main/(.+)$',
    re.IGNORECASE,
)

# 用 IP 片段写成的关键字（如 DOMAIN-KEYWORD,101.226.129.）：Surge/Loon 会拿 IP 字符串匹配，
# mihomo/Clash 中直连 IP 的连接没有域名可匹配，基本不会命中，合并时丢弃。纯数字关键字（如 163）不受影响
IP_FRAGMENT_KEYWORD_PATTERN = re.compile(r'^DOMAIN-KEYWORD,\d{1,3}(\.\d{1,3}){1,3}\.?$')

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 下载失败的规则源 (源文件名, URL)，运行结束时汇总输出
FAILED_SOURCES: list[tuple[str, str]] = []

def fetch_text(url: str, retries: int = MAX_RETRIES) -> str | None:
    """获取 URL 的文本内容（本仓库链接直接读本地文件），网络错误按指数退避重试；失败返回 None。"""
    match = SELF_URL_PATTERN.match(url)
    if match:
        local_file = Path(match.group(1))
        try:
            logging.info(f"Reading {url} from local file {local_file}")
            return local_file.read_text(encoding='utf-8-sig')
        except OSError as e:
            logging.error(f"Failed to read local file {local_file} for {url}: {e}")
            return None

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT, headers={'User-Agent': USER_AGENT})
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            return response.content.decode('utf-8-sig', errors='replace')
        except requests.exceptions.RequestException as e:
            # Avoid retrying on 4xx client errors (like 404 Not Found)
            if e.response is not None and 400 <= e.response.status_code < 500:
                logging.error(f"Failed to download {url} due to client error: {e}. Not retrying.")
                return None
            if attempt == retries:
                logging.error(f"Failed to download {url} after {retries} attempts: {e}")
                return None
            delay = RETRY_DELAY * 2 ** (attempt - 1)
            logging.warning(f"Error downloading {url}: {e} (Attempt {attempt}/{retries}). Retrying in {delay}s...")
            time.sleep(delay)
    return None

def download_content(url: str) -> set[str] | None:
    """下载并解析规则列表（支持纯文本列表和 YAML payload 格式）；下载失败返回 None。"""
    content = fetch_text(url)
    if content is None:
        return None

    # 检查是否是 YAML 格式
    if url.lower().endswith(('.yaml', '.yml')) or 'payload:' in content:
        logging.info(f"Detected YAML format for {url}, applying special processing")
        rules = process_yaml_content(content)
    else:
        # 处理常规列表格式
        rules = {line.strip() for line in content.splitlines()
                 if line.strip() and not line.strip().startswith(('#', '!', '/', ';', '[', 'payload:'))}

    logging.info(f"Successfully downloaded and processed {len(rules)} rules from {url}")
    return rules

def write_rule_file(output_file: Path, stats: dict[str, int], rules: set[str]):
    """写入规则文件；除 UPDATED 外内容无变化时跳过，避免产生仅时间戳变化的提交。"""
    header = [
        f"# NAME: {output_file.stem}",
        f"# AUTHOR: {RULE_AUTHOR}",
        f"# REPO: {REPO_URL}",
        f"# UPDATED: {time.strftime('%Y-%m-%d %H:%M:%S')}",
    ]
    header += [f"# {rule_type}: {count}" for rule_type, count in sorted(stats.items())]
    header.append(f"# TOTAL: {len(rules)}")
    content = "\n".join(header) + "\n\n" + "".join(f"{rule}\n" for rule in sorted(rules))

    def strip_updated(text: str) -> str:
        return re.sub(r'^# UPDATED: .*\n', '', text, flags=re.M)

    if output_file.exists() and strip_updated(output_file.read_text(encoding='utf-8')) == strip_updated(content):
        logging.info(f"No rule changes for {output_file}, keeping existing file")
        return
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)
    logging.info(f"Successfully wrote {len(rules)} rules to {output_file}")

def process_yaml_content(content):
    """处理 YAML 内容并提取规则。"""
    rules = set()
    lines = content.splitlines()
    payload_found = False
    
    # 首先查找 payload: 行
    for i, line in enumerate(lines):
        if line.strip() == 'payload:':
            payload_found = True
            logging.debug(f"Found payload: at line {i+1}")
            
            # 从 payload: 的下一行开始处理
            for j in range(i + 1, len(lines)):
                line = lines[j]
                stripped = line.strip()
                
                # 空行或注释行跳过
                if not stripped or stripped.startswith('#'):
                    continue
                
                # 如果不是以 - 开头，可能 payload 部分已经结束
                if not stripped.startswith('-'):
                    logging.debug(f"Leaving payload section at line {j+1}: '{stripped}'")
                    break
                
                # 移除 - 前缀和多余空格
                rule = stripped[1:].strip()
                
                # 添加非空规则
                if rule:
                    logging.debug(f"Extracted rule: '{rule}'")
                    rules.add(rule)
            
            # 找到并处理完 payload 部分后跳出循环
            break
    
    # 如果没有找到标准 payload 结构，尝试备用方法
    if not payload_found or len(rules) == 0:
        logging.debug("No standard payload structure found or no rules extracted, trying fallback method...")
        
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
                    logging.debug(f"Fallback method extracted rule (line {i+1}): '{rule}'")
                    rules.add(rule)
            # 不以连字符开头的行，可能是普通的规则
            elif not any(stripped.startswith(prefix) for prefix in ['#', '!', '/', ';', '[', 'payload:']):
                rules.add(stripped)
    
    # 最终清理规则
    cleaned_rules = set()
    for rule in rules:
        # 递归移除可能的多重 - 前缀
        while rule.startswith('-'):
            logging.debug(f"Cleaning remaining '-' prefix: '{rule}' -> '{rule[1:].strip()}'")
            rule = rule[1:].strip()
        cleaned_rules.add(rule)
    
    return cleaned_rules

def process_asn_content(content: str) -> set[str]:
    """
    处理 ASN 规则内容：
    1. 去掉 // 注释
    2. 去掉 # 注释行
    3. 添加 ,no-resolve 后缀

    输入格式: IP-ASN,140238 // CHINATELECOM Shaanxi province
    输出格式: IP-ASN,140238,no-resolve
    """
    rules = set()
    for line in content.splitlines():
        line = line.strip()

        # 跳过空行和 # 注释行
        if not line or line.startswith('#'):
            continue

        # 去掉 // 及其后面的注释
        if '//' in line:
            line = line.split('//')[0].strip()

        if not line:
            continue

        # 如果已有 no-resolve 则保持不变
        if line.lower().endswith(',no-resolve'):
            rules.add(line)
        else:
            # 添加 ,no-resolve 后缀
            rules.add(f"{line},no-resolve")

    return rules

def download_asn_content(url: str) -> set[str] | None:
    """下载并按 ASN 规则处理；下载失败返回 None。"""
    content = fetch_text(url)
    if content is None:
        return None
    rules = process_asn_content(content)
    logging.info(f"Successfully downloaded and processed {len(rules)} ASN rules from {url}")
    return rules

def process_asn_source_file(source_file: Path):
    """Process a single ASN source file and generate corresponding output file."""
    logging.info(f"Processing ASN source file: {source_file.name}")

    # Define output file path
    output_file = ASN_OUTPUT_DIR / f"{source_file.stem}.list"

    # Read URLs from the source file
    urls = []
    try:
        with open(source_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.startswith(('http://', 'https://')):
                    urls.append(line)

            logging.info(f"Read {len(urls)} URLs from ASN source file {source_file.name}")
    except FileNotFoundError:
        logging.error(f"ASN source file not found: {source_file}. Skipping.")
        return
    except Exception as e:
        logging.error(f"Error reading ASN source file {source_file}: {e}")
        return

    if not urls:
        logging.warning(f"No valid URLs found in {source_file.name}. Skipping.")
        return

    # Download and process ASN rules from each URL
    all_rules = set()

    logging.info(f"Downloading ASN rules from {len(urls)} URLs for {source_file.name}")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(download_asn_content, url): url for url in urls}

        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                rules_from_url = future.result()
                if rules_from_url is None:
                    FAILED_SOURCES.append((f"ASN/{source_file.name}", url))
                    continue
                all_rules.update(rules_from_url)
            except Exception as e:
                logging.error(f"Error processing ASN result for {url}: {e}")
                FAILED_SOURCES.append((f"ASN/{source_file.name}", url))

    logging.info(f"Total unique ASN rules collected for {source_file.name}: {len(all_rules)}")

    if not all_rules:
        logging.warning(f"No ASN rules collected for {source_file.name}. Keeping existing output file (if any).")
        return

    # Write the output file
    try:
        write_rule_file(output_file, {"IP-ASN": len(all_rules)}, all_rules)
    except IOError as e:
        logging.error(f"Error writing ASN rules to {output_file}: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred during ASN file writing: {e}")

def process_source_file(source_file: Path):
    """Process a single source file and generate corresponding output file."""
    logging.info(f"Processing source file: {source_file.name}")
    
    # Define output file path, using the same name but with .list extension
    output_file = OUTPUT_DIR / f"{source_file.stem}.list"
    
    # Read contents from the source file
    urls = []
    direct_rules = set()
    try:
        with open(source_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Check if the line is a URL or a direct rule
                if line.startswith(('http://', 'https://')):
                    urls.append(line)  # Add as URL to be downloaded
                else:
                    # 添加所有非空且非注释的规则
                    direct_rules.add(line)
            
            logging.info(f"Read {len(urls)} URLs and {len(direct_rules)} direct rules from {source_file.name}")
    except FileNotFoundError:
        logging.error(f"Source file not found: {source_file}. Skipping.")
        return
    except Exception as e:
        logging.error(f"Error reading source file {source_file}: {e}")
        return
    
    if not urls and not direct_rules:
        logging.warning(f"No valid URLs or rules found in {source_file.name}. Skipping.")
        return
    
    # Download and process rules from each URL
    all_rules = direct_rules.copy()  # Start with direct rules
    
    if urls:
        logging.info(f"Downloading rules from {len(urls)} URLs for {source_file.name}")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit download tasks
            future_to_url = {executor.submit(download_content, url): url for url in urls}
            
            # Process completed tasks as they finish
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    rules_from_url = future.result()
                    if rules_from_url is None:
                        FAILED_SOURCES.append((source_file.name, url))
                        continue
                    # 不再进行内容筛选，保留所有规则
                    all_rules.update(rules_from_url)
                except Exception as e:
                    # Catch errors during result processing
                    logging.error(f"Error processing result for {url}: {e}")
                    FAILED_SOURCES.append((source_file.name, url))
    
    # 过滤并规范化规则，确保没有 payload: 行和重复规则（须先于统计，否则头部计数会偏大）
    filtered_rules = set()
    ip_fragment_keywords = 0
    for rule in all_rules:
        # 跳过 payload: 行
        if rule.strip() == 'payload:':
            continue
        
        # 递归移除任何多余的 - 前缀
        cleaned_rule = rule
        while cleaned_rule.startswith('-'):
            cleaned_rule = cleaned_rule[1:].strip()

        # 规范化规则格式：移除所有逗号后的空格
        # 例如：DOMAIN, example.com -> DOMAIN,example.com
        #      IP-CIDR, 1.2.3.4/24, no-resolve -> IP-CIDR,1.2.3.4/24,no-resolve
        cleaned_rule = re.sub(r',\s+', ',', cleaned_rule)

        if IP_FRAGMENT_KEYWORD_PATTERN.match(cleaned_rule):
            ip_fragment_keywords += 1
            continue

        if cleaned_rule:
            filtered_rules.add(cleaned_rule)
    
    if ip_fragment_keywords:
        logging.info(f"Dropped {ip_fragment_keywords} IP-fragment DOMAIN-KEYWORD rules from {source_file.name}")
    
    logging.info(f"Total unique rules collected for {source_file.name}: {len(filtered_rules)}")
    
    # 没有收集到任何规则（如所有源均下载失败）时保留旧文件
    if not filtered_rules:
        logging.warning(f"No rules collected for {source_file.name}. Keeping existing output file (if any).")
        return
    
    # 只统计规则类型，不修改规则内容
    rule_types_count = {}
    for rule in filtered_rules:
        # 提取规则类型（如果有）
        rule_type = None
        for prefix in ["DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "IP-CIDR", "IP-CIDR6", 
                      "USER-AGENT", "IP-ASN", "PROCESS-NAME"]:
            if rule.startswith(f"{prefix},") or rule.startswith(f"{prefix}:"):
                rule_type = prefix
                break
        
        # 如果找到类型，更新计数
        if rule_type:
            rule_types_count[rule_type] = rule_types_count.get(rule_type, 0) + 1
        else:
            rule_types_count["OTHER"] = rule_types_count.get("OTHER", 0) + 1
    
    # Write the output file
    try:
        write_rule_file(output_file, rule_types_count, filtered_rules)
    except IOError as e:
        logging.error(f"Error writing merged rules to {output_file}: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred during file writing: {e}")

def main():
    """Main function to merge rule lists."""
    start_time = time.time()
    
    # Check if source directory exists
    if not SOURCE_DIR.is_dir():
        logging.error(f"Source directory '{SOURCE_DIR}' not found.")
        return
    
    # Find all source files
    source_files = list(SOURCE_DIR.glob("*.txt"))
    if not source_files:
        logging.warning(f"No source files (.txt) found in '{SOURCE_DIR}'. Exiting.")
        return
    
    # Create output directory if it doesn't exist
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 仅删除源文件已不存在的旧输出；其余文件按需覆盖，下载全部失败时保留旧文件
    logging.info("Cleaning output directory...")
    for file in OUTPUT_DIR.glob("*.list"):
        if not (SOURCE_DIR / f"{file.stem}.txt").exists():
            try:
                file.unlink()
                logging.info(f"Deleted stale file: {file}")
            except Exception as e:
                logging.error(f"Failed to delete file {file}: {e}")
    
    # Process each source file separately
    for source_file in source_files:
        process_source_file(source_file)

    # Process ASN folder if it exists
    if ASN_SOURCE_DIR.is_dir():
        logging.info(f"Processing ASN source directory: {ASN_SOURCE_DIR}")

        # Create ASN output directory
        ASN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # 仅删除源文件已不存在的旧 ASN 输出
        for file in ASN_OUTPUT_DIR.glob("*.list"):
            if not (ASN_SOURCE_DIR / f"{file.stem}.txt").exists():
                try:
                    file.unlink()
                    logging.info(f"Deleted stale ASN file: {file}")
                except Exception as e:
                    logging.error(f"Failed to delete ASN file {file}: {e}")

        # Find and process ASN source files
        asn_source_files = list(ASN_SOURCE_DIR.glob("*.txt"))
        if asn_source_files:
            for asn_file in asn_source_files:
                process_asn_source_file(asn_file)
        else:
            logging.warning(f"No ASN source files (.txt) found in '{ASN_SOURCE_DIR}'.")
    else:
        logging.info(f"ASN source directory '{ASN_SOURCE_DIR}' not found. Skipping ASN processing.")

    # 汇总下载失败的规则源：已跳过，不影响其余规则；::warning:: 会在 GitHub Actions 页面显示为注解
    if FAILED_SOURCES:
        logging.warning(f"{len(FAILED_SOURCES)} rule source(s) failed to download and were skipped:")
        for source_name, url in sorted(FAILED_SOURCES):
            logging.warning(f"  [{source_name}] {url}")
            print(f"::warning title=规则源下载失败 ({source_name})::{url}")

    end_time = time.time()
    logging.info(f"Script finished in {end_time - start_time:.2f} seconds.")

if __name__ == "__main__":
    main()
