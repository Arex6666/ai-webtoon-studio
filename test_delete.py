import requests
import json

url = 'http://localhost:8000/api/v1/projects/8f5f4097-0291-43d8-bd24-efbbdb258621'

# Try delete
response = requests.delete(url, timeout=30)
print(f"Status: {response.status_code}")

# Parse and save as formatted JSON
try:
    data = response.json()
    # Write formatted JSON to file
    with open('response.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("Saved to response.json")
    
    # Print just the key info
    print(f"\nError: {data.get('error', 'N/A')}")
    print(f"Message: {data.get('message', 'N/A')[:500]}")
except Exception as e:
    print(f"Parse error: {e}")
    print(f"Raw: {response.text[:500]}")
