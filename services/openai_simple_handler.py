"""Упрощенный обработчик OpenAI с Responses API."""
import json
import asyncio
from typing import Dict, Any, List, Optional
import openai
from loguru import logger

from config.settings import Settings
from models.trading import MarketData


class OpenAISimpleHandler:
    """
    Упрощенный обработчик для работы с OpenAI через Responses API.
    
    Использует простые чат-завершения вместо сложного Assistants API.
    """
    
    def __init__(self, settings: Settings):
        """
        Инициализация обработчика.
        
        Args:
            settings: Настройки приложения
        """
        self.settings = settings
        self.client = openai.OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.conversation_history: List[Dict[str, str]] = []
        
        # Состояние для обработки ошибок
        self.last_successful_response: Optional[str] = None
        self.retry_count = 0
        self.max_retries = 3
        self.retry_delay = 300  # 5 минут в секундах
        
        logger.info("Инициализирован упрощенный OpenAI обработчик")
    
    def get_trader_prompt(self) -> str:
        """
        Возвращает промпт профессионального трейдера с дополнениями по торговой логике и безопасности.
        
        Returns:
            Текст промпта для OpenAI ассистента
        """
        return f"""Ты — профессиональный трейдер по паре BTC-USDT.
Твоя задача — постоянно анализировать рынок, адаптироваться к текущим условиям и вести торговлю так, чтобы достичь заданной цели доходности при минимально возможных рисках.
Ты действуешь не как жёсткий торговый робот, а как опытный трейдер: используешь технический и контекстный анализ, следишь за балансом, открытыми позициями и реакцией рынка в режиме реального времени.

ЦЕЛЬ:
target_apy = {self.settings.target_apy}  # целевая годовая доходность в %

Ты стремишься принимать **частые, но безопасные** торговые решения, максимизируя прибыль и минимизируя риски.
Основная цель — **ПРЕДСКАЗЫВАТЬ НАПРАВЛЕНИЕ ДВИЖЕНИЯ ЦЕНЫ** на основе комплексного анализа и находить лучшие точки входа для покупки BTC с оптимальными take profit (TP) и stop loss (SL).

ТВОЯ ГЛАВНАЯ ЗАДАЧА - ПРОГНОЗИРОВАНИЕ:
1. **АНАЛИЗИРУЙ КУДА ПОЙДЕТ ЦЕНА** в ближайшие 5-60 минут
2. **ОПРЕДЕЛЯЙ ВЕРОЯТНОСТЬ РОСТА/ПАДЕНИЯ** на основе технических индикаторов  
3. **ПОКУПАЙ BTC ТОЛЬКО** когда уверен в росте цены
4. **УСТАНАВЛИВАЙ ТОЧНЫЕ TP/SL** исходя из прогноза движения

УЧИТЫВАЕШЬ ПРИ РЕШЕНИИ:
- Крупные таймфреймы (1h, 4h, 1d): тренд, уровни поддержки/сопротивления.
- Малые таймфреймы (5m, 15m): импульсы, сигналы на вход, короткие тенденции.
- Текущую цену (`last`), high24h и low24h.
- Скользящие средние (SMA20, SMA50).
- RSI, ATR, объём торгов.
- Глубину стакана, если доступна.
- Динамику последних свечей: тени, волатильность, цвет.
- Время суток и день недели.
- Историю последних сделок (последние 3+ сделки).

АЛГОРИТМ РАБОТЫ:
1. При первом сообщении я передаю историю рыночных данных:
   - 5m: 144 баров
   - 15m: 96 баров  
   - 1h: 72 бара
   - 4h: 90 баров
   - 1d: 90 баров
   Плюс: стакан (топ-20 bid/ask с объёмами и изменениями), баланс, открытые ордера.
   Ты анализируешь данные, формируешь стартовую торговую картину и начальные параметры риск-менеджмента для достижения цели.

2. Каждые 5 минут я передаю обновления:
   - последние 10 минутных свечей (OHLCV с timestamp);
   - актуальный стакан (топ-20 bid/ask, объёмы, изменения);
   - текущий баланс;
   - открытые ордера.
   Ты обновляешь внутреннюю историю, пересчитываешь все старшие таймфреймы (5m, 15m, 1h, 4h, 1d), индикаторы (RSI, MACD, SMA, EMA, ATR и т.д.) и корректируешь стратегию.

УСЛОВИЯ ДЛЯ ПОКУПКИ (пример логики):
- Если `last < low24h + 0.2%` → можно купить на 20% от баланса.
- Если `last > high24h - 0.2%` → максимум 5% от баланса.
- Если цена внутри диапазона и высокая волатильность/объём → до 10% от баланса.
- RSI < 30 → сигнал на вход (перепроданность). RSI > 70 → пропустить.
- SMA20 > SMA50 → подтверждённый тренд вверх.
- SMA20 <= SMA50 → покупка только при совпадении сигналов на малом и большом ТФ.
- Объём за 5 минут > среднего за 1 час → подтверждение сигнала.
- Падение объёма → пропустить.

TP/SL:
- Если доступен ATR:
  - TP% = min(ATR * 1.2, 0.5)
  - SL% = min(ATR * 0.8, 0.2)
- Если ATR недоступен:
  - волатильность < 0.8% → TP 1%, SL 0.5%
  - волатильность 0.8–1.5% → TP 2%, SL 1%
  - волатильность > 1.5% → TP 3%, SL 1.5%

БЕЗОПАСНОСТЬ:
- Не покупай, если:
  - баланс < 20% от начального;
  - открыто > 3 ордеров;
  - задействовано > 70% капитала;
  - последняя сделка была < 5 минут назад;
  - последние 3 сделки убыточны → пауза на 60 минут.
- Минимальный размер ордера: 0.00001 BTC.
- Размер `sz` форматируй как строку с 8 знаками после запятой.
- TP и SL округляй до 0.1 USDT.
- Отменяй ордера, если:
  - цена ушла против позиции на 0.3% и нет признаков разворота;
  - ордер не исполнен в течение 10 минут.

РИСК-МЕНЕДЖМЕНТ (динамический):
- Сам подбираешь риск на сделку, RRR, размер позиции, количество одновременно открытых сделок и условия перевода в безубыток, исходя из текущего состояния рынка и цели доходности.
- В периоды высокой волатильности — снижаешь риск, при стабильном рынке — можешь увеличивать.
- Если рынок без направления — приостанавливаешь торговлю или действуешь минимальными объёмами.

АНАЛИЗ И ПРОГНОЗИРОВАНИЕ РЫНКА:
- **ОБЯЗАТЕЛЬНО АНАЛИЗИРУЙ НАПРАВЛЕНИЕ**: определи куда вероятнее всего пойдет цена в следующие 5-60 минут
- **ТЕХНИЧЕСКИЙ АНАЛИЗ**: тренды по разным ТФ, ключевые уровни, реакция в стакане, объёмы, паттерны, волатильность (ATR)
- **ПОВЕДЕНЧЕСКИЙ АНАЛИЗ**: поведение покупателей и продавцов, давление на цену, силу движения
- **КОНТЕКСТНЫЙ АНАЛИЗ**: настроение рынка (risk-on/risk-off), корреляция с другими активами, аномальные движения
- **ПРОГНОЗ ЦЕНЫ**: на основе всех факторов делай четкий прогноз - ВВЕРХ, ВНИЗ или НЕОПРЕДЕЛЕННО
- **РЕШЕНИЕ О ПОКУПКЕ**: покупай BTC ТОЛЬКО при прогнозе "ВВЕРХ" с высокой вероятностью
- Если прогноз неопределенный или направлен вниз - используй "pause" и объясни причину

ФОРМАТ ОТВЕТА:
Всегда отвечай ТОЛЬКО в формате JSON без дополнительного текста:

Для паузы:
{{
  "status": "pause",
  "response": "ПРОГНОЗ: [ВВЕРХ/ВНИЗ/НЕОПРЕДЕЛЕННО] - объяснение почему не покупаю"
}}

Для покупки BTC:
{{
  "status": "buy", 
  "response": "ПРОГНОЗ: ВВЕРХ - краткое объяснение почему цена пойдет вверх и логика TP/SL",
  "buy_amount": числовое_значение_в_USDT,
  "take_profit_percent": процент_тейк_профита_основанный_на_прогнозе,
  "stop_loss_percent": процент_стоп_лосса_основанный_на_анализе
}}

Для продажи:
{{
  "status": "sell",
  "response": "краткое объяснение решения", 
  "sell_amount": количество_BTC_для_продажи
}}

Для отмены ордера:
{{
  "status": "cancel",
  "response": "краткое объяснение решения",
  "order_id": "ID_ордера_для_отмены"
}}

ВАЖНО: Ответ должен быть валидным JSON без дополнительных символов или текста!"""
    
    async def _handle_region_error(self) -> Optional[str]:
        """
        Обрабатывает ошибку региона, ждет и возвращает последний успешный ответ.
        
        Returns:
            Последний успешный ответ или None если его нет
        """
        self.retry_count += 1
        
        if self.retry_count > self.max_retries:
            logger.error(f"🚫 Превышено максимальное количество попыток ({self.max_retries})")
            return None
        
        logger.warning(f"🌍 ОШИБКА РЕГИОНА: попытка {self.retry_count}/{self.max_retries}")
        
        if self.last_successful_response:
            logger.info(f"♻️ ВОЗВРАЩАЮ ПОСЛЕДНЕЕ УСПЕШНОЕ РЕШЕНИЕ: {self.last_successful_response}")
            return self.last_successful_response
        else:
            # Если нет предыдущего ответа, возвращаем решение о паузе
            fallback_response = {
                "status": "pause",
                "response": f"Ошибка региона OpenAI, ожидание {self.retry_delay//60} минут (попытка {self.retry_count}/{self.max_retries})"
            }
            fallback_json = json.dumps(fallback_response, ensure_ascii=False)
            logger.info(f"⏸️ FALLBACK РЕШЕНИЕ: {fallback_json}")
            return fallback_json
    
    async def _wait_and_retry(self) -> None:
        """Ждет перед повторной попыткой."""
        logger.info(f"⏰ ОЖИДАНИЕ {self.retry_delay} секунд ({self.retry_delay//60} минут)...")
        await asyncio.sleep(self.retry_delay)
    
    def _is_valid_response(self, response: str) -> bool:
        """
        Проверяет, содержит ли ответ правильный статус.
        
        Args:
            response: Ответ от OpenAI
            
        Returns:
            True если статус правильный, False в противном случае
        """
        try:
            import json
            data = json.loads(response.strip())
            status = data.get('status', '').lower()
            valid_statuses = ['pause', 'buy', 'sell', 'cancel']
            return status in valid_statuses
        except:
            return False
    
    async def get_trading_decision(self, market_data: MarketData, is_initial: bool = False) -> str:
        """
        Получает торговое решение от OpenAI.
        
        Args:
            market_data: Рыночные данные
            is_initial: Первый запрос (с полной историей) или обновление
            
        Returns:
            JSON ответ с торговым решением
        """
        try:
            # Подготавливаем сообщение
            if is_initial:
                message = self._prepare_initial_message(market_data)
                logger.info("📊 ОТПРАВКА НАЧАЛЬНЫХ ДАННЫХ В OPENAI")
            else:
                message = self._prepare_update_message(market_data)
                logger.info("🔄 ОТПРАВКА ОБНОВЛЕННЫХ ДАННЫХ В OPENAI")
            
            # Логируем размер сообщения (без полного содержимого - оно очень большое)
            logger.debug(f"📏 РАЗМЕР СООБЩЕНИЯ: {len(message)} символов")
            
            # Добавляем сообщение в историю
            self.conversation_history.append({
                "role": "user",
                "content": message
            })
            
            # Подготавливаем сообщения для API
            messages = [
                {"role": "system", "content": self.get_trader_prompt()}
            ] + self.conversation_history
            
            # Выполняем запрос к OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=500
            )
            
            assistant_response = response.choices[0].message.content
            
            # Логируем информацию об использованных токенах
            if response.usage:
                logger.info(f"💰 ТОКЕНЫ: input={response.usage.prompt_tokens}, output={response.usage.completion_tokens}, total={response.usage.total_tokens}")
            
            # Логируем полный ответ от OpenAI
            logger.info(f"🤖 OPENAI ПОЛНЫЙ ОТВЕТ: {assistant_response}")
            
            # Проверяем ответ на правильность статуса
            if not self._is_valid_response(assistant_response):
                logger.warning("🔄 НЕПРАВИЛЬНЫЙ ОТВЕТ, ПРОБУЮ ЕЩЕ РАЗ...")
                # Добавляем уточняющее сообщение
                clarification = "ВНИМАНИЕ! Твой предыдущий ответ содержал неправильный статус. ИСПОЛЬЗУЙ ТОЛЬКО: pause, buy, sell, cancel. Дай правильный ответ:"
                self.conversation_history.append({
                    "role": "user", 
                    "content": clarification
                })
                
                # Повторный запрос
                messages = [
                    {"role": "system", "content": self.get_trader_prompt()}
                ] + self.conversation_history
                
                retry_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=200
                )
                
                assistant_response = retry_response.choices[0].message.content
                logger.info(f"🔄 ПОВТОРНЫЙ ОТВЕТ OPENAI: {assistant_response}")
            
            # Сохраняем последний успешный ответ
            self.last_successful_response = assistant_response
            self.retry_count = 0  # Сбрасываем счетчик попыток при успехе
            
            # Добавляем ответ в историю
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_response
            })
            
            # Ограничиваем историю последними 10 сообщениями
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]
            
            logger.success("✅ Получен успешный ответ от OpenAI")
            return assistant_response
            
        except openai.PermissionDeniedError as e:
            if "unsupported_country_region_territory" in str(e):
                logger.error(f"🌍 ОШИБКА РЕГИОНА OpenAI: {e}")
                
                # Обрабатываем ошибку региона
                fallback_response = await self._handle_region_error()
                if fallback_response:
                    # Ждем перед следующей попыткой
                    await self._wait_and_retry()
                    return fallback_response
                else:
                    raise
            else:
                logger.error(f"Ошибка доступа OpenAI: {e}")
                raise
        except Exception as e:
            logger.error(f"Ошибка получения решения от OpenAI: {e}")
            raise
    
    def _prepare_initial_message(self, market_data: MarketData) -> str:
        """
        Подготавливает начальное сообщение с полными данными.
        
        Args:
            market_data: Аналитические данные рынка
            
        Returns:
            Сообщение для OpenAI
        """
        return f"""НАЧАЛЬНЫЕ ДАННЫЕ ДЛЯ АНАЛИЗА:

Торговая пара: {market_data.inst_id}
Время: {market_data.timestamp}

РЫНОЧНЫЕ ДАННЫЕ:
{json.dumps(market_data.market_data, ensure_ascii=False, indent=2)}

ПОЛЬЗОВАТЕЛЬСКИЕ ДАННЫЕ:
Баланс USDT: {market_data.user_data.balances.USDT}
Баланс BTC: {market_data.user_data.balances.BTC}
Активные ордера: {len(market_data.user_data.active_orders)}

ИНДИКАТОРЫ:
Текущая цена: {market_data.indicators.current_price}
Объем 24ч: {market_data.indicators.volume_24h}
Изменение 24ч: {market_data.indicators.change_24h}%
Максимум 24ч: {market_data.indicators.high_24h}
Минимум 24ч: {market_data.indicators.low_24h}

Проанализируй данные и сформируй начальную торговую стратегию. Ответь в формате JSON."""
    
    def _prepare_update_message(self, market_data: MarketData) -> str:
        """
        Подготавливает сообщение с обновленными данными.
        
        Args:
            market_data: Данные мониторинга рынка
            
        Returns:
            Сообщение для OpenAI
        """
        orderbook = market_data.market_data.get('orderbook', [])
        candles = market_data.market_data.get('candles', {}).get('1m', [])
        
        return f"""ОБНОВЛЕНИЕ РЫНОЧНЫХ ДАННЫХ:

Время: {market_data.timestamp}

СТАТИСТИКА ДАННЫХ:
📊 Стакан ордеров: {len(orderbook)} записей
📈 Минутные свечи: {len(candles)} записей  
📋 Активные ордера: {len(market_data.user_data.active_orders)} записей

СТАКАН ОРДЕРОВ (топ-5):
{json.dumps(orderbook[:5], ensure_ascii=False, indent=2)}

ПОСЛЕДНИЕ СВЕЧИ (1m, топ-3):
{json.dumps(candles[:3], ensure_ascii=False, indent=2)}

БАЛАНС:
USDT: {market_data.user_data.balances.USDT}
BTC: {market_data.user_data.balances.BTC}

АКТИВНЫЕ ОРДЕРА:
{json.dumps(market_data.user_data.active_orders, ensure_ascii=False, indent=2)}

ТЕКУЩИЕ ИНДИКАТОРЫ:
Цена: {market_data.indicators.current_price}
Объем 24ч: {market_data.indicators.volume_24h}
Изменение 24ч: {market_data.indicators.change_24h}%
Максимум 24ч: {market_data.indicators.high_24h}
Минимум 24ч: {market_data.indicators.low_24h}

Обнови свой анализ и прими торговое решение на основе ДОСТУПНЫХ данных. Ответь в формате JSON."""
    
    async def send_initial_data(self, market_data: MarketData) -> str:
        """
        Отправляет начальные данные и получает первое решение.
        
        Args:
            market_data: Аналитические данные рынка
            
        Returns:
            JSON ответ с торговым решением
        """
        return await self.get_trading_decision(market_data, is_initial=True)
    
    async def send_update_data(self, market_data: MarketData) -> str:
        """
        Отправляет обновленные данные и получает решение.
        
        Args:
            market_data: Данные мониторинга рынка
            
        Returns:
            JSON ответ с торговым решением
        """
        return await self.get_trading_decision(market_data, is_initial=False)
    
    def get_status(self) -> Dict[str, Any]:
        """
        Возвращает текущий статус обработчика.
        
        Returns:
            Словарь с информацией о статусе
        """
        return {
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "has_last_response": self.last_successful_response is not None,
            "conversation_length": len(self.conversation_history)
        }
    
    def reset_retry_state(self) -> None:
        """Сбрасывает состояние повторных попыток."""
        self.retry_count = 0
        logger.info("🔄 Состояние повторных попыток сброшено")
    
    async def initialize(self) -> None:
        """Инициализация обработчика - ничего дополнительного не требуется."""
        logger.info("Упрощенный OpenAI обработчик готов к работе")
