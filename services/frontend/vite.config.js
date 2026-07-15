import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icons/apple-touch-icon.png'],
      manifest: {
        name: 'Attendance Ledger',
        short_name: 'Ledger',
        description: 'Attendance management, regularization, and face check-in.',
        theme_color: '#1B2A41',
        background_color: '#EEF1EF',
        display: 'standalone',
        start_url: '/',
        scope: '/',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/icons/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // IMPORTANT: this app is almost entirely live data (attendance
        // records, approval queues, reports) served from 5 separate
        // backend APIs. The service worker must never cache those
        // responses -- a cached "Pending Requests" list or attendance
        // history would be actively misleading, not just stale UI chrome.
        // Only the app shell (JS/CSS/HTML/icons) is precached; every API
        // call always goes to the network.
        navigateFallbackDenylist: [/^\/api/, /^\/auth/],
        runtimeCaching: [], // no runtime caching rules -- API calls are never intercepted
      },
      devOptions: {
        enabled: false, // keep the PWA plugin out of the way during `npm run dev`
      },
    }),
  ],
  server: {
    port: 3000,
    host: true,
  },
})
