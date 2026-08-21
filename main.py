import os
from time import perf_counter
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from loguru import logger

from api.dependencies import get_company_store, get_transcribe_store
from core.middleware import (
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    ProcessTimeMiddleware
)
from core.rate_limiter import limiter

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
#parth
from course_sync.course_sync_router import router as course_sync_router


from config import settings
from models.database import get_pool, close_pool

# Routers
from api.chat_router import router as chat_router
from api.login_router import router as login_router
from api.logout_router import router as logout_router
from api.quiz_router import router as quiz_router
from api.session_router import router as session_router
from api.forgot_password import router as forgot_password_router
from core.redis_client import redis_service
from api.company_router import router as company_router
from api.video_transcribe_router import router as transcribe_router

# ============================================================
# 1. Lifespan – DB init + FAISS rebuild + Scheduler
# ============================================================
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     """
#     FastAPI lifespan:
#     - Initialize PostgresSQL pool
#     - Rebuild FAISS index from tutor_content (with tqdm logging)
#     - Start daily 03:00 AM FAISS rebuild job
#     - Shutdown: stop scheduler + close DB pool
#     """
#     logger.info("🚀 Starting Marine Tutor AI (env={})", settings.app_env)

#     # -----------------------------
#     # DB init
#     # -----------------------------
#     logger.info("⏳ Initializing PostgresSQL connection pool...")
#     t0 = perf_counter()
#     await get_pool()
#     logger.info("✅ PostgresSQL pool ready in {:.2f}s", perf_counter() - t0)

#     # -----------------------------
#     # FAISS init + scheduler
#     # -----------------------------
#     from apscheduler.schedulers.asyncio import AsyncIOScheduler
#     from api.dependencies import get_faiss_store
#     from retrieval.refresh_chunks import rebuild_faiss_index, schedule_daily_rebuild

#     scheduler: AsyncIOScheduler | None = None

#     try:
#         logger.info("🚀 Lifespan: Initializing FAISS index...")

#         # ⚡ OPTIMIZATION: Use singleton FAISS store (shared with request dependencies)
#         store = get_faiss_store()

#         logger.info("⏳ Performing first FAISS rebuild (startup)...")
#         # await rebuild_faiss_index(store)
#         logger.success("🎉 Startup FAISS rebuild COMPLETE!")

#         # Daily 03:00 AM scheduler
#         scheduler = AsyncIOScheduler()
#         schedule_daily_rebuild(scheduler, store)
#         scheduler.start()
#         logger.info("⏰ Scheduler started — daily FAISS rebuild at 03:00 AM")

#         # Hand control to FastAPI
#         yield

#     finally:
#         logger.info("🛑 Lifespan shutdown starting...")
#         if scheduler is not None:
#             logger.info("🕒 Stopping scheduler...")
#             scheduler.shutdown(wait=False)

#         logger.info("🛑 Closing DB pool")
#         await close_pool()
#         logger.info("🐬 Marine Tutor AI shutdown complete")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Marine Tutor AI (env={})", settings.app_env)

    # -----------------------------
    # ✅ ADD REDIS HERE
    # -----------------------------
    logger.info("🔴 Connecting to Redis...")
    await redis_service.connect()

    # -----------------------------
    # DB init
    # -----------------------------
    logger.info("⏳ Initializing PostgresSQL connection pool...")
    t0 = perf_counter()
    await get_pool()
    logger.info("✅ PostgresSQL pool ready in {:.2f}s", perf_counter() - t0)

    # -----------------------------
    # FAISS init + scheduler
    # -----------------------------
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from api.dependencies import get_faiss_store
    from retrieval.refresh_chunks import rebuild_faiss_index, schedule_daily_rebuild

    scheduler: AsyncIOScheduler | None = None

    try:
        logger.info("🚀 Lifespan: Initializing FAISS index...")

        store = get_faiss_store()
        # company_store = get_company_store()
        # transcribe_store = get_transcribe_store()

        logger.info("⏳ Performing first FAISS rebuild (startup)...")
        logger.success("🎉 Startup FAISS rebuild COMPLETE!")

        scheduler = AsyncIOScheduler()
        schedule_daily_rebuild(scheduler, store)
        # schedule_daily_rebuild(scheduler, company_store)
        # schedule_daily_rebuild(scheduler, transcribe_store)
        scheduler.start()
        logger.info("⏰ Scheduler started — daily FAISS rebuild at 03:00 AM")

        yield

    finally:
        logger.info("🛑 Lifespan shutdown starting...")

        # -----------------------------
        # ✅ CLOSE REDIS HERE
        # -----------------------------
        logger.info("🔴 Closing Redis...")
        await redis_service.close()

        if scheduler is not None:
            logger.info("🕒 Stopping scheduler...")
            scheduler.shutdown(wait=False)

        logger.info("🛑 Closing DB pool")
        await close_pool()

        logger.info("🐬 Marine Tutor AI shutdown complete")


