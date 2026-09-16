from concurrent.futures import ThreadPoolExecutor

import normalizacion as norm
from cache_utils import obtener_con_cache
from models import Restaurante
from data.google_places import search_restaurants_granada
from data.osm import search_restaurants_osm_granada
from data.macarfi import scrape_macarfi_granada


def crear_restaurante_google(datos_google):
    nombre = datos_google.get("displayName", {}).get("text", "Desconocido")
    id_google = datos_google.get("id", norm.normalizar_nombre(nombre))
    restaurante = Restaurante(id_restaurante=id_google, nombre=nombre)

    ubicacion_google = datos_google.get("location", {})
    direccion_google = datos_google.get("formattedAddress")
    restaurante.ubicacion.latitud = ubicacion_google.get("latitude")
    restaurante.ubicacion.longitud = ubicacion_google.get("longitude")
    restaurante.ubicacion.direccion = norm.limpiar_direccion(direccion_google)

    restaurante.valoracion.valoracion_media = datos_google.get("rating")
    restaurante.valoracion.num_valoraciones = datos_google.get("userRatingCount")

    restaurante.contacto.telefono = datos_google.get("nationalPhoneNumber")
    restaurante.contacto.web = norm.normalizar_web(datos_google.get("websiteUri"))

    aplicar_horario_google(restaurante, datos_google)
    aplicar_precio_google(restaurante, datos_google)
    aplicar_caracteristicas_google(restaurante, datos_google)

    restaurante.comer_alli = datos_google.get("dineIn", True)
    restaurante.recoger = datos_google.get("takeout", False)
    norm.agregar_unico(restaurante.fuentes_integradas, "Google Places")
    return restaurante


def aplicar_horario_google(restaurante, datos_google):
    horario_regular = datos_google.get("regularOpeningHours") or {}
    horario_actual = datos_google.get("currentOpeningHours") or horario_regular

    proximo_cierre = horario_actual.get("nextCloseTime")
    hora_cierre = norm.formatear_fecha_hora_google(proximo_cierre)

    restaurante.horario.abierto = horario_actual.get("openNow")
    restaurante.horario.proximo_cierre = hora_cierre

    descripciones = horario_regular.get("weekdayDescriptions")
    if not descripciones:
        descripciones = horario_actual.get("weekdayDescriptions")
    if descripciones:
        restaurante.horario.horario_completo = " | ".join(descripciones)
        restaurante.horario.horario_hoy = norm.extraer_horario_hoy(descripciones)


def aplicar_precio_google(restaurante, datos_google):
    nivel_precio = datos_google.get("priceLevel")
    rango_precio = datos_google.get("priceRange")

    nivel_google = norm.mapear_nivel_precio(nivel_precio)
    rango_texto, precio_google = norm.normalizar_rango_precio(rango_precio)
    if precio_google is None:
        precio_google = norm.precio_desde_google(nivel_google)

    restaurante.precio.nivel_precio_google = nivel_google
    restaurante.precio.rango_precio_google = rango_texto
    restaurante.precio.precio_google = precio_google


def aplicar_caracteristicas_google(restaurante, datos_google):
    tipo_principal = datos_google.get("primaryTypeDisplayName", {}).get("text")
    if tipo_principal:
        restaurante.caracteristicas.tipo_cocina = tipo_principal

    terraza = datos_google.get("outdoorSeating") is True
    restaurante.caracteristicas.terraza = terraza

    if datos_google.get("servesVegetarianFood") is True:
        dietas = restaurante.caracteristicas.opciones_dieteticas
        norm.agregar_unico(dietas, "Vegetariano")


def completar_precio_google(destino, origen):
    destino.precio.nivel_precio_google = (
        destino.precio.nivel_precio_google
        if destino.precio.nivel_precio_google is not None
        else origen.precio.nivel_precio_google
    )
    
    destino.precio.rango_precio_google = (destino.precio.rango_precio_google or origen.precio.rango_precio_google)
    if destino.precio.precio_google is None:
        destino.precio.precio_google = origen.precio.precio_google


