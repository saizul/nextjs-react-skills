import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  experimental: { serverActions: { allowedOrigins: ['app.example.com'], bodySizeLimit: '2mb' } },
}

export default nextConfig
