/** @type {import('next').NextConfig} */
const securityHeaders = [
  // Don't advertise the framework — small surface for known-CVE scanners.
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
  { key: 'X-Frame-Options', value: 'SAMEORIGIN' },
  // The site uses JWTs in localStorage, so Permissions-Policy stays minimal.
  { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
];

module.exports = {
  reactStrictMode: true,
  poweredByHeader: false,
  images: {
    domains: [],
  },
  async headers() {
    return [
      {
        source: '/:path*',
        headers: securityHeaders,
      },
    ];
  },
};
