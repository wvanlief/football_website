from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

# Cache-busting headers for dev pages
NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0"
}

@router.get("/")
def get_index():
    return FileResponse("frontend/index.html", headers=NO_CACHE_HEADERS)

@router.get("/recommended")
def get_recommended_page():
    return FileResponse("frontend/recommended.html", headers=NO_CACHE_HEADERS)

@router.get("/country/{country_name}")
def get_country_page(country_name: str):
    return FileResponse("frontend/country.html", headers=NO_CACHE_HEADERS)

@router.get("/group/{group_letter}")
def get_group_page(group_letter: str):
    return FileResponse("frontend/group.html", headers=NO_CACHE_HEADERS)

@router.get("/bracket")
def get_bracket_page():
    return FileResponse("frontend/bracket.html", headers=NO_CACHE_HEADERS)

@router.get("/calendar")
def get_calendar_page():
    return FileResponse("frontend/calendar.html", headers=NO_CACHE_HEADERS)

