# Game Price Bot

A Telegram bot that tracks game prices across digital game
stores and notifies users about discounts and deals

<hr>

**Important**: This bot does not respond to commands;
it only sends messages about sales on popular digital game store platforms, such as Steam

### Add your bot to a Telegram group:
1. Create a supergroup in Telegram.
2. Add your bot as an administrator with permission to send messages

### Get the chat ID of created group:
Follow the [instructions](https://docs.leadconverter.su/faq/populyarnye-voprosy/telegram/kak-uznat-id-telegram-gruppy-chata)

### Add your bot token and group id
1. Create file **.env**
2. Add these lines:
```bash
TOKEN={YOUR_BOT_TOKEN}
CHAT_ID={YOUR_GROUP_CHAT_ID}
STEAM_API_KEY={YOUR_STEAM_API_KEY}
```

### App id counter
1. In the root of project create "counter.txt" file.
2. Write 1 into it

### Install packages:
```bash
  pip3 install -r requirements.txt
```

### Run:
```bash
python3 main.py
```

### Run tests:
```bash
PYTHONPATH=. pytest tests/ 
```