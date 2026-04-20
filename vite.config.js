import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const isElectron = mode === 'electron'
  const isAndroid  = mode === 'android'

  return {
    plugins: [react()],

    // Electron & Android: use relative paths, no hash routing
    base: (isElectron || isAndroid) ? './' : '/',

    define: {
      __APP_MODE__:    JSON.stringify(mode || 'web'),
      __IS_ELECTRON__: isElectron,
      __IS_ANDROID__:  isAndroid,
    },

    server: {
      host: '0.0.0.0',
      port: 3000,
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api/, ''),
        },
      },
    },

    build: {
      outDir:    'dist',
      sourcemap: false,
      rollupOptions: {
        output: {
          // Smaller chunks for Android WebView
          manualChunks: isAndroid ? undefined : {
            vendor: ['react', 'react-dom'],
          },
        },
      },
    },
  }
})
