"""
Configuration module for the Metabase Reporter application.
Handles environment variables and application settings.
"""
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    host: str
    port: str
    name: str
    user: str
    password: str
    
    @property
    def url(self) -> str:
        """Generate database URL for connections"""
        return f"postgresql+psycopg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


@dataclass
class MetabaseConfig:
    """Metabase API configuration"""
    url: str
    api_key: str
    embed_secret: str
    default_db_id: int = 3
    

@dataclass
class AIConfig:
    """AI/LLM configuration settings"""
    # Azure OpenAI settings
    azure_endpoint: str = ""
    azure_api_key: str = ""
    azure_deployment: str = ""
    azure_api_version: str = "2024-02-01"
    azure_embedding_deployment: str = ""
    
    # Model settings
    model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-large"
    temperature: float = 0.2
    k_samples: int = 7
    
    # Legacy OpenAI settings (kept for compatibility)
    completion_endpoint: str = ""
    completion_key: str = ""
    
    @property
    def use_azure(self) -> bool:
        """Check if Azure OpenAI should be used"""
        return bool(self.azure_endpoint and self.azure_api_key and self.azure_deployment)


@dataclass
class AppConfig:
    """Main application configuration"""
    flask_env: str
    debug: bool
    testing: bool
    embed_worksheets: bool = False
    collection_name: str = "embedded_schema"
    

class Config:
    """Central configuration manager"""
    
    def __init__(self):
        self.database = DatabaseConfig(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            name=os.getenv("DB_NAME", "unity_ai"),
            user=os.getenv("DB_USER", "unity_user"),
            password=os.getenv("DB_PASSWORD", "unity_pass")
        )
        
        self.metabase = MetabaseConfig(
            url=os.getenv("MB_EMBED_URL", ""),
            api_key=os.getenv("METABASE_KEY", ""),
            embed_secret=os.getenv("MB_EMBED_SECRET", "")
        )
        
        self.ai = AIConfig(
            # Azure OpenAI settings
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            azure_api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", ""),
            azure_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
            azure_embedding_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", ""),
            # Model settings
            model=os.getenv("AI_MODEL", "gpt-4o-mini"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-large"),
            # Legacy OpenAI settings
            completion_endpoint=os.getenv("COMPLETION_ENDPOINT", ""),
            completion_key=os.getenv("COMPLETION_KEY", "")
        )
        
        flask_env = os.getenv("FLASK_ENV", "development")
        self.app = AppConfig(
            flask_env=flask_env,
            debug=flask_env != "production",
            testing=False,
            embed_worksheets=os.getenv("EMBED_WORKSHEETS", "true").lower() == "true"
        )
        
        # Tenant configuration - extensible for different use cases
        self.tenant_mappings = self._load_tenant_mappings()
    
    def _load_tenant_mappings(self) -> Dict[str, Dict[str, Any]]:
        """
        Load tenant to database/collection mappings.
        This can be extended to load from a config file or database.
        """
        return {
            "Cyrus Org": {
                "db_id": 3,
                "collection_id": 47,
                "schema_types": ["public"]
            },
            "default": {
                "db_id": 3,
                "collection_id": 47,
                "schema_types": ["public"]
            }
        }
    
    def get_tenant_config(self, tenant_id: str) -> Dict[str, Any]:
        """Get configuration for a specific tenant"""
        return self.tenant_mappings.get(tenant_id, self.tenant_mappings["default"])
    
    @property
    def metabase_headers(self) -> Dict[str, str]:
        """Get headers for Metabase API requests"""
        return {"x-api-key": self.metabase.api_key}


# Global config instance
config = Config()