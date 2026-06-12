# Kapruka AI Shopping Agent Frontend

This is the Vite + React frontend for the Kapruka AI Shopping Agent.

For full project setup, backend instructions, environment variables, and the checkout flow, see the root [README.md](../README.md).

## Commands

```bash
npm install
npm run dev
npm run build
npm run lint
```

The dev server runs at:

```text
http://localhost:5173
```

The frontend talks to the FastAPI backend through:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Do not expose backend secrets such as `OPENAI_API_KEY` in frontend environment variables.
