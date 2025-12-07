from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, items, profile
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(profile.router, prefix="/profile", tags=["Profile"])
app.include_router(items.router, prefix="/items", tags=["Items"])


@app.get("/")
def root():
    return {"status": "ok"}
