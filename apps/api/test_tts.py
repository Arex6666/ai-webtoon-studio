"""
TTS API Test - try different clusters and voice types
Tests both HTTP v1 API and checks for 大模型2.0 availability
"""
import json
import uuid
import base64
import os
import httpx
import asyncio


async def test_tts():
    appid = "8413996009"
    token = "SQn_8i0TG5bPAexfliei-dH13ywxTSHu"

    url = "https://openspeech.bytedance.com/api/v1/tts"
    test_text = "你好，这是一个语音合成测试，今天天气真不错。"

    # Comprehensive cluster + voice combinations
    attempts = [
        # 大模型语音合成 2.0 (MegaTTS) - volcano_mega cluster
        ("volcano_mega", "BV700_streaming", "Mega: BV700 cancan female"),
        ("volcano_mega", "BV701_streaming", "Mega: BV701"),
        ("volcano_mega", "BV034_streaming", "Mega: BV034"),
        ("volcano_mega", "BV001_streaming", "Mega: BV001 standard"),
        # 标准 TTS - volcano_tts cluster
        ("volcano_tts", "BV700_streaming", "TTS: BV700 cancan female"),
        ("volcano_tts", "BV701_streaming", "TTS: BV701"),
        ("volcano_tts", "BV001_streaming", "TTS: BV001 standard"),
        ("volcano_tts", "BV034_streaming", "TTS: BV034"),
        # ICL cluster (voice cloning)
        ("volcano_icl", "BV700_streaming", "ICL: BV700"),
        # BigTTS voices
        ("volcano_tts", "zh_male_M392_conversation_wvae_bigtts", "TTS: BigTTS male M392"),
        ("volcano_mega", "zh_male_M392_conversation_wvae_bigtts", "Mega: BigTTS male M392"),
    ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        for cluster, voice, desc in attempts:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer;{token}",
            }
            body = {
                "app": {
                    "appid": appid,
                    "token": "access_token",
                    "cluster": cluster,
                },
                "user": {"uid": "test_user"},
                "audio": {
                    "voice_type": voice,
                    "encoding": "mp3",
                    "speed_ratio": 1.0,
                    "rate": 24000,
                },
                "request": {
                    "reqid": str(uuid.uuid4()),
                    "text": test_text,
                    "operation": "query",
                },
            }

            print(f"\n--- {desc} ---")
            print(f"    cluster={cluster}, voice={voice}")

            try:
                resp = await client.post(url, headers=headers, content=json.dumps(body))
                if resp.status_code == 200:
                    result = resp.json()
                    code = result.get("code")
                    msg = result.get("message", "")
                    print(f"    code={code}, msg={msg}")

                    if code == 3000:
                        audio_bytes = base64.b64decode(result["data"])
                        duration = result.get("addition", {}).get("duration", "?")
                        out_path = os.path.join(os.path.dirname(__file__), f"test_output_{cluster}_{voice}.mp3")
                        with open(out_path, "wb") as f:
                            f.write(audio_bytes)
                        print(f"    SUCCESS! {len(audio_bytes)} bytes, duration={duration}ms -> {out_path}")
                        # Don't return - test all combinations to see what's available
                    else:
                        print(f"    FAILED: code={code}")
                else:
                    try:
                        err = resp.json()
                        print(f"    HTTP {resp.status_code}: code={err.get('code')}, msg={err.get('message','')[:120]}")
                    except Exception:
                        print(f"    HTTP {resp.status_code}: {resp.text[:120]}")
            except Exception as e:
                print(f"    Error: {e}")

    print("\n[DONE] Test complete.")


if __name__ == "__main__":
    asyncio.run(test_tts())