def buscar_coincidencia_osm(restaurantes, datos_osm, umbral=0.7, distancia=300):
    etiquetas = datos_osm.get("tags") or {}
    nombre_osm = etiquetas.get("name")
    if not nombre_osm:
        return None

    latitud = datos_osm.get("lat") or datos_osm.get("center", {}).get("lat")
    longitud = datos_osm.get("lon") or datos_osm.get("center", {}).get("lon")
    return norm.mejor_coincidencia(restaurantes, nombre_osm, latitud, longitud, umbral, distancia)


def aplicar_osm(restaurante, datos_osm):
    etiquetas = datos_osm.get("tags") or {}
    facebook = etiquetas.get("contact:facebook") or etiquetas.get("facebook")
    instagram = etiquetas.get("contact:instagram") or etiquetas.get("instagram")
    web = etiquetas.get("website") or etiquetas.get("contact:website")
    menu = etiquetas.get("website:menu") or etiquetas.get("url:menu") or etiquetas.get("menu")

    facebook = norm.normalizar_social(facebook, "facebook")
    instagram = norm.normalizar_social(instagram, "instagram")
    web = norm.normalizar_web(web)

    if facebook:
        restaurante.contacto.facebook = facebook
    if instagram:
        restaurante.contacto.instagram = instagram
    if web and not restaurante.contacto.web:
        restaurante.contacto.web = web

    cocina_osm = etiquetas.get("cuisine")
    if cocina_osm and not restaurante.caracteristicas.tipo_cocina:
        restaurante.caracteristicas.tipo_cocina = cocina_osm

    if not restaurante.caracteristicas.terraza:
        terraza = etiquetas.get("outdoor_seating")
        restaurante.caracteristicas.terraza = norm.es_afirmativo(terraza)

    accesibilidad_osm = etiquetas.get("wheelchair")
    if accesibilidad_osm:
        accesible = norm.es_afirmativo(accesibilidad_osm)
        restaurante.caracteristicas.accesibilidad = accesible

    reserva = etiquetas.get("reservation")
    if norm.es_afirmativo(reserva, extras=("recommended", "required")):
        restaurante.caracteristicas.reserva = True

    menu = norm.normalizar_web(menu)
    if menu and not restaurante.caracteristicas.menu:
        restaurante.caracteristicas.menu = menu

    if norm.es_afirmativo(etiquetas.get("diet:vegan")):
        dietas = restaurante.caracteristicas.opciones_dieteticas
        norm.agregar_unico(dietas, "Vegano")

    if norm.es_afirmativo(etiquetas.get("diet:vegetarian")):
        dietas = restaurante.caracteristicas.opciones_dieteticas
        norm.agregar_unico(dietas, "Vegetariano")

    horario_osm = etiquetas.get("opening_hours")
    if horario_osm and not restaurante.horario.horario_completo:
        restaurante.horario.horario_completo = horario_osm

    norm.agregar_unico(restaurante.fuentes_integradas, "OpenStreetMap")


def aplicar_macarfi(restaurante, datos_macarfi):
    cocina_macarfi = datos_macarfi.get("tipo_cocina")
    if cocina_macarfi and not restaurante.caracteristicas.tipo_cocina:
        restaurante.caracteristicas.tipo_cocina = cocina_macarfi

    coste = norm.normalizar_precio(datos_macarfi.get("coste_estimado"))
    if coste is not None:
        restaurante.precio.coste_estimado = f"{coste:g} €"

    for campo in ("puntuacion_comida", "puntuacion_decoracion", "puntuacion_servicio"):
        valor = datos_macarfi.get(campo)
        if valor is not None:
            setattr(restaurante.valoracion, campo, float(valor))

    norm.agregar_unico(restaurante.fuentes_integradas, "Macarfi")


def buscar_coincidencia_macarfi(restaurantes, datos_macarfi, umbral=0.8):
    nombre_macarfi = datos_macarfi.get("nombre")
    if not nombre_macarfi:
        return None

    return norm.mejor_coincidencia(restaurantes, nombre_macarfi, umbral=umbral)


def buscar_google_preciso(nombre):
    consulta = f"{nombre} Granada"
    datos_google = obtener_con_cache("google_preciso", search_restaurants_granada, consulta, 1)
    return [crear_restaurante_google(datos) for datos in datos_google]


