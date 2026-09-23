"""Detector de manos en vivo con MediaPipe.

Script del catalogo de Uzi: se manda a un esclavo con enviar_archivo_a_pc y se
corre con ejecutar_script_en_pc (background=True, porque abre una ventana que
el usuario cierra a mano). No hace falta pedirle a Claude Code que lo genere
de nuevo cada vez.

Uso:
    python ver_manos.py [--camera N]

Abre la camara, dibuja los landmarks de cada mano detectada y muestra el
conteo en pantalla. Se cierra con 'q' o ESC.

Requiere mediapipe instalado.
"""

from __future__ import annotations

import argparse
import sys

import cv2

try:
    import mediapipe as mp
except ImportError:
    print(
        "mediapipe no esta instalado en esta PC. Instala con: pip install mediapipe",
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", type=int, default=0)
    args = parser.parse_args()

    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"No se pudo abrir la camara {args.camera}", file=sys.stderr)
        sys.exit(1)

    try:
        with mp_hands.Hands(max_num_hands=4, min_detection_confidence=0.5) as hands:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                res = hands.process(rgb)

                count = 0
                if res.multi_hand_landmarks:
                    count = len(res.multi_hand_landmarks)
                    for hand_landmarks in res.multi_hand_landmarks:
                        mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

                cv2.putText(
                    frame, f"Manos detectadas: {count}", (10, 30),
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
