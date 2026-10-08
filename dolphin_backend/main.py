import os
import io
import hashlib
from time import perf_counter
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
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
from api.user_router import router as user_router
from api.video_transcribe_router import router as transcribe_router
from api.course_router import router as course_router
from api.feedback_router import router as feedback_router

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
    # FAISS + BM25 init + scheduler
    # -----------------------------
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from api.dependencies import get_faiss_store, get_company_store, get_transcribe_store, get_bm25_store, get_approved_memory_service
    from retrieval.refresh_chunks import rebuild_faiss_index, schedule_daily_rebuild

    scheduler: AsyncIOScheduler | None = None

    try:
        logger.info("🚀 Lifespan: Pre-warming FAISS stores and BM25 index...")

        store = get_faiss_store()
        company_store = get_company_store()
        transcribe_store = get_transcribe_store()
        bm25_store = get_bm25_store()

        try:
            approved_mem_svc = await get_approved_memory_service()
            await approved_mem_svc.warmup_cache()
            logger.info("⚡ Approved memory cache pre-warmed")
        except Exception as app_mem_err:
            logger.warning(f"Approved memory warmup warning: {app_mem_err}")

        try:
            from services.dynamic_acronym_service import dynamic_acronym_service
            db_pool = await get_pool()
            await dynamic_acronym_service.harvest_course_acronyms(db_pool)
        except Exception as acr_err:
            logger.warning(f"Dynamic acronym harvest warning: {acr_err}")

        try:
            from services.dynamic_domain_service import dynamic_domain_service
            db_pool = await get_pool()
            await dynamic_domain_service.harvest_course_topics(db_pool)
        except Exception as dom_err:
            logger.warning(f"Dynamic domain harvest warning: {dom_err}")

        logger.success("🎉 Singletons pre-warmed and ready in memory!")

        scheduler = AsyncIOScheduler()
        schedule_daily_rebuild(scheduler, store)
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
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Rate limiter configuration
if settings.enable_rate_limiting:
    logger.info("Rate limiting")
    app.state.limiter = limiter
    app.add_middleware(RateLimitMiddleware)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

cors_origins = [
    "https://dolphin.aduacademy.in",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:3002",
    "http://localhost:3003",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8001",
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
]

if settings.all_cors_origins:
    for origin in settings.all_cors_origins:
        if origin not in cors_origins:
            cors_origins.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 3. Storage & UI Static Files
# ============================================================

storage_dir = os.path.join(BASE_DIR, "storage")
images_dir = os.path.join(storage_dir, "images")
pdf_images_dir = os.path.join(storage_dir, "pdf_images")
pdf_thumbnails_dir = os.path.join(storage_dir, "pdf_thumbnails")
os.makedirs(images_dir, exist_ok=True)
os.makedirs(pdf_images_dir, exist_ok=True)
os.makedirs(pdf_thumbnails_dir, exist_ok=True)


