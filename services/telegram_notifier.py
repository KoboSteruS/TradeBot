"""Модуль для отправки Telegram уведомлений."""
import asyncio
from typing import Optional, Dict, Any
import httpx
from loguru import logger

from config.settings import Settings


class TelegramNotifier:
    """
    Отправляет уведомления в Telegram.
    
    Уведомляет о покупках и отменах ордеров.
    """
    
    def __init__(self, settings: Settings):
        """
        Инициализация уведомлений.
        
        Args:
            settings: Настройки приложения
        """
        self.settings = settings
        self.bot_token = "8498262007:AAHvGNPaZUwa-IAUorTLIpJPnZCIw8NAIyg"
        self.chat_id = "-4872990353"
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        # Настройки HTTP клиента
        timeout_config = httpx.Timeout(
            connect=5.0,
            read=10.0,
            write=5.0,
            pool=5.0
        )
        
        self.client = httpx.AsyncClient(
            timeout=timeout_config,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "TradeBot/1.0.0"
            }
        )
        
        logger.info("Инициализирован Telegram уведомления")
    
    async def __aenter__(self):
        """Асинхронный контекстный менеджер - вход."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный контекстный менеджер - выход."""
        await self.close()
    
    async def close(self) -> None:
        """Закрывает HTTP клиент."""
        await self.client.aclose()
        logger.info("Telegram клиент закрыт")
    
    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        Отправляет сообщение в Telegram.
        
        Args:
            text: Текст сообщения
            parse_mode: Режим парсинга (HTML, Markdown)
            
        Returns:
            True если сообщение отправлено успешно
        """
        try:
            url = f"{self.base_url}/sendMessage"
            
            data = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }
            
            response = await self.client.post(url, json=data)
            response.raise_for_status()
            
            result = response.json()
            if result.get("ok"):
                logger.info("✅ Telegram уведомление отправлено")
                return True
            else:
                logger.error(f"❌ Ошибка отправки Telegram: {result}")
                return False
                
        except httpx.HTTPError as e:
            logger.error(f"🌐 Ошибка HTTP при отправке Telegram: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при отправке Telegram: {e}")
            return False
    
    async def notify_buy_order(
        self, 
        amount: float, 
        take_profit_percent: float, 
        stop_loss_percent: float,
        current_price: str,
        response: str
    ) -> None:
        """
        Уведомляет о покупке BTC.
        
        Args:
            amount: Сумма покупки в USDT
            take_profit_percent: Процент тейк-профита
            stop_loss_percent: Процент стоп-лосса
            current_price: Текущая цена BTC
            response: Объяснение решения от ИИ
        """
        text = f"""
🟢 <b>ПОКУПКА BTC</b>

💰 <b>Сумма:</b> {amount:.2f} USDT
📈 <b>Текущая цена:</b> {current_price} USDT
🎯 <b>Take Profit:</b> {take_profit_percent}%
🛑 <b>Stop Loss:</b> {stop_loss_percent}%

🤖 <b>Решение ИИ:</b>
{response}

⏰ <b>Время:</b> {self._get_current_time()}
        """.strip()
        
        await self.send_message(text)
    
    async def notify_cancel_order(
        self, 
        order_id: str, 
        response: str,
        order_details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Уведомляет об отмене ордера.
        
        Args:
            order_id: ID отмененного ордера
            response: Объяснение решения от ИИ
            order_details: Детали ордера (опционально)
        """
        text = f"""
🔴 <b>ОТМЕНА ОРДЕРА</b>

🆔 <b>ID ордера:</b> {order_id}
        """.strip()
        
        if order_details:
            text += f"""
📊 <b>Детали ордера:</b>
• Инструмент: {order_details.get('instId', 'N/A')}
• Сторона: {order_details.get('side', 'N/A')}
• Цена: {order_details.get('px', 'N/A')} USDT
• Размер: {order_details.get('sz', 'N/A')} BTC
• Возраст: {order_details.get('age_minutes', 'N/A')} мин
            """.strip()
        
        text += f"""

🤖 <b>Решение ИИ:</b>
{response}

⏰ <b>Время:</b> {self._get_current_time()}
        """.strip()
        
        await self.send_message(text)
    
    async def notify_sell_after_cancel(
        self, 
        btc_amount: float, 
        response: str
    ) -> None:
        """
        Уведомляет о продаже BTC после отмены ордера.
        
        Args:
            btc_amount: Количество проданного BTC
            response: Объяснение решения от ИИ
        """
        text = f"""
🟡 <b>ПРОДАЖА ПОСЛЕ ОТМЕНЫ</b>

💰 <b>Продано BTC:</b> {btc_amount:.8f} BTC

🤖 <b>Решение ИИ:</b>
{response}

⏰ <b>Время:</b> {self._get_current_time()}
        """.strip()
        
        await self.send_message(text)
    
    async def notify_sell_order(
        self, 
        btc_amount: float, 
        response: str
    ) -> None:
        """
        Уведомляет о продаже BTC.
        
        Args:
            btc_amount: Количество проданного BTC
            response: Объяснение решения от ИИ
        """
        text = f"""
🟡 <b>ПРОДАЖА BTC</b>

💰 <b>Продано BTC:</b> {btc_amount:.8f} BTC

🤖 <b>Решение ИИ:</b>
{response}

⏰ <b>Время:</b> {self._get_current_time()}
        """.strip()
        
        await self.send_message(text)
    
    def _get_current_time(self) -> str:
        """Возвращает текущее время в читаемом формате."""
        import datetime
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    async def test_connection(self) -> bool:
        """
        Тестирует соединение с Telegram API.
        
        Returns:
            True если соединение успешно
        """
        try:
            url = f"{self.base_url}/getMe"
            response = await self.client.get(url)
            response.raise_for_status()
            
            result = response.json()
            if result.get("ok"):
                bot_info = result.get("result", {})
                logger.info(f"✅ Telegram бот подключен: @{bot_info.get('username', 'N/A')}")
                return True
            else:
                logger.error(f"❌ Ошибка подключения к Telegram: {result}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка тестирования Telegram: {e}")
            return False
