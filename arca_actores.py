"""
Simulación educativa del modelo de actores aplicada al Arca de Noé.

Los cuatro actores poseen una hebra, un estado privado y un buzón propio.  Pygame
solo se usa desde la hebra principal; las demás hebras publican cambios visuales
en la cola segura ``eventos_ui``.
"""

# 0. IMPORTS
from collections import deque
from itertools import count
from queue import Empty, Queue
from threading import Event, Lock, Semaphore, Thread
from pathlib import Path
import sys
import time

import pygame


# 1. CONFIGURACIÓN VISUAL
ANCHO_BASE = 1536
ALTO_BASE = 1024
# Alias usados por la configuración visual: todo se dibuja en esta superficie
# lógica y luego se escala uniformemente hacia la ventana real.
ANCHO_VENTANA = ANCHO_BASE
ALTO_VENTANA = ALTO_BASE
FPS = 60
CARPETA_PROYECTO = Path(__file__).resolve().parent
CARPETA_IMAGENES = CARPETA_PROYECTO / "img"

RUTA_FUENTE_TEXTO = "assets/fonts/TitilliumWeb-Regular.ttf"
RUTA_FUENTE_SEMIBOLD = "assets/fonts/TitilliumWeb-SemiBold.ttf"
RUTA_FUENTE_BOLD = "assets/fonts/TitilliumWeb-Bold.ttf"
RUTA_FUENTE_TITULO = "assets/fonts/Jost-ExtraBold.ttf"

COLORES = {
    "fondo": (101, 151, 91),
    "panel": (24, 31, 39),
    "panel_claro": (43, 54, 66),
    "texto": (235, 240, 247),
    "texto_suave": (174, 188, 207),
    "borde": (222, 205, 163),
    "sombra": (18, 23, 29),
    "rojo": (235, 76, 76),
    "verde": (80, 205, 135),
    "amarillo": (250, 194, 74),
    "animacion": (255, 236, 130),
}

TAMANO_TITULO_INTRO = 68
TAMANO_TITULO_ACTOR = 22
TAMANO_SUBTITULO = 18
TAMANO_TEXTO = 16
TAMANO_TEXTO_PEQUENO = 14
TAMANO_AVISO = 17

# Posiciones editables del mapa. Ninguna función de dibujo fija por su cuenta
# dónde debe aparecer un edificio.
POSICIONES_ACTORES = {
    "Recepción": {"pos": (346, 70), "tamaño": (282, 198)},
    "Establos": {"pos": (850, 64), "tamaño": (352, 230)},
    "Enfermería": {"pos": (378, 416), "tamaño": (282, 205)},
    "Depósito": {"pos": (900, 416), "tamaño": (282, 205)},
}
POSICIONES_ETIQUETAS = {
    "Recepción": (10, 118),
    "Establos": (1206, 118),
    "Enfermería": (10, 570),
    "Depósito": (1206, 570),
}
TAMANO_ETIQUETA_ACTOR = (320, 166)
POSICIONES_ESPERA_MENSAJES = {
    "Recepción": (680, 285),
    "Establos": (1050, 330),
    "Enfermería": (680, 650),
    "Depósito": (1050, 650),
}
POSICION_ENTRADA = (-90, 326)
DESTINOS_ESPERA_RECEPCION = [
    (563, 262), (621, 314), (538, 365), (666, 358), (666, 269)
]
DESTINOS_ESTABLOS = [
    (973, 275), (1056, 288), (1139, 282), (998, 346), (1107, 352)
]
PROGRESO_RECT = (338, 10, 860, 76)
PANEL_ORDEN_RECT = (13, 230, 237, 314)
PANEL_INFERIOR_RECT = (0, 850, ANCHO_BASE, 174)
PANEL_ESPECIE_RECT = (19, 862, 435, 150)
PANEL_BUZONES_RECT = (467, 862, 448, 150)
PANEL_EVENTOS_RECT = (20, 862, 1496, 145)
POSICION_CONFIRMACIONES = (650, 180)

TAMANO_EDIFICIOS = {
    nombre: datos["tamaño"] for nombre, datos in POSICIONES_ACTORES.items()
}
ANCHO_ANIMAL = 95
ANCHO_MENSAJE = 49
ALTURA_ICONO_BUZON = 23
ANCHO_RECURSO = 18
ANCHO_MINIATURA_ORDEN = 38
CONTROLES_CENTRO_X = ANCHO_BASE // 2
CONTROLES_Y = 785
ALTURA_BOTON = 50
ESPACIO_ENTRE_BOTONES = 10

# Los tiempos son segundos de simulación. El factor de velocidad se aplica en
# la lógica y también en los movimientos de la hebra principal.
TIEMPO_ENTRE_LLEGADAS = 0.5
TIEMPO_MENSAJE = 1.8
TIEMPO_AVISO_BUZON_LLENO = 2.5
TIEMPO_ENTRADA_ANIMAL = 0.4
VELOCIDAD_ANIMALES = 90.0
VELOCIDAD_SIMULACION = 1.0
VELOCIDADES = {"Lento": 0.5, "Normal": 1.0, "Rápido": 2.0}
LUGARES_INICIALES = 10
RACIONES_INICIALES = 10
ANIMALES_TOTALES = 10
BUZON_CAPACIDAD = 4

TIEMPOS_PROCESAMIENTO = {
    "llegada": 1.2,
    "reservar_lugar": 3.5,
    "reservar_comida": 3.5,
    "revisar": 4.0,
    "respuesta_lugar": 0.4,
    "respuesta_comida": 0.4,
    "respuesta_revision": 0.4,
}

PASOS_RECORRIDO = (
    "Llegada",
    "Registro",
    "Solicitudes",
    "Procesamiento",
    "Respuestas",
    "Traslado",
)


# 2. CARGA DE ASSETS
def escalar_por_ancho(imagen, nuevo_ancho):
    proporcion = nuevo_ancho / imagen.get_width()
    nuevo_alto = max(1, int(imagen.get_height() * proporcion))
    return pygame.transform.smoothscale(imagen, (nuevo_ancho, nuevo_alto))


def escalar_por_alto(imagen, nuevo_alto):
    proporcion = nuevo_alto / imagen.get_height()
    nuevo_ancho = max(1, int(imagen.get_width() * proporcion))
    return pygame.transform.smoothscale(imagen, (nuevo_ancho, nuevo_alto))


def cargar_fuente(ruta, tamano, negrita=False):
    """Carga una fuente local o usa Arial/sans-serif como respaldo."""
    ruta = CARPETA_PROYECTO / ruta
    if ruta.is_file():
        try:
            return pygame.font.Font(str(ruta), tamano)
        except pygame.error as error:
            print(f"[FUENTE] No se pudo cargar {ruta.name}: {error}")
    return pygame.font.SysFont("arial,sans-serif", tamano, bold=negrita)


def cargar_fuentes():
    return {
        "intro": cargar_fuente(
            RUTA_FUENTE_TITULO, TAMANO_TITULO_INTRO, True
        ),
        "titulo": cargar_fuente(
            RUTA_FUENTE_BOLD, TAMANO_TITULO_ACTOR, True
        ),
        "normal": cargar_fuente(
            RUTA_FUENTE_TEXTO, TAMANO_TEXTO
        ),
        "negrita": cargar_fuente(
            RUTA_FUENTE_BOLD, TAMANO_SUBTITULO, True
        ),
        "semibold": cargar_fuente(
            RUTA_FUENTE_SEMIBOLD, TAMANO_SUBTITULO, True
        ),
        "pequena": cargar_fuente(
            RUTA_FUENTE_TEXTO, TAMANO_TEXTO_PEQUENO
        ),
        "pequena_negrita": cargar_fuente(
            RUTA_FUENTE_SEMIBOLD, TAMANO_TEXTO_PEQUENO, True
        ),
        "aviso": cargar_fuente(
            RUTA_FUENTE_BOLD, TAMANO_AVISO, True
        ),
    }


def cargar_imagen(
    nombre,
    color_respaldo,
    texto,
    fuente,
    nuevo_ancho=None,
    nuevo_alto=None,
):
    """Carga y escala una imagen; si falta, crea un recurso identificable.

    Esta función se llama exclusivamente desde la hebra principal, después de
    inicializar Pygame.
    """
    ruta = CARPETA_IMAGENES / nombre
    imagen = None
    if ruta.is_file():
        try:
            imagen = pygame.image.load(str(ruta)).convert_alpha()
        except pygame.error as error:
            print(f"[ASSET] No se pudo cargar {ruta.name}: {error}")

    if imagen is None:
        ancho_base = nuevo_ancho or max(32, int((nuevo_alto or 40) * 1.4))
        alto_base = nuevo_alto or max(24, int(ancho_base * 0.7))
        imagen = pygame.Surface((ancho_base, alto_base), pygame.SRCALPHA)
        imagen.fill((*color_respaldo, 235))
        pygame.draw.rect(imagen, COLORES["borde"], imagen.get_rect(), 2, 8)
        etiqueta = fuente.render(texto, True, (20, 25, 30))
        etiqueta_rect = etiqueta.get_rect(center=imagen.get_rect().center)
        imagen.blit(etiqueta, etiqueta_rect)

    if nuevo_ancho is not None:
        return escalar_por_ancho(imagen, nuevo_ancho)
    if nuevo_alto is not None:
        return escalar_por_alto(imagen, nuevo_alto)
    return imagen


