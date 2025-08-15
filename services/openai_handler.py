"""Обработчик для работы с OpenAI API."""
import json
from typing import Dict, Any, Optional
import openai
from loguru import logger

from config.settings import Settings
from models.trading import MarketData


class OpenAIHandler:
    """
    Обработчик для взаимодействия с OpenAI API.
    
    Управляет созданием ассистента, потоков сообщений и обработкой ответов.
    """
    
    def __init__(self, settings: Settings):
        """
        Инициализация обработчика.
        
        Args:
            settings: Настройки приложения
        """
        self.settings = settings
        self.client = openai.OpenAI(
            api_key=settings.openai_api_key,
            default_headers={"OpenAI-Beta": "assistants=v2"}
        )
        self.model = settings.openai_model
        self.assistant_id: Optional[str] = None
        self.thread_id: Optional[str] = None
        
        logger.info("Инициализирован OpenAI обработчик")
    
    def get_trader_prompt(self) -> str:
        """
        Возвращает промпт профессионального трейдера.
        
        Returns:
            Текст промпта для OpenAI ассистента
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
    
    async def create_assistant(self) -> str:
        """
        Создает ассистента OpenAI с промптом трейдера.
        
        Returns:
            ID созданного ассистента
        """
        try:
            assistant = self.client.beta.assistants.create(
                name="Professional BTC-USDT Trader",
                instructions=self.get_trader_prompt(),
                model=self.model,
                tools=[{"type": "code_interpreter"}],
                extra_headers={"OpenAI-Beta": "assistants=v2"}
            )
            
            self.assistant_id = assistant.id
            logger.info(f"Создан ассистент OpenAI: {self.assistant_id}")
            return self.assistant_id
            
        except Exception as e:
            logger.error(f"Ошибка создания ассистента: {e}")
            raise
    
    async def create_thread(self) -> str:
        """
        Создает поток для истории чата.
        
        Returns:
            ID созданного потока
        """
        try:
            thread = self.client.beta.threads.create(
                extra_headers={"OpenAI-Beta": "assistants=v2"}
            )
            self.thread_id = thread.id
            logger.info(f"Создан поток OpenAI: {self.thread_id}")
            return self.thread_id
            
        except Exception as e:
            logger.error(f"Ошибка создания потока: {e}")
            raise
    
    async def send_message(self, content: str) -> None:
        """
        Отправляет сообщение в поток.
        
        Args:
            content: Содержимое сообщения
        """
        if not self.thread_id:
            raise ValueError("Поток не создан. Вызовите create_thread() сначала.")
        
        try:
            self.client.beta.threads.messages.create(
                thread_id=self.thread_id,
                role="user",
                content=content,
                extra_headers={"OpenAI-Beta": "assistants=v2"}
            )
            logger.debug("Сообщение отправлено в поток")
            
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
            raise
    
    async def run_assistant(self) -> str:
        """
        Запускает ответ ассистента.
        
        Returns:
            ID запуска
        """
        if not self.thread_id or not self.assistant_id:
            raise ValueError("Поток или ассистент не созданы.")
        
        try:
            run = self.client.beta.threads.runs.create(
                thread_id=self.thread_id,
                assistant_id=self.assistant_id,
                extra_headers={"OpenAI-Beta": "assistants=v2"}
            )
            logger.debug(f"Запущен ассистент: {run.id}")
            return run.id
            
        except Exception as e:
            logger.error(f"Ошибка запуска ассистента: {e}")
            raise
    
    async def wait_for_completion(self, run_id: str, max_wait_time: int = 120) -> bool:
        """
        Ждет завершения работы ассистента.
        
        Args:
            run_id: ID запуска
            max_wait_time: Максимальное время ожидания в секундах
            
        Returns:
            True если завершено успешно, False если превышено время ожидания
        """
        import asyncio
        
        if not self.thread_id:
            raise ValueError("Поток не создан.")
        
        wait_time = 0
        while wait_time < max_wait_time:
            try:
                run = self.client.beta.threads.runs.retrieve(
                    thread_id=self.thread_id, 
                    run_id=run_id,
                    extra_headers={"OpenAI-Beta": "assistants=v2"}
                )
                
                if run.status == "completed":
                    logger.debug("Ассистент завершил работу")
                    return True
                elif run.status == "failed":
                    logger.error(f"Ассистент завершился с ошибкой: {run.last_error}")
                    return False
                
                await asyncio.sleep(2)
                wait_time += 2
                
            except Exception as e:
                logger.error(f"Ошибка проверки статуса: {e}")
                await asyncio.sleep(2)
                wait_time += 2
        
        logger.warning(f"Превышено время ожидания ответа ассистента: {max_wait_time}s")
        return False
    
    async def get_last_message(self) -> str:
        """
        Получает последнее сообщение от ассистента.
        
        Returns:
            Текст последнего сообщения
        """
        if not self.thread_id:
            raise ValueError("Поток не создан.")
        
        try:
            messages = self.client.beta.threads.messages.list(
                thread_id=self.thread_id,
                extra_headers={"OpenAI-Beta": "assistants=v2"}
            )
            if not messages.data:
                raise ValueError("Нет сообщений в потоке")
            
            last_message = messages.data[0].content[0].text.value
            logger.debug("Получено последнее сообщение от ассистента")
            return last_message
            
        except Exception as e:
            logger.error(f"Ошибка получения сообщения: {e}")
            raise
    
    async def send_initial_data(self, market_data: MarketData) -> str:
        """
        Отправляет начальные рыночные данные ассистенту.
        
        Args:
            market_data: Аналитические данные рынка
            
        Returns:
            Ответ ассистента в формате JSON
        """
        message = f"""НАЧАЛЬНЫЕ ДАННЫЕ ДЛЯ АНАЛИЗА:

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

        await self.send_message(message)
        run_id = await self.run_assistant()
        
        if await self.wait_for_completion(run_id):
            return await self.get_last_message()
        else:
            raise TimeoutError("Превышено время ожидания ответа ассистента")
    
    async def send_update_data(self, market_data: MarketData) -> str:
        """
        Отправляет обновленные рыночные данные ассистенту.
        
        Args:
            market_data: Данные мониторинга рынка
            
        Returns:
            Ответ ассистента в формате JSON
        """
        message = f"""ОБНОВЛЕНИЕ РЫНОЧНЫХ ДАННЫХ:

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

        await self.send_message(message)
        run_id = await self.run_assistant()
        
        if await self.wait_for_completion(run_id):
            return await self.get_last_message()
        else:
            raise TimeoutError("Превышено время ожидания ответа ассистента")
    
    async def initialize(self) -> None:
        """Инициализирует ассистента и поток."""
        await self.create_assistant()
        await self.create_thread()
        logger.info("OpenAI обработчик полностью инициализирован")
