from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.routers import ingredients, inventory, recipes
from app.core.redis_client import close_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_redis()


app = FastAPI(title="냉장고 재고 관리 API", version="0.1.0", lifespan=lifespan)

app.include_router(ingredients.router, prefix="/api/v1")
app.include_router(inventory.router, prefix="/api/v1")
app.include_router(recipes.router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
