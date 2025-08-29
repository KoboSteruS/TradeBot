"""Упрощенный обработчик OpenAI с Responses API."""
import json
import asyncio
import time
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
        
        # Защита от дублирования запросов
        self._request_in_progress = False
        self._last_request_timestamp = 0
        self._min_request_interval = 5  # Минимум 5 секунд между запросами
        self._request_lock = asyncio.Lock()
        
        logger.info("Инициализирован упрощенный OpenAI обработчик")
    
    def get_trader_prompt(self) -> str:
        """
        Возвращает промпт профессионального трейдера с дополнениями по торговой логике и безопасности.
        
        Returns:
            Текст промпта для OpenAI ассистента
        """
        return f"""Ты — профессиональный трейдер по паре BTC-USDT.  
Цель — достичь годовой доходности {self.settings.target_apy}% при минимальных рисках.  
Ты работаешь как опытный трейдер: анализируешь рынок, прогнозируешь движение цены и принимаешь решения в реальном времени. Ты не робот с фиксированными правилами, а трейдер, который адаптируется к текущим условиям.

### Основные принципы
- Анализируй рынок по таймфреймам: 5m, 15m, 1h, 4h, 1d.  
- Используй RSI, SMA20/50, MACD, ATR, объёмы, стакан, свечные паттерны.  
- Прогнозируй движение на 5–60 минут вперёд: ВВЕРХ, ВНИЗ или НЕОПРЕДЕЛЕННО.  
- Покупка только при прогнозе "ВВЕРХ".  
- Все сделки должны иметь SL и TP, рассчитанные динамически.  

### Риск-менеджмент
- Риск на сделку: 1–2% от капитала (в зависимости от силы сигнала).  
- Риск на серию усреднений: не более 5–6% капитала.  
- Соотношение риск/прибыль (RRR) ≥ 1:2.  
- Если рынок не даёт условий для RRR ≥ 1:2 → пауза, сделка не открывается.  
- Ошибки и убытки учитываются через риск: если серия сделок убыточна, автоматически снижается размер следующих входов.  

### Размер сделки
- Рассчитывается через риск и выбранный SL:  
  риск_USDT = баланс * (риск% / 100)  
  размер_сделки = риск_USDT / (SL% в цене)  
- Таким образом, риск фиксирован в %, а размер сделки адаптируется под рынок.  

### TP и SL (динамические)
- SL: за ближайший уровень поддержки (для лонга) либо = 1–1.5×ATR.  
- TP: рассчитывается так, чтобы RRR ≥ 1:2, либо до ближайшего сильного сопротивления, может подтягиваться выше при продолжении движения.  
- Управление: при росте цены и подтверждении тренда подтягивай SL вверх (трейлинг) и поднимай TP. При достижении 50% от TP фиксируй 50% позиции (частичная продажа).  

### Усреднение
- Допускается усреднение, если рынок идёт против позиции, но сохраняются признаки продолжения тренда.  
- Каждое усреднение учитывает общий риск: совокупный риск серии ≤ 5–6% капитала.  
- Усреднение вверх (добавление в растущую позицию) допустимо при усилении сигнала.  

### Сила сигнала
- Слабый (RSI 30–40, слабый объём) → риск 1%  
- Средний (RSI <30, подтверждён тренд) → риск 1.5%  
- Сильный (RSI <25, объём выше среднего, SMA20 > SMA50) → риск 2%  
- Отличный (RSI <20 + уровни + объём) → риск 2% и допускается усреднение вверх  

### Логика SELL
- Продажа по достижению TP или SL.  
- Частичная фиксация при +50% TP.  
- Полное закрытие при смене прогноза на ВНИЗ.  
- Возможна корректировка TP/SL в процессе сделки (трейлинг и адаптация).  

### Режим паузы
- Прогноз = ВНИЗ → пауза.  
- Прогноз = НЕОПРЕДЕЛЕННО → пауза, либо удержание текущей позиции без новых входов.  
- Если нет условий для RRR ≥ 1:2 → пауза.  

### КРИТИЧЕСКИ ВАЖНО - ФОРМАТ ОТВЕТА
Отвечай СТРОГО в формате JSON БЕЗ markdown разметки, БЕЗ ```json```, БЕЗ дополнительного текста!

PAUSE:
{{"status": "pause", "response": "ПРОГНОЗ: [ВВЕРХ/ВНИЗ/НЕОПРЕДЕЛЕННО] - причина паузы"}}

BUY:
{{"status": "buy", "response": "ПРОГНОЗ: ВВЕРХ - объяснение входа", "buy_amount": число_USDT, "take_profit_percent": число_процентов, "stop_loss_percent": число_процентов}}

SELL:
{{"status": "sell", "response": "причина продажи", "sell_amount": число_BTC}}

CANCEL:
{{"status": "cancel", "response": "причина отмены", "order_id": "ID_ордера"}}

ДОПУСТИМЫЕ СТАТУСЫ: "pause", "buy", "sell", "cancel"
ЗАПРЕЩЕННЫЕ СТАТУСЫ: "strategy", "analysis", "hold", "wait"

НЕ ДОБАВЛЯЙ ```json``` или любые другие маркеры! Только чистый JSON!"""
    
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
        Получает торговое решение от OpenAI с защитой от дублирования.
        
        Args:
            market_data: Рыночные данные
            is_initial: Первый запрос (с полной историей) или обновление
            
        Returns:
            JSON ответ с торговым решением
        """
        # Защита от дублирования запросов
        async with self._request_lock:
            current_time = time.time()
            
            # Проверяем, не слишком ли часто отправляем запросы (кроме проверки ордеров)
            if not is_initial and (current_time - self._last_request_timestamp) < self._min_request_interval:
                logger.warning(f"🚫 ЗАПРОС ОТКЛОНЕН: слишком быстро после предыдущего ({current_time - self._last_request_timestamp:.1f}s)")
                # Возвращаем последний успешный ответ или паузу
                if self.last_successful_response:
                    logger.info("🔄 ВОЗВРАЩАЮ ПОСЛЕДНИЙ УСПЕШНЫЙ ОТВЕТ")
                    return self.last_successful_response
                else:
                    return '{"status": "pause", "response": "ПРОГНОЗ: НЕОПРЕДЕЛЕННО - слишком частые запросы, ожидаю"}'
            
            # Проверяем, нет ли уже запроса в процессе
            if self._request_in_progress:
                logger.warning("🚫 ЗАПРОС УЖЕ ВЫПОЛНЯЕТСЯ - ОТКЛОНЯЮ ДУБЛИРУЮЩИЙ")
                if self.last_successful_response:
                    return self.last_successful_response
                else:
                    return '{"status": "pause", "response": "ПРОГНОЗ: НЕОПРЕДЕЛЕННО - предыдущий запрос еще обрабатывается"}'
            
            # Устанавливаем флаг выполнения запроса
            self._request_in_progress = True
            self._last_request_timestamp = current_time
            logger.info(f"🔒 БЛОКИРОВКА УСТАНОВЛЕНА - начинаю обработку запроса")
        
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
        finally:
            # Освобождаем блокировку
            self._request_in_progress = False
            logger.info("🔓 БЛОКИРОВКА СНЯТА - запрос завершен")
    
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
Баланс USDT: {market_data.user_data.get('balances', {}).get('USDT', 0)}
Баланс BTC: {market_data.user_data.get('balances', {}).get('BTC', 0)}
Активные ордера: {len(market_data.user_data.get('active_orders', []))}

ИНДИКАТОРЫ:
Текущая цена: {market_data.indicators.get('current_price', '0')}
Объем 24ч: {market_data.indicators.get('volume_24h', '0')}
Изменение 24ч: {market_data.indicators.get('change_24h', '0')}%
Максимум 24ч: {market_data.indicators.get('high_24h', '0')}
Минимум 24ч: {market_data.indicators.get('low_24h', '0')}

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
📋 Активные ордера: {len(market_data.user_data.get('active_orders', []))} записей

СТАКАН ОРДЕРОВ (топ-5):
{json.dumps(orderbook[:5], ensure_ascii=False, indent=2)}

ПОСЛЕДНИЕ СВЕЧИ (1m, топ-3):
{json.dumps(candles[:3], ensure_ascii=False, indent=2)}

БАЛАНС:
USDT: {market_data.user_data.get('balances', {}).get('USDT', 0)}
BTC: {market_data.user_data.get('balances', {}).get('BTC', 0)}

АКТИВНЫЕ ОРДЕРА:
{json.dumps(market_data.user_data.get('active_orders', []), ensure_ascii=False, indent=2)}

ТЕКУЩИЕ ИНДИКАТОРЫ:
Цена: {market_data.indicators.get('current_price', '0')}
Объем 24ч: {market_data.indicators.get('volume_24h', '0')}
Изменение 24ч: {market_data.indicators.get('change_24h', '0')}%
Максимум 24ч: {market_data.indicators.get('high_24h', '0')}
Минимум 24ч: {market_data.indicators.get('low_24h', '0')}

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
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_timestamp
        
        return {
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "has_last_response": self.last_successful_response is not None,
            "conversation_length": len(self.conversation_history),
            "request_in_progress": self._request_in_progress,
            "time_since_last_request": round(time_since_last_request, 1),
            "min_request_interval": self._min_request_interval,
            "can_make_request": time_since_last_request >= self._min_request_interval and not self._request_in_progress
        }
    
    def reset_retry_state(self) -> None:
        """Сбрасывает состояние повторных попыток."""
        self.retry_count = 0
        logger.info("🔄 Состояние повторных попыток сброшено")
    
    async def check_orders_decision(self, orders_data: Dict[str, Any], market_data: MarketData) -> str:
        """
        Получает решение по проверке и управлению ордерами.
        
        Args:
            orders_data: Данные активных ордеров
            market_data: Текущие рыночные данные
            
        Returns:
            JSON ответ с решением по ордерам
        """
        try:
            # Подготавливаем сообщение для проверки ордеров
            message = self._prepare_orders_check_message(orders_data, market_data)
            
            # Добавляем сообщение в историю
            self.conversation_history.append({
                "role": "user",
                "content": message
            })
            
            # Подготавливаем сообщения для API
            messages = [
                {"role": "system", "content": self.get_orders_check_prompt()}
            ] + self.conversation_history
            
            # Выполняем запрос к OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=300
            )
            
            assistant_response = response.choices[0].message.content
            
            # Логируем полный ответ от OpenAI
            logger.info(f"🤖 OPENAI ОТВЕТ ПО ОРДЕРАМ: {assistant_response}")
            
            # Добавляем ответ в историю
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_response
            })
            
            # Ограничиваем историю последними 10 сообщениями
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]
            
            return assistant_response
            
        except Exception as e:
            logger.error(f"Ошибка получения решения по ордерам от OpenAI: {e}")
            return '{"status": "pause", "response": "ОШИБКА ПРОВЕРКИ ОРДЕРОВ"}'
    
    def get_orders_check_prompt(self) -> str:
        """
        Возвращает промпт для проверки ордеров.
        
        Returns:
            Текст промпта для проверки ордеров
        """
        return """Ты — профессиональный трейдер по паре BTC-USDT, который анализирует активные ордера.

