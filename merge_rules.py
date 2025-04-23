import os
import requests
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# --- Configuration ---
# Directory containing the source URL lists
SOURCE_DIR = Path("sources")
# Directory to output the merged list
OUTPUT_DIR = Path("dist")
# Name of the final merged file
OUTPUT_FILENAME = "merged_rules.list"
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
            if response.status_code >= 400 and response.status_code < 500:
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

def main():
    """Main function to merge rule lists."""
    start_time = time.time()
    if not SOURCE_DIR.is_dir():
        logging.error(f"Source directory '{SOURCE_DIR}' not found.")
        # Optionally create it? For now, let's error out.
        # SOURCE_DIR.mkdir(parents=True, exist_ok=True)
        # logging.info(f"Created source directory '{SOURCE_DIR}'. Please add source files.")
        return

    source_files = list(SOURCE_DIR.glob("*.txt")) # Ensure we only look for .txt files
    if not source_files:
        logging.warning(f"No source files (.txt) found in '{SOURCE_DIR}'. Exiting.")
        # Create empty output file if no sources? Or just exit? Let's exit.
        return

    all_urls = set() # Use set to avoid duplicate URLs from the start
    for file_path in source_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Read URLs, strip whitespace, ignore comments and empty lines
                urls_in_file = {line.strip() for line in f if line.strip() and not line.startswith('#')}
                all_urls.update(urls_in_file)
                logging.info(f"Read {len(urls_in_file)} unique URLs from {file_path.name}")
        except FileNotFoundError:
             logging.error(f"Source file not found: {file_path}. Skipping.")
        except Exception as e:
            logging.error(f"Error reading source file {file_path}: {e}")

    if not all_urls:
        logging.warning("No valid URLs found in source files after reading. Exiting.")
        return

    logging.info(f"Found {len(all_urls)} unique URLs in total. Starting download process with {MAX_WORKERS} workers...")

    merged_rules = set()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit download tasks
        future_to_url = {executor.submit(download_content, url): url for url in all_urls}

        processed_count = 0
        # Process completed tasks as they finish
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            processed_count += 1
            try:
                rules_from_url = future.result()
                # Perform basic validation if needed (e.g., check if rule looks like a domain/ip)
                # This is a very basic check, might need refinement depending on rule format
                valid_rules = {rule for rule in rules_from_url if '.' in rule or ':' in rule} # Simple check for dot or colon (IPv6)
                invalid_count = len(rules_from_url) - len(valid_rules)
                if invalid_count > 0:
                    logging.debug(f"Filtered out {invalid_count} potentially invalid rules (no '.' or ':') from {url}.")
                merged_rules.update(valid_rules)
            except Exception as e:
                # Catch errors during result processing (though download_content should handle most)
                logging.error(f"Error processing result for {url}: {e}")
            # Optional: Log progress
            # logging.info(f"Processed {processed_count}/{len(all_urls)} URLs...")

    logging.info(f"Total unique and valid rules collected: {len(merged_rules)}")

    # Create output directory if it doesn't exist
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_path = OUTPUT_DIR / OUTPUT_FILENAME
    try:
        # Sort rules before writing for consistency and better diffs
        sorted_rules = sorted(list(merged_rules))
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# Merged Rule List\\n")
            f.write(f"# Description: Combined list from various sources\\n")
            f.write(f"# Total rules: {len(sorted_rules)}\\n")
            f.write(f"# Last updated: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}\\n")
            # Make the repository URL dynamic or configurable if possible
            # f.write("# Generated by script: https://github.com/YourUsername/YourRepoName\\n") # Replace with your repo URL
            f.write("\\n") # Add a blank line after header
            for rule in sorted_rules:
                f.write(rule + '\\n')
        logging.info(f"Successfully merged and wrote {len(sorted_rules)} rules to {output_path}")
    except IOError as e:
        logging.error(f"Error writing merged rules to {output_path}: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred during file writing: {e}")

    end_time = time.time()
    logging.info(f"Script finished in {end_time - start_time:.2f} seconds.")


if __name__ == "__main__":
    main() 