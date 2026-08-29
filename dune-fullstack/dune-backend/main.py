from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes import auth, chat, connections, documents, notifications, actions

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Intelligent AI Academic Assistant for Students & Researchers",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(connections.router)
app.include_router(documents.router)
app.include_router(notifications.router)
app.include_router(actions.router)

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "DUNE AI Assistant Backend",
        "version": "1.0.0",
        "endpoints": {
            "docs": "/docs",
            "auth": "/auth",
            "chat": "/chat",
            "connections": "/connections",
            "documents": "/documents",
            "notifications": "/notifications",
            "actions": "/actions"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
