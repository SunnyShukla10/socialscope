/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  distDir: process.env.SOCIALSCOPE_BUILD_DIR || '.next',
  experimental: { cpus: 1 },
  output: 'standalone',
  poweredByHeader: false,
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.API_INTERNAL_URL || 'http://backend:8001'}/api/:path*`,
      },
    ]
  },
  images: {
    // No application component uses next/image. Do not expose a wildcard
    // server-side image fetcher; add explicit hosts if optimized images are added.
    remotePatterns: [],
  },
}

module.exports = nextConfig
