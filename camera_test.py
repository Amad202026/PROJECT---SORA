import time

import cv2


CAMERA_INDEX = 0
WINDOW_NAME = "Sora - Camera Test"


def main():
    print(f"OpenCV: {cv2.__version__}")

    if cv2.__version__.split(".")[0] != "5":
        raise RuntimeError("OpenCV 5 is required.")

    camera = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)

    try:
        if not camera.isOpened():
            raise RuntimeError(
                "Unable to open the camera. "
                "Check camera permissions or CAMERA_INDEX."
            )

        # Ini permintaan resolusi; kamera dapat memakai ukuran berbeda.
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

        frame_count = 0
        fps = 0.0
        measurement_start = time.perf_counter()
        reported_size = False

        print("Camera started.")
        print("Click the camera window and press Q to quit.")

        while True:
            success, frame = camera.read()

            if not success or frame is None:
                raise RuntimeError(
                    "Unable to read a camera frame. "
                    "Check the connection or other apps using the camera."
                )

            if not reported_size:
                height, width = frame.shape[:2]
                print(f"Actual resolution: {width} x {height}")
                reported_size = True

            frame_count += 1
            now = time.perf_counter()
            elapsed = now - measurement_start

            if elapsed >= 1.0:
                fps = frame_count / elapsed
                frame_count = 0
                measurement_start = now

            # Balik horizontal agar preview terasa seperti cermin.
            preview = cv2.flip(frame, 1)

            cv2.putText(
                preview,
                f"FPS: {fps:.1f} | Q: quit",
                (15, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )

            cv2.imshow(WINDOW_NAME, preview)

            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), ord("Q")):
                break

            if cv2.getWindowProperty(
                WINDOW_NAME, cv2.WND_PROP_VISIBLE
            ) < 1:
                break

    finally:
        camera.release()
        cv2.destroyAllWindows()
        print("Camera released. Test finished.")


if __name__ == "__main__":
    main()