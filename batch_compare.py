import requests
from bs4 import BeautifulSoup
import difflib
import csv
import os

# Constants
ARCHIVE_PREFIX = "https://wayback.archive-it.org/9618/20250701131117/"
INPUT_CSV = "url_list.csv"
OUTPUT_CSV = "site_diff_summary.csv"

def fetch_html(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"❌ Failed to fetch {url}: {e}")
        return None

def extract_tagged_blocks(html):
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    elements = soup.find_all(['h1','h2','h3','h4','h5','h6','p','li','div'])

    blocks = []
    for el in elements:
        text = el.get_text(separator=' ', strip=True)
        if text:
            blocks.append(f"<{el.name}> {text}")
    return blocks

def compare_sites(live_url, archive_url):
    live_html = fetch_html(live_url)
    archive_html = fetch_html(archive_url)

    if not live_html or not archive_html:
        return None  # Skip comparison if either fails

    live_blocks = extract_tagged_blocks(live_html)
    archive_blocks = extract_tagged_blocks(archive_html)

    additions = deletions = inline_changes = 0
    matcher = difflib.SequenceMatcher(None, archive_blocks, live_blocks)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'insert':
            deletions += (j2 - j1)
        elif tag == 'delete':
            additions += (i2 - i1)
        elif tag == 'replace':
            inline_changes += max(i2 - i1, j2 - j1)

    total_blocks = len(set(archive_blocks + live_blocks))
    total_changes = additions + deletions + inline_changes
    percent_changed = (total_changes / total_blocks * 100) if total_blocks > 0 else 0.0

    return {
        "URL": live_url,
        "Percentage of Content Changed": f"{percent_changed:.1f}%",
        "Additions": additions,
        "Deletions": deletions,
        "Inline Changes": inline_changes
    }

def main():
    # Check if output exists
    write_header = not os.path.exists(OUTPUT_CSV)

    with open(INPUT_CSV, newline='', encoding='utf-8') as infile, \
         open(OUTPUT_CSV, "a", newline='', encoding='utf-8') as outfile:
        
        reader = csv.reader(infile)
        writer = csv.writer(outfile)

        if write_header:
            writer.writerow(["URL", "Percentage of Content Changed", "Additions", "Deletions", "Inline Changes"])

        for row in reader:
            if not row or not row[0].strip():
                continue  # skip blank lines
            live_url = row[0].strip()
            archive_url = ARCHIVE_PREFIX + live_url
            print(f"🔍 Comparing: {live_url}")

            result = compare_sites(live_url, archive_url)
            if result:
                writer.writerow([
                    result["URL"],
                    result["Percentage of Content Changed"],
                    result["Additions"],
                    result["Deletions"],
                    result["Inline Changes"]
                ])
                print(f"✅ Done: {live_url}")
            else:
                print(f"⚠️ Skipped: {live_url}")

    # After all rows processed, analyze the output CSV for change ranges
    bins = [0] * 10  # 10 bins: 0-10%, 10-20%, ..., 90-100%

    with open(OUTPUT_CSV, newline='', encoding='utf-8') as summary_file:
        reader = csv.DictReader(summary_file)
        for row in reader:
            percent_str = row["Percentage of Content Changed"].strip().rstrip('%')
            try:
                pct = float(percent_str)
                index = min(int(pct // 10), 9)
                bins[index] += 1
            except ValueError:
                continue  # skip malformed percentages

    # Print histogram summary
    print("\n📊 Change Summary:")
    for i in range(10):
        low = i * 10
        high = low + 10
        print(f"  {low:2d}–{high:3d}% : {bins[i]} URLs")


if __name__ == "__main__":
    main()
