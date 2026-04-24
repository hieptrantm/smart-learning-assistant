import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/authdb")
SECRET_KEY = os.getenv("SECRET_KEY", "hiep-tran-thanh-mieu")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "your-sendgrid-id")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "your-google-client-id")
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 30
CORS_ORIGINS = ["*"]