def cargar_assets(fuentes):
    """Centraliza nombres reales de archivos y sus tamaños visuales."""
    assets = {
        "fondo": cargar_imagen(
            "fondo_arca.png", COLORES["fondo"], "Fondo del Arca",
            fuentes["normal"], nuevo_ancho=ANCHO_VENTANA
        ),
        "mensaje": cargar_imagen(
            "mensaje.png", (244, 225, 167), "MSG",
            fuentes["pequena"], nuevo_ancho=ANCHO_MENSAJE
        ),
    }
    assets["fondo_real"] = (CARPETA_IMAGENES / "fondo_arca.png").is_file()
    archivos_edificios = {
        "Recepción": "recepcion.png",
        "Establos": "establos.png",
        "Depósito": "deposito.png",
        "Enfermería": "enfermeria.png",
    }
    colores_edificios = {
        "Recepción": (91, 151, 190),
        "Establos": (157, 112, 68),
        "Depósito": (146, 120, 75),
        "Enfermería": (101, 170, 151),
    }
    assets["edificios"] = {
        nombre: cargar_imagen(
            archivo, colores_edificios[nombre], nombre, fuentes["normal"],
            nuevo_ancho=TAMANO_EDIFICIOS[nombre][0]
        )
        for nombre, archivo in archivos_edificios.items()
    }
    assets["animales"] = {}
    for datos in ESPECIES:
        assets["animales"][datos["nombre"]] = [
            cargar_imagen(
                archivo, datos["color"], datos["nombre"][:-1],
                fuentes["pequena"], nuevo_ancho=ANCHO_ANIMAL
            )
            for archivo in datos["archivos"]
        ]
    archivos_botones = {
        "iniciar": "btn_iniciar.png",
        "pausar": "btn_pausar.png",
        "reiniciar": "btn_reiniciar.png",
        "lento": "btn_lento.png",
        "rapido": "btn_rapido.png",
        "paso": "btn_paso.png",
        "cerrar": "btn_cerrar.png",
    }
    assets["botones"] = {
        accion: cargar_imagen(
            archivo, (214, 188, 116), accion.capitalize(),
            fuentes["pequena"], nuevo_alto=ALTURA_BOTON
        )
        for accion, archivo in archivos_botones.items()
    }
    assets["recursos"] = {
        "comida": cargar_imagen(
            "comida.png", (201, 145, 67), "Ración",
            fuentes["pequena"], nuevo_ancho=ANCHO_RECURSO
        ),
        "heno": cargar_imagen(
            "heno.png", (192, 159, 68), "Lugar",
            fuentes["pequena"], nuevo_ancho=ANCHO_RECURSO
        ),
        "botiquin": cargar_imagen(
            "botiquin.png", (205, 225, 218), "OK",
            fuentes["pequena"], nuevo_ancho=ANCHO_RECURSO
        ),
    }
    assets["icono_buzon"] = escalar_por_alto(
        assets["mensaje"], ALTURA_ICONO_BUZON
    )
    assets["miniaturas"] = {
        especie: escalar_por_ancho(imagenes[0], ANCHO_MINIATURA_ORDEN)
        for especie, imagenes in assets["animales"].items()
    }
    return assets


# 3. DATOS Y CONSTANTES
ESPECIES = [
    {
        "nombre": "Elefantes", "color": (118, 160, 181), "cantidad": 2,
        "archivos": ("elefante_1.png", "elefante_2.png"),
    },
    {
        "nombre": "Jirafas", "color": (232, 180, 73), "cantidad": 2,
        "archivos": ("jirafa_1.png", "jirafa_2.png"),
    },
    {
        "nombre": "Hienas", "color": (175, 145, 93), "cantidad": 2,
        "archivos": ("hiena_1.png", "hiena_2.png"),
    },
    {
        "nombre": "Cebras", "color": (205, 211, 218), "cantidad": 2,
        "archivos": ("cebra_1.png", "cebra_2.png"),
    },
    {
        "nombre": "Leones", "color": (222, 126, 57), "cantidad": 2,
        "archivos": ("leon_1.png", "leon_2.png"),
    },
]

