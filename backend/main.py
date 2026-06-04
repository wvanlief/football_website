import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.database import init_db, get_db, Fixture
from backend.ingestor import seed_database
from backend.routers.pages import router as pages_router
from backend.routers.api_fixtures import router as fixtures_router
from backend.routers.api_groups import router as groups_router
from backend.routers.api_countries import router as countries_router
from backend.routers.api_bracket import router as bracket_router
from backend.routers.api_weights import router as weights_router

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
