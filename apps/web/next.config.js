/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
        port: '9000',
        pathname: '/**',
      },
      {
        protocol: 'https',
        hostname: '**.minio.io',
        pathname: '/**',
      },
    ],
  },
  // API 代理配置 - 将 /api/v1 请求代理到后端
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: 'http://localhost:8000/api/v1/:path*',
      },
    ]
  },
  // 解决 Konva 在 SSR 时尝试加载 canvas 模块的问题
  webpack: (config, { isServer }) => {
    // canvas 是 Konva 的可选依赖，仅在 Node.js 环境需要
    // 在浏览器中不需要，因此可以忽略
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        canvas: false,
      };
    }

    // 忽略 canvas 模块（避免构建时报错）
    config.externals = [...(config.externals || []), { canvas: 'canvas' }];

    return config;
  },
}

module.exports = nextConfig