async def _fetch_and_cache_remote_image(image_id: str, target_path: str):
    """Fetch image on-demand from external course API and cache locally on disk."""
    api_key = settings.external_api_key
    if not api_key or api_key == "test-mode":
        api_key = "CDDDCD43BC944F2AA5DC501FB2CDE136"

    api_base = settings.external_api_base_url
    if not api_base or api_base == "test-mode":
        api_base = "https://ai.marinerskills.com/aidata"

    try:
        import base64
        import httpx
        url = f"{api_base.rstrip('/')}/ImageData"
        payload = {"Key": api_key, "ID": image_id}
        async with httpx.AsyncClient(verify=False, timeout=12.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("errorCode", 0) == 0 and data.get("value"):
                    image_data_str = data["value"]
                    if image_data_str.startswith("data:image/"):
                        _, encoded = image_data_str.split(",", 1)
                        image_bytes = base64.b64decode(encoded)
                    else:
                        image_bytes = base64.b64decode(image_data_str)

                    try:
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with open(target_path, "wb") as f:
                            f.write(image_bytes)
                        # Also ensure it is present in storage/images
                        img_images_dir = os.path.join(storage_dir, "images")
                        os.makedirs(img_images_dir, exist_ok=True)
                        filename = os.path.basename(target_path)
                        with open(os.path.join(img_images_dir, filename), "wb") as f2:
                            f2.write(image_bytes)
                    except Exception as cache_err:
                        logger.warning(f"Failed to cache image {image_id} to disk: {cache_err}")

                    return image_bytes
    except Exception as e:
        logger.warning(f"On-demand image fetch failed for {image_id}: {e}")
    return None


def _find_and_cache_from_image_json(image_id: str, target_path: str):
    """Look up image in storage/image_json and cache to disk if found."""
    try:
        import base64
        image_json_dir = os.path.join(storage_dir, "image_json")
        if not os.path.exists(image_json_dir):
            return None

        clean_id = str(image_id).strip().lower()
        for fname in os.listdir(image_json_dir):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(image_json_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            item_id = str(item.get("Id") or item.get("id") or "").strip().lower()
                            if item_id == clean_id:
                                b64_str = item.get("base64")
                                if b64_str and str(b64_str).strip() not in ("None", "null", ""):
                                    if b64_str.startswith("data:image/"):
                                        _, encoded = b64_str.split(",", 1)
                                        img_bytes = base64.b64decode(encoded)
                                    else:
                                        img_bytes = base64.b64decode(b64_str)
                                    
                                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                                    with open(target_path, "wb") as f_out:
                                        f_out.write(img_bytes)
                                    
                                    # Also save to storage/images
                                    images_out_dir = os.path.join(storage_dir, "images")
                                    os.makedirs(images_out_dir, exist_ok=True)
                                    with open(os.path.join(images_out_dir, os.path.basename(target_path)), "wb") as f_out2:
                                        f_out2.write(img_bytes)

                                    return img_bytes
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"Error checking image_json for {image_id}: {e}")
    return None


async def _fetch_and_extract_pdf_image(filename: str, target_path: str):
    """
    On-demand extract image from remote PDF if local pdf_images file is missing.
    Filename pattern: {pdf_id}_img_{page_num}_{obj_name}.png
    """
    try:
        import re, io, httpx, PyPDF2
        base_name, _ = os.path.splitext(filename)
        match = re.match(r'^([0-9a-fA-F-]+)_img_(\d+)_(.+)$', base_name)
        if not match:
            return None

        pdf_id, page_num_str, obj_name = match.groups()
        page_num = int(page_num_str)

        pdf_url = f"https://ai.marinerskills.com/pdf/{pdf_id}.pdf"
        async with httpx.AsyncClient(verify=False, timeout=20.0) as client:
            resp = await client.get(pdf_url)
            if resp.status_code != 200:
                logger.warning(f"Failed to download remote PDF {pdf_url}: status {resp.status_code}")
                return None
            pdf_bytes = resp.content

        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        if page_num >= len(reader.pages):
            return None

        page = reader.pages[page_num]
        if '/Resources' not in page or '/XObject' not in page['/Resources']:
            return None

        xObject = page['/Resources']['/XObject'].get_object()
        target_obj = None
        for k in [f"/{obj_name}", obj_name]:
            if k in xObject and xObject[k].get('/Subtype') == '/Image':
                target_obj = xObject[k]
                break

        if not target_obj:
            for k in xObject:
                if xObject[k].get('/Subtype') == '/Image':
                    target_obj = xObject[k]
                    break

        if target_obj:
            img_data = target_obj.get_data()
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "wb") as f:
                f.write(img_data)
            pdf_img_dir = os.path.join(storage_dir, "pdf_images")
            os.makedirs(pdf_img_dir, exist_ok=True)
            with open(os.path.join(pdf_img_dir, os.path.basename(target_path)), "wb") as f2:
                f2.write(img_data)
            return img_data

    except Exception as e:
        logger.warning(f"On-demand PDF image extraction failed for {filename}: {e}")

    return None


