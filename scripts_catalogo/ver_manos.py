"""Detector de manos en vivo con MediaPipe (API Tasks: HandLandmarker).

Script del catalogo de Uzi: se manda a un esclavo con enviar_archivo_a_pc y se
corre con ejecutar_script_en_pc (background=True, porque abre una ventana que
el usuario cierra a mano). No hace falta pedirle a Claude Code que lo genere
de nuevo cada vez.

Uso:
    python ver_manos.py [--camera N]

Abre la camara, dibuja los landmarks de cada mano detectada y muestra el
conteo en pantalla. Se cierra con 'q' o ESC.

Requiere mediapipe instalado. IMPORTANTE: mediapipe elimino la API vieja
'mediapipe.solutions.hands' en sus releases recientes (0.10.30+ / 1.x) para
Windows/Python nuevos - este script usa la API nueva 'Tasks'
(HandLandmarker), que descarga un modelo .task ~10MB la primera vez que
corre y lo cachea junto a este archivo (carpeta '_models/').
"""

from __future__ import annotations

import argparse
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
    print(
        "mediapipe no esta instalado en esta PC. Instala con: pip install mediapipe",
        file=sys.stderr,
    )
    sys.exit(1)


_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)
_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_models", "hand_landmarker.task")

# Topologia fija de los 21 landmarks de una mano (indices del modelo de
# MediaPipe), para dibujar el "esqueleto" sin depender de mp.solutions
# (que ya no existe en las versiones nuevas).
_HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),          # pulgar
    (0, 5), (5, 6), (6, 7), (7, 8),          # indice
    (5, 9), (9, 10), (10, 11), (11, 12),     # medio
    (9, 13), (13, 14), (14, 15), (15, 16),   # anular
    (13, 17), (17, 18), (18, 19), (19, 20),  # menique
    (0, 17),                                  # base de la palma
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


def _dibujar_mano(frame, landmarks_norm) -> None:
    h, w = frame.shape[:2]
    puntos = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks_norm]
    for a, b in _HAND_CONNECTIONS:
        cv2.line(frame, puntos[a], puntos[b], (0, 255, 0), 2)
    for x, y in puntos:
        cv2.circle(frame, (x, y), 4, (0, 200, 255), -1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", type=int, default=0)
    args = parser.parse_args()

    options = mp_vision.HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=_ensure_model()),
        num_hands=4,
        min_hand_detection_confidence=0.5,
        running_mode=mp_vision.RunningMode.VIDEO,
    )

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"No se pudo abrir la camara {args.camera}", file=sys.stderr)
        sys.exit(1)

    start = time.monotonic()
    last_ts = -1

    try:
        with mp_vision.HandLandmarker.create_from_options(options) as landmarker:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

                ts_ms = int((time.monotonic() - start) * 1000)
                if ts_ms <= last_ts:
                    ts_ms = last_ts + 1
                last_ts = ts_ms

                res = landmarker.detect_for_video(mp_image, ts_ms)

                hands = res.hand_landmarks or []
                for hand_landmarks in hands:
                    _dibujar_mano(frame, hand_landmarks)

                cv2.putText(
                    frame, f"Manos detectadas: {len(hands)}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2,
                )

                cv2.imshow("Uzi - Deteccion de manos (q o ESC para salir)", frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
