from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers.carritoRouter import router as carrito_router
from app.api.routers.catalogoRouter import router as catalogo_router
from app.api.routers.categoriasRouter import router as categorias_router
from app.api.routers.marcasRouter import router as marcas_router
from app.api.routers.pedidosRouter import admin_router as pedidos_admin_router
from app.api.routers.adminProductosRouter import router as admin_productos_router
from app.api.routers.authRouter import router as auth_router
from app.api.routers.adminUsuariosRouter import router as admin_usuarios_router
from app.api.routers.adminClientesDuxRouter import router as admin_clientes_dux_router
from app.api.routers.adminConfiguracionRouter import router as admin_configuracion_router
from app.api.routers.pedidosRouter import router as pedidos_router
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
app.include_router(auth_router)
app.include_router(admin_usuarios_router)
app.include_router(admin_clientes_dux_router)
app.include_router(admin_configuracion_router)

app.include_router(
    categorias_router
)

app.include_router(
    subcategorias_router
)

app.include_router(
    marcas_router
)

app.include_router(
    catalogo_router
)

app.include_router(
    carrito_router
)

app.include_router(
    pedidos_router
)

app.include_router(
    pedidos_admin_router
)
app.include_router(
    admin_productos_router
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
