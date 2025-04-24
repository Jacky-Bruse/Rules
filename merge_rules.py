import os
import requests
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import re
from collections import defaultdict

# --- Configuration ---
# Directory containing the source URL lists
SOURCE_DIR = Path("sources")
# Directory to output the merged list
OUTPUT_DIR = Path("output")
# Repository information
RULE_AUTHOR = "Jacky-Bruse"
REPO_URL = "https://github.com/Jacky-Bruse/Clash_Rules"
# Number of concurrent download threads
MAX_WORKERS = 10
# Request timeout in seconds
REQUEST_TIMEOUT = 15
# User-Agent for requests
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
# Retry attempts for failed downloads
MAX_RETRIES = 3
# Delay between retries in seconds
RETRY_DELAY = 2

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def download_content(url: str, retries: int = MAX_RETRIES) -> set[str]:
    """Downloads content from a URL with retries, handling potential errors."""
    rules = set()
    headers = {'User-Agent': USER_AGENT}
    attempt = 0
    while attempt < retries:
        try:
            # Use stream=True for potentially large files and better memory usage
            response = requests.get(url, timeout=REQUEST_TIMEOUT, headers=headers, stream=True)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

            content = ""
            # Read content line by line, decoding chunks
            for chunk in response.iter_content(chunk_size=8192, decode_unicode=True):
                 if chunk: # filter out keep-alive new chunks
                    content += chunk

            # Process lines after successful download
            lines = {line.strip() for line in content.splitlines()
                     if line.strip() and not line.strip().startswith(('#', '!', '/', ';', '['))} # Added more potential comment chars
            rules.update(lines)
            logging.info(f"Successfully downloaded and processed {len(lines)} rules from {url}")
            return rules # Success, exit retry loop

        except requests.exceptions.Timeout:
            attempt += 1
            logging.warning(f"Timeout downloading {url} (Attempt {attempt}/{retries}). Retrying in {RETRY_DELAY}s...")
            if attempt < retries:
                time.sleep(RETRY_DELAY)
            else:
                logging.error(f"Failed to download {url} after {retries} attempts (Timeout).")
        except requests.exceptions.RequestException as e:
            attempt += 1
            # Avoid retrying on 4xx client errors (like 404 Not Found)
            if hasattr(response, 'status_code') and response.status_code >= 400 and response.status_code < 500:
                 logging.error(f"Failed to download {url} due to client error: {e}. Not retrying.")
                 break # Exit retry loop for client errors
            logging.warning(f"Error downloading {url}: {e} (Attempt {attempt}/{retries}). Retrying in {RETRY_DELAY}s...")
            if attempt < retries:
                time.sleep(RETRY_DELAY)
            else:
                logging.error(f"Failed to download {url} after {retries} attempts: {e}")
        except Exception as e:
            # For unexpected errors, don't retry automatically, log and break
            logging.error(f"An unexpected error occurred while processing {url}: {e}")
            break # Exit retry loop for non-request errors

    return rules # Return empty set if all retries fail or unexpected error

