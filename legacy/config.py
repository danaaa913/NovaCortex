"""
Configuration Management for NovaCortex Bot
Handles all environment variables and configuration settings
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class BotConfig:
    """Main bot configuration"""
    telegram_token: str
    gemini_api_key: str
    gemini_model_id: str = "gemini-2.5-flash"
    
    @classmethod
    def from_env(cls) -> 'BotConfig':
        """Load configuration from environment variables"""
        telegram_token = os.getenv("TELEGRAM_TOKEN")
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        
        if not telegram_token:
            raise ValueError("❌ TELEGRAM_TOKEN is required in environment variables")
        if not gemini_api_key:
            raise ValueError("❌ GEMINI_API_KEY is required in environment variables")
        
        return cls(
            telegram_token=telegram_token,
            gemini_api_key=gemini_api_key,
            gemini_model_id=os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash")
        )


@dataclass
class DatabaseConfig:
    """Database configuration"""
    path: str = "chat_history.db"
    
    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        return cls(path=os.getenv("DATABASE_PATH", "chat_history.db"))


@dataclass
class VectorStoreConfig:
    """Vector store and RAG configuration"""
    persist_dir: str = "./chroma_university_db"
    collection_name: str = "yarmouk_rag_json"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    max_docs_for_bm25: int = 5000
    vector_search_k: int = 10
    bm25_search_k: int = 6
    hybrid_vector_weight: float = 0.7
    hybrid_bm25_weight: float = 0.3
    
    @classmethod
    def from_env(cls) -> 'VectorStoreConfig':
        return cls(
            persist_dir=os.getenv("CHROMA_PERSIST_DIR", "./chroma_university_db"),
            collection_name=os.getenv("CHROMA_COLLECTION_NAME", "yarmouk_rag_json"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
            max_docs_for_bm25=int(os.getenv("MAX_DOCS_FOR_BM25", "5000")),
            vector_search_k=int(os.getenv("VECTOR_SEARCH_K", "10")),
            bm25_search_k=int(os.getenv("BM25_SEARCH_K", "6")),
            hybrid_vector_weight=float(os.getenv("HYBRID_VECTOR_WEIGHT", "0.7")),
            hybrid_bm25_weight=float(os.getenv("HYBRID_BM25_WEIGHT", "0.3"))
        )


@dataclass
class MemoryConfig:
    """Memory and caching configuration"""
    chat_history_limit: int = 6
    long_term_memory_limit: int = 6
    similarity_threshold: float = 0.78
    
    @classmethod
    def from_env(cls) -> 'MemoryConfig':
        return cls(
            chat_history_limit=int(os.getenv("CHAT_HISTORY_LIMIT", "6")),
            long_term_memory_limit=int(os.getenv("LONG_TERM_MEMORY_LIMIT", "6")),
            similarity_threshold=float(os.getenv("SIMILARITY_THRESHOLD", "0.78"))
        )


@dataclass
class RateLimitConfig:
    """Rate limiting configuration"""
    messages_per_window: int = 20
    window_seconds: int = 60
    
    @classmethod
    def from_env(cls) -> 'RateLimitConfig':
        return cls(
            messages_per_window=int(os.getenv("RATE_LIMIT_MESSAGES", "20")),
            window_seconds=int(os.getenv("RATE_LIMIT_WINDOW", "60"))
        )


@dataclass
class GeminiConfig:
    """Gemini API specific configuration"""
    temperature: float = 0.65
    max_retries: int = 3
    retry_delay: int = 2
    
    @classmethod
    def from_env(cls) -> 'GeminiConfig':
        return cls(
            temperature=float(os.getenv("GEMINI_TEMPERATURE", "0.65")),
            max_retries=int(os.getenv("GEMINI_MAX_RETRIES", "3")),
            retry_delay=int(os.getenv("GEMINI_RETRY_DELAY", "2"))
        )


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    file: str = "bot.log"
    
    @classmethod
    def from_env(cls) -> 'LoggingConfig':
        return cls(
            level=os.getenv("LOG_LEVEL", "INFO"),
            file=os.getenv("LOG_FILE", "bot.log")
        )


class Config:
    """Main configuration class aggregating all configs"""
    
    def __init__(self):
        self.bot = BotConfig.from_env()
        self.database = DatabaseConfig.from_env()
        self.vectorstore = VectorStoreConfig.from_env()
        self.memory = MemoryConfig.from_env()
        self.rate_limit = RateLimitConfig.from_env()
        self.gemini = GeminiConfig.from_env()
        self.logging = LoggingConfig.from_env()
    
    @classmethod
    def load(cls) -> 'Config':
        """Load configuration from environment"""
        return cls()


# Load environment variables from .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass