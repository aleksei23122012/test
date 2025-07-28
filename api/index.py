from flask import Flask, request
import json # Подключаем библиотеку для красивого вывода
import datetime # Подключаем библиотеку для времени

app = Flask(__name__)

# --- НАШ НОВЫЙ ДЕТЕКТОР ---
# Теперь он принимает и GET (от браузера) и POST (от Telegram) запросы
@app.route('/', methods=['GET', 'POST'])
def webhook_detector():
    # Если это GET-запрос (открытие в браузере)
    if request.method == 'GET':
        print("--- !!! GET ЗАПРОС ОБНАРУЖЕН (это был браузер) !!! ---")
        return 'Детектор запущен! Теперь отправьте /start вашему боту и обновите эту страницу с логами.', 200

    # Если это POST-запрос (мы надеемся, от Telegram)
    if request.method == 'POST':
        # Просто записываем в лог всё, что к нам пришло
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"--- !!! POST ЗАПРОС ОБНАРУЖЕН в {current_time} !!! ---")
        
        # Попытаемся красиво распечатать данные
        try:
            data = request.get_json()
            print("--- ДАННЫЕ ВНУТРИ ЗАПРОСА: ---")
            print(json.dumps(data, indent=2)) # dumps с отступом для читаемости
        except Exception as e:
            print(f"--- НЕ УДАЛОСЬ ПРОЧИТАТЬ JSON: {e} ---")
            print("--- СЫРЫЕ ДАННЫЕ: ---")
            print(request.data)

        print("--- !!! КОНЕЦ POST ЗАПРОСА !!! ---")
        
        # Отвечаем Telegram, что все в порядке
        return 'ok', 200
        
# Эта часть нужна для локального тестирования, но Vercel ее не использует
if __name__ == "__main__":
    app.run(debug=True)
