"""
Security module for car sales project.

包含三个核心功能：
1. ExtractorEvaluator - 评估 extract_agent 信息提取质量
2. PromptInjectionDetector - 基于 LLM 检测和清理 Prompt Injection 攻击
3. DeterministicFilter - 基于关键词规则的确定性过滤器
"""

from .extractor_evaluator import ExtractorEvaluator, ScoreResult
from .llm_detection import (
    PromptInjectionDetector,
    InjectionDetectionResult,
    detect_and_clean_sync,
    detect_and_clean_async,
    with_injection_detection
)
from .deterministic_filter import (
    DeterministicFilter,
    FilterResult,
    filter_user_input,
    with_deterministic_filter
)

__all__ = [
    'ExtractorEvaluator',
    'ScoreResult',
    'PromptInjectionDetector',
    'InjectionDetectionResult',
    'detect_and_clean_sync',
    'detect_and_clean_async',
    'with_injection_detection'
]
