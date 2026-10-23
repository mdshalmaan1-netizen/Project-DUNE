from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes import auth, chat, connections, documents, notifications, actions, mcp

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
app.include_router(mcp.router)


import os
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Paths to frontend files and assets
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HTML_PATH = os.path.join(BASE_DIR, "dune.html")
ASSETS_PATH = os.path.join(BASE_DIR, "assets")

if os.path.exists(ASSETS_PATH):
    app.mount("/assets", StaticFiles(directory=ASSETS_PATH), name="assets")

@app.api_route("/", methods=["GET", "HEAD"])
async def serve_index():
    if os.path.exists(HTML_PATH):
        return FileResponse(HTML_PATH, media_type="text/html")
    return {
        "status": "online",
        "service": "DUNE AI Assistant Backend",
        "version": "1.0.0"
    }

@app.api_route("/app", methods=["GET", "HEAD"])
async def serve_app():
    if os.path.exists(HTML_PATH):
        return FileResponse(HTML_PATH, media_type="text/html")
    return {"error": "dune.html not found"}

@app.api_route("/api", methods=["GET", "HEAD"])
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
            "actions": "/actions",
            "mcp": "/mcp",
            "db_status": "/api/db-status"
        }
    }

@app.get("/api/db-status")
async def get_db_status():
    from app.db.mongo import check_mongo_status
    return await check_mongo_status()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
