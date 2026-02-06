```cpp
# 1. 确保在正确的目录
cd /hy-tmp/ComfyUI

# 2. 再次确保 Aria2 已安装
apt-get update && apt-get install -y aria2

echo "🚀 开始下载满血版模型 (Flux FP8 + T5 FP16 + SVD)..."

# --- [1] Flux UNet (16GB) ---
cd models/unet
echo "📥 [1/5] 下载 Flux UNet..."
aria2c -c -x 16 -s 16 -k 1M https://hf-mirror.com/Comfy-Org/flux1-dev/resolve/main/flux1-dev-fp8.safetensors

# --- [2] T5 Text Encoder (FP16 满血版 - 9GB) ---
cd ../clip
echo "📥 [2/5] 下载 T5 (FP16版)..."
aria2c -c -x 16 -s 16 -k 1M https://hf-mirror.com/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp16.safetensors

# --- [3] CLIP L ---
echo "📥 [3/5] 下载 CLIP L..."
aria2c -c -x 16 -s 16 -k 1M https://hf-mirror.com/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors

# --- [4] VAE ---
cd ../vae
echo "📥 [4/5] 下载 VAE..."
aria2c -c -x 16 -s 16 -k 1M https://modelscope.cn/models/AI-ModelScope/FLUX.1-schnell/resolve/master/ae.safetensors

# --- [5] SVD 视频模型 (9GB) ---
cd ../checkpoints
echo "📥 [5/5] 下载 SVD 视频模型..."
aria2c -c -x 16 -s 16 -k 1M https://modelscope.cn/models/AI-ModelScope/stable-video-diffusion-img2vid-xt/resolve/master/svd_xt.safetensors

# 3. 修复管理器 (确保它是好的)
cd ../../custom_nodes
rm -rf ComfyUI-Manager
git clone https://gitee.com/loop00/ComfyUI-Manager.git

echo "✅ 所有下载任务已启动！请务必等待所有进度条显示 100% [OK]。"
```

