from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.routers import lost_items, found_items
from app.db.db import create_db_and_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up...")
    try:
        create_db_and_tables()
        print("DB ready.")
    except Exception as e:
        print("ERROR: Cannot connect to DB:", e)
    yield
    print("Shutting down...")

app = FastAPI(lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(lost_items.router, prefix="/lost-items", tags=["Lost Items"])
app.include_router(found_items.router, prefix="/found-items", tags=["Found Items"])


@app.get("/")
def root():
    return {"status": "ok"}
