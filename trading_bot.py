"""Основной модуль торгового бота."""
import asyncio
import time
from typing import Optional
from loguru import logger

from config.settings import Settings
from services import TradingAPIClient
from services.openai_simple_handler import OpenAISimpleHandler
from handlers import ResponseParser
from models.trading import MarketData
from models.responses import BuyDecision, SellDecision, CancelDecision, PauseDecision
from utils import setup_logger, log_trading_decision, log_api_call, log_openai_interaction


class TradingBot:
    """
    Главный класс торгового бота.
    
    Управляет циклом торговли, взаимодействием с API и принятием решений.
    """
    
    def __init__(self, settings: Settings):
        """
        Инициализация торгового бота.
        
        Args:
            settings: Настройки приложения
        """
        self.settings = settings
        self.api_client: Optional[TradingAPIClient] = None
        self.openai_handler: Optional[OpenAISimpleHandler] = None
        self.parser = ResponseParser()
        self.is_initialized = False
        self.is_running = False
        
        # Настраиваем логирование
        setup_logger(settings)
        logger.info("Инициализация торгового бота")
    
    async def initialize(self) -> None:
        """Инициализирует все компоненты бота."""
        try:
            logger.info("Начало инициализации компонентов")
            
            # Инициализируем API клиент
            self.api_client = TradingAPIClient(self.settings)
            
            # Тестируем соединение с API
            if not await self.api_client.test_connection():
                raise ConnectionError("Не удалось подключиться к торговому API")
            
            # Инициализируем OpenAI обработчик
            self.openai_handler = OpenAISimpleHandler(self.settings)
            await self.openai_handler.initialize()
            
            self.is_initialized = True
            logger.success("Все компоненты успешно инициализированы")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации: {e}")
            await self.cleanup()
            raise
    
    async def send_initial_data(self) -> None:
        """Отправляет начальные аналитические данные в OpenAI."""
        try:
            logger.info("Получение и отправка начальных данных")
            
            # Получаем аналитические данные за 3 месяца
            start_time = time.time()
            market_data = await self.api_client.get_market_analytics()
            response_time = time.time() - start_time
            
            log_api_call("/api/v1/market/analytics", "GET", 200, response_time)
            
            # Отправляем данные в OpenAI
            start_time = time.time()
            response = await self.openai_handler.send_initial_data(market_data)
            response_time = time.time() - start_time
            
            log_openai_interaction("initial", len(response), response_time)
            
            # Парсим и обрабатываем ответ
            decision = self.parser.parse_and_validate(response)
            await self.execute_decision(decision)
            
            logger.success("Начальные данные успешно обработаны")
            
        except Exception as e:
            logger.error(f"Ошибка отправки начальных данных: {e}")
            raise
    
    async def trading_cycle(self) -> None:
        """Основной цикл торговли - выполняется каждые 5 минут."""
        try:
            logger.debug("Начало торгового цикла")
            
            # Логируем статус OpenAI обработчика
            status = self.openai_handler.get_status()
            logger.info(f"📊 СТАТУС OPENAI: попытки {status['retry_count']}/{status['max_retries']}, история: {status['conversation_length']} сообщений")
            
            # Получаем обновленные данные мониторинга
            start_time = time.time()
            market_data = await self.api_client.get_market_monitor()
            response_time = time.time() - start_time
            
            log_api_call("/api/v1/market/monitor", "GET", 200, response_time)
            
            # Отправляем обновления в OpenAI
            start_time = time.time()
            response = await self.openai_handler.send_update_data(market_data)
            response_time = time.time() - start_time
            
            log_openai_interaction("update", len(response), response_time)
            
            # Парсим и обрабатываем ответ
            decision = self.parser.parse_and_validate(response)
            await self.execute_decision(decision)
            
            logger.debug("Торговый цикл завершен успешно")
            
        except Exception as e:
            if "validation errors for MarketData" in str(e):
                logger.error(f"📊 ОШИБКА ВАЛИДАЦИИ ДАННЫХ: {e}")
                logger.info("💡 Возможно, формат ответа API изменился. Проверьте эндпоинт /api/v1/market/monitor")
            else:
                logger.error(f"❌ ОШИБКА В ТОРГОВОМ ЦИКЛЕ: {e}")
            # Не прерываем выполнение, продолжаем в следующем цикле
    
    async def execute_decision(
        self, 
        decision: BuyDecision | SellDecision | CancelDecision | PauseDecision
    ) -> None:
        """
        Выполняет торговое решение.
        
        Args:
            decision: Решение от OpenAI
        """
        try:
            if isinstance(decision, PauseDecision):
                log_trading_decision("pause", decision.response)
                logger.info(f"ПАУЗА: {decision.response}")
            
            elif isinstance(decision, BuyDecision):
                log_trading_decision(
                    "buy", 
                    f"Сумма: {decision.buy_amount} USDT, TP: {decision.take_profit_percent}%, SL: {decision.stop_loss_percent}%"
                )
                
                result = await self.api_client.place_buy_order(
                    decision.buy_amount,
                    decision.take_profit_percent,
                    decision.stop_loss_percent
                )
                
                logger.success(f"ПОКУПКА выполнена: {result}")
            
            elif isinstance(decision, SellDecision):
                log_trading_decision("sell", f"Количество: {decision.sell_amount} BTC")
                
                result = await self.api_client.place_sell_order(decision.sell_amount)
                logger.success(f"ПРОДАЖА выполнена: {result}")
            
            elif isinstance(decision, CancelDecision):
                log_trading_decision("cancel", f"Ордер ID: {decision.order_id}")
                
                result = await self.api_client.cancel_order(decision.order_id)
                logger.success(f"ОТМЕНА выполнена: {result}")
            
        except Exception as e:
            logger.error(f"Ошибка выполнения решения {type(decision).__name__}: {e}")
            raise
    
    async def run(self) -> None:
        """Запускает торгового бота."""
        if not self.is_initialized:
            raise RuntimeError("Бот не инициализирован. Вызовите initialize() сначала.")
        
        self.is_running = True
        logger.info("🚀 Торговый бот запущен")
        
        try:
            # Отправляем начальные данные
            await self.send_initial_data()
            
            # Основной цикл торговли
            while self.is_running:
                try:
                    await self.trading_cycle()
                    
                    # Ждем до следующего цикла (5 минут)
                    logger.info(f"Ожидание {self.settings.update_interval} секунд до следующего цикла")
                    await asyncio.sleep(self.settings.update_interval)
                    
                except KeyboardInterrupt:
                    logger.info("Получен сигнал остановки")
                    break
                except Exception as e:
                    logger.error(f"Критическая ошибка в основном цикле: {e}")
                    # Ждем перед повторной попыткой
                    await asyncio.sleep(60)
        
        finally:
            self.is_running = False
            await self.cleanup()
            logger.info("🛑 Торговый бот остановлен")
    
    async def stop(self) -> None:
        """Останавливает торгового бота."""
        logger.info("Получена команда остановки бота")
        self.is_running = False
    
    async def cleanup(self) -> None:
        """Очищает ресурсы."""
        try:
            if self.api_client:
                await self.api_client.close()
            logger.info("Ресурсы очищены")
        except Exception as e:
            logger.error(f"Ошибка при очистке ресурсов: {e}")


async def main():
    """Главная функция приложения."""
    try:
        # Загружаем настройки
        from config.settings import settings
        
        # Создаем и инициализируем бота
        bot = TradingBot(settings)
        await bot.initialize()
        
        # Запускаем бота
        await bot.run()
        
    except KeyboardInterrupt:
        logger.info("Прерывание пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