def centro_actor(nombre):
    x, y = POSICIONES_ACTORES[nombre]["pos"]
    ancho, alto = POSICIONES_ACTORES[nombre]["tamaño"]
    return (x + ancho // 2, y + alto // 2)


POSICIONES_MENSAJES = {
    nombre: centro_actor(nombre) for nombre in POSICIONES_ACTORES
}
POSICIONES_MENSAJES["Exterior"] = (15, 255)

NOMBRES_ACCION = {
    "llegada": "Llegada",
    "reservar_lugar": "Reservar lugar",
    "reservar_comida": "Reservar comida",
    "revisar": "Solicitar revisión",
    "respuesta_lugar": "Respuesta",
    "respuesta_comida": "Respuesta",
    "respuesta_revision": "Respuesta",
}


# 4. LÓGICA CONCURRENTE EXISTENTE
class Buzon:
    """
    Cada buzón utiliza dos semáforos:

    mensajes_disponibles comienza en 0.
    El actor espera cuando no tiene mensajes.

    espacios_libres comienza en 4.
    El emisor espera cuando el buzón está lleno.

    Cuando se agrega un mensaje:
    - se adquiere un espacio;
    - se agrega a la cola;
    - se libera un mensaje disponible.

    Cuando se retira un mensaje:
    - se adquiere un mensaje disponible;
    - se retira de la cola FIFO;
    - se libera un espacio.

    Los Threads generan concurrencia real.
    Los tiempos configurados solamente simulan la duración de cada tarea.
    """

    def __init__(self, nombre, capacidad=BUZON_CAPACIDAD):
        self.nombre = nombre
        self.capacidad = capacidad
        self._mensajes = deque()
        self.espacios_libres = Semaphore(capacidad)
        self.mensajes_disponibles = Semaphore(0)
        self._lock = Lock()
        self._emisores_esperando = 0
        self._cerrado = False
        self.maximo_observado = 0

    def enviar(self, mensaje, finalizar, al_llenarse, al_liberarse):
        """Espera un lugar y agrega exactamente un mensaje.

        Se usan timeouts cortos únicamente para poder observar ``finalizar`` y
        cerrar sin dejar una hebra bloqueada para siempre.
        """
        if finalizar.is_set():
            return False

        esperando = False
        if not self.espacios_libres.acquire(blocking=False):
            with self._lock:
                if self._cerrado:
                    return False
                self._emisores_esperando += 1
                cantidad = len(self._mensajes)
            esperando = True
            al_llenarse(self.nombre, cantidad, self.capacidad)

            while not finalizar.is_set():
                if self.espacios_libres.acquire(timeout=0.05):
                    break
            else:
                with self._lock:
                    self._emisores_esperando -= 1
                return False

        if finalizar.is_set():
            if esperando:
                with self._lock:
                    self._emisores_esperando -= 1
            self.espacios_libres.release()
            return False

        with self._lock:
            if self._cerrado:
                if esperando:
                    self._emisores_esperando -= 1
                self.espacios_libres.release()
                return False
            self._mensajes.append(mensaje)
            self.maximo_observado = max(
                self.maximo_observado, len(self._mensajes)
            )
            if esperando:
                self._emisores_esperando -= 1

        if esperando:
            al_liberarse(self.nombre)
        self.mensajes_disponibles.release()
        return True

    def recibir(self, finalizar, antes_de_retirar=None):
        """Retira un solo mensaje FIFO y devuelve inmediatamente el lugar."""
        while not finalizar.is_set():
            if self.mensajes_disponibles.acquire(timeout=0.05):
                # En modo paso a paso, el mensaje permanece visible en la
                # deque hasta que el expositor habilita la recepción.
                if (
                    antes_de_retirar is not None
                    and not antes_de_retirar()
                ):
                    self.mensajes_disponibles.release()
                    return None
                with self._lock:
                    if self._mensajes:
                        mensaje = self._mensajes.popleft()
                    else:
                        # Un cierre puede liberar el semáforo solo para despertar.
                        mensaje = None
                if mensaje is not None:
                    self.espacios_libres.release()
                    return mensaje
        return None

    def estado(self):
        """Entrega una fotografía segura sin consultar Semaphore._value."""
        with self._lock:
            pendientes = [
                f"{m['accion']}: {m.get('especie', '')}".strip()
                for m in self._mensajes
            ]
            return {
                "cantidad": len(self._mensajes),
                "capacidad": self.capacidad,
                "mensajes": len(self._mensajes),
                "espacios": self.capacidad - len(self._mensajes),
                "pendientes": pendientes,
                "hay_emisor_esperando": self._emisores_esperando > 0,
            }

    def cerrar(self):
        """Despierta receptores y emisores para que puedan observar el cierre."""
        with self._lock:
            self._cerrado = True
            esperando = self._emisores_esperando
        self.mensajes_disponibles.release()
        # No se inspecciona el valor interno de ningún semáforo.
        for _ in range(esperando):
            self.espacios_libres.release()


# 4.1 CLASE ACTOR
class Actor:
    """Unidad activa: hebra + buzón + estado que solo ella modifica."""

    def __init__(self, nombre, sistema, estado_privado, comportamiento):
        self.nombre = nombre
        self.sistema = sistema
        self.estado_privado = estado_privado
        self.comportamiento = comportamiento
        self.buzon = Buzon(nombre)
        self.hebra = Thread(
            target=self.trabajar,
            name=f"Actor-{nombre}",
            daemon=False,
        )

    def iniciar(self):
        self.hebra.start()

    def trabajar(self):
        # La primera fotografía también la publica la hebra del actor; la
        # interfaz nunca lee directamente su estado privado.
        self.publicar_estado()
        while not self.sistema.finalizar.is_set():
            if not self.sistema.esperar_si_pausado():
                break
            mensaje = self.buzon.recibir(
                self.sistema.finalizar,
                self.sistema.esperar_evento_importante,
            )
            if mensaje is None:
                continue
            if not self.sistema.esperar_si_pausado():
                break

            self.sistema.registrar_procesamiento(mensaje["id"])
            descripcion = describir_mensaje(mensaje)
            self.sistema.registrar_evento(
                describir_recepcion(self.nombre, mensaje)
            )
            if mensaje["accion"] in (
                "reservar_lugar", "reservar_comida", "revisar"
            ):
                self.sistema.actualizar_progreso(
                    mensaje["especie"],
                    4,
                    f"{self.nombre} procesa la solicitud",
                    estado=f"{self.nombre} está procesando",
                )
            self.sistema.publicar_ui(
                {"tipo": "procesando", "actor": self.nombre,
                 "texto": descripcion}
            )
            self.sistema.marcar_actor_activo(self.nombre, True)

            # Un actor ejecuta un único comportamiento por vez. Otro actor sí
            # puede estar ejecutando el suyo simultáneamente.
            self.comportamiento(self, mensaje)

            self.sistema.marcar_actor_activo(self.nombre, False)
            self.sistema.publicar_ui(
                {"tipo": "procesando", "actor": self.nombre, "texto": "—"}
            )
            self.publicar_estado()

    def esperar_trabajo(self, mensaje):
        accion = mensaje["accion"]
        duracion = TIEMPOS_PROCESAMIENTO.get(accion, 1.0)
        return self.sistema.dormir_con_progreso(
            actor=self.nombre,
            accion=accion,
            especie=mensaje["especie"],
            segundos=duracion,
        )

    def publicar_estado(self):
        recurso = recurso_actor(self.nombre, self.estado_privado)
        self.sistema.publicar_ui(
            {
                "tipo": "estado_actor",
                "actor": self.nombre,
                "resumen": resumir_estado(self.nombre, self.estado_privado),
                "recurso": recurso,
            }
        )


# 4.2 COMPORTAMIENTO DE CADA ACTOR
def procesar_recepcion(actor, mensaje):
    """Recepción registra llegadas y reúne tres respuestas por especie."""
    sistema = actor.sistema
    estado = actor.estado_privado
    especie = mensaje["especie"]

    if mensaje["accion"] == "llegada":
        if not actor.esperar_trabajo(mensaje):
            return
        estado["registrados"].append(especie)
        estado["respuestas"][especie] = {}
        sistema.registrar_evento(
            f"Recepción registra la pareja de {especie}."
        )
        sistema.actualizar_animal(especie, "En Recepción")
        sistema.actualizar_animal(especie, "Esperando respuestas")
        sistema.actualizar_progreso(
            especie,
            2,
            "Recepción registra la pareja",
            estado="Esperando solicitudes",
            lugar="Recepción",
        )
        actor.publicar_estado()

        # Un único paso oral habilita el grupo de tres solicitudes. Después los
        # tres sobres viajan concurrentemente hacia actores diferentes.
        if not sistema.esperar_evento_importante():
            return
        sistema.actualizar_progreso(
            especie,
            3,
            "Recepción envía las solicitudes",
            estado="Esperando respuestas",
        )
        sistema.enviar_mensaje(
            "Recepción", "Establos", "reservar_lugar", especie, 2,
            controlar_paso=False,
        )
        sistema.enviar_mensaje(
            "Recepción", "Depósito", "reservar_comida", especie, 2,
            controlar_paso=False,
        )
        sistema.enviar_mensaje(
            "Recepción", "Enfermería", "revisar", especie, 2,
            controlar_paso=False,
        )
        return

    if not actor.esperar_trabajo(mensaje):
        return
    tipo = mensaje["accion"]
    estado["respuestas"].setdefault(especie, {})[tipo] = mensaje["aceptado"]

    estados_visuales = {
        "respuesta_lugar": "Lugar reservado",
        "respuesta_comida": "Comida reservada",
        "respuesta_revision": "Revisión completa",
    }
    if mensaje["aceptado"]:
        sistema.actualizar_animal(especie, estados_visuales[tipo])
        textos_confirmacion = {
            "respuesta_lugar": "✓ Lugar reservado",
            "respuesta_comida": "✓ Comida reservada",
            "respuesta_revision": "✓ Revisión completa",
        }
        sistema.publicar_ui(
            {
                "tipo": "confirmacion",
                "especie": especie,
                "texto": textos_confirmacion[tipo],
                "duracion": 3.0,
            }
        )
    else:
        sistema.actualizar_animal(especie, "Solicitud rechazada")
    campos_respuesta = {
        "respuesta_lugar": {"lugar_reservado": mensaje["aceptado"]},
        "respuesta_comida": {"comida_reservada": mensaje["aceptado"]},
        "respuesta_revision": {"revision_completa": mensaje["aceptado"]},
    }
    sistema.actualizar_progreso(
        especie,
        5,
        "Recepción recibe las respuestas",
        estado="Recibiendo respuestas",
        **campos_respuesta[tipo],
    )

    respuestas = estado["respuestas"][especie]
    if len(respuestas) == 3:
        sistema.registrar_evento(
            f"Recepción recibió las tres respuestas para {especie}."
        )
        if not sistema.esperar_evento_importante():
            return
        if all(respuestas.values()):
            sistema.actualizar_animal(especie, "Recorrido terminado")
            sistema.actualizar_progreso(
                especie,
                6,
                "La pareja se traslada a Establos",
                estado="Trasladándose a Establos",
                lugar="Camino a Establos",
            )
            sistema.registrar_evento(
                f"La pareja de {especie} puede trasladarse a Establos."
            )
        else:
            sistema.actualizar_animal(especie, "Terminado con rechazo")
        sistema.marcar_finalizada(especie)
        sistema.registrar_evento(
            f"La pareja de {especie} completó el recorrido."
        )


def procesar_establos(actor, mensaje):
    """Solo Establos puede descontar lugares de su estado privado."""
    if (
        mensaje["accion"] != "reservar_lugar"
        or not actor.esperar_trabajo(mensaje)
    ):
        return
    cantidad = mensaje["cantidad"]
    aceptado = actor.estado_privado["lugares"] >= cantidad
    if aceptado:
        actor.estado_privado["lugares"] -= cantidad
        actor.sistema.registrar_evento(
            f"Establos reserva dos lugares para {mensaje['especie']}."
        )
    else:
        actor.sistema.registrar_evento(
            f"Establos rechaza la reserva para {mensaje['especie']}."
        )
    actor.publicar_estado()
    actor.sistema.enviar_mensaje(
        "Establos", "Recepción", "respuesta_lugar",
        mensaje["especie"], cantidad, aceptado
    )


def procesar_deposito(actor, mensaje):
    """Solo Depósito puede descontar raciones de su estado privado."""
    if (
        mensaje["accion"] != "reservar_comida"
        or not actor.esperar_trabajo(mensaje)
    ):
        return
    cantidad = mensaje["cantidad"]
    aceptado = actor.estado_privado["raciones"] >= cantidad
    if aceptado:
        actor.estado_privado["raciones"] -= cantidad
        actor.sistema.registrar_evento(
            f"Depósito reserva dos raciones para {mensaje['especie']}."
        )
    else:
        actor.sistema.registrar_evento(
            f"Depósito rechaza la comida para {mensaje['especie']}."
        )
    actor.publicar_estado()
    actor.sistema.enviar_mensaje(
        "Depósito", "Recepción", "respuesta_comida",
        mensaje["especie"], cantidad, aceptado
    )


def procesar_enfermeria(actor, mensaje):
    """La lista de revisados pertenece únicamente a Enfermería."""
    if (
        mensaje["accion"] != "revisar"
        or not actor.esperar_trabajo(mensaje)
    ):
        return
    especie = mensaje["especie"]
    actor.estado_privado["revisados"].append(especie)
    actor.sistema.registrar_evento(
        f"Enfermería termina la revisión de {especie}."
    )
    actor.publicar_estado()
    actor.sistema.enviar_mensaje(
        "Enfermería", "Recepción", "respuesta_revision",
        especie, mensaje["cantidad"], True
    )


# 4.3 FUNCIONES DE COMUNICACIÓN
class SistemaActores:
    """Crea los actores y contiene solo infraestructura de comunicación/UI."""

    def __init__(self):
        self.eventos_ui = Queue()
        self.finalizar = Event()
        self.en_ejecucion = Event()
        self.en_ejecucion.set()  # clear significa pausa
        self.modo_paso = Event()
        self._permisos_paso = Semaphore(0)
        self._lock_velocidad = Lock()
        self._velocidad = VELOCIDAD_SIMULACION
        self._ids = count(1)
        self._lock_metricas = Lock()
        self._lock_consola = Lock()
        self._procesados = set()
        self.duplicados = []
        self.finalizadas = set()
        self.actores_activos = set()
        self.max_actores_simultaneos = 0
        self.hubo_buzon_lleno = False
        self.mensajes_liberados = 0
        self.hebras_envio = []
        self.hebra_llegadas = None
        self.iniciado = False

        self.actores = {
            "Recepción": Actor(
                "Recepción", self,
                {"registrados": [], "respuestas": {}},
                procesar_recepcion,
            ),
            "Establos": Actor(
                "Establos", self,
                {"lugares": LUGARES_INICIALES},
                procesar_establos,
            ),
            "Depósito": Actor(
                "Depósito", self,
                {"raciones": RACIONES_INICIALES},
                procesar_deposito,
            ),
            "Enfermería": Actor(
                "Enfermería", self, {"revisados": []}, procesar_enfermeria
            ),
        }
        for actor in self.actores.values():
            actor.iniciar()

    def publicar_ui(self, evento):
        self.eventos_ui.put(evento)

    def registrar_evento(self, texto):
        with self._lock_consola:
            print(texto, flush=True)
        self.publicar_ui({"tipo": "log", "texto": texto})

    def nuevo_mensaje(
        self, origen, destino, accion, especie, cantidad=2, aceptado=None
    ):
        mensaje = {
            "id": next(self._ids),
            "origen": origen,
            "destino": destino,
            "accion": accion,
            "especie": especie,
            "cantidad": cantidad,
        }
        if aceptado is not None:
            mensaje["aceptado"] = aceptado
        return mensaje

    def enviar_mensaje(
        self,
        origen,
        destino,
        accion,
        especie,
        cantidad=2,
        aceptado=None,
        controlar_paso=True,
    ):
        """Inicia una entrega sin bloquear el ciclo de procesamiento del actor.

        La hebra de entrega representa la operación de envío asincrónica. Si el
        buzón está lleno, esa operación espera y el mensaje nunca se pierde.
        Esto también evita un interbloqueo de buzones limitados cuando varios
        actores intentan responder simultáneamente a Recepción.
        """
        mensaje = self.nuevo_mensaje(
            origen, destino, accion, especie, cantidad, aceptado
        )
        hebra = Thread(
            target=self._entregar,
            args=(mensaje, controlar_paso),
            name=f"Envio-{mensaje['id']}",
            daemon=False,
        )
        with self._lock_metricas:
            self.hebras_envio.append(hebra)
        hebra.start()

    def _entregar(self, mensaje, controlar_paso):
        destino = mensaje["destino"]
        buzon = self.actores[destino].buzon

        def al_llenarse(nombre, cantidad, capacidad):
            with self._lock_metricas:
                self.hubo_buzon_lleno = True
            self.publicar_ui(
                {
                    "tipo": "buzon_lleno",
                    "actor": nombre,
                    "duracion": TIEMPO_AVISO_BUZON_LLENO,
                }
            )
            self.publicar_ui(
                {
                    "tipo": "mensaje_esperando",
                    "id": mensaje["id"],
                    "origen": mensaje["origen"],
                    "destino": nombre,
                    "especie": mensaje["especie"],
                    "etiqueta": NOMBRES_ACCION[mensaje["accion"]],
                }
            )
            self.registrar_evento(
                f"El buzón de {nombre} está lleno. "
                f"{mensaje['origen']} espera para enviar el mensaje."
            )

        def al_liberarse(nombre):
            with self._lock_metricas:
                self.mensajes_liberados += 1
            self.publicar_ui(
                {"tipo": "mensaje_liberado", "id": mensaje["id"]}
            )
            self.registrar_evento(
                "Se liberó un espacio. El mensaje entra al buzón "
                f"de {nombre}."
            )

        if controlar_paso and not self.esperar_evento_importante():
            return

        # El mensaje se anuncia a la interfaz antes de la latencia de viaje.
        # La hebra principal anima el sobre; la entrega real ocurre al terminar
        # este mismo tiempo de comunicación.
        self.registrar_evento(describir_envio_natural(mensaje))
        self.publicar_ui(
            {
                "tipo": "animacion",
                "id": mensaje["id"],
                "origen": mensaje["origen"],
                "destino": destino,
                "etiqueta": NOMBRES_ACCION[mensaje["accion"]],
                "especie": mensaje["especie"],
            }
        )
        if not self.dormir_controlado(TIEMPO_MENSAJE):
            return

        enviado = buzon.enviar(
            mensaje, self.finalizar, al_llenarse, al_liberarse
        )
        if not enviado:
            return
        self.publicar_ui(
            {
                "tipo": "mensaje_entregado",
                "id": mensaje["id"],
                "actor": destino,
            }
        )
        self.registrar_evento(
            f"El mensaje entra al buzón de {destino}. "
            "El actor puede continuar."
        )
        if mensaje["accion"] in (
            "reservar_lugar", "reservar_comida", "revisar"
        ):
            self.actualizar_progreso(
                mensaje["especie"],
                3,
                f"La solicitud llegó a {destino}",
            )
        elif mensaje["accion"].startswith("respuesta_"):
            self.actualizar_progreso(
                mensaje["especie"],
                5,
                f"La respuesta de {mensaje['origen']} llegó a Recepción",
            )

    def iniciar_simulacion(self):
        if self.iniciado:
            return
        self.iniciado = True
        self.en_ejecucion.set()
        self.hebra_llegadas = Thread(
            target=self._generar_llegadas,
            name="Generador-llegadas",
            daemon=False,
        )
        self.hebra_llegadas.start()

    def _generar_llegadas(self):
        for orden, datos in enumerate(ESPECIES, start=1):
            if self.finalizar.is_set():
                return
            if not self.esperar_evento_importante():
                return
            especie = datos["nombre"]
            self.actualizar_animal(especie, "Llegando")
            self.actualizar_progreso(
                especie,
                1,
                f"Llegada {orden} de {len(ESPECIES)}: {especie}",
                estado="Entrando al Arca",
                lugar="Entrada",
            )
            ordinales = ("primer", "segundo", "tercer", "cuarto", "quinto")
            self.registrar_evento(
                f"Llega la pareja de {especie} en "
                f"{ordinales[orden - 1]} lugar."
            )
            # El animal es solo estado visual. La espera representa su camino
            # hasta Recepción y no utiliza Pygame desde esta hebra.
            if not self.dormir_controlado(TIEMPO_ENTRADA_ANIMAL):
                return
            self.actualizar_progreso(
                especie,
                1,
                f"{especie} llega a Recepción",
                estado="Esperando registro",
                lugar="Recepción",
            )
            if not self.esperar_evento_importante():
                return
            self.enviar_mensaje(
                "Exterior", "Recepción", "llegada",
                especie, datos["cantidad"], controlar_paso=False
            )
            espera = max(0.0, TIEMPO_ENTRE_LLEGADAS - TIEMPO_ENTRADA_ANIMAL)
            if not self.dormir_controlado(espera):
                return

    def esperar_si_pausado(self):
        while not self.finalizar.is_set():
            if self.en_ejecucion.wait(timeout=0.05):
                return True
        return False

    def dormir_controlado(self, segundos):
        """Sleep interrumpible y pausable, siempre fuera de los Locks."""
        restante = segundos
        while restante > 0 and not self.finalizar.is_set():
            if not self.esperar_si_pausado():
                return False
            paso_real = 0.03
            time.sleep(paso_real)
            restante -= paso_real * self.obtener_velocidad()
        return not self.finalizar.is_set()

    def dormir_con_progreso(self, actor, accion, especie, segundos):
        """Espera real del actor e informa avances sin usar Pygame ni Locks."""
        self.publicar_ui(
            {
                "tipo": "inicio_proceso",
                "actor": actor,
                "accion": accion,
                "especie": especie,
                "duracion": segundos,
            }
        )
        self.publicar_ui(
            {"tipo": "progreso_proceso", "actor": actor, "progreso": 0.0}
        )
        transcurrido = 0.0
        ultimo_evento = time.monotonic()
        while transcurrido < segundos and not self.finalizar.is_set():
            if not self.esperar_si_pausado():
                self.publicar_ui({"tipo": "fin_proceso", "actor": actor})
                return False
            paso_real = 0.03
            time.sleep(paso_real)
            transcurrido = min(
                segundos,
                transcurrido + paso_real * self.obtener_velocidad(),
            )
            ahora = time.monotonic()
            if ahora - ultimo_evento >= 0.1 or transcurrido == segundos:
                self.publicar_ui(
                    {
                        "tipo": "progreso_proceso",
                        "actor": actor,
                        "progreso": transcurrido / segundos,
                    }
                )
                ultimo_evento = ahora

        terminado = not self.finalizar.is_set()
        if terminado:
            self.publicar_ui(
                {"tipo": "progreso_proceso", "actor": actor, "progreso": 1.0}
            )
        self.publicar_ui({"tipo": "fin_proceso", "actor": actor})
        return terminado

    def alternar_pausa(self):
        if self.en_ejecucion.is_set():
            self.en_ejecucion.clear()
            self.registrar_evento("[PAUSA] Simulación pausada")
        else:
            self.en_ejecucion.set()
            self.registrar_evento("[CONTINÚA] Simulación reanudada")

    def obtener_velocidad(self):
        with self._lock_velocidad:
            return self._velocidad

    def cambiar_velocidad(self, velocidad):
        with self._lock_velocidad:
            self._velocidad = velocidad
        # Elegir una velocidad vuelve al modo continuo.
        self.modo_paso.clear()
        self._vaciar_permisos_paso()
        self.en_ejecucion.set()
        self.publicar_ui(
            {
                "tipo": "velocidad",
                "velocidad": velocidad,
                "modo_paso": False,
                "aviso": f"Velocidad: {velocidad:g}x",
            }
        )
        self.registrar_evento(f"[VELOCIDAD] {velocidad:g}x")

    def activar_modo_automatico(self):
        self.modo_paso.clear()
        self._vaciar_permisos_paso()
        self.en_ejecucion.set()
        self.publicar_ui(
            {
                "tipo": "velocidad",
                "velocidad": self.obtener_velocidad(),
                "modo_paso": False,
            }
        )

    def avanzar_paso(self):
        """Habilita un único acontecimiento importante, no un fotograma."""
        activando = not self.modo_paso.is_set()
        if activando:
            self._vaciar_permisos_paso()
        self.modo_paso.set()
        self.en_ejecucion.set()
        self._permisos_paso.release()
        if activando:
            self.publicar_ui(
                {
                    "tipo": "velocidad",
                    "velocidad": self.obtener_velocidad(),
                    "modo_paso": True,
                    "aviso": "Modo paso a paso activado",
                }
            )

    def _vaciar_permisos_paso(self):
        hay_permiso = self._permisos_paso.acquire(blocking=False)
        while hay_permiso:
            hay_permiso = self._permisos_paso.acquire(blocking=False)

    def esperar_evento_importante(self):
        if not self.esperar_si_pausado():
            return False
        while self.modo_paso.is_set() and not self.finalizar.is_set():
            if self._permisos_paso.acquire(timeout=0.05):
                return True
        return not self.finalizar.is_set()

    def actualizar_animal(self, especie, estado):
        self.publicar_ui(
            {"tipo": "estado_animal", "especie": especie, "estado": estado}
        )

    def actualizar_progreso(self, especie, paso, descripcion, **cambios):
        self.publicar_ui(
            {
                "tipo": "progreso",
                "especie": especie,
                "paso": paso,
                "descripcion": descripcion,
                "cambios": cambios,
            }
        )

    def registrar_procesamiento(self, identificador):
        with self._lock_metricas:
            if identificador in self._procesados:
                self.duplicados.append(identificador)
            self._procesados.add(identificador)

    def marcar_actor_activo(self, nombre, activo):
        with self._lock_metricas:
            if activo:
                self.actores_activos.add(nombre)
            else:
                self.actores_activos.discard(nombre)
            self.max_actores_simultaneos = max(
                self.max_actores_simultaneos, len(self.actores_activos)
            )

    def marcar_finalizada(self, especie):
        with self._lock_metricas:
            self.finalizadas.add(especie)

    def cerrar(self):
        self.finalizar.set()
        self.en_ejecucion.set()
        for actor in self.actores.values():
            actor.buzon.cerrar()

    def hebras(self):
        with self._lock_metricas:
            envios = list(self.hebras_envio)
        hebras = [a.hebra for a in self.actores.values()] + envios
        if self.hebra_llegadas is not None:
            hebras.append(self.hebra_llegadas)
        return hebras

    def termino(self):
        return all(not hebra.is_alive() for hebra in self.hebras())


def describir_mensaje(mensaje):
    accion = NOMBRES_ACCION.get(mensaje["accion"], mensaje["accion"])
    return f"{accion}: {mensaje['especie']}"


def describir_envio_natural(mensaje):
    accion = mensaje["accion"]
    especie = mensaje["especie"]
    if accion == "llegada":
        return f"La llegada de {especie} se comunica a Recepción."
    if accion == "reservar_lugar":
        return f"Recepción solicita dos lugares a Establos para {especie}."
    if accion == "reservar_comida":
        return f"Recepción solicita dos raciones a Depósito para {especie}."
    if accion == "revisar":
        return f"Recepción solicita la revisión de {especie} a Enfermería."
    resultado = "aceptada" if mensaje.get("aceptado") else "rechazada"
    return (
        f"{mensaje['origen']} responde a Recepción por {especie}: "
        f"solicitud {resultado}."
    )


def describir_recepcion(nombre, mensaje):
    especie = mensaje["especie"]
    if mensaje["accion"].startswith("respuesta_"):
        return (
            f"Recepción retira la respuesta sobre {especie}. "
            "Se libera un espacio del buzón."
        )
    return (
        f"{nombre} retira un mensaje para {especie}. "
        "Se libera un espacio del buzón."
    )


def recurso_actor(nombre, estado):
    if nombre == "Recepción":
        return {
            "etiqueta": "Registrados",
            "actual": len(estado["registrados"]) * 2,
            "maximo": ANIMALES_TOTALES,
        }
    if nombre == "Establos":
        return {
            "etiqueta": "Lugares",
            "actual": estado["lugares"],
            "maximo": LUGARES_INICIALES,
        }
    if nombre == "Depósito":
        return {
            "etiqueta": "Raciones",
            "actual": estado["raciones"],
            "maximo": RACIONES_INICIALES,
        }
    return {
        "etiqueta": "Revisados",
        "actual": len(estado["revisados"]) * 2,
        "maximo": ANIMALES_TOTALES,
    }


def resumir_estado(nombre, estado):
    recurso = recurso_actor(nombre, estado)
    return (
        f"{recurso['etiqueta']}: "
        f"{recurso['actual']}/{recurso['maximo']}"
    )


# 5. ESTADO VISUAL DE ANIMALES
class AnimalVisual:
    """Pareja visual sin hebra ni participación en la lógica de actores."""

    def __init__(self, especie, imagenes, indice):
        self.especie = especie
        self.imagenes = imagenes
        self.indice = indice
        self.posicion = pygame.Vector2(POSICION_ENTRADA)
        self.destino = pygame.Vector2(POSICION_ENTRADA)
        self.estado = "Esperando para entrar"
        self.velocidad = VELOCIDAD_ANIMALES
        self.visible = False
        self._final_pendiente = False

    def cambiar_estado(self, estado):
        self.estado = estado
        if estado == "Llegando":
            self.visible = True
            self.destino = pygame.Vector2(
                DESTINOS_ESPERA_RECEPCION[self.indice]
            )
        elif estado == "Recorrido terminado":
            self.destino = pygame.Vector2(DESTINOS_ESTABLOS[self.indice])
            self.estado = "Hacia Establos"
            self._final_pendiente = True

    def actualizar(self, delta_simulacion):
        if not self.visible:
            return
        desplazamiento = self.destino - self.posicion
        distancia = desplazamiento.length()
        avance = self.velocidad * delta_simulacion
        if distancia <= avance or distancia == 0:
            self.posicion.update(self.destino)
            if self._final_pendiente:
                self.estado = "Recorrido terminado"
                self._final_pendiente = False
        else:
            self.posicion += desplazamiento.normalize() * avance


# 6. ANIMACIÓN DE MENSAJES
class MensajeVisual:
    """Sobre animado en la hebra principal durante el viaje real del mensaje."""

    def __init__(self, identificador, origen, destino, etiqueta, especie):
        self.identificador = identificador
        self.origen = pygame.Vector2(POSICIONES_MENSAJES[origen])
        self.destino = pygame.Vector2(POSICIONES_MENSAJES[destino])
        self.etiqueta = etiqueta
        self.especie = especie
        self.progreso = 0.0

    def actualizar(self, delta_simulacion):
        self.progreso = min(
            1.0, self.progreso + delta_simulacion / TIEMPO_MENSAJE
        )
        return self.progreso >= 1.0

    def posicion_actual(self):
        # Suavizado simple para que el sobre arranque y llegue sin saltos.
        t = self.progreso * self.progreso * (3.0 - 2.0 * self.progreso)
        return self.origen.lerp(self.destino, t)


# 7. FUNCIONES DE DIBUJO
def dibujar_texto(
    superficie, texto, fuente, color, posicion, ancho_maximo=None
):
    """Dibuja texto y, opcionalmente, lo divide en líneas sencillas."""
    x, y = posicion
    if not ancho_maximo:
        superficie.blit(fuente.render(texto, True, color), (x, y))
        return y + fuente.get_linesize()

    palabras = texto.split()
    linea = ""
    for palabra in palabras:
        candidata = f"{linea} {palabra}".strip()
        if fuente.size(candidata)[0] <= ancho_maximo:
            linea = candidata
        else:
            superficie.blit(fuente.render(linea, True, color), (x, y))
            y += fuente.get_linesize()
            linea = palabra
    if linea:
        superficie.blit(fuente.render(linea, True, color), (x, y))
        y += fuente.get_linesize()
    return y


def acortar_texto(texto, fuente, ancho_maximo):
    if fuente.size(texto)[0] <= ancho_maximo:
        return texto
    recortado = texto
    while recortado and fuente.size(recortado + "…")[0] > ancho_maximo:
        recortado = recortado[:-1]
    return recortado.rstrip() + "…"


def dibujar_mapa(superficie, assets):
    superficie.blit(assets["fondo"], (0, 0))
    if not assets["fondo_real"]:
        # Respaldo sencillo mientras falta fondo_arca.png.
        pygame.draw.rect(
            superficie, (63, 111, 80), (0, 0, ANCHO_VENTANA, 550)
        )
        caminos = [
            [(-20, 270), (250, 270), (570, 275), (970, 150)],
            [(570, 275), (260, 420)],
            [(570, 275), (970, 420)],
        ]
        for puntos in caminos:
            pygame.draw.lines(
                superficie, (207, 187, 141), False, puntos, 58
            )
            pygame.draw.lines(
                superficie, (169, 148, 108), False, puntos, 3
            )
        pygame.draw.rect(superficie, COLORES["panel"], PANEL_INFERIOR_RECT)


def dibujar_actor(superficie, nombre, assets, lleno):
    datos = POSICIONES_ACTORES[nombre]
    posicion = datos["pos"]
    imagen = assets["edificios"][nombre]
    superficie.blit(imagen, posicion)
    if lleno:
        pygame.draw.rect(
            superficie,
            COLORES["rojo"],
            imagen.get_rect(topleft=posicion),
            5,
            border_radius=10,
        )


def dibujar_animales(superficie, animales, fuentes):
    for animal in animales.values():
        if not animal.visible:
            continue
        x, y = animal.posicion
        # Las dos imágenes forman una pareja, pero se superponen levemente para
        # ocupar poco espacio dentro del mapa.
        superficie.blit(animal.imagenes[0], (round(x), round(y)))
        superficie.blit(animal.imagenes[1], (round(x + 40), round(y + 7)))
        texto = f"{animal.especie} · {animal.estado}"
        etiqueta = fuentes["pequena_negrita"].render(
            texto, True, COLORES["texto"]
        )
        fondo = etiqueta.get_rect(midtop=(round(x + 55), round(y + 65)))
        fondo.inflate_ip(10, 5)
        pygame.draw.rect(
            superficie, (*COLORES["panel"], 225), fondo, border_radius=5
        )
        superficie.blit(etiqueta, etiqueta.get_rect(center=fondo.center))


def dibujar_mensajes(superficie, mensajes, assets, fuentes):
    for mensaje in mensajes:
        posicion = mensaje.posicion_actual()
        rect = assets["mensaje"].get_rect(center=posicion)
        superficie.blit(assets["mensaje"], rect)
        etiqueta = fuentes["pequena"].render(
            f"{mensaje.etiqueta} · {mensaje.especie}",
            True,
            COLORES["texto"],
        )
        etiqueta_rect = etiqueta.get_rect(
            midbottom=(rect.centerx, rect.top - 3)
        )
        fondo = etiqueta_rect.inflate(8, 4)
        pygame.draw.rect(
            superficie, (*COLORES["panel"], 225), fondo, border_radius=4
        )
        superficie.blit(etiqueta, etiqueta_rect)


def dibujar_recurso_actor(
    superficie, nombre, recurso, assets, posicion
):
    if recurso is None:
        return
    x, y = posicion
    actual = recurso["actual"]
    maximo = recurso["maximo"]
    for indice in range(maximo):
        icono_x = x + indice * 15
        activo = indice < actual
        if nombre == "Establos":
            color = (229, 211, 161) if activo else (65, 58, 51)
            pygame.draw.rect(
                superficie, color, (icono_x, y, 12, 12), border_radius=2
            )
            pygame.draw.rect(
                superficie, COLORES["borde"],
                (icono_x, y, 12, 12), 1, border_radius=2
            )
        elif nombre == "Depósito":
            icono = assets["recursos"]["comida"].copy()
            icono.set_alpha(255 if activo else 55)
            superficie.blit(icono, (icono_x, y - 2))
        else:
            color = COLORES["verde"] if activo else (70, 75, 77)
            pygame.draw.circle(
                superficie, color, (icono_x + 6, y + 6), 5
            )
            pygame.draw.circle(
                superficie, COLORES["borde"],
                (icono_x + 6, y + 6), 5, 1
            )


def descripcion_trabajo(nombre, accion, especie):
    descripciones = {
        "llegada": f"Registrando la pareja de {especie}",
        "reservar_lugar": f"Preparando lugar para {especie}",
        "reservar_comida": f"Preparando comida para {especie}",
        "revisar": f"Revisando {especie}",
        "respuesta_lugar": f"Guardando respuesta de Establos",
        "respuesta_comida": f"Guardando respuesta de Depósito",
        "respuesta_revision": f"Guardando respuesta de Enfermería",
    }
    return descripciones.get(accion, f"{nombre} procesa {especie}")


def dibujar_slots_buzon(superficie, estado, assets, posicion):
    x, y = posicion
    icono = assets["icono_buzon"]
    for indice in range(estado["capacidad"]):
        slot = pygame.Rect(x + indice * 27, y, 24, 21)
        pygame.draw.rect(
            superficie, COLORES["panel_claro"], slot, border_radius=3
        )
        pygame.draw.rect(
            superficie, COLORES["borde"], slot, 1, border_radius=3
        )
        if indice < estado["cantidad"]:
            superficie.blit(icono, icono.get_rect(center=slot.center))


def dibujar_buzones(superficie, sistema, vista, assets, fuentes):
    for nombre, actor in sistema.actores.items():
        estado = actor.buzon.estado()
        vista_actor = vista["actores"][nombre]
        x, y = POSICIONES_ETIQUETAS[nombre]
        ancho, alto = TAMANO_ETIQUETA_ACTOR
        lleno = estado["espacios"] == 0
        color_borde = COLORES["rojo"] if lleno else COLORES["borde"]
        panel = pygame.Surface((ancho, alto), pygame.SRCALPHA)
        panel.fill((*COLORES["panel"], 218))
        superficie.blit(panel, (x, y))
        pygame.draw.rect(
            superficie, color_borde, (x, y, ancho, alto), 2, 8
        )

        nombre_texto = nombre.upper()
        dibujar_texto(
            superficie, nombre_texto, fuentes["titulo"],
            color_borde, (x + 10, y + 5)
        )
        dibujar_slots_buzon(
            superficie, estado, assets, (x + ancho - 120, y + 8)
        )

        resumen = vista_actor["resumen"]
        dibujar_texto(
            superficie,
            f"{resumen}   ·   Buzón: "
            f"{estado['cantidad']}/{estado['capacidad']}",
            fuentes["pequena_negrita"], COLORES["texto"],
            (x + 10, y + 37)
        )

        color_mensajes = (
            COLORES["verde"] if estado["mensajes"] > 0 else (115, 120, 125)
        )
        color_espacios = (
            COLORES["verde"] if estado["espacios"] > 0 else COLORES["rojo"]
        )
        pygame.draw.circle(
            superficie, color_mensajes, (x + 17, y + 66), 6
        )
        dibujar_texto(
            superficie, f"MENSAJES: {estado['mensajes']}",
            fuentes["pequena_negrita"], color_mensajes, (x + 29, y + 57)
        )
        pygame.draw.circle(
            superficie, color_espacios, (x + 174, y + 66), 6
        )
        dibujar_texto(
            superficie, f"ESPACIOS: {estado['espacios']}",
            fuentes["pequena_negrita"], color_espacios, (x + 186, y + 57)
        )
        dibujar_texto(
            superficie,
            f"Mensajes + espacios = {estado['capacidad']}",
            fuentes["pequena"], COLORES["texto_suave"], (x + 10, y + 79)
        )

        if vista_actor["trabajando"]:
            accion = descripcion_trabajo(
                nombre, vista_actor["accion"], vista_actor["especie"]
            )
            dibujar_texto(
                superficie, accion, fuentes["pequena_negrita"],
                COLORES["amarillo"], (x + 10, y + 100), ancho - 20
            )
            progreso = max(0.0, min(1.0, vista_actor["progreso"]))
            barra = pygame.Rect(x + 10, y + 124, ancho - 70, 14)
            pygame.draw.rect(
                superficie, COLORES["panel_claro"], barra, border_radius=5
            )
            relleno = barra.copy()
            relleno.width = round(barra.width * progreso)
            if relleno.width > 0:
                pygame.draw.rect(
                    superficie, COLORES["amarillo"],
                    relleno, border_radius=5
                )
            dibujar_texto(
                superficie, f"{round(progreso * 100)} %",
                fuentes["pequena_negrita"], COLORES["texto"],
                (barra.right + 7, y + 119)
            )
            dibujar_texto(
                superficie,
                f"{estado['cantidad']} mensajes pendientes",
                fuentes["pequena"], COLORES["texto_suave"],
                (x + 10, y + 143)
            )
        else:
            texto_inactivo = (
                "Esperando mensajes" if estado["mensajes"] == 0
                else "El actor puede continuar"
            )
            dibujar_texto(
                superficie, texto_inactivo, fuentes["pequena_negrita"],
                COLORES["texto_suave"], (x + 10, y + 111)
            )
            if lleno:
                dibujar_texto(
                    superficie, "El emisor debe esperar",
                    fuentes["pequena_negrita"], COLORES["rojo"],
                    (x + 10, y + 137)
                )


def dibujar_mensajes_esperando(superficie, vista, assets, fuentes):
    agrupados = {}
    for mensaje in vista["mensajes_esperando"].values():
        destino = mensaje["destino"]
        indice = agrupados.get(destino, 0)
        agrupados[destino] = indice + 1
        x, y = POSICIONES_ESPERA_MENSAJES[destino]
        y += indice * 34
        superficie.blit(
            assets["mensaje"],
            assets["mensaje"].get_rect(center=(x, y)),
        )
        texto = fuentes["aviso"].render(
            "ESPERANDO ESPACIO", True, COLORES["rojo"]
        )
        fondo = texto.get_rect(midleft=(x + 25, y))
        panel = fondo.inflate(8, 5)
        pygame.draw.rect(
            superficie, (*COLORES["panel"], 230), panel, border_radius=4
        )
        superficie.blit(texto, fondo)


def dibujar_confirmaciones(superficie, vista, fuentes):
    x, y = POSICION_CONFIRMACIONES
    for indice, confirmacion in enumerate(vista["confirmaciones"][-3:]):
        texto = fuentes["pequena_negrita"].render(
            f"{confirmacion['texto']} · {confirmacion['especie']}",
            True,
            COLORES["verde"],
        )
        rect = texto.get_rect(topleft=(x, y + indice * 27))
        fondo = rect.inflate(12, 6)
        panel = pygame.Surface((fondo.width, fondo.height), pygame.SRCALPHA)
        panel.fill((*COLORES["panel"], 220))
        superficie.blit(panel, fondo)
        superficie.blit(texto, rect)


def dibujar_orden_llegada(superficie, vista, assets, fuentes):
    x, y, ancho, alto = PANEL_ORDEN_RECT
    panel = pygame.Surface((ancho, alto), pygame.SRCALPHA)
    panel.fill((*COLORES["panel"], 210))
    superficie.blit(panel, (x, y))
    pygame.draw.rect(
        superficie, COLORES["borde"], PANEL_ORDEN_RECT, 1, border_radius=7
    )
    dibujar_texto(
        superficie, "ORDEN DE LLEGADA", fuentes["pequena_negrita"],
        COLORES["amarillo"], (x + 9, y + 8)
    )
    vista["rects_especies"] = {}
    llegada_actual = vista["ultima_llegada"]
    for indice, datos in enumerate(ESPECIES):
        fila = pygame.Rect(x + 7, y + 31 + indice * 39, ancho - 14, 35)
        vista["rects_especies"][datos["nombre"]] = fila
        if indice == llegada_actual:
            pygame.draw.rect(
                superficie, (111, 86, 42), fila, border_radius=5
            )
            color = COLORES["amarillo"]
        elif llegada_actual is not None and indice < llegada_actual:
            color = (105, 111, 113)
        else:
            color = COLORES["texto"]
        miniatura = assets["miniaturas"][datos["nombre"]].copy()
        if llegada_actual is not None and indice < llegada_actual:
            miniatura.set_alpha(80)
        superficie.blit(
            miniatura,
            miniatura.get_rect(midleft=(fila.x + 25, fila.centery)),
        )
        dibujar_texto(
            superficie, f"{indice + 1}. {datos['nombre']}",
            fuentes["pequena_negrita"], color,
            (fila.x + 48, fila.y + 9)
        )


def dibujar_progreso(superficie, vista, fuentes):
    x, y, ancho, alto = PROGRESO_RECT
    panel = pygame.Surface((ancho, alto), pygame.SRCALPHA)
    panel.fill((*COLORES["panel"], 220))
    superficie.blit(panel, (x, y))
    seguimiento = vista["seguimiento"][vista["seleccionada"]]
    paso_actual = seguimiento["paso"]
    nombre_paso = (
        PASOS_RECORRIDO[paso_actual - 1].upper()
        if paso_actual else "ESPERANDO"
    )
    encabezado = (
        f"{vista['seleccionada'].upper()} · "
        f"PASO {paso_actual or 0} DE 6 · {nombre_paso}"
    )
    texto_encabezado = fuentes["titulo"].render(
        encabezado, True, COLORES["amarillo"]
    )
    superficie.blit(
        texto_encabezado,
        texto_encabezado.get_rect(midtop=(x + ancho // 2, y + 7)),
    )
    descripcion = seguimiento["descripcion"] or "Esperando el inicio"
    frase = fuentes["normal"].render(
        descripcion, True, COLORES["texto"]
    )
    superficie.blit(
        frase, frase.get_rect(midtop=(x + ancho // 2, y + 43))
    )


def texto_evento_compacto(texto):
    reemplazos = (
        ("[ENVÍO] ", ""),
        ("[RESPUESTA] ", ""),
        ("[RECIBE] ", ""),
        ("[PROCESA] ", ""),
        ("[FINALIZADO] ", ""),
        ("[BUZÓN LLENO] ", "LLENO: "),
        (" | ", ": "),
    )
    for anterior, nuevo in reemplazos:
        texto = texto.replace(anterior, nuevo)
    return texto


def dibujar_panel_inferior(superficie, vista, fuentes):
    eventos_x, eventos_y = PANEL_EVENTOS_RECT[:2]
    panel = pygame.Surface(
        (PANEL_EVENTOS_RECT[2], PANEL_EVENTOS_RECT[3]), pygame.SRCALPHA
    )
    panel.fill((*COLORES["panel"], 220))
    superficie.blit(panel, (eventos_x, eventos_y))
    pygame.draw.rect(
        superficie, COLORES["panel_claro"],
        PANEL_EVENTOS_RECT, 1, border_radius=7
    )
    dibujar_texto(
        superficie, "ÚLTIMOS EVENTOS", fuentes["titulo"],
        COLORES["amarillo"], (eventos_x + 16, eventos_y + 8)
    )
    eventos = list(vista["eventos"])[:6]
    ancho_columna = (PANEL_EVENTOS_RECT[2] - 48) // 2
    for indice, evento in enumerate(eventos):
        columna = indice // 3
        fila = indice % 3
        dibujar_texto(
            superficie, texto_evento_compacto(evento),
            fuentes["pequena"], COLORES["texto_suave"],
            (
                eventos_x + 16 + columna * (ancho_columna + 16),
                eventos_y + 41 + fila * 33,
            ),
            ancho_columna - 10,
        )


def dibujar_botones(superficie, assets, mouse_logico):
    botones = {}
    orden = [
        "iniciar", "paso", "pausar", "reiniciar",
        "lento", "rapido", "cerrar",
    ]
    ancho_total = sum(
        assets["botones"][accion].get_width() for accion in orden
    ) + ESPACIO_ENTRE_BOTONES * (len(orden) - 1)
    x = CONTROLES_CENTRO_X - ancho_total // 2
    for accion in orden:
        imagen = assets["botones"][accion]
        rect = imagen.get_rect(topleft=(x, CONTROLES_Y))
        botones[accion] = rect
        superficie.blit(imagen, rect)
        if rect.collidepoint(mouse_logico):
            pygame.draw.rect(
                superficie, COLORES["amarillo"], rect, 2, 6
            )
        x = rect.right + ESPACIO_ENTRE_BOTONES
    return botones


def dibujar_aviso_temporal(superficie, vista, fuentes):
    aviso = vista["aviso_temporal"]
    if aviso is None:
        return
    texto = fuentes["aviso"].render(
        aviso["texto"], True, COLORES["amarillo"]
    )
    rect = texto.get_rect(
        midbottom=(CONTROLES_CENTRO_X, CONTROLES_Y - 8)
    )
    fondo = rect.inflate(20, 10)
    panel = pygame.Surface((fondo.width, fondo.height), pygame.SRCALPHA)
    panel.fill((*COLORES["panel"], 225))
    superficie.blit(panel, fondo)
    superficie.blit(texto, rect)


def actualizar_animales(animales, delta_simulacion):
    for animal in animales.values():
        animal.actualizar(delta_simulacion)


def actualizar_mensajes(mensajes, delta_simulacion):
    return [
        mensaje for mensaje in mensajes
        if not mensaje.actualizar(delta_simulacion)
    ]


# 8. CONTROLES
def obtener_accion_control(
    evento, botones, rects_especies, posicion_mouse=None
):
    if evento.type == pygame.QUIT:
        return "cerrar"
    if evento.type == pygame.KEYDOWN:
        teclas = {
            pygame.K_ESCAPE: "cerrar",
            pygame.K_SPACE: "espacio",
            pygame.K_r: "reiniciar",
            pygame.K_RIGHT: "paso",
        }
        return teclas.get(evento.key)
    if evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
        posicion = posicion_mouse or evento.pos
        for accion, rect in botones.items():
            if rect.collidepoint(posicion):
                return accion
        for especie, rect in rects_especies.items():
            if rect.collidepoint(posicion):
                return f"seleccionar:{especie}"
    return None


def control_espacio(sistema):
    if sistema.iniciado:
        sistema.alternar_pausa()
    else:
        sistema.activar_modo_automatico()
        sistema.iniciar_simulacion()


def control_iniciar(sistema):
    sistema.activar_modo_automatico()
    if not sistema.iniciado:
        sistema.iniciar_simulacion()


def control_pausa(sistema):
    sistema.alternar_pausa()


def control_mas_lento(sistema):
    actual = sistema.obtener_velocidad()
    nueva = (
        VELOCIDADES["Lento"] if actual <= VELOCIDADES["Normal"]
        else VELOCIDADES["Normal"]
    )
    sistema.cambiar_velocidad(nueva)


def control_mas_rapido(sistema):
    actual = sistema.obtener_velocidad()
    nueva = (
        VELOCIDADES["Rápido"] if actual >= VELOCIDADES["Normal"]
        else VELOCIDADES["Normal"]
    )
    sistema.cambiar_velocidad(nueva)


def control_paso(sistema):
    sistema.avanzar_paso()
    if not sistema.iniciado:
        sistema.iniciar_simulacion()


def aplicar_control(accion, sistema):
    if accion in ("cerrar", "reiniciar"):
        return accion
    controles = {
        "espacio": control_espacio,
        "iniciar": control_iniciar,
        "pausar": control_pausa,
        "lento": control_mas_lento,
        "rapido": control_mas_rapido,
        "paso": control_paso,
    }
    controlador = controles.get(accion)
    if controlador is not None:
        controlador(sistema)
    return "continuar"


# 9. CREACIÓN DEL SISTEMA
def crear_vista_inicial(assets):
    return {
        "actores": {
            nombre: {
                "resumen": "Estado: cargando…",
                "procesando": "—",
                "recurso": None,
                "trabajando": False,
                "accion": None,
                "especie": None,
                "progreso": 0.0,
            }
            for nombre in POSICIONES_ACTORES
        },
        "animales": {
            datos["nombre"]: AnimalVisual(
                datos["nombre"],
                assets["animales"][datos["nombre"]],
                indice,
            )
            for indice, datos in enumerate(ESPECIES)
        },
        "eventos": deque(maxlen=8),
        "mensajes": [],
        "mensajes_esperando": {},
        "confirmaciones": [],
        "avisos_lleno": dict.fromkeys(POSICIONES_ACTORES, 0.0),
        "destellos_buzon": dict.fromkeys(POSICIONES_ACTORES, 0.0),
        "velocidad": VELOCIDAD_SIMULACION,
        "modo_paso": False,
        "aviso_temporal": None,
        "seguimiento": {
            datos["nombre"]: {
                "orden": indice + 1,
                "paso": 0,
                "descripcion": "",
                "estado": "Esperando su turno",
                "lugar": "Fuera del Arca",
                "lugar_reservado": None,
                "comida_reservada": None,
                "revision_completa": None,
            }
            for indice, datos in enumerate(ESPECIES)
        },
        "seleccionada": ESPECIES[0]["nombre"],
        "seleccion_manual": False,
        "ultima_llegada": None,
        "rects_especies": {},
    }


def aplicar_progreso_ui(evento, vista):
    especie = evento["especie"]
    seguimiento = vista["seguimiento"][especie]
    if evento["paso"] >= seguimiento["paso"]:
        seguimiento["paso"] = evento["paso"]
        seguimiento["descripcion"] = evento["descripcion"]
    seguimiento.update(evento["cambios"])
    nueva_llegada = (
        evento["paso"] == 1
        and evento["cambios"].get("estado") == "Entrando al Arca"
    )
    if nueva_llegada:
        vista["ultima_llegada"] = seguimiento["orden"] - 1
        if not vista["seleccion_manual"]:
            vista["seleccionada"] = especie


def aplicar_aviso_temporal(evento, vista):
    aviso = evento.get("aviso")
    if aviso:
        vista["aviso_temporal"] = {
            "texto": aviso,
            "restante": 1.0,
        }


def aplicar_evento_ui(evento, vista):
    tipo = evento["tipo"]
    if tipo == "log":
        vista["eventos"].appendleft(evento["texto"])
    elif tipo == "estado_actor":
        vista["actores"][evento["actor"]]["resumen"] = evento["resumen"]
        vista["actores"][evento["actor"]]["recurso"] = evento["recurso"]
    elif tipo == "procesando":
        vista["actores"][evento["actor"]]["procesando"] = evento["texto"]
    elif tipo == "estado_animal":
        vista["animales"][evento["especie"]].cambiar_estado(evento["estado"])
    elif tipo == "animacion":
        vista["mensajes"].append(
            MensajeVisual(
                evento["id"], evento["origen"], evento["destino"],
                evento["etiqueta"], evento["especie"],
            )
        )
    elif tipo == "mensaje_esperando":
        vista["mensajes_esperando"][evento["id"]] = evento
    elif tipo == "mensaje_liberado":
        vista["mensajes_esperando"].pop(evento["id"], None)
    elif tipo == "buzon_lleno":
        vista["avisos_lleno"][evento["actor"]] = max(
            vista["avisos_lleno"][evento["actor"]], evento["duracion"]
        )
    elif tipo == "mensaje_entregado":
        vista["mensajes_esperando"].pop(evento["id"], None)
        vista["destellos_buzon"][evento["actor"]] = 0.65
    elif tipo == "velocidad":
        vista["velocidad"] = evento["velocidad"]
        vista["modo_paso"] = evento["modo_paso"]
        aplicar_aviso_temporal(evento, vista)
    elif tipo == "progreso":
        aplicar_progreso_ui(evento, vista)
    elif tipo == "inicio_proceso":
        estado = vista["actores"][evento["actor"]]
        estado["trabajando"] = True
        estado["accion"] = evento["accion"]
        estado["especie"] = evento["especie"]
        estado["progreso"] = 0.0
    elif tipo == "progreso_proceso":
        vista["actores"][evento["actor"]]["progreso"] = evento["progreso"]
    elif tipo == "fin_proceso":
        estado = vista["actores"][evento["actor"]]
        estado["trabajando"] = False
        estado["accion"] = None
        estado["especie"] = None
        estado["progreso"] = 0.0
    elif tipo == "confirmacion":
        vista["confirmaciones"].append(
            {
                "especie": evento["especie"],
                "texto": evento["texto"],
                "restante": evento["duracion"],
            }
        )


def procesar_eventos_ui(sistema, vista):
    while True:
        try:
            evento = sistema.eventos_ui.get_nowait()
        except Empty:
            break
        aplicar_evento_ui(evento, vista)


def probar_espera_de_buzon():
    """Fuerza de forma determinista un quinto envío sobre capacidad cuatro."""
    buzon = Buzon("Prueba")
    finalizar = Event()
    resultado = {"lleno": False, "liberado": False}

    def al_llenarse(_nombre, _cantidad, _capacidad):
        resultado["lleno"] = True

    def al_liberarse(_nombre):
        resultado["liberado"] = True

    for identificador in range(BUZON_CAPACIDAD):
        mensaje = {
            "id": identificador,
            "accion": "prueba",
            "especie": "Prueba",
        }
        assert buzon.enviar(
            mensaje, finalizar, al_llenarse, al_liberarse
        )

    mensaje_extra = {
        "id": BUZON_CAPACIDAD,
        "accion": "prueba",
        "especie": "Prueba",
    }
    emisor = Thread(
        target=buzon.enviar,
        args=(
            mensaje_extra,
            finalizar,
            al_llenarse,
            al_liberarse,
        ),
    )
    emisor.start()
    time.sleep(0.08)
    assert emisor.is_alive(), "El quinto emisor no esperó"
    assert buzon.recibir(finalizar) is not None
    emisor.join(timeout=2)
    assert not emisor.is_alive(), "El emisor no ingresó al liberarse espacio"
    assert buzon.estado()["cantidad"] == BUZON_CAPACIDAD
    for _ in range(BUZON_CAPACIDAD):
        assert buzon.recibir(finalizar) is not None
    buzon.cerrar()
    return resultado["lleno"] and resultado["liberado"]


def ejecutar_prueba_automatica():
    """Prueba sin ventana para comprobar las propiedades principales."""
    sistema = SistemaActores()
    assert (
        sistema.actores["Establos"].estado_privado["lugares"]
        == LUGARES_INICIALES
    )
    assert (
        sistema.actores["Depósito"].estado_privado["raciones"]
        == RACIONES_INICIALES
    )
    assert all(
        actor.buzon.estado()["cantidad"] == 0
        and actor.buzon.estado()["capacidad"] == BUZON_CAPACIDAD
        for actor in sistema.actores.values()
    )
    # Conserva todas las proporciones temporales, pero evita una prueba de más
    # de un minuto. La interfaz solo ofrece 0.5x, 1x y 2x.
    sistema.cambiar_velocidad(30.0)
    sistema.iniciar_simulacion()
    limite = time.monotonic() + 20
    while time.monotonic() < limite:
        with sistema._lock_metricas:
            completas = len(sistema.finalizadas)
        if completas == len(ESPECIES):
            break
        time.sleep(0.05)

    with sistema._lock_metricas:
        completas = set(sistema.finalizadas)
        duplicados = list(sistema.duplicados)
        max_concurrentes = sistema.max_actores_simultaneos
        lleno = sistema.hubo_buzon_lleno
        liberados = sistema.mensajes_liberados
        procesados = len(sistema._procesados)
    maximos = {
        nombre: actor.buzon.maximo_observado
        for nombre, actor in sistema.actores.items()
    }
    estados_finales = {
        nombre: actor.buzon.estado()
        for nombre, actor in sistema.actores.items()
    }
    hebras_actores = [
        actor.hebra for actor in sistema.actores.values()
    ]
    sistema.cerrar()
    for hebra in sistema.hebras():
        hebra.join(timeout=2)

    esperadas = {datos["nombre"] for datos in ESPECIES}
    assert completas == esperadas, f"Recorridos incompletos: {completas}"
    assert not duplicados, f"Mensajes duplicados: {duplicados}"
    assert procesados == 35, f"Se procesaron {procesados}/35 mensajes"
    assert all(v <= BUZON_CAPACIDAD for v in maximos.values()), maximos
    espera_validada = probar_espera_de_buzon()
    assert espera_validada, "Falló la espera/liberación del buzón"
    if lleno:
        assert liberados > 0, "Un mensaje real quedó esperando"
    assert all(
        estado["cantidad"] == 0 for estado in estados_finales.values()
    ), estados_finales
    assert all(
        not estado["hay_emisor_esperando"]
        for estado in estados_finales.values()
    ), estados_finales
    assert max_concurrentes >= 2, "No se observó trabajo concurrente"
    assert all(not hebra.is_alive() for hebra in hebras_actores)
    assert sistema.termino(), "Quedaron hebras bloqueadas al cerrar"
    print(
        "[PRUEBA OK] recursos 10/10, 5 recorridos, sin duplicados, "
        "buzones <= 4, espera/liberación, concurrencia y cierre correctos."
    )


# 10. BUCLE PRINCIPAL DE PYGAME
def actualizar_vista_visual(sistema, vista, delta_real):
    pausado = not sistema.en_ejecucion.is_set()
    delta_simulacion = (
        0.0 if pausado else delta_real * sistema.obtener_velocidad()
    )
    actualizar_animales(vista["animales"], delta_simulacion)
    for especie, animal in vista["animales"].items():
        seguimiento = vista["seguimiento"][especie]
        if (
            animal.estado == "Recorrido terminado"
            and seguimiento["paso"] == 6
        ):
            seguimiento["estado"] = "Recorrido terminado"
            seguimiento["lugar"] = "Establos"
            seguimiento["descripcion"] = "La pareja llegó a Establos"
    vista["mensajes"] = actualizar_mensajes(
        vista["mensajes"], delta_simulacion
    )
    for nombre in vista["avisos_lleno"]:
        vista["avisos_lleno"][nombre] = max(
            0.0, vista["avisos_lleno"][nombre] - delta_simulacion
        )
        vista["destellos_buzon"][nombre] = max(
            0.0, vista["destellos_buzon"][nombre] - delta_simulacion
        )
    for confirmacion in vista["confirmaciones"]:
        confirmacion["restante"] -= delta_simulacion
    vista["confirmaciones"] = [
        confirmacion for confirmacion in vista["confirmaciones"]
        if confirmacion["restante"] > 0
    ]
    if vista["aviso_temporal"] is not None:
        vista["aviso_temporal"]["restante"] -= delta_real
        if vista["aviso_temporal"]["restante"] <= 0:
            vista["aviso_temporal"] = None


def dibujar_escena(
    pantalla, sistema, vista, assets, fuentes, mouse_logico=(-1, -1)
):
    dibujar_mapa(pantalla, assets)
    for nombre, actor in sistema.actores.items():
        estado_buzon = actor.buzon.estado()
        lleno = (
            estado_buzon["hay_emisor_esperando"]
            or vista["avisos_lleno"][nombre] > 0
        )
        dibujar_actor(pantalla, nombre, assets, lleno)
    dibujar_animales(pantalla, vista["animales"], fuentes)
    dibujar_mensajes(pantalla, vista["mensajes"], assets, fuentes)
    dibujar_mensajes_esperando(pantalla, vista, assets, fuentes)
    dibujar_confirmaciones(pantalla, vista, fuentes)
    dibujar_buzones(pantalla, sistema, vista, assets, fuentes)
    dibujar_progreso(pantalla, vista, fuentes)
    dibujar_panel_inferior(pantalla, vista, fuentes)
    dibujar_aviso_temporal(pantalla, vista, fuentes)
    return dibujar_botones(pantalla, assets, mouse_logico)


def dibujar_intro(pantalla, assets, fuentes, transcurrido):
    pantalla.blit(assets["fondo"], (0, 0))
    if transcurrido < 1.0:
        avance = transcurrido
        escala = 0.35 + 0.65 * (avance * avance * (3 - 2 * avance))
        alpha_titulo = 255
    elif transcurrido < 2.0:
        escala = 1.0
        alpha_titulo = 255
    else:
        escala = 1.0
        alpha_titulo = max(0, int(255 * (3.0 - transcurrido)))

    alpha_fondo = max(0, min(175, alpha_titulo))
    sombra = pygame.Surface(
        (ANCHO_VENTANA, ALTO_VENTANA), pygame.SRCALPHA
    )
    sombra.fill((0, 0, 0, alpha_fondo))
    pantalla.blit(sombra, (0, 0))

    titulo_base = fuentes["intro"].render(
        "EL ARCA CONCURRENTE", True, COLORES["amarillo"]
    )
    ancho = max(1, int(titulo_base.get_width() * escala))
    titulo = escalar_por_ancho(titulo_base, ancho)
    titulo.set_alpha(alpha_titulo)
    pantalla.blit(
        titulo, titulo.get_rect(center=(ANCHO_VENTANA // 2, ALTO_VENTANA // 2))
    )
    return transcurrido >= 3.0


def evento_omite_intro(evento):
    return (
        evento.type == pygame.KEYDOWN
        and evento.key in (pygame.K_SPACE, pygame.K_RETURN)
    )


def manejar_evento_intro(evento, ejecutando, intro_activa):
    if evento.type == pygame.QUIT:
        return False, intro_activa
    if evento_omite_intro(evento):
        return ejecutando, False
    return ejecutando, intro_activa


def manejar_evento_simulacion(
    evento,
    sistema,
    vista,
    assets,
    botones,
    sistemas_cerrando,
    tamano_ventana,
):
    posicion_logica = None
    if evento.type == pygame.MOUSEBUTTONDOWN:
        posicion_logica = ventana_a_logica(evento.pos, tamano_ventana)
    accion = obtener_accion_control(
        evento, botones, vista["rects_especies"], posicion_logica
    )
    if accion and accion.startswith("seleccionar:"):
        vista["seleccionada"] = accion.split(":", 1)[1]
        vista["seleccion_manual"] = True
        return True, sistema, vista

    resultado = aplicar_control(accion, sistema)
    if resultado == "cerrar":
        return False, sistema, vista
    if resultado == "reiniciar":
        # El sistema anterior termina por evento compartido; no hay join en el
        # bucle gráfico y la nueva interfaz parte de cero.
        sistema.cerrar()
        sistemas_cerrando.append(sistema)
        return True, SistemaActores(), crear_vista_inicial(assets)
    return True, sistema, vista


def calcular_tamano_inicial():
    info = pygame.display.Info()
    maximo_ancho = max(1, int(info.current_w * 0.90))
    maximo_alto = max(1, int(info.current_h * 0.88))
    proporcion = ANCHO_BASE / ALTO_BASE
    if maximo_ancho / maximo_alto > proporcion:
        alto = maximo_alto
        ancho = round(alto * proporcion)
    else:
        ancho = maximo_ancho
        alto = round(ancho / proporcion)
    return ancho, alto


def area_logica_en_ventana(tamano_ventana):
    ancho_real, alto_real = tamano_ventana
    escala = min(ancho_real / ANCHO_BASE, alto_real / ALTO_BASE)
    ancho = max(1, round(ANCHO_BASE * escala))
    alto = max(1, round(ALTO_BASE * escala))
    margen_x = (ancho_real - ancho) // 2
    margen_y = (alto_real - alto) // 2
    return escala, pygame.Rect(margen_x, margen_y, ancho, alto)


def ventana_a_logica(posicion, tamano_ventana):
    escala, area = area_logica_en_ventana(tamano_ventana)
    if not area.collidepoint(posicion):
        return (-1, -1)
    return (
        (posicion[0] - area.x) / escala,
        (posicion[1] - area.y) / escala,
    )


def presentar_superficie(pantalla, superficie_logica, tamano_ventana):
    pantalla.fill(COLORES["sombra"])
    _, area = area_logica_en_ventana(tamano_ventana)
    escalada = pygame.transform.smoothscale(
        superficie_logica, (area.width, area.height)
    )
    pantalla.blit(escalada, area)
    pygame.display.flip()


def main():
    if "--prueba" in sys.argv:
        ejecutar_prueba_automatica()
        return

    pygame.init()
    tamano_ventana = calcular_tamano_inicial()
    pantalla = pygame.display.set_mode(tamano_ventana, pygame.RESIZABLE)
    superficie_logica = pygame.Surface((ANCHO_BASE, ALTO_BASE))
    pygame.display.set_caption("Arca de Noé - Modelo de actores")
    reloj = pygame.time.Clock()
    fuentes = cargar_fuentes()
    assets = cargar_assets(fuentes)

    sistema = SistemaActores()
    sistemas_cerrando = []
    vista = crear_vista_inicial(assets)
    botones = {}
    ejecutando = True
    intro_activa = True
    intro_inicio = pygame.time.get_ticks()

    while ejecutando:
        for evento in pygame.event.get():
            if evento.type == pygame.VIDEORESIZE:
                tamano_ventana = (
                    max(640, evento.w),
                    max(426, evento.h),
                )
                pantalla = pygame.display.set_mode(
                    tamano_ventana, pygame.RESIZABLE
                )
                continue
            if intro_activa:
                ejecutando, intro_activa = manejar_evento_intro(
                    evento, ejecutando, intro_activa
                )
            else:
                ejecutando, sistema, vista = manejar_evento_simulacion(
                    evento,
                    sistema,
                    vista,
                    assets,
                    botones,
                    sistemas_cerrando,
                    tamano_ventana,
                )

        if not ejecutando:
            break
        if intro_activa:
            transcurrido = (
                pygame.time.get_ticks() - intro_inicio
            ) / 1000.0
            intro_activa = not dibujar_intro(
                superficie_logica, assets, fuentes, transcurrido
            )
            presentar_superficie(
                pantalla, superficie_logica, tamano_ventana
            )
            reloj.tick(FPS)
            continue

        procesar_eventos_ui(sistema, vista)
        sistemas_cerrando = [
            anterior for anterior in sistemas_cerrando
            if not anterior.termino()
        ]

        actualizar_vista_visual(sistema, vista, reloj.tick(FPS) / 1000.0)
        mouse_logico = ventana_a_logica(
            pygame.mouse.get_pos(), tamano_ventana
        )
        botones = dibujar_escena(
            superficie_logica,
            sistema,
            vista,
            assets,
            fuentes,
            mouse_logico,
        )

        presentar_superficie(
            pantalla, superficie_logica, tamano_ventana
        )

    sistema.cerrar()
    for anterior in sistemas_cerrando:
        anterior.cerrar()
    pygame.quit()


if __name__ == "__main__":
    main()
