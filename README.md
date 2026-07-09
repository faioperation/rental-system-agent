# Aria — AI Real Estate Agent

A complete AI-powered real estate customer service and lead generation system. It features a ChatGPT/Claude-style customer chat interface and a protected admin dashboard for managing leads, properties, and a knowledge base.

## Features & Capabilities

### Chatbot (Customer Facing - `/`)
- **ChatGPT-Style Interface**: Full-page chat layout with left sidebar for conversation history and right sidebar for shared context/files.
- **Session Memory**: Remembers past conversations. Chat sessions are stored and can be revisited or deleted.
- **File Uploads**: Customers can upload documents (`.txt`, `.md`, `.csv`). The bot will read and use these files as context for its answers.
- **Property Recommendations**: The agent searches the embedded property database to find and recommend properties based on user queries (location, budget, bedrooms, etc.).
- **Knowledge Base (RAG)**: The agent can answer general questions using documents (FAQs, financing policies, neighborhood guides) stored in the Knowledge Base.
- **Multilingual Support**: Supports English, Bengali, French, Portuguese, Arabic, and more.
- **Rate Limiting**: Handles API limits gracefully by showing a rate-limit message with an animated typing bubble.

### Admin Dashboard (`/admin`)
- **Secure Login**: Access the admin panel using the credentials:
  - **Email:** `admin@fireai.com`
  - **Password:** `1234`
  *(Once logged in, the session is saved in the browser until you click Log Out).*
- **Leads Management**: View and filter captured leads (tickets) by status and priority.
- **Property Management**: Add individual property listings or bulk import them from a CSV file. Each listing is automatically vectorized for AI search.
- **Knowledge Base**: Add non-property content (policies, FAQs) for the AI to use as context.
- **Viewings**: View scheduled viewings and download `.ics` calendar invites.

---

## 1. Setup Instructions

### Prerequisites
- Python 3.10+
- A [Supabase](https://supabase.com) account (Free tier is fine)
- A [Groq](https://console.groq.com/keys) API Key

### Database Setup (Supabase)
1. Create a new Supabase project.
2. Go to **SQL Editor → New query**, paste the contents of `database/schema.sql`, and run it. This creates tables for `customers`, `conversations`, `messages`, `properties`, `kb_documents`, `tickets`, `viewing_slots`, and `viewings`, along with pgvector matching functions.
3. Go to **Project Settings → API Keys** and copy the `service_role` key (JWT format, `eyJ...`). This is required for write access from the backend.

### Application Setup
1. Clone the repository and navigate to the project directory:
   ```bash
   cd realestate-agent
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate        # Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and set:
   - `GROQ_API_KEY`
   - `GROQ_MODEL`
   - `GROQ_FALLBACK_MODEL`
   - `SUPABASE_URL`
   - `SUPABASE_KEY` (use the `service_role` key)

---
## 3. Usage Guide

### Managing Properties
Use the **Properties** tab in the admin dashboard to add listings (title, city, price, bedrooms, features, description). Each listing is embedded automatically and becomes searchable via RAG — the chat agent will only ever recommend properties that exist in this list.

### Generating Viewing Slots
On the **Properties** tab, click **"Generate slots"** next to any listing. This creates hourly slots for the next 7 days in `viewing_slots`. 

### Managing the Knowledge Base
Use the **Knowledge Base** tab in the admin dashboard to add non-property content like "Financing FAQ", "Pet Policies", or "Neighborhood Guides". The AI will search this content to answer general questions.

### Testing File Uploads
In the customer chat (`/`), click the paperclip icon in the input box to upload a `.txt` or `.csv` file. Send a message, and the AI will reference the uploaded file.

---

## 4. Architecture

| Component | Technology |
|---|---|
| **Backend** | FastAPI (Python) |
| **Database** | Supabase (PostgreSQL with `pgvector`) |
| **Embeddings** | `fastembed` (Runs locally via ONNX, no external API needed) |
| **LLM Inference** | Groq (Fast Llama/Mixtral inference with chat streaming) |
| **Frontend** | Vanilla HTML/CSS/JS (SSE for streaming) |

## 5. Deployment
For production deployment (e.g., Render, Railway, Fly.io):
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Provide all required environment variables in your hosting provider's dashboard.
