import json
import urllib.parse
import urllib.request
import io
import sys
import re

# Force UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

wikis = [
    ("onepiece", "https://onepiece.fandom.com/api.php"),
    ("bleach", "https://bleach.fandom.com/api.php"),
    ("aot", "https://attackontitan.fandom.com/api.php"),
    ("demon_slayer", "https://kimetsu-no-yaiba.fandom.com/api.php"),
    ("jjk", "https://jujutsu-kaisen.fandom.com/api.php"),
]

for name, endpoint in wikis:
    url = f"{endpoint}?action=parse&page=Episode_1&prop=wikitext&format=json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AnimeAI/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            wt = data.get("parse", {}).get("wikitext", {}).get("*", "")
            print(f"=== {name.upper()} Episode 1 ===")
            for line in wt.splitlines()[:30]:
                if any(k in line.lower() for k in ["|title", "|english", "|kanji", "|romaji", "|chapter", "|airdate", "|release", "|arc"]):
                    print("  ", line[:100])
    except Exception as e:
        print(f"=== {name.upper()} Error: {e} ===")
