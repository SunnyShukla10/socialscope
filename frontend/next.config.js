/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  distDir: process.env.SOCIALSCOPE_CHECK_BUILD === "1" ? (process.env.SOCIALSCOPE_CHECK_DIR || ".next-validation") : ".next",
  experimental: { cpus: 1 },
  output: process.env.SOCIALSCOPE_CHECK_BUILD === '1' ? undefined : 'standalone',
  webpack(config) {
    if (process.env.SOCIALSCOPE_CHECK_BUILD === '1') config.cache = false
    return config
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.API_INTERNAL_URL || 'http://backend:8001'}/api/:path*`,
      },
    ]
  },
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**',
      },
    ],
  },
}

module.exports = nextConfig
