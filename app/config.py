import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Business database configuration (insurance data)
BUSINESS_DB_CONFIG = {
    "dbname": os.getenv("BUSINESS_DB_NAME", "insurance_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}

# Application database configuration (conversations, embeddings, etc.)
APPLICATION_DB_CONFIG = {
    "dbname": os.getenv("APPLICATION_DB_NAME", "application_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}

# Path to verified queries YAML
YAML_FILE_PATH = os.getenv("YAML_FILE_PATH", "verified_queries.yaml")

# LLM configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "app.log")

# Application settings
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"