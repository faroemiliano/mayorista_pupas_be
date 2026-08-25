from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from app.core.config import settings
import app.models
from app.database.base import Base

# IMPORTAR MODELOS
# Más adelante agregaremos:
# from app.models.categoria import Categoria
# from app.models.producto import Producto
# etc.


config = context.config


# =========================================================
# CONFIGURAR DATABASE URL
# =========================================================

config.set_main_option(
    "sqlalchemy.url",
    settings.DATABASE_URL,
)


# =========================================================
# LOGGING
# =========================================================

if config.config_file_name is not None:
    fileConfig(
        config.config_file_name,
    )


# =========================================================
# METADATA
# =========================================================

target_metadata = Base.metadata


# =========================================================
# OFFLINE
# =========================================================

def run_migrations_offline() -> None:

    url = config.get_main_option(
        "sqlalchemy.url"
    )

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named",
        },
    )

    with context.begin_transaction():
        context.run_migrations()


# =========================================================
# ONLINE
# =========================================================

def run_migrations_online() -> None:

    connectable = engine_from_config(
        config.get_section(
            config.config_ini_section,
            {},
        ),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


# =========================================================
# EJECUTAR
# =========================================================

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()