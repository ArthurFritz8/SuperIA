from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # Tendery configurações
    tenderly_access_key: str = Field(default="", env="TENDERLY_ACCESS_KEY")
    tenderly_account_slug: str = Field(default="", env="TENDERLY_ACCOUNT_SLUG")
    tenderly_project_slug: str = Field(default="", env="TENDERLY_PROJECT_SLUG")
    
    # Configurações Web3 / Bundler
    rpc_url: str = Field(default="https://eth-mainnet.g.alchemy.com/v2/demo", env="RPC_URL")
    bundler_url: str = Field(default="https://bundler.biconomy.io/api/v2/...", env="BUNDLER_URL")
    paymaster_url: str = Field(default="https://paymaster.biconomy.io/api/v1/...", env="PAYMASTER_URL")

    # Configs do modelo IA (Placeholder)
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
