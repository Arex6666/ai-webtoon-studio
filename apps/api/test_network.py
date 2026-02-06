"""
Test Volcengine Ark API connectivity
"""
import asyncio
import httpx
import os
import socket

SEEDREAM_API_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"

async def test_connection():
    results = []
    results.append("=" * 50)
    results.append("Testing Volcengine Ark API Connection")
    results.append("=" * 50)
    
    # 1. Test DNS
    results.append("\n1. Testing DNS resolution...")
    try:
        ip = socket.gethostbyname("ark.cn-beijing.volces.com")
        results.append(f"   OK: ark.cn-beijing.volces.com -> {ip}")
    except socket.gaierror as e:
        results.append(f"   FAILED: DNS resolution failed: {e}")
        return "\n".join(results)
    
    # 2. Test HTTPS
    results.append("\n2. Testing HTTPS connection...")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                SEEDREAM_API_URL,
                headers={"Content-Type": "application/json"},
                json={"model": "test"}
            )
            results.append(f"   OK: HTTPS connection successful! Status: {response.status_code}")
            if response.status_code == 401:
                results.append("   OK: Server responded (401 = auth needed, expected)")
            else:
                results.append(f"   Response: {response.text[:200]}")
    except httpx.ConnectError as e:
        results.append(f"   FAILED: Connection error: {e}")
        results.append("\n   Possible causes:")
        results.append("   - Firewall blocking access")
        results.append("   - Proxy not configured correctly")
        results.append("   - VPN interference")
    except httpx.TimeoutException as e:
        results.append(f"   FAILED: Timeout: {e}")
    except Exception as e:
        results.append(f"   FAILED: {type(e).__name__}: {e}")
    
    # 3. Proxy check
    results.append("\n3. Proxy configuration...")
    has_proxy = False
    for name in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
        value = os.environ.get(name)
        if value:
            results.append(f"   {name} = {value}")
            has_proxy = True
    if not has_proxy:
        results.append("   No proxy configured")
    
    results.append("\n" + "=" * 50)
    return "\n".join(results)

if __name__ == "__main__":
    result = asyncio.run(test_connection())
    # Write to file to avoid encoding issues
    with open("test_result.txt", "w", encoding="utf-8") as f:
        f.write(result)
    print("Result written to test_result.txt")
