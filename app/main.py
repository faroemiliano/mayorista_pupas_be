from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers.categoriasRouter import router as categorias_router
from app.api.routers.marcasRouter import router as marcas_router
from app.api.routers.productosRouter import router as productos_router
from app.api.routers.subcategoriasRouter import router as subcategorias_router
from app.core.config import settings


app = FastAPI(
    title="Pupas Mayorista API",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(
    productos_router
)

app.include_router(
    categorias_router
)

app.include_router(
    subcategorias_router
)

app.include_router(
    marcas_router
)


@app.get("/")
def root():
    return {
        "mensaje": "Pupas Mayorista API funcionando"
    }


@app.get("/api/health")
def health():
    return {
        "status": "ok"
    }
