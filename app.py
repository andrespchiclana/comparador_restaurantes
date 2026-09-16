import os

from flask import Flask, redirect, render_template, request, url_for

from cache_utils import borrar_cache
from integrador import obtener_restaurantes_integrados


app = Flask(__name__)

MAX_RESULTADOS = 60
RESULTADOS_POR_PAGINA = 15


def construir_query_google(query_user, cocina, zona):
    if query_user:
        return " ".join(t for t in (query_user, zona, "Granada") if t)
    return " ".join(t for t in ("restaurantes", cocina, zona, "Granada") if t)


def pagina_actual():
    try:
        return max(1, int(request.args.get("page", 1)))
    except ValueError:
        return 1


def ordenar_restaurantes(restaurantes, sort):
    if sort == "precio_asc":
        restaurantes.sort(
            key=lambda r: (r.precio.precio_calculado is None, r.precio.precio_calculado or 0,)
        )
    elif sort == "fiabilidad":
        restaurantes.sort(
            key=lambda r: (len(r.fuentes_integradas), r.valoracion.puntuacion_global or 0,), reverse=True,
        )
    else:
        restaurantes.sort(
            key=lambda r: (r.valoracion.puntuacion_global or 0, len(r.fuentes_integradas),), reverse=True,
        )


def tiene_dieta(restaurante, dieta):
    return dieta in restaurante.caracteristicas.opciones_dieteticas


@app.route("/", methods=["GET"])
def index():
    return render_template(
        "index.html",
        cache_borrada=request.args.get("cache") == "borrada",
        cache_eliminada=request.args.get("n", "0"),
    )


@app.route("/borrar-cache", methods=["POST"])
def borrar_cache_route():
    eliminados = borrar_cache()
    return redirect(url_for("index", cache="borrada", n=eliminados))


@app.route("/buscar", methods=["GET"])
def buscar():
    query_user = request.args.get("q", "").strip()
    cocina = request.args.get("cocina", "").strip()
    zona = request.args.get("zona", "").strip()

    restaurantes = obtener_restaurantes_integrados(
        query_google=construir_query_google(query_user, cocina, zona),
        filtro_precio=request.args.get("precio", ""),
        filtro_servicio=request.args.get("servicio", ""),
    )

    if request.args.get("accesibilidad") == "yes":
        restaurantes = [r for r in restaurantes if r.caracteristicas.accesibilidad]
    if request.args.get("abierto") == "yes":
        restaurantes = [r for r in restaurantes if r.horario.abierto is True]
    if request.args.get("vegano") == "yes":
        restaurantes = [r for r in restaurantes if tiene_dieta(r, "Vegano")]
    if request.args.get("vegetariano") == "yes":
        restaurantes = [r for r in restaurantes if tiene_dieta(r, "Vegetariano")]

    ordenar_restaurantes(restaurantes, request.args.get("sort", "puntuacion"))

    restaurantes = restaurantes[:MAX_RESULTADOS]
    total_resultados = len(restaurantes)
    total_paginas = max(1, (total_resultados + RESULTADOS_POR_PAGINA - 1) // RESULTADOS_POR_PAGINA,)
    page = min(pagina_actual(), total_paginas)

    inicio = (page - 1) * RESULTADOS_POR_PAGINA
    resultados_paginados = restaurantes[inicio:inicio + RESULTADOS_POR_PAGINA]

    base_args = request.args.to_dict()
    base_args.pop("page", None)

    return render_template(
        "resultados.html",
        restaurantes=resultados_paginados,
        total_resultados=total_resultados,
        pagina_actual=page,
        total_paginas=total_paginas,
        base_args=base_args,
    )


if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=puerto, debug=True)
