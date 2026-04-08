/** @type {import('next').NextConfig} */
const nextConfig = {
  // FastAPI 서버로 API 요청 프록시
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/:path*`,
      },
      {
        source: "/webhook/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/webhook/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
