import os
import time

import requests
from dotenv import load_dotenv


load_dotenv()
API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")


def search_restaurants_granada(query="restaurantes en Granada", max_paginas=3):
    if not API_KEY:
        print("Aviso: no se encontro GOOGLE_PLACES_API_KEY")
        return []

    campos = [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.location",
        "places.rating",
        "places.userRatingCount",
        "places.priceLevel",
        "places.priceRange",
        "places.nationalPhoneNumber",
        "places.websiteUri",
        "places.currentOpeningHours",
        "places.regularOpeningHours",
        "places.outdoorSeating",
        "places.servesVegetarianFood",
        "places.primaryTypeDisplayName",
        "places.takeout",
        "places.dineIn",
        "nextPageToken",
    ]
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": ",".join(campos),
    }

    restaurantes = []
    page_token = ""

    for pagina in range(1, max_paginas + 1):
        payload = {
            "textQuery": query,
            "maxResultCount": 20,
            "languageCode": "es",
        }
        if page_token:
            payload["pageToken"] = page_token

        try:
            response = requests.post(
                "https://places.googleapis.com/v1/places:searchText",
                headers=headers,
                json=payload,
                timeout=20,
            )
            response.raise_for_status()
            datos = response.json()
            restaurantes.extend(datos.get("places", []))

            page_token = datos.get("nextPageToken")
            if not page_token:
                break

            time.sleep(1.5)

        except Exception as e:
            print(f"Error en Google Places (pagina {pagina}): {e}")
            break

    return restaurantes
