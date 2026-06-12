# Kapruka AI Shopping Agent

A React + FastAPI shopping assistant for Kapruka-style product discovery, cart building, and agent-assisted guest checkout.

The app lets customers chat naturally in English, Sinhala, or Tanglish, receive visual product recommendations, add items to a cart, and submit checkout details only when they are ready to continue.

## Features

- Conversational AI shopping assistant
- Product recommendation cards with image, name, price, reason, and Kapruka link
- Multi-item cart with approximate total
- Checkout details collected only at checkout
- Recipient, sender, delivery, order type, currency, and gift message form
- Existing chat API flow used for checkout continuation
- Backend-only OpenAI integration
- Kapruka MCP tool integration through the FastAPI backend

## Project Structure

```text
kapruka-proj/
├── backend/
│   └── app.py
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   ├── index.css
│   │   └── components/
│   │       └── CheckoutForm.jsx
│   ├── package.json
│   └── vite.config.js
├── requirements.txt
└── README.md
```

## Requirements

- Node.js 20 or newer
- npm
- Python 3.10 or newer
- An OpenAI API key

## Environment Variables

Create a `.env` file in the project root for backend secrets:

```bash
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
```

Optional frontend environment variable:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Keep `OPENAI_API_KEY` on the backend only. Do not expose it in Vite or any frontend code.

## Backend Setup

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install fastapi uvicorn pydantic
uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

The backend should be available at:

```text
http://127.0.0.1:8000
```

Main API endpoint:

```text
POST /api/chat
```

## Frontend Setup

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend should be available at:

```text
http://localhost:5173
```

## Build

To create a production frontend build:

```bash
cd frontend
npm run build
```

To preview the production build locally:

```bash
npm run preview
```

## Checkout Flow

1. The customer chats with the shopping assistant.
2. The assistant recommends products visually.
3. The customer adds products to the cart without entering personal details.
4. The customer clicks **Checkout with agent**.
5. The checkout form collects recipient, sender, delivery, date, order type, currency, and optional gift message details.
6. On submit, the frontend converts the form and cart into one clear checkout message.
7. The message is sent to the backend through the existing `/api/chat` flow.
8. The assistant checks delivery availability first, then helps continue to Kapruka guest checkout.

## Development Notes

- Frontend API calls should use `VITE_API_BASE_URL` and `/api/chat`.
- The frontend must not connect directly to OpenAI or MCP services.
- Backend conversation state is currently stored in memory by `session_id`.
- CORS is configured for Vite local development on `localhost:5173` and `127.0.0.1:5173`.
- The Kapruka MCP endpoint is configured in `backend/app.py`.

## Useful Commands

```bash
# Backend
uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000

# Frontend dev server
cd frontend
npm run dev

# Frontend build
cd frontend
npm run build

# Frontend lint
cd frontend
npm run lint
```
