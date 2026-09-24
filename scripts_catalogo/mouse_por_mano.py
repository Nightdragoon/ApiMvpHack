"""Controla el mouse con la mano (MediaPipe Tasks + PyAutoGUI).

Script del catalogo de Uzi: se manda a un esclavo con enviar_archivo_a_pc y se
corre con ejecutar_script_en_pc (background=True, porque corre indefinidamente
hasta que se cierre con 'q'/ESC en la ventana de vista previa).

Uso:
    python mouse_por_mano.py [--camera N] [--no-preview]
                              [--smoothing 0.35] [--click-cooldown 0.6] [--margin 0.15]
                              [--scroll-sensitivity 25]

Como funciona:
- Sigue UNA mano con MediaPipe HandLandmarker (API Tasks).
- El cursor se mueve con un punto de referencia ESTABLE (promedio de la
  muñeca y los nudillos), no con la punta de un dedo, para que no salte de
  lugar cuando cierras el puño.
- Mano ABIERTA (al menos un dedo extendido, sin ser un gesto de scroll) =
  mueve el cursor.
- Mano CERRADA (puño, cero dedos extendidos) = un clic izquierdo. Solo hace
  clic en el instante en que la mano se cierra (no repite mientras la
  mantengas cerrada) y respeta un cooldown entre clics.
- Gesto "PISTOLA" (pulgar + índice extendidos, medio/anular/meñique doblados)
  o "DOS DEDOS" (índice + medio extendidos, tipo señal de victoria) = modo
  SCROLL: el cursor se congela donde está y mover la mano arriba/abajo
  scrollea la página (como la ruedita del mouse), sin necesidad de hacer
  clic. Al soltar el gesto, vuelve a mover el cursor normal.
- Ventana de vista previa (activada por default; --no-preview la quita) con
  los landmarks de la mano y el estado detectado. Se cierra con 'q' o ESC.

Requiere mediapipe y pyautogui instalados. IMPORTANTE: mediapipe elimino la
API vieja 'mediapipe.solutions.hands' en sus releases recientes (0.10.30+ /
1.x) para Windows/Python nuevos - este script usa la API nueva 'Tasks'
(HandLandmarker), que descarga un modelo .task ~10MB la primera vez que corre
y lo cachea junto a este archivo (carpeta '_models/').
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
import urllib.request

import cv2

try:
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python import vision as mp_vision
except ImportError:
    print("mediapipe no esta instalado. Instala con: pip install mediapipe", file=sys.stderr)
    sys.exit(1)

try:
    import pyautogui
except ImportError:
    print("pyautogui no esta instalado. Instala con: pip install pyautogui", file=sys.stderr)
    sys.exit(1)


_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)
_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_models", "hand_landmarker.task")

# Indices del modelo de MediaPipe para cada dedo (excepto el pulgar): (punta, PIP).
_DEDOS = {
    "index": (8, 6),
    "middle": (12, 10),
    "ring": (16, 14),
    "pinky": (20, 18),
}

# Puntos usados como referencia estable del cursor: muñeca + nudillos (MCP).
# A diferencia de la punta de un dedo, no se mueven cuando cierras el puño.
_PUNTOS_REFERENCIA = (0, 5, 9, 13, 17)

# Topologia fija de los 21 landmarks de una mano, para dibujar el
# "esqueleto" sin depender de mp.solutions (ya no existe en las versiones nuevas).
_HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
]


def _ensure_model() -> str:
    if os.path.isfile(_MODEL_PATH):
        return _MODEL_PATH
    os.makedirs(os.path.dirname(_MODEL_PATH), exist_ok=True)
    print("Descargando modelo de manos de MediaPipe (una sola vez)...", file=sys.stderr)
    tmp = _MODEL_PATH + ".tmp"
    try:
        urllib.request.urlretrieve(_MODEL_URL, tmp)
        os.replace(tmp, _MODEL_PATH)
    except Exception as exc:
        print(f"No se pudo descargar el modelo de manos: {exc}", file=sys.stderr)
        sys.exit(1)
    return _MODEL_PATH


def _dist(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _dedos_extendidos(landmarks) -> dict:
    """Devuelve {'index': bool, 'middle': bool, 'ring': bool, 'pinky': bool}
    comparando la altura (y) de la punta contra su articulacion PIP; en
    coordenadas de imagen, 'mas arriba' es 'y' menor."""
    return {
        nombre: landmarks[tip_idx].y < landmarks[pip_idx].y - 0.02
        for nombre, (tip_idx, pip_idx) in _DEDOS.items()
    }


def _pulgar_extendido(landmarks) -> bool:
    """El pulgar se dobla hacia los lados, no hacia arriba/abajo como los
    demas dedos, asi que compara distancias en vez de altura: si la punta
    del pulgar (4) esta bastante mas lejos del nudillo del meñique (17) que
    la base del pulgar (2), esta extendido/separado de la palma."""
    tip_dist = _dist(landmarks[4], landmarks[17])
    base_dist = _dist(landmarks[2], landmarks[17])
    return tip_dist > base_dist * 1.15


def _contar_extendidos(dedos: dict) -> int:
    return sum(1 for v in dedos.values() if v)


def _es_pistola(landmarks, dedos: dict, pulgar: bool) -> bool:
    """Pulgar + indice extendidos, medio/anular/meñique doblados."""
    return (
        pulgar
        and dedos["index"]
        and not dedos["middle"]
        and not dedos["ring"]
        and not dedos["pinky"]
    )


def _es_dos_dedos(dedos: dict) -> bool:
    """Indice + medio extendidos (señal de victoria/tijeras), anular y meñique doblados."""
    return dedos["index"] and dedos["middle"] and not dedos["ring"] and not dedos["pinky"]


def _punto_referencia(landmarks) -> tuple[float, float]:
    x = sum(landmarks[i].x for i in _PUNTOS_REFERENCIA) / len(_PUNTOS_REFERENCIA)
    y = sum(landmarks[i].y for i in _PUNTOS_REFERENCIA) / len(_PUNTOS_REFERENCIA)
    return x, y


def _dibujar_mano(frame, landmarks) -> None:
    h, w = frame.shape[:2]
    puntos = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]
    for a, b in _HAND_CONNECTIONS:
        cv2.line(frame, puntos[a], puntos[b], (0, 255, 0), 2)
    for x, y in puntos:
        cv2.circle(frame, (x, y), 4, (0, 200, 255), -1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--no-preview", action="store_true", help="No mostrar la ventana de la camara")
    parser.add_argument("--smoothing", type=float, default=0.35, help="0-1; mas alto = cursor mas suave/lento")
    parser.add_argument("--click-cooldown", type=float, default=0.6, help="Segundos minimos entre clics")
    parser.add_argument(
        "--margin", type=float, default=0.15,
        help="Margen (0-0.45) del cuadro de la camara que ya cuenta como borde de pantalla, "
        "para no tener que llevar la mano hasta el borde real de la imagen",
    )
    parser.add_argument(
        "--scroll-sensitivity", type=float, default=25.0,
        help="Que tanto scrollea por cada tramo que se mueve la mano en modo scroll (mas alto = mas sensible)",
    )
    args = parser.parse_args()

    screen_w, screen_h = pyautogui.size()
    pyautogui.PAUSE = 0  # nosotros controlamos el ritmo (un moveTo por frame)

    options = mp_vision.HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=_ensure_model()),
        num_hands=1,
        min_hand_detection_confidence=0.6,
        min_tracking_confidence=0.6,
        running_mode=mp_vision.RunningMode.VIDEO,
    )

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"No se pudo abrir la camara {args.camera}", file=sys.stderr)
        sys.exit(1)

    cur_x, cur_y = screen_w / 2, screen_h / 2
    # Frames seguidos con el puño cerrado antes de contar como clic: filtra
    # transiciones de un frame (p.ej. al armar el gesto de pistola/dos dedos,
    # la mano puede pasar brevemente por "todo doblado" y se confundia con clic).
    FRAMES_CLIC = 3
    puno_frames = 0
    ultimo_click = 0.0
    margin = min(max(args.margin, 0.0), 0.45)
    start = time.monotonic()
    last_ts = -1

    # Estado del modo scroll: mientras se sostiene el gesto (pistola o dos
    # dedos), el cursor se congela y el movimiento vertical de la mano se
    # traduce en "clicks" de rueda de mouse (acumulados para no perder
    # movimientos chicos entre frames).
    scroll_prev_y = None
    scroll_accum = 0.0

    try:
        with mp_vision.HandLandmarker.create_from_options(options) as landmarker:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                frame = cv2.flip(frame, 1)  # espejo: mas intuitivo al moverse

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

                ts_ms = int((time.monotonic() - start) * 1000)
                if ts_ms <= last_ts:
                    ts_ms = last_ts + 1
                last_ts = ts_ms

                res = landmarker.detect_for_video(mp_image, ts_ms)
                todas_las_manos = res.hand_landmarks or []

                estado = "sin mano"
                if todas_las_manos:
                    landmarks = todas_las_manos[0]
                    if not args.no_preview:
                        _dibujar_mano(frame, landmarks)

                    lx, ly = _punto_referencia(landmarks)
                    dedos = _dedos_extendidos(landmarks)
                    pulgar = _pulgar_extendido(landmarks)
                    modo_scroll = _es_pistola(landmarks, dedos, pulgar) or _es_dos_dedos(dedos)

                    if modo_scroll:
                        # Cursor congelado: no lo movemos mientras se scrollea.
                        if scroll_prev_y is None:
                            scroll_prev_y = ly  # primer frame del gesto: no scrollear de golpe
                        dy = ly - scroll_prev_y
                        # dy > 0 = mano bajo (ly crece hacia abajo). Mano arriba -> scroll hacia abajo
                        # y mano abajo -> scroll hacia arriba (invertido, a pedido).
                        scroll_accum += dy * args.scroll_sensitivity * 10
                        pasos = int(scroll_accum)
                        if pasos != 0:
                            pyautogui.scroll(pasos)
                            scroll_accum -= pasos
                        scroll_prev_y = ly
                        gesto = "PISTOLA" if _es_pistola(landmarks, dedos, pulgar) else "DOS DEDOS"
                        estado = f"SCROLL ({gesto})"
                        puno_frames = 0
                    else:
                        scroll_prev_y = None
                        scroll_accum = 0.0

                        # Mapea el area util de la camara (descontando el margen) a toda la pantalla.
                        nx = (lx - margin) / max(1e-6, (1 - 2 * margin))
                        ny = (ly - margin) / max(1e-6, (1 - 2 * margin))
                        nx = min(max(nx, 0.0), 1.0)
                        ny = min(max(ny, 0.0), 1.0)

                        target_x = min(max(nx * screen_w, 1), screen_w - 2)
                        target_y = min(max(ny * screen_h, 1), screen_h - 2)

                        cur_x += (target_x - cur_x) * (1 - args.smoothing)
                        cur_y += (target_y - cur_y) * (1 - args.smoothing)
                        pyautogui.moveTo(int(cur_x), int(cur_y))

                        num_extendidos = _contar_extendidos(dedos)
                        puno_cerrado = num_extendidos == 0 and not pulgar
                        puno_frames = puno_frames + 1 if puno_cerrado else 0
                        estado = "PUÑO CERRADO" if puno_cerrado else f"{num_extendidos} dedo(s) extendidos"

                        ahora = time.monotonic()
                        if puno_frames == FRAMES_CLIC and (ahora - ultimo_click) > args.click_cooldown:
                            pyautogui.click()
                            ultimo_click = ahora
                            estado += " -> CLIC"
                else:
                    puno_frames = 0
                    scroll_prev_y = None
                    scroll_accum = 0.0

                if not args.no_preview:
                    cv2.putText(
                        frame, f"Mouse por mano: {estado}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2,
                    )
                    cv2.imshow("Uzi - Mouse por mano (q o ESC para salir)", frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (ord("q"), 27):
                        break
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
