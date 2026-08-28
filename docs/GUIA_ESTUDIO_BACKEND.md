# Guía de estudio del backend mayorista

## 1. Objetivo del proyecto

Este proyecto es una API construida con FastAPI para una tienda mayorista.
El catálogo se obtiene desde Dux ERP y se guarda en una base de datos local
PostgreSQL.

La página no consulta Dux cada vez que un visitante abre el catálogo. El flujo
es el siguiente:

```text
Dux ERP
   ↓ sincronización
PostgreSQL local
   ↓ consultas SQLAlchemy
API FastAPI
   ↓ respuestas JSON
Frontend de la tienda
```

Esta separación permite que la tienda responda rápidamente y siga funcionando
sin depender de una consulta directa a Dux por cada visitante.

## 2. Tecnologías utilizadas

- Python 3.12.
- FastAPI para construir la API HTTP.
- SQLAlchemy 2 para consultar y modificar la base de datos.
- PostgreSQL como base de datos principal.
- Alembic para crear y modificar la estructura de la base de datos.
- Pydantic para validar variables de entorno y respuestas de la API.
- HTTPX para comunicarse con Dux.
- Pytest para las pruebas automáticas.
- python-slugify para crear slugs aptos para URLs.

## 3. Organización de carpetas

```text
app/
├── api/routers/       Rutas HTTP de FastAPI
├── core/              Configuración y variables de entorno
├── database/          Conexión y base de SQLAlchemy
├── integrations/dux/  Cliente HTTP para Dux
├── models/            Tablas y relaciones de la base de datos
├── repositories/      Consultas a la base de datos
├── schemas/           Formato público de las respuestas JSON
├── scripts/           Comandos manuales
└── services/          Reglas de negocio y sincronización

alembic/               Migraciones de la base de datos
tests/                 Pruebas automáticas
docs/                  Documentación para estudiar el proyecto
```

## 4. Configuración del proyecto

El archivo principal de configuración es `app/core/config.py`.

Las variables privadas se cargan desde `.env`. Este archivo está ignorado por
Git para evitar publicar contraseñas y el token de Dux.

`.env.example` sirve como plantilla:

```env
DATABASE_URL=postgresql+psycopg://usuario:password@localhost:5432/mayorista
DUX_API_TOKEN=reemplazar_con_token_dux
DUX_ID_EMPRESA=1
DUX_LISTA_PRECIO_MAYORISTA_ID=4710
DUX_LISTA_PRECIO_24_ID=43406
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

No se deben escribir tokens o contraseñas reales dentro de `.env.example`.

## 5. Conexión a PostgreSQL

`app/database/session.py` crea:

- `engine`: conexión general de SQLAlchemy.
- `SessionLocal`: fábrica de sesiones.
- `get_db()`: dependencia utilizada por FastAPI.

Un router recibe una sesión de esta forma:

```python
def listar_productos(
    db: Session = Depends(get_db),
):
    ...
