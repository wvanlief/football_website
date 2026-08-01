import json, os, base64

cache_dir = r"c:\Users\user\PycharmProjects\football_website\backend\data\cache"

for f in sorted(os.listdir(cache_dir)):
    if not f.endswith(".json"):
        continue
    path = os.path.join(cache_dir, f)
    size_kb = os.path.getsize(path) / 1024
    try:
        data = json.loads(open(path, encoding="utf-8").read())
        url = data.get("url", "?")
        content_b64 = data.get("content", "")
        try:
            content = json.loads(base64.b64decode(content_b64).decode("utf-8"))
            resp = content.get("response", [])
            if isinstance(resp, list) and len(resp) > 0:
                first = resp[0]
                league = first.get("league", {}) if isinstance(first, dict) else {}
                league_name = league.get("name", "?")
                league_id = league.get("id", "?")
                count = len(resp)
                print(f"{f} ({size_kb:.1f}KB): {url}")
                print(f"  -> {league_name} (id={league_id}), {count} items")
            else:
                print(f"{f} ({size_kb:.1f}KB): {url}")
                print(f"  -> {len(resp)} items in response")
        except Exception:
            print(f"{f} ({size_kb:.1f}KB): {url}")
            print(f"  -> (content not base64 JSON)")
    except Exception as e:
        print(f"{f} ({size_kb:.1f}KB): ERROR - {e}")
