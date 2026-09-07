from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    vcf_file: Path = Field(default=Path("data/input.vcf.gz"), validation_alias="VCF_FILE")
    api_secret: str = Field(default="change-me", min_length=1, validation_alias="API_SECRET")
    default_page_size: int = Field(default=50, ge=1, validation_alias="DEFAULT_PAGE_SIZE")
    max_page_size: int = Field(default=200, ge=1, validation_alias="MAX_PAGE_SIZE")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", validation_alias="LOG_LEVEL"
    )

    @model_validator(mode="after")
    def validate_page_sizes(self) -> Self:
        if self.default_page_size > self.max_page_size:
            raise ValueError("DEFAULT_PAGE_SIZE cannot exceed MAX_PAGE_SIZE")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
