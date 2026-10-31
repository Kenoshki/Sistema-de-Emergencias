"""
DWG EMS-05 REV A – Sistema Inteligente de Gestión de Emergencias
API principal (FastAPI).

Ejecutar desde la carpeta Backend:
    uvicorn main:app --reload --port 8000

Documentación interactiva: http://localhost:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import SessionLocal, init_db
from app.routers import analitica, auth, despacho, incidentes, publico, recursos, red, reportes, usuarios
from app.seed import sembrar_datos
from app.servicios.operaciones import ErrorOperacion


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    # Al arrancar: validar secretos, crear tablas y datos iniciales.
    settings.validar()
    init_db()
    db = SessionLocal()
    try:
        sembrar_datos(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="DWG EMS-05 API – Sistema de Emergencias",
    description="Coordinación de ambulancias, bomberos, policía y rescate con asignación automática por rutas más cortas.",
    version="2.0.0",
    lifespan=ciclo_de_vida,
    # La documentación interactiva solo se publica en depuración (o con ENABLE_DOCS=true).
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.ENABLE_DOCS else None,
)


@app.middleware("http")
async def cabeceras_de_seguridad(request: Request, call_next):
    respuesta = await call_next(request)
    respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
    respuesta.headers.setdefault("X-Frame-Options", "DENY")
    respuesta.headers.setdefault("Referrer-Policy", "no-referrer")
    respuesta.headers.setdefault("Cache-Control", "no-store")
    if not settings.DEBUG_MODE:
        respuesta.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return respuesta


# Comprime las respuestas grandes (catálogos, listados): importante con mala señal.
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,  # se usa token Bearer, no cookies
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ErrorOperacion)
async def manejar_error_operacion(_: Request, exc: ErrorOperacion):
    return JSONResponse(status_code=exc.codigo_http, content={"detail": exc.mensaje})


@app.exception_handler(RequestValidationError)
async def manejar_validacion(_: Request, exc: RequestValidationError):
    errores = []
    for e in exc.errors():
        campo = ".".join(str(p) for p in e.get("loc", []) if p not in ("body", "query", "path"))
        mensaje = str(e.get("msg", "")).replace("Value error, ", "")
        errores.append({"campo": campo, "mensaje": mensaje})
    resumen = "; ".join(f"{x['campo']}: {x['mensaje']}" if x["campo"] else x["mensaje"] for x in errores)
    return JSONResponse(status_code=422, content={"detail": resumen or "Datos inválidos.", "errors": errores})


for modulo in (publico, auth, incidentes, recursos, despacho, red, analitica, reportes, usuarios):
    app.include_router(modulo.router)


@app.get("/api/health", tags=["Sistema"])
def salud():
    return {"status": "ok", "auto_dispatch": settings.AUTO_DISPATCH}


@app.get("/", include_in_schema=False)
def raiz():
    return {"sistema": "DWG EMS-05 REV A", "docs": "/docs" if settings.ENABLE_DOCS else None}


if __name__ == "__main__":
    import os

    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=settings.DEBUG_MODE,
                proxy_headers=True, forwarded_allow_ips="*")