def completar_precios_google(restaurantes):
    pendientes = [restaurante for restaurante in restaurantes if restaurante.precio.precio_google is None]
    
    if not pendientes:
        return

    nombres = [restaurante.nombre for restaurante in pendientes]
    with ThreadPoolExecutor(max_workers=5) as executor:
        resultados = executor.map(buscar_google_preciso, nombres)
        for restaurante, candidatos in zip(pendientes, resultados):
            nombre = restaurante.nombre
            latitud = restaurante.ubicacion.latitud
            longitud = restaurante.ubicacion.longitud
            candidato = norm.mejor_coincidencia(candidatos, nombre, latitud, longitud, 0.8, 300)
            if candidato:
                completar_precio_google(restaurante, candidato)


def calcular_valores_globales(restaurantes):
    for restaurante in restaurantes:
        nota_google = restaurante.valoracion.puntuacion_google
        notas_macarfi = [
            restaurante.valoracion.puntuacion_comida,
            restaurante.valoracion.puntuacion_decoracion,
            restaurante.valoracion.puntuacion_servicio,
        ]
        notas_macarfi = [nota for nota in notas_macarfi if nota is not None]

        puntuaciones = []
        if nota_google is not None:
            puntuaciones.append(nota_google)
        if notas_macarfi:
            puntuaciones.append(sum(notas_macarfi) / len(notas_macarfi))

        if puntuaciones:
            media = sum(puntuaciones) / len(puntuaciones)
            restaurante.valoracion.puntuacion_global = round(media, 1)

        precios = [norm.normalizar_precio(restaurante.precio.coste_estimado), restaurante.precio.precio_google,]
        precios = [precio for precio in precios if precio is not None]

        if precios:
            restaurante.precio.precio_calculado = round(sum(precios) / len(precios), 2)
            diferencia = max(precios) - min(precios)
            restaurante.precio.diferencia = len(precios) > 1 and diferencia >= 15


def filtrar_por_precio(restaurantes, filtro_precio):
    if not filtro_precio:
        return restaurantes

    try:
        nivel_maximo = int(filtro_precio)
    except ValueError:
        return restaurantes

    precio_maximo = norm.precio_desde_google(nivel_maximo)
    if precio_maximo is None:
        return restaurantes

    filtrados = []
    for restaurante in restaurantes:
        precio = restaurante.precio.valor_filtrado
        if precio is not None and precio <= precio_maximo:
            filtrados.append(restaurante)
    return filtrados


def filtrar_por_servicio(restaurantes, filtro_servicio):
    if filtro_servicio == "comer":
        return [restaurante for restaurante in restaurantes if restaurante.comer_alli]
    if filtro_servicio == "recoger":
        return [restaurante for restaurante in restaurantes if restaurante.recoger]
    return restaurantes


def filtrar_integracion_minima(restaurantes):
    return [
        restaurante
        for restaurante in restaurantes
        if "Google Places" in restaurante.fuentes_integradas
        and len(restaurante.fuentes_integradas) >= 2
    ]


def obtener_restaurantes_integrados(
    query_google,
    filtro_precio=None,
    filtro_servicio=None,
):
    with ThreadPoolExecutor(max_workers=3) as executor:
        cache = obtener_con_cache
        buscar_google = search_restaurants_granada
        futuro_google = executor.submit(cache, "google", buscar_google, query_google, 3)
        futuro_osm = executor.submit(cache, "osm", search_restaurants_osm_granada)
        futuro_macarfi = executor.submit(cache, "macarfi", scrape_macarfi_granada)

        datos_google = futuro_google.result()
        datos_osm = futuro_osm.result()
        datos_macarfi = futuro_macarfi.result()

    restaurantes = [crear_restaurante_google(datos) for datos in datos_google]

    for datos in datos_osm:
        restaurante = buscar_coincidencia_osm(restaurantes, datos)
        if restaurante:
            aplicar_osm(restaurante, datos)

    for datos in datos_macarfi:
        restaurante = buscar_coincidencia_macarfi(restaurantes, datos)
        if restaurante:
            aplicar_macarfi(restaurante, datos)

    restaurantes = filtrar_integracion_minima(restaurantes)
    completar_precios_google(restaurantes)
    calcular_valores_globales(restaurantes)

    restaurantes = filtrar_por_precio(restaurantes, filtro_precio)
    restaurantes = filtrar_por_servicio(restaurantes, filtro_servicio)

    return restaurantes
