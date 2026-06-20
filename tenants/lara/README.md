# Tenant: lara

## Setup
1. Add AI engineering documents to `data/` folder
2. Run: `python train_local.py --tenant lara`
3. API endpoint: `POST /api/lara/chat`
4. Health check: `GET /api/lara/health`

## Config
- Behavior: `balanced_rag`
- LLM: `llama-3.3-70b-versatile`
- Vector store: `lara-docs`
- Documents: AI Engineer learning materials
