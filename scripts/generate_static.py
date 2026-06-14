import json, random, string, os

os.makedirs("static", exist_ok=True)

data = {
    "records": [
        {
            "id": i,
            "name": "".join(random.choices(string.ascii_letters, k=12)),
            "value": round(random.random() * 1000, 2),
            "tags": ["alpha", "beta", "gamma"],
        }
        for i in range(200)
    ]
}

with open("static/medium.json", "w") as f:
    json.dump(data, f)

with open("static/large.bin", "w") as f:
    f.write("X" * 200_000)

with open("static/small.html", "w") as f:
    f.write("""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Small Page</title></head>
<body><h1>Nginx Benchmark</h1>
<p>Small static HTML file for energy benchmarking.</p>
<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor
incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam quis nostrud
exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.</p>
</body></html>""")

print(" Static files generated successfully!")
print(f"  medium.json  → {os.path.getsize('static/medium.json')} bytes")
print(f"  large.bin    → {os.path.getsize('static/large.bin')} bytes")
print(f"  small.html   → {os.path.getsize('static/small.html')} bytes")
