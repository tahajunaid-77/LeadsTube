/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  devIndicators: false,
  // `npm run dev` keeps its files apart from the production build, so building
  // never breaks a running dev server (and the other way round).
  distDir: process.env.LEADTUBE_DEV ? ".next-dev" : ".next",
};
export default nextConfig;
