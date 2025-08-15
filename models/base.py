"""Базовая модель для всех сущностей проекта."""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel as PydanticBaseModel, Field


class BaseModel(PydanticBaseModel):
    """
    Базовая модель с общими полями для всех сущностей.
    
    Содержит uuid, created_at и updated_at поля.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Уникальный идентификатор")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Время создания")
    updated_at: Optional[datetime] = Field(default=None, description="Время последнего обновления")
    
    class Config:
        """Конфигурация модели."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        use_enum_values = True
        validate_assignment = True
    
    def update_timestamp(self) -> None:
        """Обновляет timestamp последнего изменения."""
        self.updated_at = datetime.utcnow()
