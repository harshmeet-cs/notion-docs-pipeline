/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  experimental: {
    // Enable Module Federation for Studio widget remotes
  },

  webpack(config, { isServer }) {
    if (!isServer) {
      const { ModuleFederationPlugin } = require("webpack").container;
      config.plugins.push(
        new ModuleFederationPlugin({
          name: "studio_client",
          remotes: {
            // v3: remoteEntry path now versioned for cache-busting
            "studio-locates": `studio-locates@[window.REMOTES.locates]/v3/remoteEntry.js`,
            "studio-blotter": `studio-blotter@[window.REMOTES.blotter]/remoteEntry.js`,
            "studio-risk": `studio-risk@[window.REMOTES.risk]/remoteEntry.js`,
          },
          shared: {
            react: { singleton: true, requiredVersion: "^18.0.0" },
            "react-dom": { singleton: true, requiredVersion: "^18.0.0" },
          },
        })
      );
    }
    return config;
  },
};

module.exports = nextConfig;
