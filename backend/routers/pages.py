from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

@router.get("/")
def get_index():
    return FileResponse("frontend/index.html")

@router.get("/recommended")
def get_recommended_page():
    return FileResponse("frontend/recommended.html")

@router.get("/country/{country_name}")
def get_country_page(country_name: str):
    return FileResponse("frontend/country.html")

@router.get("/group/{group_letter}")
def get_group_page(group_letter: str):
    return FileResponse("frontend/group.html")

@router.get("/bracket")
def get_bracket_page():
    return FileResponse("frontend/bracket.html")
