import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default tseslint.config(
    {
        ignores: ['dist/**', 'node_modules/**']
    },
    js.configs.recommended,
    ...tseslint.configs.recommended,
    ...pluginVue.configs['flat/recommended'],
    {
        files: ['**/*.vue'],
        languageOptions: {
            parserOptions: {
                parser: tseslint.parser
            }
        }
    },
    {
        languageOptions: {
            ecmaVersion: 'latest',
            sourceType: 'module',
            globals: {
                ...globals.browser,
                ...globals.es2021
            }
        },
        rules: {
            'indent': ['error', 4],
            'vue/html-indent': ['error', 4],
            'vue/script-indent': ['error', 4, { baseIndent: 0 }],
            'vue/multi-word-component-names': 'off',
            'vue/no-v-html': 'off',
            '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }]
        }
    }
)
