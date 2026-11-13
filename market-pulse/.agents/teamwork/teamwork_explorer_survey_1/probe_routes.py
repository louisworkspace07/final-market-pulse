import re

path = r"C:\Users\toans\Desktop\Final Market Pulse\market-pulse\gateway\app.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

routes = []
for i, line in enumerate(lines, 1):
    m = re.search(r'@app\.route\(\s*["\']([^"\']+)["\']', line)
    if m:
        # find the function name
        fn_name = ""
        for j in range(i, min(i+10, len(lines))):
            fm = re.search(r'def\s+([a-zA-Z0-9_]+)\(', lines[j])
            if fm:
                fn_name = fm.group(1)
                break
        routes.append((i, m.group(1), fn_name))

print(f"Total routes found: {len(routes)}")
for line_no, route, fn in routes:
    print(f"L{line_no:4d} | {route:35s} | {fn}")
