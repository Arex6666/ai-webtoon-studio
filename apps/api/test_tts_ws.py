"""
TTS WebSocket Binary API Test - 大模型语音合成2.0
Uses wss://openspeech.bytedance.com/api/v1/tts/ws_binary
"""
import json
import uuid
import gzip
import struct
import asyncio
import os

try:
    import websockets
except ImportError:
    print("Installing websockets...")
    import subprocess
    subprocess.check_call(["pip", "install", "websockets"])
    import websockets


APPID = "8413996009"
TOKEN = "SQn_8i0TG5bPAexfliei-dH13ywxTSHu"
WS_URL = "wss://openspeech.bytedance.com/api/v1/tts/ws_binary"

# Protocol constants
PROTOCOL_VERSION = 0b0001
HEADER_SIZE = 0b0001  # 1 * 4 bytes = 4 bytes
MESSAGE_TYPE_FULL_CLIENT = 0b0001
MESSAGE_TYPE_AUDIO_ONLY_SERVER = 0b1011
MESSAGE_TYPE_FULL_SERVER = 0b1001
MESSAGE_TYPE_ERROR = 0b1111
SERIAL_NONE = 0b0000
SERIAL_JSON = 0b0001
COMPRESSION_NONE = 0b0000
COMPRESSION_GZIP = 0b0001


def build_request(text: str, cluster: str, voice: str) -> bytes:
    """Build binary WebSocket request frame."""
    payload = {
        "app": {
            "appid": APPID,
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
            "text": text,
            "text_type": "plain",
            "operation": "submit",
        },
    }

    payload_bytes = json.dumps(payload).encode("utf-8")
    payload_compressed = gzip.compress(payload_bytes)

    # Build header: 4 bytes
    # byte 0: protocol_version(4bit) + header_size(4bit)
    # byte 1: message_type(4bit) + serialization(4bit)
    # byte 2: compression(4bit) + reserved(4bit)
    # byte 3: reserved
    header = bytes([
        (PROTOCOL_VERSION << 4) | HEADER_SIZE,
        (MESSAGE_TYPE_FULL_CLIENT << 4) | SERIAL_JSON,
        (COMPRESSION_GZIP << 4) | 0x00,
        0x00,
    ])

    # Payload size (4 bytes big-endian)
    size = struct.pack(">I", len(payload_compressed))

    return header + size + payload_compressed


def parse_response(data: bytes):
    """Parse binary WebSocket response frame."""
    if len(data) < 4:
        return None, None, "too short"

    # Parse header
    header_size = (data[0] & 0x0F) * 4  # in bytes
    msg_type = (data[1] >> 4) & 0x0F
    serialization = data[1] & 0x0F
    compression = (data[2] >> 4) & 0x0F

    if msg_type == MESSAGE_TYPE_ERROR:
        # Error response
        payload_size = struct.unpack(">I", data[4:8])[0]
        payload = data[8:8+payload_size]
        if compression == COMPRESSION_GZIP:
            payload = gzip.decompress(payload)
        error_msg = json.loads(payload) if serialization == SERIAL_JSON else payload.decode()
        return "error", None, error_msg

    if msg_type == MESSAGE_TYPE_AUDIO_ONLY_SERVER:
        # Audio data
        sequence = struct.unpack(">i", data[4:8])[0]  # -1 = last
        payload_size = struct.unpack(">I", data[8:12])[0]
        audio_data = data[12:12+payload_size]
        is_last = (sequence < 0)
        return "audio", audio_data, {"sequence": sequence, "is_last": is_last}

    if msg_type == MESSAGE_TYPE_FULL_SERVER:
        # Full server response (may contain metadata + audio)
        payload_size = struct.unpack(">I", data[header_size:header_size+4])[0]
        payload = data[header_size+4:header_size+4+payload_size]
        if compression == COMPRESSION_GZIP:
            payload = gzip.decompress(payload)
        if serialization == SERIAL_JSON:
            return "json", None, json.loads(payload)
        return "raw", payload, None

    return "unknown", None, f"msg_type={msg_type}"


async def test_ws_tts(cluster: str, voice: str, desc: str):
    """Test a single cluster+voice combination via WebSocket."""
    print(f"\n--- {desc} ---")
    print(f"    cluster={cluster}, voice={voice}")

    text = "你好，这是一个语音合成测试，今天天气真不错。"

    headers = {
        "Authorization": f"Bearer;{TOKEN}",
    }

    try:
        async with websockets.connect(
            WS_URL,
            additional_headers=headers,
            open_timeout=10,
            close_timeout=5,
        ) as ws:
            # Send request
            request_frame = build_request(text, cluster, voice)
            await ws.send(request_frame)

            # Collect audio chunks
            audio_chunks = []
            while True:
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=15)
                except asyncio.TimeoutError:
                    print("    Timeout waiting for response")
                    break

                msg_type, audio_data, info = parse_response(response)

                if msg_type == "error":
                    print(f"    ERROR: {info}")
                    return False

                if msg_type == "audio":
                    audio_chunks.append(audio_data)
                    if info.get("is_last"):
                        break

                if msg_type == "json":
                    print(f"    Server JSON: {json.dumps(info, ensure_ascii=False)[:200]}")
                    # Check if it contains audio
                    if isinstance(info, dict) and info.get("code") and info["code"] != 3000:
                        print(f"    FAILED: code={info.get('code')}, msg={info.get('message','')[:100]}")
                        return False

                if msg_type == "unknown":
                    print(f"    Unknown response: {info}")

            if audio_chunks:
                all_audio = b"".join(audio_chunks)
                out_path = os.path.join(os.path.dirname(__file__), f"test_ws_{cluster}_{voice}.mp3")
                with open(out_path, "wb") as f:
                    f.write(all_audio)
                print(f"    SUCCESS! {len(all_audio)} bytes ({len(audio_chunks)} chunks) -> {out_path}")
                return True
            else:
                print("    No audio data received")
                return False

    except websockets.exceptions.InvalidStatusCode as e:
        print(f"    WS connection rejected: HTTP {e.status_code}")
        return False
    except Exception as e:
        print(f"    Error: {type(e).__name__}: {e}")
        return False


async def main():
    attempts = [
        # 大模型2.0 - volcano_mega
        ("volcano_mega", "BV700_streaming", "Mega: BV700 cancan"),
        ("volcano_mega", "BV701_streaming", "Mega: BV701"),
        ("volcano_mega", "BV001_streaming", "Mega: BV001"),
        # 标准 TTS
        ("volcano_tts", "BV700_streaming", "TTS: BV700 cancan"),
        ("volcano_tts", "BV001_streaming", "TTS: BV001"),
        # ICL (voice cloning)
        ("volcano_icl", "BV700_streaming", "ICL: BV700"),
        # 双向流式专用 cluster
        ("volcano_bidirection", "BV700_streaming", "Bidirection: BV700"),
    ]

    successes = []
    for cluster, voice, desc in attempts:
        ok = await test_ws_tts(cluster, voice, desc)
        if ok:
            successes.append((cluster, voice, desc))

    print("\n" + "="*50)
    if successes:
        print(f"[RESULT] {len(successes)} combination(s) worked:")
        for c, v, d in successes:
            print(f"  - {d}: cluster={c}, voice={v}")
    else:
        print("[RESULT] All attempts failed.")
        print("Please check your Volcengine console:")
        print("  1. Go to https://console.volcengine.com/speech/app")
        print("  2. Make sure TTS service is enabled for your app")
        print("  3. Check which resource IDs are granted")


if __name__ == "__main__":
    asyncio.run(main())
