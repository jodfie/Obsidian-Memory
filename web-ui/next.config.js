/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  typescript: {
    // Type checking is done separately via `npm run typecheck`
    ignoreBuildErrors: false,
  },
  eslint: {
    // Linting is done separately via `npm run lint`
    ignoreDuringBuilds: false,
  },
  // Path aliases are configured in tsconfig.json
  // Output configuration
  output: 'standalone',
  // Experimental features can be added here as needed
  experimental: {},
};

module.exports = nextConfig;
