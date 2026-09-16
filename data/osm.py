import requests


OVERPASS_URL = "https://z.overpass-api.de/api/interpreter"
QUERY = """
    [out:json][timeout:40];
    area["name"="Granada"]["admin_level"="8"]->.granada;
    nwr["amenity"="restaurant"](area.granada);
    out center tags;
"""


def search_restaurants_osm_granada():
    try:
        response = requests.post(
            OVERPASS_URL,
            data={"data": QUERY},
            headers={"User-Agent": "ComparadorRestaurantes/1.0 (contacto@example.com)"},
            timeout=45,
        )
        response.raise_for_status()
        return response.json().get("elements", [])
    except Exception as e:
        print(f"Error en OpenStreetMap: {e}")
        return []
