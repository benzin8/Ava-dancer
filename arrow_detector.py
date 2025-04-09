import cv2
import numpy as np
import pyautogui
import threading
import mss
import json
import time

class ArrowDetector:
    def __init__(self, config):
        self.config = config
        self.running = False
        self.load_config()

    def load_config(self):
        """Загрузка параметров из конфига"""
        self.COLOR_LOWER = np.array(
            [int(x) for x in self.config['ArrowParams']['color_lower'].split(',')],
            dtype=np.uint8
        )
        self.COLOR_UPPER = np.array(
            [int(x) for x in self.config['ArrowParams']['color_upper'].split(',')],
            dtype=np.uint8
        )
        self.MATCH_THRESHOLD = float(self.config['ArrowParams']['match_threshold'])
        self.SCAN_INTERVAL = float(self.config['ArrowParams']['scan_interval'])
        self.ARROW_ZONES = json.loads(self.config['ArrowParams']['arrow_zones'])
        self.TEMPLATES = self.load_templates()

    def load_templates(self):
        """Загрузка шаблонов стрелок"""
        templates = {}
        for zone in self.ARROW_ZONES:
            path = self.config['Paths'][f"arrow_{zone['name']}"]
            templates[zone['name']] = cv2.imread(path, 0)
        return templates

    def start(self):
        """Запуск детектора"""
        if not self.running:
            self.running = True
            self.grabber = FrameGrabber(self.config, self.ARROW_ZONES)
            self.grabber_thread = threading.Thread(target=self.grabber.grab_loop)
            self.grabber_thread.start()

            self.detectors = []
            for zone in self.ARROW_ZONES:
                detector = ArrowDetectorThread(
                    zone, self.grabber, self.TEMPLATES,
                    self.COLOR_LOWER, self.COLOR_UPPER,
                    self.MATCH_THRESHOLD, self.SCAN_INTERVAL
                )
                detector.start()
                self.detectors.append(detector)

    def stop(self):
        """Остановка детектора"""
        if self.running:
            self.running = False
            self.grabber.stop()
            for detector in self.detectors:
                detector.stop()
            for detector in self.detectors:
                detector.join()
            self.grabber_thread.join()

class FrameGrabber:
    def __init__(self, config, arrow_zones):
        self.config = config
        self.stop_event = threading.Event()
        self.frame = None
        self.region = self.calculate_region(arrow_zones)

    def calculate_region(self, arrow_zones):
        all_x = [z['x1'] for z in arrow_zones] + [z['x2'] for z in arrow_zones]
        all_y = [z['y'] + z['height'] for z in arrow_zones]
        return {
            'left': min(all_x),
            'top': min(z['y'] for z in arrow_zones),
            'width': max(all_x) - min(all_x),
            'height': max(all_y) - min(z['y'] for z in arrow_zones)
        }

    def grab_loop(self):
        with mss.mss() as sct:
            while not self.stop_event.is_set():
                try:
                    raw = sct.grab(self.region)
                    self.frame = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
                except Exception as e:
                    print(f"Ошибка захвата: {str(e)}")
                time.sleep(float(self.config['ArrowParams']['scan_interval']))

    def stop(self):
        self.stop_event.set()

class ArrowDetectorThread(threading.Thread):
    def __init__(self, zone, grabber, templates, color_lower, color_upper, threshold, scan_interval):
        super().__init__()
        self.zone = zone
        self.grabber = grabber
        self.template = templates[zone['name']]
        self.COLOR_LOWER = color_lower
        self.COLOR_UPPER = color_upper
        self.MATCH_THRESHOLD = threshold
        self.SCAN_INTERVAL = scan_interval
        self.stop_event = threading.Event()
        self.key_pressed = False

        # Предварительный расчет смещений
        self.x_offset = zone['x1'] - self.grabber.region['left']
        self.y_offset = zone['y'] - self.grabber.region['top']
        self.width = zone['x2'] - zone['x1']
        self.height = zone['height']

    def process_image(self, frame):
        roi = frame[
            self.y_offset:self.y_offset + self.height,
            self.x_offset:self.x_offset + self.width
        ]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.COLOR_LOWER, self.COLOR_UPPER)
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        return cv2.bitwise_and(gray, gray, mask=mask)

    def run(self):
        while not self.stop_event.is_set():
            try:
                frame = self.grabber.frame.copy() if self.grabber.frame is not None else None
                if frame is not None:
                    processed = self.process_image(frame)
                    res = cv2.matchTemplate(processed, self.template, cv2.TM_CCOEFF_NORMED)
                    max_val = np.max(res)

                    if max_val >= self.MATCH_THRESHOLD and not self.key_pressed:
                        pyautogui.keyDown(self.zone['key'])
                        self.key_pressed = True
                    elif max_val < self.MATCH_THRESHOLD and self.key_pressed:
                        pyautogui.keyUp(self.zone['key'])
                        self.key_pressed = False

            except Exception as e:
                print(f"Ошибка в детекторе {self.zone['name']}: {str(e)}")

            time.sleep(self.SCAN_INTERVAL)

        if self.key_pressed:
            pyautogui.keyUp(self.zone['key'])

    def stop(self):
        self.stop_event.set()