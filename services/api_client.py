"""Клиент для работы с торговым API."""
import asyncio
from typing import Dict, Any, Optional
import httpx
from loguru import logger

from config.settings import Settings
from models.trading import MarketData


class TradingAPIClient:
    """
    Клиент для взаимодействия с торговым API.
    
    Предоставляет методы для получения рыночных данных и мониторинга.
    """
    
    def __init__(self, settings: Settings):
        """
        Инициализация клиента.
        
        Args:
            settings: Настройки приложения
        """
        self.settings = settings
        self.base_url = settings.trading_api_base_url
        self.demo_mode = settings.demo_mode
        self.timeout = 30.0
        
        # Настройки HTTP клиента
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "TradeBot/1.0.0"
            }
        )
        
        logger.info(f"Инициализирован API клиент для {self.base_url}")
    
    async def __aenter__(self):
        """Асинхронный контекстный менеджер - вход."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный контекстный менеджер - выход."""
        await self.close()
    
    async def close(self) -> None:
        """Закрывает HTTP клиент."""
        await self.client.aclose()
        logger.info("API клиент закрыт")
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Выполняет HTTP запрос к API.
        
        Args:
            method: HTTP метод (GET, POST, etc.)
            endpoint: Конечная точка API
            params: URL параметры
            json_data: JSON данные для отправки
            
        Returns:
            Ответ от API в виде словаря
            
        Raises:
            httpx.HTTPError: При ошибке HTTP запроса
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            logger.debug(f"Выполняется {method} запрос к {url}")
            
            response = await self.client.request(
                method=method,
                url=url,
                params=params,
                json=json_data
            )
            
            response.raise_for_status()
            data = response.json()
            
            logger.debug(f"Получен ответ от {url}: {response.status_code}")
            return data
            
        except httpx.HTTPError as e:
            logger.error(f"Ошибка HTTP запроса к {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при запросе к {url}: {e}")
            raise
    
    async def get_health(self) -> Dict[str, Any]:
        """
        Проверяет состояние API.
        
        Returns:
            Данные о состоянии API
        """
        return await self._make_request("GET", "/api/v1/health")
    
    async def get_market_analytics(self) -> MarketData:
        """
        Получает аналитические данные рынка (исторические данные за 3 месяца).
        
        Returns:
            Полные рыночные данные включая исторические свечи
        """
        params = {"demo": str(self.demo_mode).lower()}
        data = await self._make_request("GET", "/api/v1/market/analytics", params=params)
        
        logger.info(f"Получены аналитические данные для {data.get('inst_id', 'N/A')}")
        return MarketData(**data)
    
    async def get_market_monitor(self) -> MarketData:
        """
        Получает текущие данные мониторинга рынка (последние 10 минутных свечей).
        
        Returns:
            Текущие рыночные данные
        """
        params = {"demo": str(self.demo_mode).lower()}
        data = await self._make_request("GET", "/api/v1/market/monitor", params=params)
        
        logger.debug(f"Получены данные мониторинга для {data.get('inst_id', 'N/A')}")
        return MarketData(**data)
    
    async def place_buy_order(
        self, 
        amount: float, 
        take_profit_percent: float, 
        stop_loss_percent: float
    ) -> Dict[str, Any]:
        """
        Размещает ордер на покупку.
        
        Args:
            amount: Сумма для покупки в USDT
            take_profit_percent: Take Profit в процентах
            stop_loss_percent: Stop Loss в процентах
            
        Returns:
            Результат размещения ордера
        """
        json_data = {
            "buy_amount": amount,
            "take_profit_percent": take_profit_percent,
            "stop_loss_percent": stop_loss_percent,
            "demo": self.demo_mode
        }
        
        logger.info(f"Размещение ордера на покупку: {amount} USDT, TP: {take_profit_percent}%, SL: {stop_loss_percent}%")
        return await self._make_request("POST", "/api/v1/orders/buy", json_data=json_data)
    
    async def place_sell_order(self, amount: float) -> Dict[str, Any]:
        """
        Размещает ордер на продажу.
        
        Args:
            amount: Количество BTC для продажи
            
        Returns:
            Результат размещения ордера
        """
        json_data = {
            "sell_amount": amount,
            "demo": self.demo_mode
        }
        
        logger.info(f"Размещение ордера на продажу: {amount} BTC")
        return await self._make_request("POST", "/api/v1/orders/sell", json_data=json_data)
    
    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Отменяет ордер.
        
        Args:
            order_id: ID ордера для отмены
            
        Returns:
            Результат отмены ордера
        """
        json_data = {
            "order_id": order_id,
            "demo": self.demo_mode
        }
        
        logger.info(f"Отмена ордера: {order_id}")
        return await self._make_request("POST", "/api/v1/orders/cancel", json_data=json_data)
    
    async def test_connection(self) -> bool:
        """
        Тестирует соединение с API.
        
        Returns:
            True если соединение успешно, False в противном случае
        """
        try:
            await self.get_health()
            logger.info("Соединение с API успешно установлено")
            return True
        except Exception as e:
            logger.error(f"Ошибка соединения с API: {e}")
            return False