ТВОЯ ЗАДАЧА: Проанализировать каждый ордер и принять решение об отмене или продаже BTC.

АНАЛИЗ ОРДЕРОВ:
1. **ВРЕМЯ ЖИЗНИ**: Ордер > 60 минут → ОТМЕНИТЬ
2. **ОТКЛОНЕНИЕ ЦЕНЫ**: Цена ушла от ордера >2% → ОТМЕНИТЬ  
3. **ТРЕНД**: Тренд развернулся против позиции → ОТМЕНИТЬ
4. **ОБЪЕМЫ**: Объемы торгов упали значительно → ОТМЕНИТЬ

КРИТЕРИИ ОТМЕНЫ:
- Ордер висит >60 минут без движения
- Цена ушла от цены ордера на >2% в неблагоприятную сторону
- Тренд развернулся против позиции
- Объемы торгов упали значительно

КРИТЕРИИ ПРОДАЖИ BTC:
- Если есть BTC на балансе и нет активных ордеров → ПРОДАТЬ ВСЕ
- Если баланс USDT < 10 → ПРОДАТЬ ЧАСТЬ BTC

ДОПУСТИМЫЕ СТАТУСЫ: "pause", "cancel", "sell"
ЗАПРЕЩЕННЫЕ СТАТУСЫ: "buy", "strategy", "analysis", "hold", "wait"

