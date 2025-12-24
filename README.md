# Инструкция к развертке на хостинге

<hr>

### Добавьет бота в созданную группу:
1. Создайте супергруппу в Телеграмм
2. Добавьте бота как администратора с разрешением отсылать сообщенияAdd your bot as an administrator with permission to send messages

### Получите chat id группы:
Следуйте [инструкции](https://docs.leadconverter.su/faq/populyarnye-voprosy/telegram/kak-uznat-id-telegram-gruppy-chata)

### Получите Steam API ключ:
Ключ можно получить [здесь](https://steamcommunity.com/login/home/?goto=%2Fdev%2Fapikey)

### Добавление секретов:
2. В .env файл добавьте следующие строчки:
```bash
TOKEN=YOUR_BOT_TOKEN # токен вашего бота, полученного в Botfather.
CHAT_ID=YOUR_GROUP_CHAT_ID # id чата группы, полученный на предыдущем шаге
STEAM_API_KEY=YOUR_STEAM_API_KEY #  Steam API ключ, полученный на предыдущем шаге
```

### Установите пакеты:
```bash
  pip3 install -r requirements.txt
```

### Запустите бота:
```bash
python3 main.py
```

### (Опционально) Запустите тесты:
```bash
PYTHONPATH=. pytest tests/ 
```


Если возникнут трудности с запуском на хостинге, или бот перестал правильно работать - пишите мне в 8:00 - 18:00 по будням и выходным.

Первый месяц поддержки **полностью бесплтаный**
