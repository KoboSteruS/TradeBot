"""Настройки приложения."""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Настройки приложения."""
    
    # OpenAI настройки
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY", description="API ключ OpenAI")
    openai_model: str = Field(default="gpt-4o-mini", description="Модель OpenAI")
    
    # Trading API настройки
    trading_api_base_url: str = Field(
        default="http://109.73.192.126:8001", 
        description="Базовый URL торгового API"
    )
    demo_mode: bool = Field(default=False, description="Демо режим торговли")
    
    # Торговые настройки
    target_apy: float = Field(default=30.0, description="Целевая годовая доходность в %")
    trading_pair: str = Field(default="BTC-USDT", description="Торговая пара")
    update_interval: int = Field(default=300, description="Интервал обновления в секундах (5 минут)")
    
    # Риск-менеджмент
    max_risk_per_trade: float = Field(default=2.0, description="Максимальный риск на сделку в %")
    max_open_positions: int = Field(default=3, description="Максимальное количество открытых позиций")
    
    # Логирование
    log_level: str = Field(default="INFO", description="Уровень логирования")
    log_file: str = Field(default="tradebot.log", description="Файл логов")
    
    class Config:
        """Конфигурация настроек."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Глобальный экземпляр настроек
settings = Settings()
