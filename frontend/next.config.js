/** @type {import('next').NextConfig} */
const nextConfig = {
  allowedDevOrigins: ['*.pike.replit.dev', '*.replit.dev'],
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';
    return [
      { source: '/api/:path*', destination: `${backendUrl}/api/:path*` },
      { source: '/docs', destination: `${backendUrl}/docs` },
      { source: '/redoc', destination: `${backendUrl}/redoc` },
      { source: '/openapi.json', destination: `${backendUrl}/openapi.json` },
    ];
  },
};

module.exports = nextConfig;
