from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv('MONGO_URL')

if not MONGO_URL:
    print(f"Environment variable MONGO_URL is missing.")
    import sys
    sys.exit(1)

client = MongoClient(MONGO_URL)
db = client.get_default_database()

from .employees import get_employees_collection
from .roles import get_roles_collection
from .keys import get_keys_collection
from .login_attempts import get_login_attempts_collection

employees_collection = get_employees_collection(db)
roles_collection = get_roles_collection(db)
keys_collection = get_keys_collection(db)
login_attempts_collection = get_login_attempts_collection(db)

__all__ = ['db', 'employees_collection', 'roles_collection', 'keys_collection', 'login_attempts_collection']
