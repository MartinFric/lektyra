// Martin's code style, enforced (skill code-style): no casts, no non-null `!`, no `any`, no useEffect.
import js from '@eslint/js';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import { defineConfig, globalIgnores } from 'eslint/config';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default defineConfig([
  globalIgnores(['dist', 'node_modules']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.strictTypeChecked,
      tseslint.configs.stylisticTypeChecked,
      reactHooks.configs.flat['recommended-latest'] ?? reactHooks.configs['recommended-latest'],
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    rules: {
      '@typescript-eslint/consistent-type-assertions': ['error', { assertionStyle: 'never' }],
      '@typescript-eslint/no-non-null-assertion': 'error',
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/consistent-type-imports': 'error',
      '@typescript-eslint/restrict-template-expressions': ['error', { allowNumber: true }],
      '@typescript-eslint/no-confusing-void-expression': ['error', { ignoreArrowShorthand: true }],
      'no-restricted-syntax': [
        'error',
        {
          selector: "Identifier[name=/^use(Layout|Insertion)?Effect$/]",
          message: 'No effects (code-style): use CSS, TanStack Query, a state initializer, a ref callback or the event handler.',
        },
        {
          selector: "MemberExpression[object.name='console'][property.name='log']",
          message: 'No console.log in the UI; errors go through AppError and toasts.',
        },
      ],
      'no-restricted-globals': ['error', { name: 'fetch', message: 'Use apiRequest/apiSend from @/platform/api.' }],
    },
  },
  {
    files: ['src/platform/api/client.ts'],
    rules: { 'no-restricted-globals': 'off' },
  },
]);
