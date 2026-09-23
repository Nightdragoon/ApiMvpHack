"""Controla el mouse con la mano (MediaPipe + PyAutoGUI).

Script del catalogo de Uzi: se manda a un esclavo con enviar_archivo_a_pc y se
corre con ejecutar_script_en_pc (background=True, porque corre indefinidamente
hasta que se cierre con 'q'/ESC en la ventana de vista previa).

Uso:
    python mouse_por_mano.py [--camera N] [--no-preview]
                              [--smoothing 0.35] [--click-cooldown 0.6] [--margin 0.15]

Como funciona:
- Sigue UNA mano con MediaPipe Hands.
- El cursor se mueve con un punto de referencia ESTABLE (promedio de la
  muñeca y los nudillos), no con la punta de un dedo, para que no salte de
  lugar cuando cierras el puño.
- Mano ABIERTA (al menos un dedo extendido) = mueve el cursor.
- Mano CERRADA (puño, cero dedos extendidos) = un clic izquierdo. Solo hace
  clic en el instante en que la mano se cierra (no repite mientras la
  mantengas cerrada) y respeta un cooldown entre clics.
- Ventana de vista previa (activada por default; --no-preview la quita) con
  los landmarks de la mano y el estado detectado. Se cierra con 'q' o ESC.

Requiere mediapipe y pyautogui instalados.
"""

from __future__ import annotations

import argparse
import sys
import time

import cv2

try:
    import mediapipe as mp
except ImportError:
    print("mediapipe no esta instalado. Instala con: pip install mediapipe", file=sys.stderr)
    sys.exit(1)

try:
    import pyautogui
except ImportError:
    print("pyautogui no esta instalado. Instala con: pip install pyautogui", file=sys.stderr)
    sys.exit(1)


# Indices de MediaPipe Hands para cada dedo (excepto el pulgar): (punta, PIP).
_DEDOS = {
    "index": (8, 6),
    "middle": (12, 10),
    "ring": (16, 14),
    "pinky": (20, 18),
}

# Puntos usados como referencia estable del cursor: muñeca + nudillos (MCP).
# A diferencia de la punta de un dedo, no se mueven cuando cierras el puño.
_PUNTOS_REFERENCIA = (0, 5, 9, 13, 17)


def _dedos_extendidos(landmarks) -> int:
    """Cuenta dedos extendidos comparando la altura (y) de la punta contra
    su articulacion PIP; en coordenadas de imagen, 'mas arriba' es 'y' menor."""
    count = 0
    for tip_idx, pip_idx in _DEDOS.values():
        if landmarks[tip_idx].y < landmarks[pip_idx].y - 0.02:
            count += 1
    return count


def _punto_referencia(landmarks) -> tuple[float, float]:
    x = sum(landmarks[i].x for i in _PUNTOS_REFERENCIA) / len(_PUNTOS_REFERENCIA)
    y = sum(landmarks[i].y for i in _PUNTOS_REFERENCIA) / len(_PUNTOS_REFERENCIA)
    return x, y


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
    args = parser.parse_args()

    screen_w, screen_h = pyautogui.size()
    pyautogui.PAUSE = 0  # nosotros controlamos el ritmo (un moveTo por frame)

    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"No se pudo abrir la camara {args.camera}", file=sys.stderr)
        sys.exit(1)

    cur_x, cur_y = screen_w / 2, screen_h / 2
    puno_cerrado_antes = False
    ultimo_click = 0.0
    margin = min(max(args.margin, 0.0), 0.45)

    try:
        with mp_hands.Hands(
            max_num_hands=1, min_detection_confidence=0.6, min_tracking_confidence=0.6
        ) as hands:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                frame = cv2.flip(frame, 1)  # espejo: mas intuitivo al moverse

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                res = hands.process(rgb)

                estado = "sin mano"
                if res.multi_hand_landmarks:
                    hand_landmarks = res.multi_hand_landmarks[0]
                    landmarks = hand_landmarks.landmark
                    if not args.no_preview:
                        mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

                    lx, ly = _punto_referencia(landmarks)
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

                    dedos = _dedos_extendidos(landmarks)
                    puno_cerrado = dedos == 0
                    estado = "PUÑO CERRADO" if puno_cerrado else f"{dedos} dedo(s) extendidos"

                    ahora = time.monotonic()
                    if puno_cerrado and not puno_cerrado_antes and (ahora - ultimo_click) > args.click_cooldown:
                        pyautogui.click()
                        ultimo_click = ahora
                        estado += " -> CLIC"
                    puno_cerrado_antes = puno_cerrado
                else:
                    puno_cerrado_antes = False

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