КРИТИЧЕСКИ ВАЖНО - ФОРМАТ ОТВЕТА:
Отвечай СТРОГО в формате JSON БЕЗ ```json``` БЕЗ дополнительного текста!

PAUSE (ничего не делать):
{{"status": "pause", "response": "ПРОГНОЗ: [ВВЕРХ/ВНИЗ/НЕОПРЕДЕЛЕННО] - все ордера в порядке"}}

CANCEL (отменить ордер):
{{"status": "cancel", "response": "ПРОГНОЗ: [ВВЕРХ/ВНИЗ/НЕОПРЕДЕЛЕННО] - причина отмены", "order_id": "ID_ордера"}}

SELL (продать BTC):
{{"status": "sell", "response": "причина продажи", "sell_amount": число_BTC}}

НЕ ДОБАВЛЯЙ никаких маркеров! Только чистый JSON!"""
    
    def _prepare_orders_check_message(self, orders_data: Dict[str, Any], market_data: MarketData) -> str:
        """
        Подготавливает сообщение для проверки ордеров.
        
        Args:
            orders_data: Данные активных ордеров
            market_data: Текущие рыночные данные
            
        Returns:
            Сообщение для OpenAI
        """
        orders = orders_data.get('orders', [])
        current_time = time.time()
        current_price = float(market_data.indicators.get('current_price', 0))
        
        # Анализируем ордера с детальной информацией
        orders_info = []
        for order in orders:
            order_time = int(order.get('cTime', '0')) / 1000  # Конвертируем из миллисекунд
            age_minutes = (current_time - order_time) / 60
            order_price = float(order.get('px', 0))
            
            # Рассчитываем отклонение цены
            if current_price > 0 and order_price > 0:
                price_deviation = ((current_price - order_price) / order_price) * 100
                price_status = "ВЫШЕ" if price_deviation > 0 else "НИЖЕ"
            else:
                price_deviation = 0
                price_status = "НЕИЗВЕСТНО"
            
            # Анализируем состояние ордера
            order_state = order.get('state', 'N/A')
            side = order.get('side', 'N/A')
            
            # Определяем тип ордера и его параметры
            order_type = "ПОКУПКА" if side == "buy" else "ПРОДАЖА"
            
            orders_info.append(f"""