# ============================================================
# 2. App Instance
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(
    title="Marine Tutor AI",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)

if settings.debug_mode:
    app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(ProcessTimeMiddleware)


if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        #allow_origins=settings.all_cors_origins,
        allow_origins=[
        "https://dolphin.aduacademy.in",
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3003",
        "http://localhost:8000",
        "http://localhost:8001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3002",
        "http://127.0.0.1:3003",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8001",
        "http://74.48.194.139/dolphin/ui/",
        "http://74.48.194.139/dolphin-rb/ui",
        "http://192.168.29.227:3000/dolphin/ui",
        "http://localhost:5173",
        "http://localhost",
        "http://192.168.29.76:8000",
        "http://192.168.29.227:3002",  
        "http://192.168.29.227:3000",
        "http://192.168.29.227:3000/dolphin/ui",
        "http://192.168.29.227:3001/dolphin/ui",
        "http://192.168.29.227:3001/dolphin-rb/ui",
        "http://192.168.29.227:3001/",
        "http://203.88.119.83/dolphin_staging/ui/",
        "http://203.88.119.83/dolphin_staging/ui",
        "http://203.88.119.83",
        "http://192.168.0.9:3000",
        "http://10.136.70.164:3001",
        "http://192.168.0.39:3001",
        "http://192.168.0.39:3002",
        "http://192.168.0.26:3000",
        "http://192.168.0.16:3001",
        "http://192.168.0.21:3001",
        "http://192.168.0.31:3001"
    ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Rate limiter configuration
if settings.enable_rate_limiting:
    logger.info("Rate limiting")
    app.state.limiter = limiter
    app.add_middleware(RateLimitMiddleware)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ============================================================
# 3. UI Static Files
# ============================================================

storage_dir = os.path.join(BASE_DIR, "storage")
os.makedirs(storage_dir, exist_ok=True)
app.mount("/storage",
    StaticFiles(directory=storage_dir),
    name="storage"
)

if settings.serve_static_files:
    ui_dir = settings.ui_directory
    if os.path.exists(ui_dir):
        app.mount("/ui", StaticFiles(directory=ui_dir, html=True), name="ui")
        logger.info(f"📂 UI mounted at /ui (directory: {ui_dir})")
    else:
        logger.warning(f"⚠️ UI directory not found: {ui_dir}")

@app.get("/", include_in_schema=False)
async def root():
    if settings.serve_static_files and os.path.exists(settings.ui_directory):
        index_page = os.path.join(settings.ui_directory, "index.html")
        if os.path.exists(index_page):
            return FileResponse(index_page)
        login_page = os.path.join(settings.ui_directory, "login.html")
        if os.path.exists(login_page):
            return FileResponse(login_page)
    return {
        "service": "Marine Tutor AI",
        "environment": settings.app_env,
        "health": "/api/v1/health",
        "status": "operational"
    }


# ============================================================
# 4. Routers
# ============================================================
app.include_router(login_router)
app.include_router(logout_router)
app.include_router(chat_router)
app.include_router(quiz_router)
app.include_router(session_router)
app.include_router(forgot_password_router)
app.include_router(company_router)
app.include_router(transcribe_router)

# add parth
app.include_router(course_sync_router)

logger.info("🔗 Routers registered")


# ============================================================
# 5. Health Check
# ============================================================
@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}


@app.get("/api/v1/faiss/status")
async def faiss_status():
    """Check FAISS index health and status."""
    try:
        from api.dependencies import get_faiss_store  # uses singleton
        from datetime import datetime

        store = get_faiss_store()  # returns cached singleton

        if store is None:
            return {
                "status": "unhealthy",
                "error": "FAISS store not initialized",
                "index_size": 0,
                "last_rebuild": None
            }

        index_size = store.index.ntotal if (store and store.index is not None) else 0

        return {
            "status": "healthy" if index_size > 0 else "unhealthy",
            "index_size": index_size,
            "index_path": store.index_path,
            "checked_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"FAISS health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "index_size": 0
        } 
