# Tenant: jihad

## Setup
1. Add documents to `data/` folder
2. Run: `python train_local.py --tenant jihad`
3. API endpoint: `POST /api/jihad/chat`

## Config
- Behavior: `strict_rag`
- LLM: `llama3-8b-8192`
- Vector store: `jihad-notes`
## copy vectore store to cloud


scp -i "D:\AI\mycareer\AWS\LightsailDefaultKey-eu-west-3.pem" -r "D:\AI\AI engineer projects\chatwithmydata\vector_store\ai-roadmap-notes" ubuntu@51.45.26.105:/home/ubuntu/lighchat/vector_store/

to start both :
python -m notebooks.start_both_any    