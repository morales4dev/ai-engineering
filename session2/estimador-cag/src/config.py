from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	anthropic_api_key: str
	openai_api_key: str
	llm_provider: str
	llm_model: str
	app_env: str
	log_level: str

	model_config = SettingsConfigDict(
		env_file=".env",
		env_file_encoding="utf-8",
	)


settings = Settings()
