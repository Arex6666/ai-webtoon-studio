
import httpx
import hashlib
import hmac
import datetime
import json
import base64
from urllib.parse import quote
import asyncio
import os

# 用户提供的 SK
SK_RAW = "TURFeU9UVXhOekF4WWpFMU5EUmpPRGszWmpVek9EZzRNelZtWldVMk56QQ=="
AK = "AKLTOGU3M2VhMjVhZDllNDAwMjllMjI0YzNiYjE1ZTY5NzE"

HOST = "visual.volcengineapi.com"
SERVICE = "cv"
REGION = "cn-north-1"

def sign(sk, method, path, query, headers, body):
    algorithm = "HMAC-SHA256"
    t = datetime.datetime.utcnow()
    date_stamp = t.strftime("%Y%m%d")
    amz_date = t.strftime("%Y%m%dT%H%M%SZ")
    
    credential_scope = f"{date_stamp}/{REGION}/{SERVICE}/request"
    
    # Process headers
    canonical_headers_list = []
    signed_headers_list = []
    for k, v in sorted(headers.items()):
        lower_k = k.lower()
        if lower_k in ["content-type", "host", "x-date", "x-content-sha256"]:
            processed_v = v.strip()
            canonical_headers_list.append(f"{lower_k}:{processed_v}\n")
            signed_headers_list.append(lower_k)
            
    canonical_headers = "".join(canonical_headers_list)
    signed_headers = ";".join(signed_headers_list)
    
    content_sha256 = hashlib.sha256(body).hexdigest()
    
    sorted_query = sorted(query.items())
    canonical_query = "&".join(f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in sorted_query)
    
    canonical_request = (
        f"{method}\n"
        f"{path}\n"
        f"{canonical_query}\n"
        f"{canonical_headers}\n"
        f"{signed_headers}\n"
        f"{content_sha256}"
    )
    
    hashed_request = hashlib.sha256(canonical_request.encode()).hexdigest()
    string_to_sign = f"{algorithm}\n{amz_date}\n{credential_scope}\n{hashed_request}"
    
    def get_sign_key(key, date_stamp, region_name, service_name):
        k_date = hmac.new(key.encode('utf-8'), date_stamp.encode('utf-8'), hashlib.sha256).digest()
        k_region = hmac.new(k_date, region_name.encode('utf-8'), hashlib.sha256).digest()
        k_service = hmac.new(k_region, service_name.encode('utf-8'), hashlib.sha256).digest()
        k_signing = hmac.new(k_service, "request".encode('utf-8'), hashlib.sha256).digest()
        return k_signing

    signing_key = get_sign_key(sk, date_stamp, REGION, SERVICE)
    signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
    
    authorization = (
        f"{algorithm} Credential={AK}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    
    return {
        "Authorization": authorization,
        "X-Date": amz_date,
        "X-Content-Sha256": content_sha256,
    }

async def test_auth(sk, label):
    print(f"\n--- Testing with {label} SK ---")
    print(f"SK (preview): {sk[:10]}...")
    
    path = "/"
    query = {"Action": "CVProcess", "Version": "2022-08-31"}
    
    payload = {
        "req_key": "jimeng_high_aes_general_v21_L",
        "prompt": "test",
        "width": 512,
        "height": 512,
        "return_url": True,
    }
    body = json.dumps(payload).encode()
    
    headers = {
        "Content-Type": "application/json",
        "Host": HOST,
    }
    
    try:
        sign_headers = sign(sk, "POST", path, query, headers, body)
        headers.update(sign_headers)
        
        query_str = "&".join(f"{k}={v}" for k, v in query.items())
        url = f"https://{HOST}{path}?{query_str}"
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, content=body)
            print(f"Status Code: {resp.status_code}")
            print(f"Response: {resp.text}")
            if resp.status_code == 200:
                print("SUCCESS!")
                return True
            else:
                print("FAILED")
                return False
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False

async def main():
    # 1. Test Raw SK
    print("Testing RAW SK string...")
    res = await test_auth(SK_RAW, "RAW")
    if res: return
    
    # 2. Test Base64 Decoded SK
    try:
        decoded_bytes = base64.b64decode(SK_RAW)
        decoded_str = decoded_bytes.decode('utf-8')
        print("Testing Base64 Decoded SK string...")
        res = await test_auth(decoded_str, "DECODED")
        if res: return
        
        print("Maybe decoded bytes?")
        # Note: hmac key expects bytes or string. My function encodes string to bytes. 
        # If SK is raw bytes, we should handle differently. But usually it's string.
    except Exception as e:
        print(f"Decoding failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
