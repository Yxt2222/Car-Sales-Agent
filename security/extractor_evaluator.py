"""
Extractor Evaluation Module

评估 extract_agent 的信息提取质量。
采用包含关系匹配字符串，适用于同源信息提取场景。
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional


@dataclass
class ScoreResult:
    """评分结果"""
    score: float  # 0-1 之间的加权分数
    matched_fields: List[str]  # 匹配的字段名
    mismatched_fields: List[str]  # 不匹配的字段名
    missing_fields: List[str]  # 缺失的字段名
    details: Dict[str, Dict[str, Any]]  # 每个字段的详细对比
    matched_weight: float = 0.0  # 匹配字段的总权重
    total_weight: float = 0.0  # 所有字段的总权重


class ExtractorEvaluator:
    """
    信息提取评估器

    评估原则：
    1. Schema 匹配（宽容模式）：允许提取结果包含额外字段，但不能缺少必需字段
    2. 字符串比较：使用包含关系 (v1 in v2 or v2 in v1) 判断语义相近
    3. 布尔/None 值：精确比较
    4. 评分公式：加权评分 = Σ(匹配字段权重) / Σ(所有字段权重)
    """

    # 字段权重配置（区分重要性）
    # has_intent: 核心字段，影响后续流程
    # brand, budget, interested, visit_time: 业务关键字段
    # concerns, has_real_difficulty, promotion_is_valid: 辅助推断字段
    FIELD_WEIGHTS = {
        'has_intent': 2.0,           # 核心：是否有购车意愿
        'brand': 1.5,                # 关键：品牌偏好
        'budget': 1.5,               # 关键：预算范围
        'interested': 1.5,           # 关键：是否感兴趣
        'visit_time': 1.5,           # 关键：预约时间
        'concerns': 1.0,             # 辅助：用户顾虑
        'has_real_difficulty': 1.0,  # 辅助：是否有合理顾虑
        'promotion_is_valid': 1.0,   # 辅助：促销是否有效
    }

    # 总权重（用于归一化）: 2.0 + 1.5*4 + 1.0*3 = 11.0
    TOTAL_WEIGHT = sum(FIELD_WEIGHTS.values())  # 11.0

    # 必需字段列表（与 extract_agent 输出 schema 一致）
    REQUIRED_FIELDS = list(FIELD_WEIGHTS.keys())

    @classmethod
    def evaluate(cls, extracted: Dict[str, Any], ground_truth: Dict[str, Any]) -> ScoreResult:
        """
        评估提取结果

        Args:
            extracted: 模型提取的结果（字典格式）
            ground_truth: 真实标注结果（字典格式）

        Returns:
            ScoreResult: 评分结果对象
        """
        matched_fields = []
        mismatched_fields = []
        missing_fields = []
        details = {}

        # 1. Schema 检查（宽容模式：允许 extra keys）
        extracted_keys = set(extracted.keys())
        required_keys = set(cls.REQUIRED_FIELDS)

        # 检查是否缺少必需字段
        missing_keys = required_keys - extracted_keys
        if missing_keys:
            missing_fields = list(missing_keys)
            # 缺少必需字段，直接返回 0 分
            return ScoreResult(
                score=0.0,
                matched_fields=[],
                mismatched_fields=[],
                missing_fields=missing_fields,
                details={}
            )

        # 2. 逐字段对比
        matched_weight = 0.0

        for field in cls.REQUIRED_FIELDS:
            extracted_val = extracted.get(field)
            ground_truth_val = ground_truth.get(field)
            field_weight = cls.FIELD_WEIGHTS[field]

            # 记录详细对比信息
            field_detail = {
                'extracted': extracted_val,
                'ground_truth': ground_truth_val,
                'match': False,
                'weight': field_weight
            }

            # 判断是否匹配
            is_match = cls._values_match(extracted_val, ground_truth_val, field)
            field_detail['match'] = is_match

            if is_match:
                matched_fields.append(field)
                matched_weight += field_weight
            else:
                mismatched_fields.append(field)

            details[field] = field_detail

        # 3. 计算加权分数
        score = matched_weight / cls.TOTAL_WEIGHT if cls.TOTAL_WEIGHT > 0 else 0.0

        return ScoreResult(
            score=score,
            matched_fields=matched_fields,
            mismatched_fields=mismatched_fields,
            missing_fields=missing_fields,
            details=details,
            matched_weight=matched_weight,
            total_weight=cls.TOTAL_WEIGHT
        )

    @classmethod
    def _values_match(cls, v1: Any, v2: Any, field: str) -> bool:
        """
        判断两个值是否匹配

        匹配规则：
        - None/布尔值：精确相等
        - 字符串：包含关系（v1 in v2 or v2 in v1）

        Args:
            v1: 第一个值
            v2: 第二个值
            field: 字段名（用于特殊处理）

        Returns:
            bool: 是否匹配
        """
        # 处理 None 值
        if v1 is None or v2 is None:
            return v1 == v2

        # 处理布尔值
        if isinstance(v1, bool) or isinstance(v2, bool):
            return v1 == v2

        # 处理空字符串（视为 null）
        if isinstance(v1, str) and v1.strip() == '':
            return v2 is None or (isinstance(v2, str) and v2.strip() == '')
        if isinstance(v2, str) and v2.strip() == '':
            return v1 is None or (isinstance(v1, str) and v1.strip() == '')

        # 字符串包含关系匹配
        if isinstance(v1, str) and isinstance(v2, str):
            return v1 in v2 or v2 in v1

        # 其他类型精确比较
        return v1 == v2

    @classmethod
    def evaluate_batch(cls, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        批量评估

        Args:
            results: 包含 (extracted, ground_truth) 的列表，格式为:
                     [
                         {'extracted': {...}, 'ground_truth': {...}},
                         ...
                     ]

        Returns:
            统计结果字典
        """
        total = len(results)
        scores = []
        field_stats = {field: {'matched': 0, 'total': 0} for field in cls.REQUIRED_FIELDS}

        for item in results:
            result = cls.evaluate(item['extracted'], item['ground_truth'])
            scores.append(result.score)

            # 统计各字段匹配情况
            for field in cls.REQUIRED_FIELDS:
                field_stats[field]['total'] += 1
                if field in result.matched_fields:
                    field_stats[field]['matched'] += 1

        # 计算统计指标
        avg_score = sum(scores) / total if total > 0 else 0.0
        min_score = min(scores) if scores else 0.0
        max_score = max(scores) if scores else 0.0

        # 计算各字段准确率
        field_accuracy = {
            field: (stats['matched'] / stats['total'] * 100) if stats['total'] > 0 else 0
            for field, stats in field_stats.items()
        }

        return {
            'total': total,
            'avg_score': avg_score,
            'min_score': min_score,
            'max_score': max_score,
            'field_accuracy': field_accuracy,
            'scores': scores
        }


# 便捷函数
def evaluate_extraction(extracted: Dict[str, Any], ground_truth: Dict[str, Any]) -> float:
    """
    便捷函数：评估单个提取结果，返回分数

    Args:
        extracted: 模型提取的结果
        ground_truth: 真实标注结果

    Returns:
        float: 0-1 之间的分数
    """
    result = ExtractorEvaluator.evaluate(extracted, ground_truth)
    return result.score
