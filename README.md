# Arca de Noé: modelo de actores

Simulación educativa en Python y Pygame de un sistema concurrente basado en
actores. Los animales son datos; los actores son las áreas que los procesan.

## Instalación y ejecución

```bash
pip install -r requirements.txt
python arca_actores.py
```

Controles:

- `ESPACIO`: iniciar, pausar o continuar la simulación.
- `R`: cerrar el sistema actual y crear uno nuevo.
- `Flecha derecha`: activar el modo paso a paso y liberar un acontecimiento.
- `ESC`: cerrar.

Los botones permiten las mismas acciones y cambiar progresivamente entre
velocidad lenta (0.5x), normal (1x) y rápida (2x).

La introducción puede omitirse con `ESPACIO` o `ENTER`. El segundo botón activa
el modo paso a paso; **Iniciar** vuelve al modo automático.

También se puede ejecutar una comprobación automática sin abrir la ventana:

```bash
python arca_actores.py --prueba
```

## Actores

- **Recepción:** registra las parejas y reúne las tres respuestas de cada
  especie.
- **Establos:** es el único dueño de la cantidad de lugares disponibles.
- **Depósito:** es el único dueño de la cantidad de raciones.
- **Enfermería:** mantiene la lista privada de especies revisadas.

Cada actor se ejecuta en una hebra propia, retira mensajes FIFO de a uno y solo
modifica su propio estado. La concurrencia se observa cuando Establos, Depósito
y Enfermería muestran al mismo tiempo mensajes distintos en “Procesando”.

La interfaz usa las imágenes de `img/`: las parejas entran por la rampa,
esperan junto a Recepción y, al completar sus tres solicitudes, caminan hasta
Establos. Los sobres animados representan los mismos mensajes que efectivamente
se entregan en los buzones; no son una animación separada de la lógica.

## Buzones y semáforos

Cada buzón tiene capacidad para cuatro mensajes y usa una `deque`, un `Lock` y
dos semáforos. `lugares_libres` comienza en 4: cada envío adquiere un permiso antes
de insertar y cada recepción lo devuelve. `mensajes_disponibles` comienza en 0:
el envío libera un permiso y el receptor lo adquiere antes de retirar.

Si no queda un lugar libre, la operación de envío espera sin perder el mensaje.
La interfaz y la consola muestran `BUZÓN LLENO`; cuando el receptor libera un
espacio, el envío continúa. El `Lock` solo protege el acceso breve a la cola y
nunca se mantiene durante el tiempo de procesamiento.

## Fuentes

La interfaz usa Titillium Web y el título de la introducción usa Jost ExtraBold.
Los archivos se incluyen en `assets/fonts/`; si falta alguno, la aplicación
utiliza automáticamente Arial o una fuente sans-serif del sistema.
