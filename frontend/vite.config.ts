import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'

export default defineConfig({
    plugins: [vue(), tailwindcss()],
    base: '/v2t/',
    resolve: {
        alias: {
            '@': resolve(__dirname, 'src')
        }
    },
    build: {
        outDir: 'dist',
        emptyOutDir: true,
    },
    server: {
        proxy: {
            '/v2t/api': {
                target: 'http://localhost:8100',
                changeOrigin: true,
                rewrite: (path) => path.replace(/^\/v2t/, ''),
            },
        },
    },
})
