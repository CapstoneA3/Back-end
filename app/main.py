from fastapi import FastAPI
from app.routers import ingredients, inventory

app = FastAPI(title="냉장고 재고 관리 API", version="0.1.0")

app.include_router(ingredients.router, prefix="/api/v1")
app.include_router(inventory.router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
