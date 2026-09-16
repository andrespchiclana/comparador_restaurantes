from dataclasses import dataclass, field
from typing import List, Optional

import normalizacion as norm


@dataclass
class Ubicacion:
    direccion: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None


@dataclass
class Contacto:
    telefono: Optional[str] = None
    web: Optional[str] = None
    facebook: Optional[str] = None
    instagram: Optional[str] = None


@dataclass
class Horario:
    horario_completo: Optional[str] = None
    horario_hoy: Optional[str] = None
    abierto: Optional[bool] = None
    proximo_cierre: Optional[str] = None

    @property
    def disponible(self) -> bool:
        return bool(self.horario_hoy)

    @property
    def texto_mostrado(self) -> str:
        return self.horario_hoy or "no disponible"


@dataclass
class Caracteristicas:
    tipo_cocina: Optional[str] = None
    accesibilidad: bool = False
    terraza: bool = False
    reserva: bool = False
    menu: Optional[str] = None
    opciones_dieteticas: List[str] = field(default_factory=list)


@dataclass
class Valoracion:
    valoracion_media: Optional[float] = None
    num_valoraciones: Optional[int] = None
    puntuacion_comida: Optional[float] = None
    puntuacion_decoracion: Optional[float] = None
    puntuacion_servicio: Optional[float] = None
    puntuacion_global: Optional[float] = None

    @property
    def puntuacion_google(self) -> Optional[float]:
        if self.valoracion_media is None:
            return None
        return round(self.valoracion_media * 2, 1)

    @property
    def puntuacion_macarfi(self) -> Optional[float]:
        notas = [self.puntuacion_comida, self.puntuacion_decoracion, self.puntuacion_servicio,]
        notas = [nota for nota in notas if nota is not None]
        return round(sum(notas) / len(notas), 1) if notas else None


@dataclass
class Precio:
    coste_estimado: Optional[str] = None
    nivel_precio_google: Optional[int] = None
    rango_precio_google: Optional[str] = None
    precio_google: Optional[float] = None
    precio_calculado: Optional[float] = None
    diferencia: bool = False

    @property
    def precio_macarfi(self) -> Optional[float]:
        return norm.normalizar_precio(self.coste_estimado)

    def _formatear_euros(self, valor) -> Optional[str]:
        if valor is None:
            return None
        return f"{valor:g} €"

    @property
    def texto_precio_macarfi(self) -> Optional[str]:
        return self._formatear_euros(self.precio_macarfi)

    @property
    def texto_precio_google(self) -> Optional[str]:
        if self.rango_precio_google:
            return self.rango_precio_google
        if self.precio_google is not None:
            return f"~{self.precio_google:g} €"
        return None

    @property
    def texto_precio_calculado(self) -> Optional[str]:
        if self.precio_calculado is None:
            return None
        return f"~{self.precio_calculado:g} €"

    @property
    def valor_filtrado(self) -> Optional[float]:
        if self.diferencia:
            return self.precio_calculado

        if self.precio_macarfi is not None:
            return self.precio_macarfi

        if self.precio_google is not None:
            return self.precio_google
        return self.precio_calculado

    @property
    def disponible(self) -> bool:
        return (
            bool(self.coste_estimado)
            or bool(self.rango_precio_google)
            or self.precio_calculado is not None
            or self.precio_google is not None
        )

    @property
    def texto_mostrado(self) -> str:
        if self.diferencia and self.precio_calculado is not None:
            return f"~{self.precio_calculado:g} €"
        if self.coste_estimado:
            return self.coste_estimado
        if self.rango_precio_google:
            return self.rango_precio_google
        if self.precio_google is not None:
            return f"~{self.precio_google:g} €"
        if self.precio_calculado is not None:
            return f"~{self.precio_calculado:g} €"
        return "no disponible"

    @property
    def fuente_mostrada(self) -> Optional[str]:
        if self.diferencia:
            return None
        if self.coste_estimado:
            return "Fuente: Macarfi"
        if self.rango_precio_google or self.precio_google is not None:
            return "Fuente: Google Places"
        return None

    @property
    def aviso_variacion(self) -> bool:
        return self.diferencia and self.precio_calculado is not None


@dataclass
class Restaurante:
    id_restaurante: str
    nombre: str
    ubicacion: Ubicacion = field(default_factory=Ubicacion)
    contacto: Contacto = field(default_factory=Contacto)
    horario: Horario = field(default_factory=Horario)
    caracteristicas: Caracteristicas = field(default_factory=Caracteristicas)
    valoracion: Valoracion = field(default_factory=Valoracion)
    precio: Precio = field(default_factory=Precio)
    fuentes_integradas: List[str] = field(default_factory=list)
    comer_alli: bool = True
    recoger: bool = False

    def __post_init__(self):
        if self.nombre:
            self.nombre = self.nombre.strip()