Ордер {order.get('ordId', 'N/A')}:
- Тип: {order_type}
- Инструмент: {order.get('instId', 'N/A')}
- Цена ордера: {order_price} USDT
- Текущая цена: {current_price} USDT
- Отклонение: {price_deviation:.2f}% ({price_status})
- Размер: {order.get('sz', 'N/A')} BTC
- Состояние: {order_state}
- Возраст: {age_minutes:.1f} минут
- Время создания: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(order_time))}
""")
        
        # Получаем рыночные индикаторы для анализа
        indicators = market_data.indicators
        market_analysis = f"""
АНАЛИЗ РЫНКА:
- Текущая цена: {current_price} USDT
- Изменение 24ч: {indicators.get('change_24h', 'N/A')}%
- Объем 24ч: {indicators.get('volume_24h', 'N/A')}
- Максимум 24ч: {indicators.get('high_24h', 'N/A')} USDT
- Минимум 24ч: {indicators.get('low_24h', 'N/A')} USDT
- Волатильность: {abs(float(indicators.get('change_24h', 0))):.2f}%
"""
        
        return f"""ПРОВЕРКА АКТИВНЫХ ОРДЕРОВ:

Время проверки: {time.strftime('%Y-%m-%d %H:%M:%S')}

{market_analysis}

АКТИВНЫЕ ОРДЕРА ({len(orders)}):
{chr(10).join(orders_info) if orders_info else "Нет активных ордеров"}

ТЕКУЩИЙ БАЛАНС:
- USDT: {market_data.user_data.get('balances', {}).get('USDT', 0)}
- BTC: {market_data.user_data.get('balances', {}).get('BTC', 0)}

АНАЛИЗИРУЙ КАЖДЫЙ ОРДЕР ОТДЕЛЬНО:
1. Сравни текущую цену с ценой ордера
2. Оцени возраст ордера и его актуальность
3. Проанализируй рыночные условия
4. Прими решение: оставить, отменить или продать

Ответь в формате JSON с обоснованием решения."""
    
    async def initialize(self) -> None:
        """Инициализация обработчика - ничего дополнительного не требуется."""
        logger.info("Упрощенный OpenAI обработчик готов к работе")
