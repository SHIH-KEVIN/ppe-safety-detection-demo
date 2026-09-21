"""Minimal camera/video-source connectivity test with no embedded credentials."""

import argparse
import time
import cv2


def parse_source(value: str):
    return int(value) if value.isdigit() else value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="0", help="Webcam index, video path, or RTSP URL")
    args = parser.parse_args()

    cap = cv2.VideoCapture(parse_source(args.source), cv2.CAP_FFMPEG)
    print("opened:", cap.isOpened())
    time.sleep(0.5)

    for i in range(1, 11):
        ok, frame = cap.read()
        print(f"read {i}: {ok}")
        if ok and frame is not None:
            print("shape:", frame.shape)
            break

    cap.release()


if __name__ == "__main__":
    main()
