/** @type {import('next').NextConfig} */
const nextConfig = {
  async headers() {
    return [
      {
        source: '/api/:path*',
        headers: [
          { key: 'Access-Control-Allow-Origin', value: '*' },
          { key: 'Access-Control-Allow-Methods', value: 'GET,POST,PUT,DELETE,OPTIONS' },
          { key: 'Access-Control-Allow-Headers', value: 'Content-Type' },
        ],
      },
    ];
  },
  env: {
    API_URL: process.env.NODE_ENV === 'production' 
      ? 'https://accident-risk-prediction.onrender.com'
      : 'http://localhost:5000',
  },
};

export default nextConfig;
