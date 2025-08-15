"""Настройка логирования для приложения."""
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from loguru import logger

if TYPE_CHECKING:
    from config.settings import Settings


def setup_logger(settings) -> None:
    """
    Настраивает логирование для приложения.
    
    Args:
        settings: Настройки приложения
    """
    # Удаляем стандартный обработчик loguru
    logger.remove()
    
    # Настраиваем формат логов
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    # Консольный вывод
    logger.add(
        sys.stdout,
        format=log_format,
        level=settings.log_level,
        colorize=True,
        backtrace=True,
        diagnose=True
    )
    
    # Создаем директорию для логов если её нет
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Файловое логирование - общий лог
    logger.add(
        log_dir / settings.log_file,
        format=log_format,
        level=settings.log_level,
        rotation="100 MB",
        retention="30 days",
        compression="zip",
        backtrace=True,
        diagnose=True
    )
    
    # Файловое логирование - только ошибки
    logger.add(
        log_dir / "errors.log",
        format=log_format,
        level="ERROR",
        rotation="50 MB",
        retention="60 days",
        compression="zip",
        backtrace=True,
        diagnose=True
    )
    
    # Файловое логирование - торговые решения
    logger.add(
        log_dir / "trading_decisions.log",
        format=log_format,
        level="INFO",
        rotation="50 MB",
        retention="90 days",
        compression="zip",
        filter=lambda record: "TRADING" in record["extra"].get("category", ""),
        backtrace=False,
        diagnose=False
    )
    
    # Файловое логирование - ответы OpenAI
    logger.add(
        log_dir / "openai_responses.log",
        format=log_format,
        level="INFO",
        rotation="50 MB",
        retention="30 days",
        compression="zip",
        filter=lambda record: "🤖 OPENAI" in record["message"] or "📝 СЫРОЙ ОТВЕТ" in record["message"] or "✅ РАСПАРСЕННЫЙ JSON" in record["message"],
        backtrace=False,
        diagnose=False
    )
    
    logger.info(f"Логирование настроено. Уровень: {settings.log_level}")


def get_trading_logger():
    """
    Возвращает логгер для торговых операций.
    
    Returns:
        Экземпляр логгера с меткой для торговых операций
    """
    return logger.bind(category="TRADING")


def log_trading_decision(decision_type: str, details: str) -> None:
    """
    Логирует торговое решение.
    
    Args:
        decision_type: Тип решения (buy, sell, cancel, pause)
        details: Детали решения
    """
    trading_logger = get_trading_logger()
    trading_logger.info(f"РЕШЕНИЕ: {decision_type.upper()} | {details}")


def log_api_call(endpoint: str, method: str, status_code: int, response_time: float) -> None:
    """
    Логирует API вызов.
    
    Args:
        endpoint: Конечная точка API
        method: HTTP метод
        status_code: Код ответа
        response_time: Время ответа в секундах
    """
    logger.info(
        f"API {method} {endpoint} | {status_code} | {response_time:.3f}s",
        extra={"category": "API"}
    )


def log_openai_interaction(prompt_type: str, tokens_used: int, response_time: float) -> None:
    """
    Логирует взаимодействие с OpenAI.
    
    Args:
        prompt_type: Тип промпта (initial, update)
        tokens_used: Количество использованных токенов
        response_time: Время ответа в секундах
    """
    logger.info(
        f"OpenAI {prompt_type} | {tokens_used} tokens | {response_time:.3f}s",
        extra={"category": "OPENAI"}
    )


def log_market_data_update(symbol: str, price: float, volume: float) -> None:
    """
    Логирует обновление рыночных данных.
    
    Args:
        symbol: Торговая пара
        price: Текущая цена
        volume: Объем торгов
    """
    logger.debug(
        f"MARKET {symbol} | Price: {price} | Volume: {volume}",
        extra={"category": "MARKET"}
    )
