import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables, making sure to load them from the .env file and throw an error if not found
load = load_dotenv()
if not load:
    raise EnvironmentError("Failed to load environment variables from .env file.")


# Business database configuration (insurance data)
BUSINESS_DB_CONFIG = {
    "dbname": os.getenv("BUSINESS_DB_NAME", "insurance_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}
BUSINESS_DATABASE_TYPE = os.getenv("BUSINESS_DATABASE_TYPE", "postgresql")
BUSINESS_DB_CONNECTION_STRING = f"{BUSINESS_DATABASE_TYPE}://{BUSINESS_DB_CONFIG['user']}:{BUSINESS_DB_CONFIG['password']}@{BUSINESS_DB_CONFIG['host']}:{BUSINESS_DB_CONFIG['port']}/{BUSINESS_DB_CONFIG['dbname']}"

# Application database configuration (conversations, logs etc.)
APPLICATION_DB_CONFIG = {
    "dbname": os.getenv("APPLICATION_DB_NAME", "application_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}
APPLICATION_DATABASE_TYPE = os.getenv("APPLICATION_DATABASE_TYPE", "postgresql")
APPLICATION_DB_CONNECTION_STRING = f"{APPLICATION_DATABASE_TYPE}://{APPLICATION_DB_CONFIG['user']}:{APPLICATION_DB_CONFIG['password']}@{APPLICATION_DB_CONFIG['host']}:{APPLICATION_DB_CONFIG['port']}/{APPLICATION_DB_CONFIG['dbname']}"


# Path to verified queries YAML
YAML_FILE_PATH = os.getenv("YAML_FILE_PATH", "verified_queries.yaml")

# LLM configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "app.log")

# Application settings
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"

# Embedding model configuration
EMBEDDING_MODEL = 'all-MiniLM-L6-v2'