@app.get("/storage/{filepath:path}")
@app.get("/api/storage/{filepath:path}")
@app.get("/dolphin/storage/{filepath:path}")
@app.get("/dolphin/api/storage/{filepath:path}")
@app.get("/images/{filepath:path}")
@app.get("/pdf_images/{filepath:path}")
@app.get("/api/images/{filepath:path}")
@app.get("/dolphin/images/{filepath:path}")
async def serve_storage_file(filepath: str):
    """Serve storage files with automatic fallback and on-demand fetching for missing images."""
    normalized_path = filepath.strip("/\\")
    file_path = os.path.join(storage_dir, normalized_path)

    # 1. Direct hit on disk
    if os.path.isfile(file_path):
        return FileResponse(file_path)

    # 2. Check cross-folder or alternative extension (.jpeg vs .jpg vs .png)
    filename = os.path.basename(normalized_path)
    base_name, ext = os.path.splitext(filename)
    for folder in ["images", "pdf_images", ""]:
        for alt_ext in [ext, ".jpeg", ".jpg", ".png", ".webp", ""]:
            alt_path = os.path.join(storage_dir, folder, f"{base_name}{alt_ext}") if folder else os.path.join(storage_dir, f"{base_name}{alt_ext}")
            if os.path.isfile(alt_path):
                return FileResponse(alt_path)

    # 3. Check storage/image_json for base64
    save_path = file_path if ("images" in file_path or "pdf_images" in file_path) else os.path.join(storage_dir, "images", filename)
    json_image_bytes = _find_and_cache_from_image_json(base_name, save_path)
    if json_image_bytes:
        media_type = "image/png" if (ext.lower() == ".png" or json_image_bytes.startswith(b"\x89PNG")) else "image/jpeg"
        return Response(content=json_image_bytes, media_type=media_type)

    # 4. Check if it is a PDF image extracted from a remote PDF
    if "pdf_images" in normalized_path or "_img_" in filename:
        pdf_save_path = os.path.join(storage_dir, "pdf_images", filename)
        pdf_image_bytes = await _fetch_and_extract_pdf_image(filename, pdf_save_path)
        if pdf_image_bytes:
            media_type = "image/png" if pdf_image_bytes.startswith(b"\x89PNG") else "image/jpeg"
            return Response(content=pdf_image_bytes, media_type=media_type)

    # 5. On-demand fetch from external course API
    image_bytes = await _fetch_and_cache_remote_image(base_name, save_path)
    if image_bytes:
        media_type = "image/png" if (ext.lower() == ".png" or image_bytes.startswith(b"\x89PNG")) else "image/jpeg"
        return Response(content=image_bytes, media_type=media_type)

    raise HTTPException(status_code=404, detail="File not found")


