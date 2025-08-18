"""Парсер ответов от OpenAI."""
import json
import re
from typing import Union, Dict, Any
from loguru import logger

from models.responses import (
    OpenAIResponse, 
    BuyDecision, 
    SellDecision, 
    CancelDecision, 
    PauseDecision
)
from models.trading import TradingStatus


class ResponseParseError(Exception):
    """Ошибка парсинга ответа."""
    pass


class ResponseParser:
    """
    Парсер для обработки ответов от OpenAI.
    
    Преобразует JSON ответы в соответствующие типизированные модели.
    """
    
    @staticmethod
    def clean_json_response(response_text: str) -> str:
        """
        Очищает ответ от лишних символов и извлекает JSON.
        
        Args:
            response_text: Сырой ответ от OpenAI
            
        Returns:
            Очищенный JSON текст
        """
        # Удаляем markdown блоки кода
        response_text = re.sub(r'```json\s*', '', response_text)
        response_text = re.sub(r'```\s*', '', response_text)
        
        # Удаляем лишние пробелы и переносы строк
        response_text = response_text.strip()
        
        # Пытаемся найти JSON объект в тексте
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(0)
        
        return response_text
    
    @staticmethod
    def parse_response(response_text: str) -> Union[BuyDecision, SellDecision, CancelDecision, PauseDecision]:
        """
        Парсит ответ от OpenAI в соответствующую модель решения.
        
        Args:
            response_text: JSON ответ от OpenAI
            
        Returns:
            Типизированное решение соответствующего типа
            
        Raises:
            ResponseParseError: При ошибке парсинга
        """
        try:
            # Очищаем ответ
            cleaned_text = ResponseParser.clean_json_response(response_text)
            logger.info(f"📝 СЫРОЙ ОТВЕТ: {response_text}")
            logger.info(f"🧹 ОЧИЩЕННЫЙ JSON: {cleaned_text}")
            
            # Парсим JSON
            try:
                data = json.loads(cleaned_text)
                logger.info(f"✅ РАСПАРСЕННЫЙ JSON: {json.dumps(data, ensure_ascii=False, indent=2)}")
            except json.JSONDecodeError as e:
                logger.error(f"❌ ОШИБКА ПАРСИНГА JSON: {e}")
                raise ResponseParseError(f"Некорректный JSON: {e}")
            
            # Проверяем наличие обязательных полей
            if not isinstance(data, dict):
                raise ResponseParseError("Ответ должен быть JSON объектом")
            
            if 'status' not in data:
                raise ResponseParseError("Отсутствует поле 'status' в ответе")
            
            if 'response' not in data:
                raise ResponseParseError("Отсутствует поле 'response' в ответе")
            
            status = data['status'].lower()
            
            # Проверяем и исправляем неправильные статусы
            valid_statuses = [TradingStatus.PAUSE, TradingStatus.BUY, TradingStatus.SELL, TradingStatus.CANCEL]
            if status not in valid_statuses:
                logger.warning(f"🚨 НЕПРАВИЛЬНЫЙ СТАТУС '{status}' -> ИСПРАВЛЯЮ НА 'pause'")
                original_status = data['status']
                status = TradingStatus.PAUSE
                # Исправляем данные
                data['status'] = status
                data['response'] = f"Исправлен неправильный статус '{original_status}' на pause. " + str(data.get('response', ''))
            
            # Создаем соответствующую модель на основе статуса
            if status == TradingStatus.PAUSE:
                decision = PauseDecision(**data)
                logger.info(f"⏸️  РЕШЕНИЕ ПАУЗА: {decision.response}")
                return decision
            
            elif status == TradingStatus.BUY:
                # Проверяем наличие дополнительных полей для покупки
                required_fields = ['buy_amount', 'take_profit_percent', 'stop_loss_percent']
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    raise ResponseParseError(f"Отсутствуют поля для решения о покупке: {missing_fields}")
                
                decision = BuyDecision(**data)
                logger.info(f"📈 РЕШЕНИЕ ПОКУПКА: {decision.buy_amount} USDT, TP: {decision.take_profit_percent}%, SL: {decision.stop_loss_percent}% | {decision.response}")
                return decision
            
            elif status == TradingStatus.SELL:
                # Проверяем наличие дополнительных полей для продажи
                if 'sell_amount' not in data:
                    raise ResponseParseError("Отсутствует поле 'sell_amount' для решения о продаже")
                
                decision = SellDecision(**data)
                logger.info(f"📉 РЕШЕНИЕ ПРОДАЖА: {decision.sell_amount} BTC | {decision.response}")
                return decision
            
            elif status == TradingStatus.CANCEL:
                # Проверяем наличие дополнительных полей для отмены
                if 'order_id' not in data:
                    raise ResponseParseError("Отсутствует поле 'order_id' для решения об отмене")
                
                decision = CancelDecision(**data)
                logger.info(f"❌ РЕШЕНИЕ ОТМЕНА: ордер {decision.order_id} | {decision.response}")
                return decision
            
            else:
                raise ResponseParseError(f"Неизвестный статус: {status}")
                
        except ResponseParseError:
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при парсинге ответа: {e}")
            logger.error(f"Исходный текст: {response_text}")
            raise ResponseParseError(f"Неожиданная ошибка: {e}")
    
    @staticmethod
    def validate_decision(decision: Union[BuyDecision, SellDecision, CancelDecision, PauseDecision]) -> bool:
        """
        Дополнительная валидация торгового решения.
        
        Args:
            decision: Решение для валидации
            
        Returns:
            True если решение валидно, False в противном случае
        """
        try:
            if isinstance(decision, BuyDecision):
                # Проверяем разумность значений для покупки
                if decision.buy_amount <= 0:
                    logger.error("Сумма покупки должна быть положительной")
                    return False
                
                if decision.take_profit_percent <= 0 or decision.take_profit_percent > 100:
                    logger.error("Take Profit должен быть между 0 и 100%")
                    return False
                
                if decision.stop_loss_percent <= 0 or decision.stop_loss_percent > 100:
                    logger.error("Stop Loss должен быть между 0 и 100%")
                    return False
                
                # Take Profit должен быть больше Stop Loss
                if decision.take_profit_percent <= decision.stop_loss_percent:
                    logger.error("Take Profit должен быть больше Stop Loss")
                    return False
            
            elif isinstance(decision, SellDecision):
                # Проверяем разумность значений для продажи
                if decision.sell_amount <= 0:
                    logger.error("Количество для продажи должно быть положительным")
                    return False
            
            elif isinstance(decision, CancelDecision):
                # Проверяем ID ордера
                if not decision.order_id or not decision.order_id.strip():
                    logger.error("ID ордера не может быть пустым")
                    return False
            
            # PauseDecision всегда валидна, если статус правильный
            
            logger.debug(f"Решение {type(decision).__name__} прошло валидацию")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка валидации решения: {e}")
            return False
    
    @staticmethod
    def parse_and_validate(response_text: str) -> Union[BuyDecision, SellDecision, CancelDecision, PauseDecision]:
        """
        Парсит и валидирует ответ от OpenAI.
        
        Args:
            response_text: JSON ответ от OpenAI
            
        Returns:
            Валидированное торговое решение
            
        Raises:
            ResponseParseError: При ошибке парсинга или валидации
        """
        # Парсим ответ
        decision = ResponseParser.parse_response(response_text)
        
        # Валидируем решение
        if not ResponseParser.validate_decision(decision):
            raise ResponseParseError("Решение не прошло валидацию")
        
        logger.info(f"Успешно распарсено и валидировано решение: {decision.status}")
        return decision
    
    @staticmethod
    def decision_to_api_payload(
        decision: Union[BuyDecision, SellDecision, CancelDecision, PauseDecision]
    ) -> Dict[str, Any]:
        """
        Преобразует решение в полезную нагрузку для API.
        
        Args:
            decision: Торговое решение
            
        Returns:
            Словарь с данными для API
        """
        if isinstance(decision, BuyDecision):
            return {
                "action": "buy",
                "buy_amount": decision.buy_amount,
                "take_profit_percent": decision.take_profit_percent,
                "stop_loss_percent": decision.stop_loss_percent
            }
        
        elif isinstance(decision, SellDecision):
            return {
                "action": "sell",
                "sell_amount": decision.sell_amount
            }
        
        elif isinstance(decision, CancelDecision):
            return {
                "action": "cancel",
                "order_id": decision.order_id
            }
        
        elif isinstance(decision, PauseDecision):
            return {
                "action": "pause"
            }
        
        else:
            raise ValueError(f"Неизвестный тип решения: {type(decision)}")
