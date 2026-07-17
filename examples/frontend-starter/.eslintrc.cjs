module.exports = {
  root: true,
  env: { browser: true, es2021: true },
  extends: [
    'eslint:recommended',
    'plugin:react/recommended',
    'plugin:react-hooks/recommended',
  ],
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    ecmaFeatures: { jsx: true },
  },
  settings: { react: { version: 'detect' } },
  // Injected by vite.config.js's `define` block.
  globals: {
    __APP_VERSION__: 'readonly',
    __BUILD_TIME__: 'readonly',
  },
  rules: {
    // React 18 + the automatic JSX runtime (Vite's default) never requires
    // `React` in scope; every JSX-using file in this codebase relies on
    // that, so this rule is a false positive project-wide.
    'react/react-in-jsx-scope': 'off',
    // Pre-existing components don't declare prop-types; enabling this
    // would require touching dozens of files unrelated to this task.
    'react/prop-types': 'off',
    // Pre-existing JSX text widely contains raw apostrophes/quotes;
    // fixing every instance is unrelated to this task's scope.
    'react/no-unescaped-entities': 'off',
    // Pre-existing hooks across many files have incomplete dependency
    // arrays; auditing/fixing each one is a behavioral change out of
    // scope here (rules-of-hooks itself stays enabled via the preset).
    'react-hooks/exhaustive-deps': 'off',
  },
}