@app.get("/api/pdf_thumbnail")
@app.get("/pdf_thumbnail")
@app.get("/dolphin/api/pdf_thumbnail")
@app.get("/dolphin/pdf_thumbnail")
async def get_pdf_thumbnail(url: str = ""):
    """Generate and return a thumbnail of the first page of a PDF document."""
    if not url or not url.strip():
        raise HTTPException(status_code=400, detail="Missing url parameter")

    raw_url = url.strip()

    # 1. Check cache on disk
    url_hash = hashlib.md5(raw_url.encode("utf-8")).hexdigest()
    cache_path = os.path.join(pdf_thumbnails_dir, f"{url_hash}.png")
    if os.path.isfile(cache_path):
        return FileResponse(
            cache_path,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=604800"}
        )

    # 2. Retrieve PDF bytes
    pdf_bytes = None

    # Check local filesystem first
    if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
        clean_p = raw_url.lstrip("/\\")
        candidates = [
            raw_url,
            os.path.join(BASE_DIR, clean_p),
            os.path.join(storage_dir, clean_p),
            os.path.join(storage_dir, "pdf", clean_p),
        ]
        for cand in candidates:
            if os.path.isfile(cand):
                try:
                    with open(cand, "rb") as f:
                        pdf_bytes = f.read()
                    break
                except Exception:
                    pass

    # Check localhost / internal storage URLs
    if not pdf_bytes and ("localhost" in raw_url or "127.0.0.1" in raw_url):
        import urllib.parse
        parsed = urllib.parse.urlparse(raw_url)
        clean_p = parsed.path.lstrip("/\\")
        candidates = [
            os.path.join(BASE_DIR, clean_p),
            os.path.join(storage_dir, clean_p),
        ]
        for cand in candidates:
            if os.path.isfile(cand):
                try:
                    with open(cand, "rb") as f:
                        pdf_bytes = f.read()
                    break
                except Exception:
                    pass

    # Remote HTTP/HTTPS fetch
    if not pdf_bytes and (raw_url.startswith("http://") or raw_url.startswith("https://")):
        try:
            import httpx
            async with httpx.AsyncClient(verify=False, timeout=20.0) as client:
                resp = await client.get(raw_url)
                if resp.status_code == 200:
                    pdf_bytes = resp.content
                else:
                    logger.warning(f"Failed to fetch remote PDF {raw_url}: status {resp.status_code}")
        except Exception as e:
            logger.warning(f"Error fetching remote PDF {raw_url}: {e}")

    # Fallback: if raw_url is just a UUID or filename (e.g. "72bb5faa-...")
    if not pdf_bytes and not raw_url.startswith("http"):
        uuid_url = f"https://ai.marinerskills.com/pdf/{raw_url}"
        if not uuid_url.endswith(".pdf"):
            uuid_url += ".pdf"
        try:
            import httpx
            async with httpx.AsyncClient(verify=False, timeout=20.0) as client:
                resp = await client.get(uuid_url)
                if resp.status_code == 200:
                    pdf_bytes = resp.content
        except Exception:
            pass

    if not pdf_bytes:
        raise HTTPException(status_code=404, detail="PDF document could not be found or downloaded")

    # 3. Render first page (page 0)
    img_bytes = None
    try:
        import pymupdf
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        if len(doc) > 0:
            try:
                from services.pdf_service import pdf_service
                extracted_title = pdf_service.extract_title_from_pymupdf(doc)
                if extracted_title:
                    pdf_service.set_title(raw_url, extracted_title)
            except Exception as e:
                logger.debug(f"Title extraction during thumbnail failed: {e}")

            page = doc.load_page(0)
            page_width = page.rect.width
            scale = 320.0 / page_width if page_width > 0 else 1.0
            matrix = pymupdf.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=matrix)
            img_bytes = pix.tobytes("png")
            doc.close()
    except Exception as mupdf_err:
        logger.warning(f"PyMuPDF thumbnail render failed for {raw_url}: {mupdf_err}")

    if not img_bytes:
        try:
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(pdf_bytes)
            if len(pdf) > 0:
                page = pdf[0]
                pil_img = page.render(scale=1.5).to_pil()
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                img_bytes = buf.getvalue()
        except Exception as pdfium_err:
            logger.warning(f"pypdfium2 thumbnail render failed for {raw_url}: {pdfium_err}")

    if not img_bytes:
        raise HTTPException(status_code=500, detail="Could not render PDF first page")

    # 4. Cache thumbnail to disk
    try:
        with open(cache_path, "wb") as f:
            f.write(img_bytes)
    except Exception as save_err:
        logger.warning(f"Failed to cache PDF thumbnail: {save_err}")

    return Response(
        content=img_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=604800"}
    )




if settings.serve_static_files:
    ui_dir = settings.ui_directory
    if os.path.exists(ui_dir):
        app.mount("/ui", StaticFiles(directory=ui_dir), name="ui")
        logger.info(f"📂 UI mounted at /ui (directory: {ui_dir})")
    else:
        logger.warning(f"⚠️ UI directory not found: {ui_dir}")

@app.get("/", include_in_schema=False)
async def root():
    if settings.serve_static_files and os.path.exists(settings.ui_directory):
        login_page = os.path.join(settings.ui_directory, "login.html")
        if os.path.exists(login_page):
            return FileResponse(login_page)
    return {
        "service": "Marine Tutor AI",
        "environment": settings.app_env,
        "health": "/api/v1/health",
        "status": "operational"
    }

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error processing {request.method} {request.url.path}: {exc}")
    origin = request.headers.get("origin") or "http://localhost:3000"
    headers = {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
    }
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "error": str(exc)},
        headers=headers,
    )


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
app.include_router(user_router)
app.include_router(transcribe_router)
app.include_router(course_router)
app.include_router(feedback_router)

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

        index_size = len(store.ids) if hasattr(store, 'ids') and store.ids else 0

        return {
            "status": "healthy" if index_size > 0 else "unhealthy",
            "index_size": index_size,
            "index_path": settings.faiss_index_path,
            "checked_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"FAISS health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "index_size": 0
        } 
