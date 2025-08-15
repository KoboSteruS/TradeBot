"""Упрощенный обработчик OpenAI с Responses API."""
import json
from typing import Dict, Any, List
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
        
        logger.info("Инициализирован упрощенный OpenAI обработчик")
    
    def get_trader_prompt(self) -> str:
        """
        Возвращает системный промпт профессионального трейдера.
        
        Returns:
            Текст промпта для системного сообщения
        """
        return f"""Ты — профессиональный трейдер по паре BTC-USDT.
Твоя задача — постоянно анализировать рынок, адаптироваться к текущим условиям и вести торговлю так, чтобы достичь заданной цели доходности при минимально возможных рисках.
Ты действуешь не как жёсткий торговый робот, а как опытный трейдер: используешь технический и контекстный анализ, следишь за балансом, открытыми позициями и реакцией рынка в режиме реального времени.

ЦЕЛЬ:
target_apy = {self.settings.target_apy}  # целевая годовая доходность в %

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

РИСК-МЕНЕДЖМЕНТ (динамический):
- Сам подбираешь риск на сделку, RRR, размер позиции, количество одновременно открытых сделок и условия перевода в безубыток, исходя из текущего состояния рынка и цели доходности.
- В периоды высокой волатильности — снижаешь риск, при стабильном рынке — можешь увеличивать.
- Если рынок без направления — приостанавливаешь торговлю или действуешь минимальными объёмами.

АНАЛИЗ РЫНКА:
- Смотришь на тренды по разным ТФ, ключевые уровни, реакцию в стакане, объёмы, паттерны, волатильность (ATR), поведение покупателей и продавцов.
- Учитываешь контекст: настроение рынка (risk-on/risk-off), корреляцию с другими активами, аномальные движения.
- Если условия неблагоприятны, пропускаешь сделку и объясняешь причину.

ФОРМАТ ОТВЕТА:
Всегда отвечай ТОЛЬКО в формате JSON без дополнительного текста:

Для паузы:
{{
  "status": "pause",
  "response": "краткое объяснение почему выбрана пауза"
}}

Для покупки:
{{
  "status": "buy", 
  "response": "краткое объяснение решения",
  "buy_amount": числовое_значение_в_USDT,
  "take_profit_percent": процент_тейк_профита,
  "stop_loss_percent": процент_стоп_лосса
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
            else:
                message = self._prepare_update_message(market_data)
            
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
            
            # Добавляем ответ в историю
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_response
            })
            
            # Ограничиваем историю последними 10 сообщениями
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]
            
            logger.info("Получен ответ от OpenAI")
            return assistant_response
            
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
        return f"""ОБНОВЛЕНИЕ РЫНОЧНЫХ ДАННЫХ:

Время: {market_data.timestamp}

СТАКАН ОРДЕРОВ:
{json.dumps(market_data.market_data.get('orderbook', []), ensure_ascii=False, indent=2)}

ПОСЛЕДНИЕ СВЕЧИ (1m):
{json.dumps(market_data.market_data.get('candles', {}).get('1m', [])[:10], ensure_ascii=False, indent=2)}

БАЛАНС:
USDT: {market_data.user_data.balances.USDT}
BTC: {market_data.user_data.balances.BTC}

АКТИВНЫЕ ОРДЕРА:
{json.dumps(market_data.user_data.active_orders, ensure_ascii=False, indent=2)}

ТЕКУЩИЕ ИНДИКАТОРЫ:
Цена: {market_data.indicators.current_price}
Объем 24ч: {market_data.indicators.volume_24h}

Обнови свой анализ и прими торговое решение. Ответь в формате JSON."""
    
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
    
    async def initialize(self) -> None:
        """Инициализация обработчика - ничего дополнительного не требуется."""
        logger.info("Упрощенный OpenAI обработчик готов к работе")
