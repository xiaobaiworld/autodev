# 定位: base.py 定义多渠道呈现适配器的统一抽象基类。
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from requirements.presentation.model import RequirementResponse


class BasePresenter(ABC):
    """所有渠道美化呈现器的抽象基类。"""

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """渠道标识，如 'feishu_card', 'plain_text', 'web_json' 等。"""
        pass

    @abstractmethod
    def render(self, response: RequirementResponse) -> Any:
        """把语义响应对象渲染为该渠道的最佳视觉格式。"""
        pass
