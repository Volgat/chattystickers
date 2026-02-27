import requests, json

r = requests.post(
    "http://localhost:5000/api/generate",
    json={"phrase": "Mon chat dit Salut en dansant"},
    timeout=120,
)
result = r.json()
print(json.dumps(result, indent=2, ensure_ascii=False))
