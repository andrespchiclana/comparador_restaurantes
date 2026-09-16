import re

import requests
from bs4 import BeautifulSoup


def _texto(valor):
    return re.sub(r"\s+", " ", valor or "").strip()


def _numero(valor):
    match = re.search(r"\d+(?:[.,]\d+)?", str(valor or ""))
    return float(match.group(0).replace(",", ".")) if match else None


def _pedir(url, params):
    response = requests.get(
        url,
        params=params,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    response.raise_for_status()
    return response


def _slugs_granada():
    response = _pedir(
        "https://macarfi.com/gra/restaurants/search",
        {"location": 767, "zn[]": 779, "page": 1},
    )
    return {
        item.get("slug")
        for item in response.json().get("mapRestaurants", [])
        if item.get("slug")
    }


def _metricas(card):
    datos = {}

    for bloque in card.select(".grow"):
        valores = [_texto(p.get_text(" ", strip=True)) for p in bloque.find_all("p")]
        if len(valores) < 2:
            continue

        etiqueta = valores[1].lower()
        valor = _numero(valores[0])
        if etiqueta.startswith("comida"):
            datos["puntuacion_comida"] = valor
        elif etiqueta.startswith("decor"):
            datos["puntuacion_decoracion"] = valor
        elif etiqueta.startswith("servicio"):
            datos["puntuacion_servicio"] = valor
        elif etiqueta.startswith("coste"):
            datos["coste_estimado"] = valor

    return datos


def _extraer_card(card):
    enlace = card.select_one("h4.card-title a[href*='ficha-restaurante']")
    if not enlace:
        return None

    cocina_tag = card.select_one(".card-content > p")
    cocina = _texto(cocina_tag.find(string=True, recursive=False)) if cocina_tag else None
    slug = enlace.get("href", "").rstrip("/").split("/")[-1]

    item = {
        "nombre": _texto(enlace.get_text(" ", strip=True)),
        "tipo_cocina": cocina,
    }
    item.update(_metricas(card))
    return slug, item


def _cards_listado(page):
    response = _pedir(
        "https://macarfi.com/es/gra/restaurantes",
        {"zn[]": 779, "page": page},
    )
    soup = BeautifulSoup(response.text, "html.parser")
    return [
        item
        for item in (_extraer_card(card) for card in soup.select(".card"))
        if item
    ]


def scrape_macarfi_granada():
    try:
        slugs_validos = _slugs_granada()
        restaurantes = {}
        page = 1

        while len(restaurantes) < len(slugs_validos):
            total_anterior = len(restaurantes)

            for slug, item in _cards_listado(page):
                if slug in slugs_validos:
                    restaurantes[slug] = item

            if len(restaurantes) == total_anterior:
                break
            page += 1

        return list(restaurantes.values())

    except Exception as e:
        print(f"Error en Macarfi: {e}")
        return []
