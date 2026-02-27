import requests
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("HF_TOKEN")
headers = {"Authorization": f"Bearer {token}"}

model = "black-forest-labs/FLUX.1-schnell"

endpoints = [
    f"https://api-inference.huggingface.co/models/{model}",
    f"https://router.huggingface.co/hf-inference/models/{model}",
    f"https://router.huggingface.co/models/{model}",
]

for url in endpoints:
    print(f"Testing {url}...")
    try:
        # Dummy call with short timeout
        r = requests.post(url, headers=headers, json={"inputs": "test"}, timeout=10)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")
    print("-" * 20)
