import requests
import time

url = 'http://localhost:8000/api/v1/projects/8f5f4097-0291-43d8-bd24-efbbdb258621'

# Wait for server to be fully responsive
for i in range(10):
    try:
        if requests.get('http://localhost:8000/health').status_code == 200:
            break
    except:
        time.sleep(1)

print("Server is up. Attempting delete...")
response = requests.delete(url)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
