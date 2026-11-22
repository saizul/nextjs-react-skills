import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  output: 'standalone',
  poweredByHeader: false,
  deploymentId: process.env.DEPLOYMENT_VERSION,
  cacheHandler: require.resolve('./cache-handler.js'),
  cacheMaxMemorySize: 0,
  images: { remotePatterns: [{ protocol: 'https', hostname: 'cdn.example.com' }] },
}

export default nextConfig
