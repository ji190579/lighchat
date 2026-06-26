from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

from src.services.chat_service import chat_with_model
from src.data.schemas.chat_schemas import ChatRequest, ChatResponse, ContactRequest

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


@router.post("/{tenant_id}/contact")
async def contact(tenant_id: str, req: ContactRequest):
    gmail_user = os.getenv("GMAIL_USER")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")

    if not gmail_user or not gmail_password:
        raise HTTPException(status_code=500, detail="Email service not configured")

    body = f"""
New Consultation Request — {tenant_id}

Name:        {req.name}
Email:       {req.email}
Role:        {req.role}
Experience:  {req.experience or "Not specified"}
Topic:       {req.topic}
Timeline:    {req.timeline or "Not specified"}

Challenge:
{req.challenge}
"""

    msg = MIMEMultipart()
    msg["From"] = gmail_user
    msg["To"] = gmail_user
    msg["Reply-To"] = req.email
    msg["Subject"] = f"[Consultation] {req.topic} — {req.name}"
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, gmail_user, msg.as_string())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

    return {"status": "sent"}


app.include_router(router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.chat_api:app", host="0.0.0.0", port=8000, reload=True)