import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

DB_PATH = "data/database.db"
DEFAULT_QR = "data/qr.png"
DEFAULT_PDF = "data/pdf.pdf"