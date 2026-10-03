"""this file connects Alembic to database and model metadata"""
import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool
# create_engine constructs sqlalch db engine
# pool provides connection-pool strategies
from sqlalchemy.engine import URL
# safely constructs db url, netter than manually joining str as pw may contain special url chars

from alembic import context
from automate_food_places_outreach.models.base import Base
from automate_food_places_outreach.models.restaurant import Restaurant
# even tho Restaurant not called in this file, import itself has required registration effect to register restaurants table in Base.metadata

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
database_url = URL.create(
    drivername="postgresql+psycopg",
    username=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
    host=os.environ["POSTGRES_HOST"],
    port=int(os.environ["POSTGRES_PORT"]),
    database=os.environ["POSTGRES_DB"],
)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata
# target_metadata is the desired schema Alembic uses for autogeneration. now includes registered restaurant table

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available. Genertes 
    SQL wo opening a live db connection

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = create_engine(
    database_url,
    poolclass=pool.NullPool, #NullPool tells this short-lived migration process not to maintain reusable connection pool
)

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
