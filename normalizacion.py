import difflib
import math
import re
import unicodedata
from datetime import datetime


PALABRAS_RUIDO = {
    "restaurante",
    "bar",
    "cafeteria",
    "meson",
    "el",
    "la",
    "los",
    "las",
    "de",
    "del",
    "granada",
}

PRICE_LEVELS_GOOGLE = {
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}

PRECIOS_GOOGLE = {0: 0, 1: 15, 2: 25, 3: 45, 4: 65}
VALORES_AFIRMATIVOS = {"yes", "true", "1", "designated", "limited", "only"}


def normalizar_nombre(nombre):
    if not nombre:
        return ""

    texto = unicodedata.normalize("NFKD", str(nombre))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def calcular_distancia(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return float("inf")

    radio_tierra = 6371000
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    delta_phi = math.radians(float(lat2) - float(lat1))
    delta_lambda = math.radians(float(lon2) - float(lon1))

    seno_latitud = math.sin(delta_phi / 2) ** 2
    seno_longitud = math.sin(delta_lambda / 2) ** 2
    a = seno_latitud + math.cos(phi1) * math.cos(phi2) * seno_longitud
    return radio_tierra * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def limpiar_nombre(nombre):
    tokens = normalizar_nombre(nombre).split()
    tokens = [token for token in tokens if token not in PALABRAS_RUIDO]
    return " ".join(tokens)


def similitud_nombres(nombre1, nombre2):
    nombre_limpio_1 = limpiar_nombre(nombre1)
    nombre_limpio_2 = limpiar_nombre(nombre2)

    if not nombre_limpio_1 or not nombre_limpio_2:
        return 0.0
    if nombre_limpio_1 == nombre_limpio_2:
        return 1.0
    if (
        len(nombre_limpio_1) >= 4 and len(nombre_limpio_2) >= 4
        and (nombre_limpio_1 in nombre_limpio_2 or nombre_limpio_2 in nombre_limpio_1)
    ):
        return 0.9
    return difflib.SequenceMatcher(None, nombre_limpio_1, nombre_limpio_2).ratio()


def mejor_coincidencia(restaurantes, nombre, lat=None, lon=None, umbral=0.7, distancia_maxima=None,):
    mejor_restaurante = None
    mejor_puntuacion = 0.0

    for restaurante in restaurantes:
        if distancia_maxima is not None:
            lat_restaurante = restaurante.ubicacion.latitud
            lon_restaurante = restaurante.ubicacion.longitud
            distancia = calcular_distancia(lat, lon, lat_restaurante, lon_restaurante)
            if distancia > distancia_maxima:
                continue

        puntuacion = similitud_nombres(nombre, restaurante.nombre)
        if puntuacion >= umbral and puntuacion > mejor_puntuacion:
            mejor_restaurante = restaurante
            mejor_puntuacion = puntuacion

    return mejor_restaurante


def agregar_unico(lista, valor):
    if valor and valor not in lista:
        lista.append(valor)


def limpiar_direccion(direccion):
    if not direccion:
        return None

    direccion = re.sub(r"\s+", " ", str(direccion))
    partes = [parte.strip() for parte in direccion.split(",")]
    while partes and normalizar_nombre(partes[-1]) in {"espana", "spain"}:
        partes.pop()
    return ", ".join(partes).strip(" ,")


def es_afirmativo(valor, extras=()):
    valor = str(valor).strip().lower()
    return valor in VALORES_AFIRMATIVOS or valor in extras


def mapear_nivel_precio(nivel_precio):
    if nivel_precio is None:
        return None
    if isinstance(nivel_precio, int):
        return nivel_precio
    return PRICE_LEVELS_GOOGLE.get(str(nivel_precio))


def normalizar_precio(valor):
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)

    match = re.search(r"\d+(?:[.,]\d+)?", str(valor))
    return float(match.group(0).replace(",", ".")) if match else None


def normalizar_rango_precio(rango_precio):
    if not isinstance(rango_precio, dict):
        return None, None

    precios = []
    for campo in ("startPrice", "endPrice"):
        importe = rango_precio.get(campo) or {}
        euros = importe.get("units")
        if euros is not None:
            decimales = float(importe.get("nanos", 0)) / 1_000_000_000
            precios.append(float(euros) + decimales)

    if not precios:
        return None, None

    if len(precios) == 1 or precios[0] == precios[-1]:
        return f"{precios[0]:g} €", precios[0]

    return f"{precios[0]:g}-{precios[-1]:g} €", sum(precios) / len(precios)


def normalizar_web(valor):
    if not valor:
        return None

    enlace = str(valor).strip()
    if not enlace:
        return None
    if enlace.startswith(("http://", "https://")):
        return enlace
    return f"https://{enlace}" if "." in enlace else enlace


def normalizar_social(valor, red):
    if not valor:
        return None

    valor = str(valor).strip()
    if valor.startswith(("http://", "https://")):
        return valor
    if f"{red}.com" in valor:
        return normalizar_web(valor)

    usuario = valor.lstrip("@")
    return f"https://www.{red}.com/{usuario}"


def precio_desde_google(nivel_precio):
    return PRECIOS_GOOGLE.get(nivel_precio)


def extraer_horario_hoy(descripciones):
    if not descripciones:
        return None

    dia_actual = datetime.now().weekday()
    return descripciones[dia_actual] if len(descripciones) > dia_actual else None


def formatear_fecha_hora_google(valor):
    if not valor:
        return None

    try:
        dt = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return str(valor)

    return dt.astimezone().strftime("%H:%M")
