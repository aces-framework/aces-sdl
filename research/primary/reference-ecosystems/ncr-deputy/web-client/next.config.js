/** @type {import('next').NextConfig} */
const nextTranslate = require('next-translate-plugin');

module.exports = nextTranslate({
  reactStrictMode: true,
  swcMinify: true,
  env: {
    DOCUMENTATION_URL: process.env.DOCUMENTATION_URL,
    INSTALLER_URL: process.env.INSTALLER_URL,
  },
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
        ],
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: 'http://localhost:9000/api/v1/:path*',
      },
    ];
  },
});
