"""Base classes for the indicator library."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class IndicatorResult:
    """Uniform container for indicator output."""
    name: str
    values: List[float] = field(default_factory=list)
    extra: Dict[str, List[float]] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def last(self) -> float:
        return self.values[-1] if self.values else float("nan")

    def last_extra(self, key: str) -> float:
        arr = self.extra.get(key, [])
        return arr[-1] if arr else float("nan")


class Indicator(ABC):
    """Base class for stateful indicators."""

    name: str = "indicator"

    @abstractmethod
    def compute(self, *args: Any, **kwargs: Any) -> IndicatorResult:
        ...

    def __call__(self, *args: Any, **kwargs: Any) -> IndicatorResult:
        return self.compute(*args, **kwargs)
