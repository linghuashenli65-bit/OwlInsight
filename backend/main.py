"""FinanceBot FastAPI 后端入口.

启动方式:
    python -m backend.main
    # 或
    uvicorn backend.main:app --reload --port 8000
"""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# 必须在任何第三方库导入之前设置
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ.setdefault("NO_PROXY", "eastmoney.com,push2his.eastmoney.com,emot.dfcfw.com")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import chat, data, ingest, settings as settings_router
from backend.routers.alerter import router as alerter_router
from backend.alerter import alert_engine
from backend.config import settings
from backend.database import init_db
from backend.websocket_handler import ws_prices


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：初始化数据库 + 启动告警调度引擎."""
    await init_db()
    # 初始化 SQLite 连接
    from backend.memory.store import memory_store
    memory_store.connect()
    # 初始化 Milvus 连接
    from backend.rag.vector_store import vector_store
    vector_store.connect()
    # 启动告警调度引擎
    alert_engine.start()
    yield
    alert_engine.stop()


app = FastAPI(title="枭研 API", version="1.0.0", lifespan=lifespan)

# CORS — 允许前端开发服务器访问（任意端口）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(data.router, prefix="/api/data", tags=["data"])
app.include_router(ingest.router, prefix="/api/ingest", tags=["ingest"])
app.include_router(settings_router.router, prefix="/api", tags=["settings"])
app.include_router(alerter_router)


@app.get("/api/health")
def health():
    return {"status": "ok", "name": "枭研", "version": "1.0.0"}


@app.websocket("/ws/prices")
async def websocket_prices(websocket: WebSocket):
    await ws_prices(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=False,
    )
