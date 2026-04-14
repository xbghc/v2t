import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import Icons from 'unplugin-icons/vite'
import { resolve } from 'path'

function fontPreload(): Plugin {
    let base = '/'
    return {
        name: 'font-preload',
        configResolved(config) {
            base = config.base
        },
        transformIndexHtml: {
            order: 'post',
            handler(_html, ctx) {
                if (!ctx.bundle) return
                const latinFont = Object.keys(ctx.bundle).find(key =>
                    /inter-latin-wght-normal.*\.woff2$/.test(key)
                )
                if (!latinFont) return
                return [{
                    tag: 'link',
                    attrs: {
                        rel: 'preload',
                        href: base + latinFont,
                        as: 'font',
                        type: 'font/woff2',
                        crossorigin: '',
                    },
                    injectTo: 'head',
                }]
            },
        },
    }
}

export default defineConfig({
    plugins: [vue(), tailwindcss(), Icons({ compiler: 'vue3' }), fontPreload()],
    base: '/',
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
            '/api': {
                target: 'http://localhost:8103',
                changeOrigin: true,
            },
        },
    },
})
