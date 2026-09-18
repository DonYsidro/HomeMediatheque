import os
from dotenv import load_dotenv

load_dotenv()

TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
GOOGLEBOOKS_API_KEY = os.environ.get("GOOGLEBOOKS_API_KEY")
DISCOGS_TOKEN = os.environ.get("DISCOGS_TOKEN")
