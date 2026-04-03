/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  skipTrailingSlashRedirect: true,
  async rewrites() {
    const apiDest = process.env.INTERNAL_API_URL || 'http://api:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${apiDest}/api/:path*`,
      },
      {
        source: '/healthz',
        destination: `${apiDest}/healthz`,
      },
      {
        source: '/docs',
        destination: `${apiDest}/docs`,
      },
      {
        source: '/openapi.json',
        destination: `${apiDest}/openapi.json`,
      },
    ];
  },
}

module.exports = nextConfig
