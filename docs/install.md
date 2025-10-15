# Установка и запуск

## 1) Локально
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp bot/.env.example bot/.env
# открыть bot/.env и встаить BOT_TOKEN
python -m bot.main
