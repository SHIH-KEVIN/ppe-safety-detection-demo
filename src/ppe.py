from __future__ import annotations

import argparse
import configparser
import json
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import cv2
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEIGHTS = PROJECT_ROOT / "models" / "ppe_hansung.pt"
DEFAULT_WEIGHTS_URL = "https://huggingface.co/Hansung-Cho/yolov8-ppe-detection/resolve/main/best.pt"
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "config.ini"


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_source(value: str):
    return int(value) if str(value).isdigit() else value


def download_file(url: str, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        with dst.open("wb") as fh:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    fh.write(chunk)
    if not dst.exists() or dst.stat().st_size <= 1024:
        raise RuntimeError("模型下載失敗或檔案大小異常")


def ensure_weights(path: Path, url: str) -> Path:
    if path.is_dir():
        return path
    if path.suffix.lower() == ".xml":
        if not path.exists():
            raise FileNotFoundError(path)
        return path.parent
    if path.exists() and path.stat().st_size > 1024:
        return path
    if path.suffix.lower() != ".pt":
        raise FileNotFoundError(path)
    print(f"[INFO] 模型不存在，開始下載：{url}")
    download_file(url, path)
    return path


def iou(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    return inter / (area_a + area_b - inter + 1e-9)


def build_class_map(names: Dict[int, str]) -> Dict[str, Optional[int]]:
    result = {"person": None, "helmet": None, "vest": None, "no_vest": None}
    for idx, raw in names.items():
        name = str(raw).lower().replace("-", "_").replace(" ", "_")
        if name in {"person", "people", "worker"}:
            result["person"] = idx
        elif "helmet" in name and not any(x in name for x in ("no_", "without")):
            result["helmet"] = idx
        elif any(x in name for x in ("vest", "reflective")) and not any(x in name for x in ("no_", "without")):
            result["vest"] = idx
        elif any(x in name for x in ("no_vest", "without_vest")):
            result["no_vest"] = idx
    return result


def load_config(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {}
    cp = configparser.ConfigParser()
    cp.read(path, encoding="utf-8")
    sec = cp["ppe"] if "ppe" in cp else cp["DEFAULT"]
    casts = {
        "source": str, "weights": str, "weights_url": str, "device": str,
        "show": parse_bool, "print_raw": parse_bool, "conf": float, "iou": float,
        "infer_every": int, "resize_w": int, "resize_h": int,
        "head_ratio": float, "torso_top": float, "torso_bottom": float,
        "person_id": int, "helmet_id": int, "vest_id": int,
        "mqtt_enabled": parse_bool, "mqtt_broker": str, "mqtt_port": int,
        "mqtt_topic": str, "mqtt_topic_ok": str, "mqtt_topic_no_helmet": str,
        "mqtt_topic_no_vest": str, "mqtt_topic_no_helmet_no_vest": str,
        "mqtt_username": str, "mqtt_password": str, "mqtt_cooldown": float,
    }
    out: Dict[str, object] = {}
    for key, cast in casts.items():
        if key in sec:
            out[key] = cast(sec[key])
    return out


class MqttPublisher:
    def __init__(self, args):
        self.client = None
        self.cooldown = float(args.mqtt_cooldown)
        self.last_sent: Dict[str, float] = {}
        self.topics = {
            "OK": args.mqtt_topic_ok,
            "NO_HELMET": args.mqtt_topic_no_helmet,
            "NO_VEST": args.mqtt_topic_no_vest,
            "NO_HELMET,NO_VEST": args.mqtt_topic_no_helmet_no_vest,
        }
        if not args.mqtt_enabled:
            return
        import paho.mqtt.client as mqtt
        self.client = mqtt.Client(client_id=f"ppe-demo-{int(time.time())}")
        if args.mqtt_username:
            self.client.username_pw_set(args.mqtt_username, args.mqtt_password or None)
        self.client.connect(args.mqtt_broker, int(args.mqtt_port), 30)
        self.client.loop_start()

    def publish(self, counts: Dict[str, int]) -> None:
        if self.client is None:
            return
        now = time.time()
        for status, count in counts.items():
            topic = self.topics.get(status)
            if not topic or now - self.last_sent.get(topic, 0.0) < self.cooldown:
                continue
            payload = json.dumps({"status": status, "count": count, "ts": int(now)})
            self.client.publish(topic, payload, qos=0, retain=False)
            self.last_sent[topic] = now

    def close(self) -> None:
        if self.client is not None:
            self.client.loop_stop()
            self.client.disconnect()


def selftest() -> None:
    assert parse_bool("true") is True
    assert parse_bool("0") is False
    assert parse_source("0") == 0
    assert abs(iou((0, 0, 10, 10), (0, 0, 10, 10)) - 1.0) < 1e-6
    mapped = build_class_map({0: "person", 1: "helmet", 2: "vest"})
    assert mapped["person"] == 0 and mapped["helmet"] == 1 and mapped["vest"] == 2
    print("[SELFTEST] PASS")


def make_parser(defaults: Dict[str, object]) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="PPE safety detection demo")
    p.add_argument("--config", default=str(DEFAULT_CONFIG))
    p.add_argument("--source", default="0")
    p.add_argument("--weights", default=str(DEFAULT_WEIGHTS))
    p.add_argument("--weights_url", default=DEFAULT_WEIGHTS_URL)
    p.add_argument("--device", default="cpu")
    p.add_argument("--conf", type=float, default=0.35)
    p.add_argument("--iou", type=float, default=0.5)
    p.add_argument("--infer_every", type=int, default=3)
    p.add_argument("--resize_w", type=int, default=960)
    p.add_argument("--resize_h", type=int, default=540)
    p.add_argument("--head_ratio", type=float, default=0.40)
    p.add_argument("--torso_top", type=float, default=0.20)
    p.add_argument("--torso_bottom", type=float, default=0.85)
    p.add_argument("--person_id", type=int, default=-1)
    p.add_argument("--helmet_id", type=int, default=-1)
    p.add_argument("--vest_id", type=int, default=-1)
    p.add_argument("--show", action="store_true")
    p.add_argument("--print_raw", action="store_true")
    p.add_argument("--mqtt_enabled", action="store_true")
    p.add_argument("--mqtt_broker", default="localhost")
    p.add_argument("--mqtt_port", type=int, default=1883)
    p.add_argument("--mqtt_topic", default="demo/PPE")
    p.add_argument("--mqtt_topic_ok", default="demo/PPE/OK")
    p.add_argument("--mqtt_topic_no_helmet", default="demo/PPE/NO_HELMET")
    p.add_argument("--mqtt_topic_no_vest", default="demo/PPE/NO_VEST")
    p.add_argument("--mqtt_topic_no_helmet_no_vest", default="demo/PPE/NO_HELMET_NO_VEST")
    p.add_argument("--mqtt_username", default="")
    p.add_argument("--mqtt_password", default="")
    p.add_argument("--mqtt_cooldown", type=float, default=2.0)
    p.add_argument("--selftest", action="store_true")
    if defaults:
        p.set_defaults(**defaults)
    return p


def main() -> None:
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--config", default=str(DEFAULT_CONFIG))
    pre_args, _ = pre.parse_known_args()
    defaults = load_config(Path(pre_args.config))
    args = make_parser(defaults).parse_args()

    if args.selftest:
        selftest()
        return

    from ultralytics import YOLO

    weights = ensure_weights(Path(args.weights), args.weights_url)
    model = YOLO(str(weights))
    names = model.names if isinstance(model.names, dict) else {i: n for i, n in enumerate(model.names)}
    mapped = build_class_map(names)
    person_id = args.person_id if args.person_id >= 0 else mapped["person"]
    helmet_id = args.helmet_id if args.helmet_id >= 0 else mapped["helmet"]
    vest_id = args.vest_id if args.vest_id >= 0 else mapped["vest"]
    no_vest_id = mapped["no_vest"]
    if person_id is None or helmet_id is None or vest_id is None:
        raise RuntimeError(f"無法自動對應 person/helmet/vest 類別：{names}")

    cap = cv2.VideoCapture(parse_source(str(args.source)), cv2.CAP_FFMPEG)
    if not cap.isOpened():
        raise RuntimeError(f"無法開啟影像來源：{args.source}")

    mqtt = MqttPublisher(args)
    frame_no = 0
    last_result = None
    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            frame = cv2.resize(frame, (args.resize_w, args.resize_h))
            frame_no += 1
            if last_result is None or frame_no % max(1, args.infer_every) == 0:
                last_result = model(frame, conf=args.conf, iou=args.iou, device=args.device, verbose=False)[0]

            persons, helmets, vests, no_vests = [], [], [], []
            for box in last_result.boxes:
                cls_id = int(box.cls[0])
                x1, y1, x2, y2 = map(float, box.xyxy[0])
                item = (x1, y1, x2, y2)
                if cls_id == person_id:
                    persons.append(item)
                elif cls_id == helmet_id:
                    helmets.append(item)
                elif cls_id == vest_id:
                    vests.append(item)
                elif no_vest_id is not None and cls_id == no_vest_id:
                    no_vests.append(item)

            counts: Dict[str, int] = {}
            for px1, py1, px2, py2 in persons:
                ph = py2 - py1
                head = (px1, py1, px2, py1 + ph * args.head_ratio)
                has_helmet = any(iou(h, head) > 0.05 for h in helmets)

                def center_in_person(b):
                    bx1, by1, bx2, by2 = b
                    cx, cy = (bx1 + bx2) / 2.0, (by1 + by2) / 2.0
                    return px1 <= cx <= px2 and py1 <= cy <= py2

                has_vest = any(center_in_person(v) for v in vests) and not any(
                    center_in_person(v) for v in no_vests
                )
                missing = []
                if not has_helmet:
                    missing.append("NO_HELMET")
                if not has_vest:
                    missing.append("NO_VEST")
                status = "OK" if not missing else ",".join(missing)
                counts[status] = counts.get(status, 0) + 1
                color = (0, 255, 0) if status == "OK" else (0, 0, 255)
                cv2.rectangle(frame, (int(px1), int(py1)), (int(px2), int(py2)), color, 2)
                cv2.putText(
                    frame,
                    status,
                    (int(px1), max(20, int(py1) - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    color,
                    2,
                )

            mqtt.publish(counts)
            if args.print_raw and counts:
                print(counts)
            if args.show:
                cv2.imshow("PPE Safety Detection Demo", frame)
                if cv2.waitKey(1) & 0xFF in {27, ord("q")}:
                    break
    finally:
        cap.release()
        mqtt.close()
        if args.show:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
