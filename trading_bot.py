"""Основной модуль торгового бота."""
import asyncio
import time
from typing import Optional
from loguru import logger

from config.settings import Settings
from services import TradingAPIClient, TelegramNotifier
from services.openai_simple_handler import OpenAISimpleHandler
from handlers import ResponseParser
from models.trading import MarketData
from models.responses import BuyDecision, SellDecision, CancelDecision, PauseDecision, OrdersCancelDecision, OrdersSellDecision, TradingDecision, OrdersDecision
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
        self.telegram_notifier: Optional[TelegramNotifier] = None
        self.parser = ResponseParser()
        self.is_initialized = False
        self.is_running = False
        
        # Таймеры для проверки ордеров
        self.last_orders_check = 0
        self.orders_check_interval = 600  # 10 минут в секундах (более частые проверки для лучшего анализа)
        
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
            
            # Инициализируем Telegram уведомления
            self.telegram_notifier = TelegramNotifier(self.settings)
            if not await self.telegram_notifier.test_connection():
                logger.warning("⚠️ Не удалось подключиться к Telegram API")
            else:
                logger.success("✅ Telegram уведомления подключены")
            
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
            await self.execute_decision(decision, market_data)
            
            logger.success("Начальные данные успешно обработаны")
            
        except Exception as e:
            logger.error(f"Ошибка отправки начальных данных: {e}")
            raise
    
    async def check_orders_cycle(self) -> None:
        """Проверка и управление ордерами - выполняется каждые 10 минут."""
        try:
            current_time = time.time()
            
            # Проверяем, нужно ли проверять ордера
            if current_time - self.last_orders_check < self.orders_check_interval:
                return
            
            logger.info("🔄 НАЧАЛО ПРОВЕРКИ ОРДЕРОВ")
            
            # Получаем активные ордера
            start_time = time.time()
            orders_data = await self.api_client.get_orders()
            response_time = time.time() - start_time
            
            log_api_call("/api/v1/orders", "GET", 200, response_time)
            
            # Получаем текущие рыночные данные
            market_data = await self.api_client.get_market_monitor()
            
            # Получаем решение от OpenAI по ордерам
            start_time = time.time()
            response = await self.openai_handler.check_orders_decision(orders_data, market_data)
            response_time = time.time() - start_time
            
            log_openai_interaction("orders_check", len(response), response_time)
            
            # Парсим и выполняем решение
            decision = self.parser.parse_orders_decision(response)
            await self.execute_orders_decision(decision)
            
            # Обновляем время последней проверки
            self.last_orders_check = current_time
            logger.success("✅ ПРОВЕРКА ОРДЕРОВ ЗАВЕРШЕНА")
            
        except Exception as e:
            logger.error(f"❌ ОШИБКА ПРОВЕРКИ ОРДЕРОВ: {e}")
            # Не прерываем выполнение, продолжаем в следующем цикле
    
    async def trading_cycle(self) -> None:
        """Основной цикл торговли - выполняется каждые 5 минут."""
        try:
            logger.debug("Начало торгового цикла")
            
            # Логируем статус OpenAI обработчика
            status = self.openai_handler.get_status()
            logger.info(f"📊 СТАТУС OPENAI: попытки {status['retry_count']}/{status['max_retries']}, история: {status['conversation_length']} сообщений")
            logger.info(f"🔒 ЗАЩИТА ОТ ДУБЛИРОВАНИЯ: активен={status['request_in_progress']}, последний запрос {status['time_since_last_request']}s назад, можно запрос={status['can_make_request']}")
            
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
            await self.execute_decision(decision, market_data)
            
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
        decision: BuyDecision | SellDecision | CancelDecision | PauseDecision,
        market_data: MarketData
    ) -> None:
        """
        Выполняет торговое решение.
        
        Args:
            decision: Решение от OpenAI
            market_data: Текущие рыночные данные
        """
        try:
            if isinstance(decision, PauseDecision):
                log_trading_decision("pause", decision.response)
                logger.info(f"ПАУЗА: {decision.response}")
            
            elif isinstance(decision, BuyDecision):
                # Проверяем баланс перед покупкой (агрессивная стратегия)
                current_balance = market_data.user_data.get('balances', {}).get('USDT', 0)
                
                # Минимальный размер сделки 10 USDT
                if decision.buy_amount < 10:
                    logger.warning(f"⚠️ СЛИШКОМ МАЛАЯ СДЕЛКА: {decision.buy_amount} USDT < 10 USDT минимума")
                    log_trading_decision("pause", f"Слишком малая сделка: {decision.buy_amount} USDT < 10 USDT минимума")
                    return
                
                # Проверяем достаточность средств
                if current_balance < decision.buy_amount:
                    logger.warning(f"⚠️ НЕДОСТАТОЧНО СРЕДСТВ: требуется {decision.buy_amount} USDT, доступно {current_balance} USDT")
                    log_trading_decision("pause", f"Недостаточно средств для покупки: требуется {decision.buy_amount} USDT, доступно {current_balance} USDT")
                    return
                
                # Проверяем резерв (оставляем 30-40 USDT)
                reserve_needed = 35  # средний резерв
                available_for_trading = current_balance - reserve_needed
                
                if decision.buy_amount > available_for_trading:
                    logger.warning(f"⚠️ НАРУШЕНИЕ РЕЗЕРВА: сделка {decision.buy_amount} USDT оставит меньше {reserve_needed} USDT резерва")
                    log_trading_decision("pause", f"Нарушение резерва: сделка {decision.buy_amount} USDT оставит меньше {reserve_needed} USDT резерва")
                    return
                
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
                
                # Отправляем Telegram уведомление о покупке
                if self.telegram_notifier:
                    try:
                        current_price = market_data.indicators.get('current_price', 'N/A')
                        await self.telegram_notifier.notify_buy_order(
                            decision.buy_amount,
                            decision.take_profit_percent,
                            decision.stop_loss_percent,
                            current_price,
                            decision.response
                        )
                    except Exception as e:
                        logger.error(f"Ошибка отправки Telegram уведомления о покупке: {e}")
            
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
    
    async def execute_orders_decision(self, decision: OrdersDecision) -> None:
        """
        Выполняет решение по управлению ордерами.
        
        Args:
            decision: Решение от OpenAI по ордерам
        """
        try:
            if isinstance(decision, PauseDecision):
                log_trading_decision("orders_pause", decision.response)
                logger.info(f"ОРДЕРА ПАУЗА: {decision.response}")
            
            elif isinstance(decision, OrdersCancelDecision):
                log_trading_decision("orders_cancel", f"Ордер: {decision.order_id} - {decision.response}")
                
                # Отменяем ордер через новый метод
                result = await self.api_client.cancel_order_by_inst_id("BTC-USDT", decision.order_id)
                
                logger.success(f"ОТМЕНА ОРДЕРА выполнена: {result}")
                
                # Отправляем Telegram уведомление об отмене
                if self.telegram_notifier:
                    try:
                        # Получаем детали ордера для уведомления
                        orders_data = await self.api_client.get_orders()
                        order_details = None
                        
                        for order in orders_data.get('orders', []):
                            if order.get('ordId') == decision.order_id:
                                order_details = order
                                break
                        
                        await self.telegram_notifier.notify_cancel_order(
                            decision.order_id,
                            decision.response,
                            order_details
                        )
                    except Exception as e:
                        logger.error(f"Ошибка отправки Telegram уведомления об отмене: {e}")
                
                # После отмены проверяем баланс и продаем BTC если нужно
                await self._handle_post_cancel_actions()
            
            elif isinstance(decision, OrdersSellDecision):
                log_trading_decision("orders_sell", f"Продажа: {decision.sell_amount or 'все'} BTC - {decision.response}")
                
                if decision.sell_amount is None:
                    # Продаем весь BTC
                    result = await self.api_client.sell_all_btc()
                else:
                    # Продаем указанное количество
                    result = await self.api_client.place_sell_order(decision.sell_amount)
                
                logger.success(f"ПРОДАЖА ОРДЕРА выполнена: {result}")
            
            else:
                logger.warning(f"Неизвестный тип решения по ордерам: {type(decision)}")
                
        except Exception as e:
            logger.error(f"Ошибка выполнения решения по ордерам: {e}")
    
    async def _handle_post_cancel_actions(self) -> None:
        """Обрабатывает действия после отмены ордера."""
        try:
            # Получаем обновленный баланс
            market_data = await self.api_client.get_market_monitor()
            btc_balance = market_data.user_data.get('balances', {}).get('BTC', 0)
            
            if btc_balance > 0:
                logger.info(f"💰 ПОСЛЕ ОТМЕНЫ ОРДЕРА: есть {btc_balance} BTC для продажи")
                
                # Продаем весь BTC
                result = await self.api_client.sell_all_btc()
                logger.success(f"ПРОДАЖА ПОСЛЕ ОТМЕНЫ: {result}")
                
                # Отправляем Telegram уведомление о продаже после отмены
                if self.telegram_notifier:
                    try:
                        await self.telegram_notifier.notify_sell_after_cancel(
                            btc_balance,
                            "Автоматическая продажа BTC после отмены ордера"
                        )
                    except Exception as e:
                        logger.error(f"Ошибка отправки Telegram уведомления о продаже после отмены: {e}")
            else:
                logger.info("💰 ПОСЛЕ ОТМЕНЫ ОРДЕРА: нет BTC для продажи")
                
        except Exception as e:
            logger.error(f"Ошибка обработки действий после отмены: {e}")
    
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
                    # Проверяем ордера каждые 30 минут
                    await self.check_orders_cycle()
                    
                    # Основной торговый цикл каждые 5 минут
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
            if self.telegram_notifier:
                await self.telegram_notifier.close()
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
