import sys
import os
import time
import configparser
import pyautogui
import keyboard
import psutil
import subprocess
from pygetwindow import getWindowsWithTitle
from arrow_detector import ArrowDetector


class WebGameController:
    def __init__(self, config):
        self.config = config
        self.running = False
        self.score_threshold = 35000
        self.arrow_detector = ArrowDetector(config)

        # Конфигурация элементов интерфейса
        self.elements = {
            'launcher_play_button': config['Elements']['launcher_play'],
            'places_button': config['Elements']['places_button'],
            'games_tab': config['Elements']['games_tab'],
            'ava_dancer': config['Elements']['ava_dancer'],
            'solo_mode': config['Elements']['solo_mode'],
            'start_button': config['Elements']['start_button'],
            'arrow_up': config['Paths']['arrow_up'],
            'arrow_down': config['Paths']['arrow_down'],
            'arrow_left': config['Paths']['arrow_left'],
            'arrow_right': config['Paths']['arrow_right']
        }

        # Тайминги из конфига
        self.timings = {
            'launch_delay': float(config['Timings']['launch_delay']),
            'element_timeout': float(config['Timings']['element_timeout']),
            'scroll_delay': float(config['Timings']['scroll_delay']),
            'game_load_time': float(config['Timings']['game_load_time'])
        }

    def launch_game(self):
        """Запуск игры через лаунчер"""
        path = self.config['Paths']['launcher_path']
        print(f"Проверяемый путь: {path}")  # Добавьте для отладки

        if not os.path.exists(path):
            raise FileNotFoundError(f"Путь к лаунчеру не существует: {path}")

        try:
            subprocess.Popen([path])  # Запуск как списка аргументов
            print("Лаунчер запущен")

            # Ожидание и нажатие кнопки Play
            self.wait_and_click('launcher_play_button', "Кнопка Играть", timeout=10)
            return True

        except Exception as e:
            print(f"Ошибка запуска: {e}")
            return False

    def wait_and_click(self, element_key, description, timeout=120):
        """Ожидание элемента и клик по нему"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                pos = pyautogui.locateCenterOnScreen(
                    self.elements[element_key],
                    confidence=0.9,
                    grayscale=True
                )
                if pos:
                    pyautogui.click(pos)
                    print(f"{description} найдена и нажата")
                    time.sleep(1)
                    return True
            except pyautogui.ImageNotFoundException:
                time.sleep(0.5)
        raise TimeoutError(f"Элемент {description} не найден")

    def navigate_to_minigame(self):
        """Навигация к мини-игре"""
        self.wait_and_click('places_button', "Кнопка 'Места'")
        self.wait_and_click('games_tab', "Вкладка 'Игры'")

        # Скролл и выбор игры
        self.scroll_to_element('ava_dancer')
        self.wait_and_click('ava_dancer', "Ava-dancer")

        # Ожидание загрузки
        time.sleep(self.timings['game_load_time'])

        self.wait_and_click('solo_mode', "Одиночный режим")
        self.wait_and_click('start_button', "Кнопка Начать")

    def scroll_to_element(self, element_key):
        """Улучшенный скролл с фиксацией курсора"""
        scroll_x = 1225  # Фиксированная позиция X для скролла
        scroll_y = 380  # Фиксированная позиция Y для скролла
        pyautogui.moveTo(scroll_x, scroll_y)  # Устанавливаем курсор в безопасную зону

        for _ in range(5):  # Максимум 5 попыток скролла
            try:
                if pyautogui.locateOnScreen(self.elements[element_key], confidence=0.8):
                    return True
            except:
                pass

            pyautogui.scroll(-800)  # Сильный скролл вниз
            time.sleep(1.5)  # Пауза между скроллами

    def game_session(self):
        """Улучшенная игровая сессия"""
        print("Ожидание начала игры...")
        time.sleep(3)  # Ожидание старта

        try:
            self.arrow_detector.start()
            while self.running:
                # if self.check_game_over():
                #     break
                time.sleep(0.1)
        except Exception as e:
            print(f"Ошибка в игровой сессии: {e}")
        finally:
            self.arrow_detector.stop()

    def restart_game(self):
        """Полный перезапуск игры"""
        print("Инициализация перезапуска...")
        # Закрытие лаунчера
        for proc in psutil.process_iter():
            if proc.name().lower() == self.config['Paths']['launcher_process'].lower():
                proc.kill()

        time.sleep(5)
        self.launch_game()
        self.navigate_to_minigame()

    def main_loop(self):
        """Основной цикл выполнения"""
        while self.running:
            try:
                if not self.check_launcher_running():
                    self.restart_game()

                self.navigate_to_minigame()

                if self.game_session():
                    print("Успешная сессия, перезапуск...")
                else:
                    print("Проблемы в процессе игры, перезапуск...")
                    self.restart_game()

            except Exception as e:
                print(f"Критическая ошибка: {e}")
                self.restart_game()

    def check_launcher_running(self):
        """Проверка состояния лаунчера"""
        return self.config['Paths']['launcher_process'] in (p.name() for p in psutil.process_iter())


class App:
    def __init__(self):
        self.config = self.load_config()
        self.controller = WebGameController(self.config)
        keyboard.add_hotkey('alt+z', self.toggle_script)
        print("Скрипт готов. ALT+Z для старта/останова")

    def toggle_script(self):
        """Управление работой скрипта"""
        self.controller.running = not self.controller.running
        if self.controller.running:
            print("Запуск скрипта...")
            if not self.controller.check_launcher_running():
                self.controller.launch_game()
            self.controller.main_loop()
        else:
            print("Скрипт остановлен")

    def load_config(self):
        """Загрузка конфигурации с указанием кодировки"""
        config = configparser.ConfigParser()
        with open('config.ini', 'r', encoding='utf-8') as f:
            config.read_file(f)
        return config


if __name__ == "__main__":
    app = App()
    try:
        keyboard.wait()
    except KeyboardInterrupt:
        sys.exit()