```

FastAPI abre la sesión antes de ejecutar el endpoint y la cierra al finalizar.

## 6. Modelos de la base de datos

Los modelos representan tablas de PostgreSQL.

### Categoria

Archivo: `app/models/categoria.py`.

Guarda el rubro recibido desde Dux:

- `id`: identificador interno de la página.
- `dux_id`: identificador del rubro en Dux.
- `nombre`.
- `slug`.
- `descripcion`.
- `activo`.
- Fechas de creación y actualización.

Una categoría tiene muchas subcategorías y muchos productos.

### Subcategoria

Archivo: `app/models/subcategoria.py`.

Representa el `sub_rubro` de Dux. Cada subcategoría pertenece a una categoría
mediante `categoria_id`.

### Marca

Archivo: `app/models/marca.py`.

Guarda las marcas enviadas por Dux. Una marca puede estar relacionada con
muchos productos.

### Producto

Archivo: `app/models/producto.py`.

Contiene los datos generales del artículo:

- Código de Dux.
- Nombre y slug.
- Código externo.
- Descripción.
- Costo interno.
- IVA.
- Imagen principal.
- Cantidad por bulto.
- Estado habilitado.
- Categoría, subcategoría y marca.

El costo existe en la base de datos, pero no se expone en la respuesta pública
de la API.

### PrecioProducto

Archivo: `app/models/precio_producto.py`.

Un producto puede tener varios precios porque Dux utiliza listas de precios.
Cada registro identifica la lista mediante `dux_id_lista`.

Las listas encontradas en Dux fueron:

| ID | Nombre | Uso en la tienda |
|---:|---|---|
| 4710 | MAYORISTA | Precio habitual |
| 43406 | 24 PRODUCTOS | Precio desde 24 unidades totales |
| 22702 | MINORISTA | No se expone |
| 31943 | AYME | No se expone |

### StockProducto

Archivo: `app/models/stock_producto.py`.

Guarda stock real, reservado y disponible por depósito y, cuando Dux lo
informa, por variante de talle y color.

### ImagenProducto y CodigoBarraProducto

Guardan imágenes y códigos de barras asociados a cada producto.

## 7. Migraciones con Alembic

La migración inicial está en:

```text
alembic/versions/7aec4b4c1b96_create_catalog_tables.py
```

Alembic permite reproducir la estructura de la base de datos en desarrollo o
producción.

Aplicar migraciones:

```bash
alembic upgrade head
```

Ver la migración actual:

```bash
alembic current
```

## 8. Integración con Dux

### Cliente HTTP

`app/integrations/dux/client.py` contiene `DuxClient`.

Sus responsabilidades son:

- Construir la URL de Dux.
- Enviar el token Bearer.
- Aplicar un timeout.
- Reintentar errores temporales del servidor.
- Devolver la respuesta JSON.

### Servicio de sincronización

`app/services/dux_sync_service.py` contiene la lógica principal.

`sincronizar_producto_desde_dux()` procesa un producto individual:

1. Valida código y nombre.
2. Obtiene o crea categoría, subcategoría y marca.
3. Busca el producto local mediante su código Dux.
4. Crea el producto si no existe.
5. Actualiza sus datos generales.
6. Reemplaza precios, stock, códigos de barras e imágenes anteriores.
7. Guarda las nuevas relaciones.

`sincronizar_catalogo_dux()` procesa el catálogo completo por páginas:

1. Marca temporalmente categorías, subcategorías y marcas como inactivas.
2. Solicita productos a Dux de 20 en 20.
3. Sincroniza cada producto.
4. Reactiva las entidades que siguen apareciendo.
5. Deshabilita productos locales que ya no aparecen en Dux.
6. Confirma todos los cambios al terminar.

Si ocurre un error antes de finalizar, el script realiza un rollback para no
dejar el catálogo sincronizado a medias.

Como protección adicional, si Dux devuelve un catálogo vacío se cancela la
operación. Esto evita deshabilitar accidentalmente todos los productos ante una
respuesta incorrecta.

Los slugs se conservan cuando cambia un nombre. De esta manera, una modificación
en Dux no rompe URLs ya publicadas.

### Ejecutar la sincronización

```bash
python -m app.scripts.sincronizar_dux
```

Actualmente la lógica está lista, pero la ejecución periódica todavía no está
programada. Al desplegar el backend se deberá configurar un cron job en el
proveedor elegido para ejecutarla cada 5 o 15 minutos.

## 9. Arquitectura Repository-Service-Router

Para entender el proyecto conviene seguir el recorrido de una petición.

### Repository

Ejemplo: `app/repositories/producto_repository.py`.

El repositorio construye consultas SQLAlchemy. No conoce HTTP ni decide códigos
de estado.

Algunas de sus tareas son:

- Buscar productos por ID o slug.
- Aplicar filtros.
- Ordenar resultados.
- Paginar.
- Contar la cantidad total.
- Cargar relaciones anticipadamente para evitar consultas N+1.

### Service

Ejemplo: `app/services/producto_service.py`.

El servicio aplica reglas de negocio y utiliza el repositorio. Allí se calculan
las páginas totales y se seleccionan los precios públicos del catálogo.

### Router

Ejemplo: `app/api/routers/productosRouter.py`.

El router define:

- URL y método HTTP.
- Parámetros permitidos.
- Validaciones de entrada.
- Dependencia de base de datos.
- Schema de respuesta.
- Errores HTTP, como `404`.

### Schema

Ejemplo: `app/schemas/producto_schemas.py`.

El schema controla qué datos salen de la API. Aunque el modelo Producto posee un
campo `costo`, el schema no lo incluye y por eso no llega al frontend.

## 10. Endpoints disponibles

### Productos

```http
GET /api/productos/
GET /api/productos/{producto_id}
GET /api/productos/slug/{slug}
```

Filtros del listado:

- `buscar`.
- `categoria_id`.
- `subcategoria_id`.
- `marca_id`.
- `solo_habilitados`.
- `con_stock`.
- `page`.
- `limit`.
- `orden`.

Ejemplo:

```http
GET /api/productos/?categoria_id=1&marca_id=3&con_stock=true&page=1&limit=20
```

### Filtros consolidados del catálogo

```http
GET /api/catalogo/filtros
```

Este endpoint evita que el frontend tenga que realizar varias peticiones para
construir los filtros. Devuelve categorías activas con sus subcategorías y las
marcas activas:

```json
{
  "categorias": [
    {
      "id": 1,
      "dux_id": 10,
      "nombre": "Bebés",
      "slug": "bebes",
      "descripcion": null,
      "activo": true,
      "subcategorias": [
        {
          "id": 2,
          "dux_id": 11,
          "categoria_id": 1,
          "nombre": "Abrigos",
          "slug": "bebes-abrigos",
          "descripcion": null,
          "activo": true
        }
      ]
    }
  ],
  "marcas": [
    {
      "id": 1,
      "dux_id": 30,
      "nombre": "Acme",
      "slug": "acme",
      "activo": true
    }
  ]
}
```

### Categorías

```http
GET /api/categorias/
GET /api/categorias/{categoria_id}
GET /api/categorias/slug/{slug}
```

El listado incluye las subcategorías activas ordenadas alfabéticamente.

### Subcategorías

```http
GET /api/subcategorias/
GET /api/subcategorias/{subcategoria_id}
GET /api/subcategorias/slug/{slug}
```

Filtrar por categoría:

```http
GET /api/subcategorias/?categoria_id=1
```

### Marcas

```http
GET /api/marcas/
GET /api/marcas/{marca_id}
GET /api/marcas/slug/{slug}
```

En categorías, subcategorías y marcas se devuelven solamente entidades activas
por defecto. El parámetro `solo_activas=false` permite incluir inactivas.

### Cálculo del carrito

```http
POST /api/carrito/calcular
```

El frontend envía únicamente identificadores y cantidades:

```json
{
  "items": [
    {"producto_id": 1, "cantidad": 2},
    {"producto_id": 5, "cantidad": 1}
  ]
}
```

El backend vuelve a consultar los productos y sus precios. Nunca acepta un
precio calculado por el navegador, porque podría estar desactualizado o ser
manipulado. También vuelve a validar el stock y rechaza cantidades superiores a
las unidades disponibles en Dux.

La respuesta informa los importes definitivos y el progreso hacia el precio
especial:

```json
{
  "items": [],
  "cantidad_productos_diferentes": 2,
  "cantidad_unidades": 3,
  "aplica_precio_24_productos": false,
  "faltantes_para_precio_24": 22,
  "total": "36000.00"
}
```

Si el mismo producto aparece varias veces en la petición, sus cantidades se
consolidan y sigue contando como una sola referencia diferente.

## 11. Regla de precios mayoristas

La API publica dos campos:

```json
{
  "precio_mayorista": "12000.00",
  "precio_24_productos": "10500.00"
}
```

La regla comercial definida es:

- De 1 a 23 unidades totales: precio mayorista.
- Desde 24 unidades totales: precio de la lista `24 PRODUCTOS`.
- Se suman todas las unidades del carrito, aunque pertenezcan al mismo producto.
- Si un producto no posee un precio válido en la lista de 24, conserva su
  precio mayorista.

Ejemplo:

```text
23 unidades totales → precio MAYORISTA
24 unidades totales → precio 24 PRODUCTOS
```

La API entrega ambos valores. La selección definitiva se implementará en el
carrito, porque ese módulo conocerá cuántas unidades contiene el
pedido.

## 12. CORS

CORS permite que un frontend alojado en otro dominio consuma la API.

La configuración se encuentra en `app/main.py` y toma los dominios desde:

```env
CORS_ORIGINS=https://tienda.example,https://www.tienda.example
```

No se utiliza `*` porque el proyecto permite credenciales. Los dominios de
producción deberán cargarse cuando se conozca la URL definitiva del frontend.

## 13. Pruebas automáticas

Las pruebas están en:

```text
tests/conftest.py
tests/test_catalogo_endpoints.py
tests/test_cors.py
```

Utilizan una base SQLite temporal. No modifican PostgreSQL y no realizan
peticiones reales a Dux.

Ejecutarlas:

```bash
python -m pytest -q
```

Estado al crear esta guía:

```text
18 passed
```

Las pruebas verifican:

- Listados activos.
- Orden alfabético.
- Filtros de productos.
- Filtro de subcategorías por categoría.
- Consultas por slug.
- Respuestas 404.
- Inclusión opcional de entidades inactivas.
- Precios mayoristas y por 24 productos.
- Fallback al mayorista cuando el precio especial es cero.
- CORS permitido y bloqueado.
- Consolidación y cálculo seguro del carrito.
- Aplicación del precio especial con 24 unidades totales.
- Rechazo de productos inexistentes o deshabilitados en el carrito.
- Rechazo de cantidades superiores al stock disponible.

## 14. Ejecutar el backend localmente

Activar el entorno virtual si fuera necesario:

```bash
source .venv/bin/activate
```

Instalar dependencias:

```bash
python -m pip install -r requirements.txt
```

Iniciar FastAPI:

```bash
uvicorn app.main:app --reload
```

Documentación interactiva:

```text
http://127.0.0.1:8000/docs
```

Health check:

```text
http://127.0.0.1:8000/api/health
```

## 15. Orden recomendado para estudiar el código

### Primera lectura: estructura básica

1. `app/main.py`.
2. `app/core/config.py`.
3. `app/database/session.py`.
4. `app/models/producto.py`.
5. `app/models/categoria.py`.

### Segunda lectura: una petición completa

Seguir el listado de productos en este orden:

1. `app/api/routers/productosRouter.py`.
2. `app/services/producto_service.py`.
3. `app/repositories/producto_repository.py`.
4. `app/schemas/producto_schemas.py`.

Después repetir el recorrido con categorías:

1. `app/api/routers/categoriasRouter.py`.
2. `app/services/categoria_service.py`.
3. `app/repositories/categoria_repository.py`.
4. `app/schemas/categoria_schemas.py`.

### Tercera lectura: Dux

1. `app/integrations/dux/client.py`.
2. `app/services/dux_sync_service.py`.
3. `app/scripts/sincronizar_dux.py`.

### Cuarta lectura: pruebas

1. `tests/conftest.py`.
2. `tests/test_catalogo_endpoints.py`.
3. `tests/test_cors.py`.

Las pruebas son buenos ejemplos de cómo se espera que se comporte cada endpoint.

## 16. Próximos pasos

No hay una modificación incompleta en este momento. Los siguientes bloques
planificados son:

1. Definir la unidad mínima de venta y el comportamiento por bulto.
2. Implementar clientes, autenticación y pedidos.
3. Definir cómo enviar pedidos a Dux.
4. Desplegar PostgreSQL y FastAPI.
5. Configurar la sincronización automática cada 5 o 15 minutos.

## 17. Conceptos importantes para repasar

- Diferencia entre modelo SQLAlchemy y schema Pydantic.
- Responsabilidad de repository, service y router.
- Relaciones uno-a-muchos.
- Claves foráneas.
- `selectinload` y `joinedload`.
- Paginación mediante `offset` y `limit`.
- Transacciones, `flush`, `commit` y `rollback`.
- Dependencias de FastAPI con `Depends`.
- Variables de entorno.
- CORS.
- Pruebas aisladas con fixtures de Pytest.
- Sincronización idempotente: ejecutar varias veces debe actualizar datos sin
  duplicarlos.

La mejor forma de estudiar el proyecto es elegir un endpoint, comenzar en el
router y seguir cada función hasta llegar a la consulta SQLAlchemy. Luego se
puede recorrer el camino inverso para entender cómo el resultado se convierte
en JSON.
