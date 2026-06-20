from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

from src.services.chat_service import chat_with_model
from src.data.schemas.chat_schemas import ChatRequest, ChatResponse

load_dotenv()

app = FastAPI(title="RAG SaaS API", version="1.0.0")

router = APIRouter()

allowed_origins_str = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173,https://jitechonline.com,https://www.jitechonline.com"
)
ALLOWED_ORIGINS = [
    origin.strip().strip("'\"").rstrip("/")
    for origin in allowed_origins_str.split(",")
    if origin.strip()
]

print(f"CORS Origins: {ALLOWED_ORIGINS}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@router.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@router.get("/{tenant_id}/health")
async def tenant_health(tenant_id: str):
    from src.core.tenant_manager import tenant_exists
    if not tenant_exists(tenant_id):
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' not found")
    return {"tenant": tenant_id, "status": "ok"}


@router.post("/{tenant_id}/chat")
async def chat(tenant_id: str, req: ChatRequest):
    try:
        new_history, cleared_input = chat_with_model(
            tenant_id,
            req.history,
            req.message,
            req.chat_history
        )
        ai_string_response = new_history[-1][1] if new_history else ""
        return {
            "history":      new_history,
            "reply":        ai_string_response,
            "chat_history": new_history
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


app.include_router(router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.chat_api:app", host="0.0.0.0", port=8000, reload=True)