import os
import uuid
import ctypes
import logging
from flask import Flask, request, jsonify
from PIL import Image, ImageDraw, ImageFont

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),  # Логирование в файл
        logging.StreamHandler()          # Логирование в консоль
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

SAVE_DIR = "generated_images"  # Директория для сохранения изображений
os.makedirs(SAVE_DIR, exist_ok=True)  # Создание директории, если она не существует

dll_path = "./CP5200.dll"  # Путь к DLL файлу
cp5200 = ctypes.CDLL(dll_path)  # Загрузка DLL библиотеки

# Определение аргументов и типов для функций из библиотеки ctypes
cp5200.CP5200_Net_Init.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32, ctypes.c_int]
cp5200.CP5200_Net_Init.restype = ctypes.c_int

cp5200.CP5200_Net_SetBindParam.argtypes = [ctypes.c_uint32, ctypes.c_int]
cp5200.CP5200_Net_SetBindParam.restype = ctypes.c_int

cp5200.CP5200_Net_Connect.argtypes = []
cp5200.CP5200_Net_Connect.restype = ctypes.c_int

cp5200.CP5200_Net_IsConnected.argtypes = []
cp5200.CP5200_Net_IsConnected.restype = ctypes.c_int

cp5200.CP5200_Net_Disconnect.argtypes = []
cp5200.CP5200_Net_Disconnect.restype = ctypes.c_int

cp5200.CP5200_Net_SendPicture.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
cp5200.CP5200_Net_SendPicture.restype = ctypes.c_int

# Функция для преобразования IP-адреса в формат DWORD
def ip_to_dword(ip):
    return ctypes.c_uint32(int.from_bytes(map(int, ip.split('.')), byteorder='big'))

# Маршрут для генерации изображения
@app.route('/generate-image', methods=['POST'])
def generate_image():
    data = request.json  # Получение данных из POST-запроса
    logger.info(f"Received data: {data}")
    
    # Извлечение параметров из запроса
    text = data.get('text', '')
    alignment = data.get('alignment', 'center')
    font_size = int(data.get('font_size', 14))
    vertical_padding = int(data.get('vertical_padding', 0))
    horizontal_padding = int(data.get('horizontal_padding', 0))
    led_ip = data.get('led_ip', '192.168.156.68')
    led_port = int(data.get('led_port', 5200))
    led_width = int(data.get('led_width', 128))
    led_height = int(data.get('led_height', 64))

    # Создание изображения с заданными размерами
    image = Image.new('1', (led_width, led_height), color=0)

    draw = ImageDraw.Draw(image)
    font_path = "C:/Windows/Fonts/arial.ttf"  # Путь к шрифту
    font = ImageFont.truetype(font_path, font_size)

    # Подготовка текста для вывода на изображение
    lines = text.replace("\\n", "\n").splitlines()
    line_height = draw.textbbox((0, 0), "А", font=font)[3]
    total_text_height = line_height * len(lines) + vertical_padding * (len(lines) - 1)

    # Определение начальной позиции текста по вертикали в зависимости от выравнивания
    if alignment == "top":
        y = -2
    elif alignment == "bottom":
        y = led_height - total_text_height
    else:
        y = (led_height - total_text_height) // 2

    # Вывод текста на изображение
    for line in lines:
        text_bbox = draw.textbbox((0, 0), line, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        x = (led_width - text_width) // 2 + horizontal_padding  # Центрирование текста по горизонтали
        draw.text((x, y), line, fill=1, font=font)
        y += line_height + vertical_padding

    # Сохранение изображения
    image_filename = f"{uuid.uuid4().hex}.png"
    image_path = os.path.join(SAVE_DIR, image_filename)
    image.save(image_path)

    # Отправка изображения на LED-дисплей
    send_result = send_image_to_led(image_path, led_ip, led_port, led_width, led_height)

    # Возврат результата отправки
    if send_result:
        return jsonify({"send_image": "OK"})
    else:
        return jsonify({"send_image": "FAILED"})

# Функция отправки изображения на LED-дисплей
def send_image_to_led(image_path, ip_address, port, width, height):
    id_code = "255.255.255.255"  # Идентификационный код
    timeout = 10
    success = False

    dwIP = ip_to_dword(ip_address)
    dwIDCode = ip_to_dword(id_code)

    logger.info(f"Initializing network with IP: {ip_address}, Port: {port}, IDCode: {id_code}, Timeout: {timeout}")
    init_result = cp5200.CP5200_Net_Init(dwIP, port, dwIDCode, timeout)
    logger.info(f"CP5200_Net_Init result: {init_result}")

    bind_ip = "0.0.0.0"
    bind_port = 0
    dwClientIP = ip_to_dword(bind_ip)

    # Установка параметров привязки
    bind_result = cp5200.CP5200_Net_SetBindParam(dwClientIP, bind_port)

    # Подключение к сети
    connect_result = cp5200.CP5200_Net_Connect()

    # Проверка подключения
    is_connected = cp5200.CP5200_Net_IsConnected()

    if is_connected:
        picture_path = image_path.encode('utf-8')

        # Отправка изображения на LED-дисплей
        send_picture_result = cp5200.CP5200_Net_SendPicture(0xff, 0, 0, 0, width, height, picture_path, 1, 0, 0, 0)

        if send_picture_result == 0:
            success = True

        # Удаление изображения после отправки
        if os.path.exists(image_path):
            os.remove(image_path)
            logger.info(f"Image {image_path} deleted successfully.")

    # Отключение от сети
    cp5200.CP5200_Net_Disconnect()

    return success

# Запуск Flask-сервера
if __name__ == '__main__':
    logger.info("Starting Flask server...")
    app.run(host='0.0.0.0', port=5000)
