import js from '@eslint/js';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import prettierRecommended from 'eslint-plugin-prettier/recommended';

export default [
  { ignores: ['dist/', 'node_modules/', 'coverage/'] },
  js.configs.recommended,
  ...tsPlugin.configs['flat/recommended'],
  prettierRecommended,
  {
    files: ['**/*.ts'],
    languageOptions: { ecmaVersion: 2022, sourceType: 'module' },
    rules: {
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      '@typescript-eslint/explicit-function-return-type': 'off',
      '@typescript-eslint/no-explicit-any': 'warn',
      'prettier/prettier': 'error',
    },
  },
];
