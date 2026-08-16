from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

@router.get("/icons8-soccer-ball-96.png")
def get_favicon_png():
    return FileResponse("frontend/icons8-soccer-ball-96.png", media_type="image/png")

@router.get("/favicon.ico")
def get_favicon_ico():
    return FileResponse("frontend/icons8-soccer-ball-96.png", media_type="image/png")

# Cache-busting headers for dev pages
NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0"
}

import json
import os
from fastapi import Depends
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.feed_builder import load_precalculated_feed_cache, build_fixtures_feed_cache

@router.get("/", response_class=HTMLResponse)
def get_index(db: Session = Depends(get_db)):
    html_path = "frontend/index.html"
    if not os.path.exists(html_path):
        return FileResponse(html_path, headers=NO_CACHE_HEADERS)
        
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
        
    feed_data = load_precalculated_feed_cache()
    if not feed_data or feed_data.get("total_fixtures", 0) == 0:
        try:
            feed_data = build_fixtures_feed_cache(db)
        except Exception as e:
            print(f"Warning: Failed to build feed cache for index hydration: {e}")
            feed_data = {"total_fixtures": 0, "fixtures": []}
            
    json_str = json.dumps(feed_data, ensure_ascii=False)
    hydration_script = f'<script id="initial-fixtures-data" type="application/json">{json_str}</script>\n'
    
    if "</head>" in html_content:
        html_content = html_content.replace("</head>", f"{hydration_script}</head>", 1)
    else:
        html_content = hydration_script + html_content
        
    return HTMLResponse(content=html_content, headers=NO_CACHE_HEADERS)

@router.get("/recommended")
def get_recommended_page():
    return FileResponse("frontend/recommended.html", headers=NO_CACHE_HEADERS)

@router.get("/country/{country_name}")
def get_country_page(country_name: str):
    return FileResponse("frontend/team.html", headers=NO_CACHE_HEADERS)

@router.get("/team/{team_name}")
def get_team_page(team_name: str):
    return FileResponse("frontend/team.html", headers=NO_CACHE_HEADERS)

@router.get("/group/{group_letter}")
def get_group_page(group_letter: str):
    return FileResponse("frontend/group.html", headers=NO_CACHE_HEADERS)


@router.get("/bracket")
def get_bracket_page():
    return FileResponse("frontend/bracket.html", headers=NO_CACHE_HEADERS)

@router.get("/calendar")
def get_calendar_page():
    return FileResponse("frontend/calendar.html", headers=NO_CACHE_HEADERS)

@router.get("/themes")
def get_themes_page():
    return FileResponse("frontend/themes/test.html", headers=NO_CACHE_HEADERS)

