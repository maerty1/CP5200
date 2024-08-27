import requests

url = "http://localhost:5000/generate-image"

payload = {
    "text": "СТОП\nВыключить фары",
    "alignment": "top",
    "font_size": 14,
    "vertical_padding": 0,
    "horizontal_padding": 0,
    "led_ip": "192.168.178.152",
    "led_port": "5200"
}
headers = {
    "Content-Type": "application/json; charset=utf-8",
}

response = requests.request("POST", url, json=payload, headers=headers)

print(response.text)