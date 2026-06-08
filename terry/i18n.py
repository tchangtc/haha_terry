"""
国际化支持模块 (Internationalization Support Module)

提供多语言支持，目前支持：
- 英语 (en)
- 中文 (zh)
"""

from __future__ import annotations

import json
import os
from pathlib import Path


class I18n:
    """国际化管理器"""

    SUPPORTED_LANGUAGES = ['en', 'zh']
    DEFAULT_LANGUAGE = 'en'

    def __init__(self, language: str | None = None):
        """
        初始化国际化管理器

        Args:
            language: 语言代码 (en, zh)，如果不提供则从环境变量或默认值获取
        """
        self.language = language or os.getenv('TERRY_LANGUAGE', self.DEFAULT_LANGUAGE)
        if self.language not in self.SUPPORTED_LANGUAGES:
            self.language = self.DEFAULT_LANGUAGE

        self._translations: dict[str, dict] = {}
        self._load_translations()

    def _load_translations(self):
        """加载所有语言的翻译文件"""
        locale_dir = Path(__file__).parent / 'locale'

        for lang in self.SUPPORTED_LANGUAGES:
            lang_file = locale_dir / f'{lang}.json'
            if lang_file.exists():
                with open(lang_file, encoding='utf-8') as f:
                    self._translations[lang] = json.load(f)

    def t(self, key: str, **kwargs) -> str:
        """
        获取翻译文本

        Args:
            key: 翻译键，使用点号分隔，例如 'cli.welcome'
            **kwargs: 用于替换的变量，例如 name='User'

        Returns:
            翻译后的文本
        """
        # 按点号分割键
        keys = key.split('.')

        # 获取当前语言的翻译
        translation = self._translations.get(self.language, {})

        # 遍历键路径
        for k in keys:
            if isinstance(translation, dict):
                translation = translation.get(k, {})
            else:
                translation = {}
                break

        # 如果找不到翻译，使用默认语言
        if not translation or not isinstance(translation, str):
            translation = self._translations.get(self.DEFAULT_LANGUAGE, {})
            for k in keys:
                if isinstance(translation, dict):
                    translation = translation.get(k, {})
                else:
                    translation = key
                    break

            if not isinstance(translation, str):
                translation = key

        # 替换变量
        if kwargs:
            try:
                translation = translation.format(**kwargs)
            except (KeyError, ValueError):
                pass

        return translation

    def set_language(self, language: str) -> bool:
        """
        切换语言

        Args:
            language: 语言代码

        Returns:
            是否成功切换
        """
        if language in self.SUPPORTED_LANGUAGES:
            self.language = language
            return True
        return False

    def get_language(self) -> str:
        """获取当前语言"""
        return self.language

    def get_supported_languages(self) -> list:
        """获取支持的语言列表"""
        return self.SUPPORTED_LANGUAGES.copy()


# 全局 i18n 实例
_i18n_instance: I18n | None = None


def get_i18n() -> I18n:
    """获取全局 i18n 实例"""
    global _i18n_instance
    if _i18n_instance is None:
        _i18n_instance = I18n()
    return _i18n_instance


def set_i18n(instance: I18n) -> None:
    """Inject a custom I18n instance (for testing/DI)."""
    global _i18n_instance
    _i18n_instance = instance


def reset_i18n() -> None:
    """Reset i18n singleton (forces re-initialization on next get)."""
    global _i18n_instance
    _i18n_instance = None


def t(key: str, **kwargs) -> str:
    """
    获取翻译文本的快捷函数

    Args:
        key: 翻译键
        **kwargs: 用于替换的变量

    Returns:
        翻译后的文本
    """
    return get_i18n().t(key, **kwargs)
