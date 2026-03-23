from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    llm_provider:str=Field(default='gemini')
    gemini_api_key:str=Field(default='def_key')
    gemini_model:str=Field(default='gemini-2.0-flash')
    ollama_base_url:str=Field(default='http://localhost:11434')
    ollama_model:str=Field(default='llama3.1')
    output_format:str=Field(default='pdf')
    top_n_projects:int=Field(default=3)
    top_n_experience:int=Field(default=3)
    api_host:str=Field(default="0.0.0.0")
    api_port:int=Field(default=8000)
    env:str=Field(default='dev')
    model_config = SettingsConfigDict(env_file=".env")
settings = Settings()
