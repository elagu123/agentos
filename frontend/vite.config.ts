import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { compression } from 'vite-plugin-compression2';
import { visualizer } from 'rollup-plugin-visualizer';
import path from 'path';

// Bundle analyzer for development
const bundleAnalyzer = process.env.ANALYZE_BUNDLE === 'true';

export default defineConfig({
  plugins: [
    react({
      // Enable React Fast Refresh
      fastRefresh: true,
      // Optimize React imports
      babel: {
        plugins: [
          // Remove console.log in production
          process.env.NODE_ENV === 'production' && [
            'babel-plugin-transform-remove-console',
            { exclude: ['error', 'warn'] }
          ]
        ].filter(Boolean)
      }
    }),

    // Gzip compression
    compression({
      algorithm: 'gzip',
      exclude: [/\.(br)$/, /\.(gz)$/],
      threshold: 1024, // Only compress files larger than 1KB
      compressionOptions: { level: 9 }
    }),

    // Brotli compression
    compression({
      algorithm: 'brotliCompress',
      exclude: [/\.(br)$/, /\.(gz)$/],
      threshold: 1024,
      compressionOptions: { level: 11 }
    }),

    // Bundle analyzer (only when requested)
    bundleAnalyzer && visualizer({
      filename: 'dist/bundle-analysis.html',
      open: true,
      gzipSize: true,
      brotliSize: true,
      template: 'treemap' // sunburst, treemap, network
    })
  ].filter(Boolean),

  // Path resolution
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@/components': path.resolve(__dirname, './src/components'),
      '@/hooks': path.resolve(__dirname, './src/hooks'),
      '@/utils': path.resolve(__dirname, './src/utils'),
      '@/types': path.resolve(__dirname, './src/types'),
      '@/pages': path.resolve(__dirname, './src/pages')
    }
  },

  // Build optimization
  build: {
    // Target modern browsers for smaller bundles
    target: 'es2020',

    // Rollup options for advanced optimization
    rollupOptions: {
      output: {
        // Manual chunk splitting for optimal caching
        manualChunks: {
          // Vendor chunks (libraries that rarely change)
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'ui-vendor': [
            '@tanstack/react-query',
            '@tanstack/react-virtual',
            '@headlessui/react',
            'lucide-react'
          ],
          'flow-vendor': ['@xyflow/react'],
          'clerk-vendor': ['@clerk/clerk-react'],
          'chart-vendor': ['recharts'],
          'utils': [
            'axios',
            'clsx',
            'class-variance-authority',
            'zod',
            'react-hook-form',
            '@hookform/resolvers'
          ],

          // Application chunks
          'dashboard': [
            './src/pages/dashboard/index.tsx',
            './src/components/dashboard/MetricsCard.tsx',
            './src/components/dashboard/QuickActions.tsx',
            './src/components/dashboard/RecentActivity.tsx'
          ],
          'chat': [
            './src/pages/dashboard/chat.tsx',
            './src/components/chat/ChatInterface.tsx',
            './src/components/chat/MessageList.tsx',
            './src/components/chat/MessageInput.tsx'
          ],
          'workflow-builder': [
            './src/components/workflow-builder/WorkflowBuilder.tsx'
          ],
          'marketplace': [
            './src/components/marketplace/MarketplaceDashboard.tsx',
            './src/components/marketplace/TemplateCard.tsx',
            './src/components/marketplace/AnalyticsDashboard.tsx'
          ]
        },

        // Optimize chunk names for caching
        chunkFileNames: (chunkInfo) => {
          const facadeModuleId = chunkInfo.facadeModuleId
            ? chunkInfo.facadeModuleId.split('/').pop()?.replace(/\.\w+$/, '')
            : 'chunk';

          return `assets/js/[name]-[hash].js`;
        },

        // Optimize asset names
        assetFileNames: (assetInfo) => {
          const extType = assetInfo.name?.split('.').at(1);
          if (/png|jpe?g|svg|gif|tiff|bmp|ico/i.test(extType ?? '')) {
            return `assets/images/[name]-[hash][extname]`;
          }
          if (/woff2?|eot|ttf|otf/i.test(extType ?? '')) {
            return `assets/fonts/[name]-[hash][extname]`;
          }
          return `assets/[ext]/[name]-[hash][extname]`;
        }
      },

      // External dependencies that should not be bundled
      external: []
    },

    // Bundle size limits
    chunkSizeWarningLimit: 500, // Warn if chunk is larger than 500KB

    // Source maps for production debugging
    sourcemap: process.env.NODE_ENV === 'production' ? 'hidden' : true,

    // Minification
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: process.env.NODE_ENV === 'production',
        drop_debugger: true,
        pure_funcs: process.env.NODE_ENV === 'production' ? ['console.log'] : []
      },
      mangle: {
        safari10: true
      },
      format: {
        safari10: true,
        comments: false
      }
    },

    // CSS optimization
    cssMinify: true,

    // Asset inlining threshold
    assetsInlineLimit: 4096 // Inline assets smaller than 4KB
  },

  // Dependency optimization
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      '@tanstack/react-query',
      '@tanstack/react-virtual',
      'axios',
      'react-router-dom',
      '@clerk/clerk-react',
      'lucide-react'
    ],
    exclude: []
  },

  // Server configuration for development
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      }
    },
    // Enable HTTPS for development if needed
    // https: {
    //   key: './localhost-key.pem',
    //   cert: './localhost.pem'
    // }
  },

  // Preview configuration (for production preview)
  preview: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      }
    }
  },

  // Environment variables
  define: {
    __DEV__: process.env.NODE_ENV === 'development',
    __PROD__: process.env.NODE_ENV === 'production'
  },

  // CSS configuration
  css: {
    // PostCSS configuration
    postcss: './postcss.config.js',

    // CSS modules (if needed)
    modules: {
      localsConvention: 'camelCase'
    },

    // Preprocessor options
    preprocessorOptions: {
      scss: {
        additionalData: `@import "@/styles/variables.scss";`
      }
    }
  },

  // Worker configuration
  worker: {
    format: 'es'
  }
});