"""
Test Doubao Seedream 4.5 API using requests library
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
import json

SEEDREAM_API_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
SEEDREAM_MODEL = "doubao-seedream-4-5-251128"

def test_api():
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("ARK_API_KEY") or os.getenv("DOUBAO_API_KEY")
    results = []
    
    results.append("=" * 60)
    results.append("Testing Doubao Seedream 4.5 API (using requests)")
    results.append("=" * 60)
    results.append(f"API Key: {api_key[:20] if api_key else 'NOT SET'}...")
    
    if not api_key:
        results.append("ERROR: No API Key!")
        return "\n".join(results)
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    
    payload = {
        "model": SEEDREAM_MODEL,
        "prompt": "a cute cat sitting on a sofa, realistic photo, square",
        "size": "2K",
        "response_format": "url",
    }
    
    results.append(f"Payload: {json.dumps(payload, indent=2)}")
    results.append("Sending request...")
    
    try:
        response = requests.post(
            SEEDREAM_API_URL, 
            headers=headers, 
            json=payload,
            timeout=120
        )
        
        results.append(f"Status: {response.status_code}")
        
        try:
            data = response.json()
            results.append(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            if response.status_code == 200 and "data" in data:
                results.append("=" * 60)
                results.append("SUCCESS! Image generated!")
                if data.get("data") and len(data["data"]) > 0:
                    url = data['data'][0].get('url', 'N/A')
                    results.append(f"Image URL: {url[:100]}...")
                results.append("=" * 60)
            elif response.status_code == 400:
                results.append("ERROR: Bad request - check parameters")
            elif response.status_code == 401:
                results.append("ERROR: Authentication failed - check API Key")
        except:
            results.append(f"Response Text: {response.text}")
            
    except requests.exceptions.ConnectionError as e:
        results.append(f"ConnectionError: {e}")
    except requests.exceptions.Timeout as e:
        results.append(f"Timeout: {e}")
    except Exception as e:
        results.append(f"Exception: {type(e).__name__}: {e}")
    
    return "\n".join(results)

if __name__ == "__main__":
    result = test_api()
    with open("api_test_result.txt", "w", encoding="utf-8") as f:
        f.write(result)
    print("Result saved to api_test_result.txt")
    print(result)
