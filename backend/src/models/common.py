from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date

class Filter(BaseModel):
    field: str
    op: str = Field(default="=", description="比较操作符: =, !=, >, <, >=, <=")
    value: int | str | float

class TimeRange(BaseModel):
    start_date: date
    end_date: date
    unit: str = Field(default="day", description="聚合粒度: day, week, month")
