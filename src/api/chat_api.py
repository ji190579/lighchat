from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from dotenv import load_dotenv

from src.services.chat_service import chat_with_model, retriever
from src.data.schemas.chat_schemas import ChatRequest, ChatResponse

load_dotenv()

app = FastAPI()
router = APIRouter()

os.makedirs("jihad", exist_ok=True)
app.mount("/jihad", StaticFiles(directory="jihad"), name="jihad")

allowed_origins_str = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173,https://jitechonline.com,https://www.jitechonline.com"
)
ALLOWED_ORIGINS = [
    origin.strip().strip("'\"").rstrip("/")
    for origin in allowed_origins_str.split(",")
    if origin.strip()
]

print(f"🌍 CORS Allowed Origins loaded: {ALLOWED_ORIGINS}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@router.post("/chat")
async def chat(req: ChatRequest):
    new_history, cleared_input = chat_with_model(
        req.history,
        retriever,
        req.message,
        req.chat_history
    )

    ai_string_response = new_history[-1][1] if new_history else ""

    return {
        "history": new_history,
        "reply": ai_string_response,
        "chat_history": new_history
    }


app.include_router(router, prefix="/api")


def kill_port(port: int):
    """Finds and forcefully kills any Windows process using the specified port."""
    try:
        output = subprocess.check_output(f'netstat -ano | findstr :{port}', shell=True).decode()
        for line in output.strip().split('\n'):
            parts = line.split()
            if len(parts) > 4 and parts[-1] != '0':
                pid = parts[-1]
                print(f"🧹 Clearing lingering process on port {port} (PID: {pid})...")
                result = os.system(f'taskkill /F /PID {pid} >nul 2>&1')
                if result != 0:
                    print(f"⚠️ Could not kill PID {pid}. You may need Administrator rights, or the port is reserved.")
    except Exception:
        pass


if __name__ == "__main__":
    import uvicorn
    PORT = 8000
    uvicorn.run("src.api.chat_api:app", host="0.0.0.0", port=PORT, reload=True)
