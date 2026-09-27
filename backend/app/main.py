from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401  (registers all tables on Base.metadata)
from .config import settings
from .db import Base, engine
from .errors import register_exception_handlers
from .routers import admin, carts, checkout, orders, products


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Reliable Checkout & Rewards Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(products.router)
app.include_router(carts.router)
app.include_router(checkout.router)
app.include_router(orders.router)
app.include_router(admin.router)