def categorize_rules(rules: set[str]) -> dict:
    """Categorize rules by their type (DOMAIN, DOMAIN-SUFFIX, DOMAIN-KEYWORD, IP-CIDR, etc.)."""
    categorized = defaultdict(list)
    pre_formatted_rules = []  # 存储已带有前缀的规则
    
    # Patterns for identifying rule types
    ip_cidr_pattern = re.compile(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(/\d{1,2})?)$')
    ipv6_cidr_pattern = re.compile(r'^([0-9a-fA-F:]+(/\d{1,3})?)$')
    domain_keyword_pattern = re.compile(r'^([a-zA-Z0-9][-a-zA-Z0-9]*[a-zA-Z0-9]\.)+([a-zA-Z]{2,})$')
    
    for rule in rules:
        # 检查规则是否已有前缀（支持逗号和冒号两种格式）
        if any(rule.startswith(prefix) for prefix in [
            "DOMAIN,", "DOMAIN-SUFFIX,", "DOMAIN-KEYWORD,", "IP-CIDR,", "IP-CIDR6,", "PROCESS-NAME,", 
            "USER-AGENT,", "IP-ASN,", "DOMAIN:", "DOMAIN-SUFFIX:", "DOMAIN-KEYWORD:", "IP-CIDR:", 
            "IP-CIDR6:", "PROCESS-NAME:", "USER-AGENT:", "IP-ASN:"
        ]):
            # 保存已格式化的规则，稍后直接输出
            pre_formatted_rules.append(rule)
            continue
            
        # 检查是否为USER-AGENT规则
        if rule.startswith("USER-AGENT,") or rule.startswith("USER-AGENT:"):
            pre_formatted_rules.append(rule)
            continue
            
        # 检查是否为IP-ASN规则
        if rule.startswith("IP-ASN,") or rule.startswith("IP-ASN:"):
            pre_formatted_rules.append(rule)
            continue
            
        # 没有前缀，根据模式分类
        if ip_cidr_pattern.match(rule):
            categorized['IP-CIDR'].append(rule)
        elif ipv6_cidr_pattern.match(rule) and ':' in rule:
            categorized['IP-CIDR6'].append(rule)
        elif rule.startswith('.') or rule.startswith('*.'):
            # 移除开头的点
            clean_rule = rule[1:] if rule.startswith('.') else rule[2:] if rule.startswith('*.') else rule
            categorized['DOMAIN-SUFFIX'].append(clean_rule)
        elif domain_keyword_pattern.match(rule):
            # 完整域名
            categorized['DOMAIN'].append(rule)
        # 检查USER-AGENT规则格式
        elif rule.lower().startswith("user-agent,"):
            content = rule[11:]  # 提取USER-AGENT后面的内容
            categorized['USER-AGENT'].append(content)
        # 检查IP-ASN规则格式
        elif rule.lower().startswith("ip-asn,"):
            content = rule[7:]  # 提取IP-ASN后面的内容
            categorized['IP-ASN'].append(content)
        else:
            # 默认作为关键词
            categorized['DOMAIN-KEYWORD'].append(rule)
    
    return categorized, pre_formatted_rules

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
                    # 不再进行内容筛选，保留所有规则
                    all_rules.update(rules_from_url)
                except Exception as e:
                    # Catch errors during result processing
                    logging.error(f"Error processing result for {url}: {e}")
    
    logging.info(f"Total unique rules collected for {source_file.name}: {len(all_rules)}")
    
    # Skip writing if no rules were collected
    if not all_rules:
        logging.warning(f"No rules collected for {source_file.name}. No output file will be generated.")
        return
    
    # 仅用于统计目的，检测规则类型但不修改规则
    rule_types_count = {}
    for rule in all_rules:
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
        with open(output_file, 'w', encoding='utf-8') as f:
            # Write header
            f.write(f"# NAME: {source_file.stem}\n")
            f.write(f"# AUTHOR: {RULE_AUTHOR}\n")
            f.write(f"# REPO: {REPO_URL}\n")
            f.write(f"# UPDATED: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            # Write statistics for each rule type
            for rule_type, count in sorted(rule_types_count.items()):
                if count > 0:
                    f.write(f"# {rule_type}: {count}\n")
            
            # Write total count
            f.write(f"# TOTAL: {len(all_rules)}\n")
            f.write("\n")  # Add a blank line after header
            
            # Write all rules in their original format
            for rule in sorted(all_rules):
                f.write(f"{rule}\n")
            
        logging.info(f"Successfully merged and wrote {len(all_rules)} rules to {output_file}")
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
    
    # Process each source file separately
    for source_file in source_files:
        process_source_file(source_file)
    
    end_time = time.time()
    logging.info(f"Script finished in {end_time - start_time:.2f} seconds.")

if __name__ == "__main__":
    main() 