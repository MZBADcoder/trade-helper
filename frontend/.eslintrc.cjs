module.exports = {
  root: true,
  env: {
    browser: true,
    es2022: true
  },
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
    ecmaFeatures: {
      jsx: true
    }
  },
  plugins: ["import"],
  settings: {
    "import/resolver": {
      typescript: {
        project: "./tsconfig.json"
      }
    }
  },
  ignorePatterns: ["dist", "node_modules"],
  rules: {
    "import/no-restricted-paths": [
      "error",
      {
        zones: [
          {
            target: "./src/shared",
            from: ["./src/entities", "./src/features", "./src/widgets", "./src/pages", "./src/app"]
          },
          {
            target: "./src/entities",
            from: ["./src/features", "./src/widgets", "./src/pages", "./src/app"]
          },
          {
            target: "./src/features",
            from: ["./src/widgets", "./src/pages", "./src/app"]
          },
          {
            target: "./src/widgets",
            from: ["./src/pages", "./src/app"]
          },
          {
            target: "./src/pages",
            from: ["./src/app"]
          }
        ]
      }
    ]
  }
};
