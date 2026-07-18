import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_db, get_db, Fixture
from backend.ingestor import seed_database
from backend.routers.pages import router as pages_router
from backend.routers.api_fixtures import router as fixtures_router
from backend.routers.api_groups import router as groups_router
from backend.routers.api_countries import router as countries_router
from backend.routers.api_bracket import router as bracket_router
from backend.routers.api_weights import router as weights_router
from backend.routers.api_admin import router as admin_router
from backend.routers.api_competitions import router as competitions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database on startup safely within context manager
    init_db()
    
    # Seed database on startup if empty, unless we are in testing mode
    if os.getenv("TESTING") != "True":
        db = next(get_db())
        try:
            if db.query(Fixture).count() == 0:
                seed_database(db)
        finally:
            db.close()
    yield

app = FastAPI(
    title="Football Match Watchability Index",
    lifespan=lifespan
)

# Allowed hosts — Railway domain and custom domain
ALLOWED_HOSTS = [
    "web-production-ae1eb.up.railway.app",
    "findfootball.games",
    "www.findfootball.games",
    "localhost",
    "127.0.0.1",
]
if os.getenv("TESTING") == "True":
    ALLOWED_HOSTS.append("testserver")

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=ALLOWED_HOSTS,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"https://{host}" for host in ALLOWED_HOSTS if "." in host]
    + ["http://localhost", "http://127.0.0.1"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static assets
app.mount("/css", StaticFiles(directory="frontend/css"), name="css")
app.mount("/js", StaticFiles(directory="frontend/js"), name="js")

# Include Routers
app.include_router(pages_router)
app.include_router(fixtures_router)
app.include_router(groups_router)
app.include_router(countries_router)
app.include_router(bracket_router)
app.include_router(weights_router)
app.include_router(admin_router)
app.include_router(competitions_router)

