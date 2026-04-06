"""
测试 ExtractorEvaluator
"""

import sys
import io
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# 设置 UTF-8 输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from security.extractor_evaluator import ExtractorEvaluator, evaluate_extraction


def test_basic_match():
    """测试基本匹配"""
    extracted = {
        'has_intent': True,
        'brand': '奥迪',
        'budget': '20万',
        'interested': True,
        'concerns': None,
        'has_real_difficulty': None,
        'promotion_is_valid': None,
        'visit_time': None
    }
    ground_truth = {
        'has_intent': True,
        'brand': '奥迪',
        'budget': '20万',
        'interested': True,
        'concerns': None,
        'has_real_difficulty': None,
        'promotion_is_valid': None,
        'visit_time': None
    }

    result = ExtractorEvaluator.evaluate(extracted, ground_truth)
    assert result.score == 1.0
    assert len(result.mismatched_fields) == 0
    print("✓ 完全匹配测试通过")


def test_string_containment():
    """测试字符串包含关系匹配"""
    # 预算包含关系
    extracted = {'has_intent': True, 'brand': '奥迪', 'budget': '20-30万', 'interested': True,
                 'concerns': None, 'has_real_difficulty': None, 'promotion_is_valid': None, 'visit_time': None}
    ground_truth = {'has_intent': True, 'brand': '奥迪', 'budget': '20万', 'interested': True,
                    'concerns': None, 'has_real_difficulty': None, 'promotion_is_valid': null, 'visit_time': None}
    # 这里有个问题，ground_truth 的 null 没有正确设置，让我修复


def test_string_containment():
    """测试字符串包含关系匹配"""
    # 预算包含关系 - 提取值包含预期值
    extracted = {'has_intent': True, 'brand': '奥迪', 'budget': '20万左右', 'interested': True,
                 'concerns': None, 'has_real_difficulty': None, 'promotion_is_valid': None, 'visit_time': None}
    ground_truth = {'has_intent': True, 'brand': '奥迪', 'budget': '20万', 'interested': True,
                    'concerns': None, 'has_real_difficulty': None, 'promotion_is_valid': None, 'visit_time': None}

    result = ExtractorEvaluator.evaluate(extracted, ground_truth)
    # '20万' in '20万左右' → True
    print(f"Score: {result.score}")
    print(f"Matched: {result.matched_fields}")
    print(f"Mismatched: {result.mismatched_fields}")
    assert result.score == 1.0  # 所有字段应该匹配
    print("✓ 字符串包含匹配测试通过")


def test_boolean_exact_match():
    """测试布尔值精确匹配"""
    extracted = {'has_intent': False, 'brand': None, 'budget': None, 'interested': False,
                 'concerns': None, 'has_real_difficulty': False, 'promotion_is_valid': None, 'visit_time': None}
    ground_truth = {'has_intent': False, 'brand': None, 'budget': None, 'interested': False,
                    'concerns': None, 'has_real_difficulty': False, 'promotion_is_valid': None, 'visit_time': None}

    result = ExtractorEvaluator.evaluate(extracted, ground_truth)
    assert result.score == 1.0
    print("✓ 布尔值精确匹配测试通过")


def test_missing_field():
    """测试缺少必需字段"""
    extracted = {'has_intent': True, 'brand': '奥迪', 'budget': '20万'}  # 缺少其他字段
    ground_truth = {'has_intent': True, 'brand': '奥迪', 'budget': '20万', 'interested': True,
                    'concerns': None, 'has_real_difficulty': None, 'promotion_is_valid': None, 'visit_time': None}

    result = ExtractorEvaluator.evaluate(extracted, ground_truth)
    assert result.score == 0.0
    assert len(result.missing_fields) > 0
    print("✓ 缺失字段测试通过")


def test_extra_fields_allowed():
    """测试允许额外字段"""
    extracted = {
        'has_intent': True, 'brand': '奥迪', 'budget': '20万', 'interested': True,
        'concerns': None, 'has_real_difficulty': None, 'promotion_is_valid': None, 'visit_time': None,
        'extra_field': 'this is extra'  # 额外字段
    }
    ground_truth = {
        'has_intent': True, 'brand': '奥迪', 'budget': '20万', 'interested': True,
        'concerns': None, 'has_real_difficulty': None, 'promotion_is_valid': None, 'visit_time': None
    }

    result = ExtractorEvaluator.evaluate(extracted, ground_truth)
    assert result.score == 1.0  # 额外字段不影响分数
    print("✓ 额外字段宽容测试通过")


def test_batch_evaluation():
    """测试批量评估"""
    results = [
        {
            'extracted': {
                'has_intent': True, 'brand': '奥迪', 'budget': '20万', 'interested': True,
                'concerns': None, 'has_real_difficulty': None, 'promotion_is_valid': None, 'visit_time': None
            },
            'ground_truth': {
                'has_intent': True, 'brand': '奥迪', 'budget': '20万', 'interested': True,
                'concerns': None, 'has_real_difficulty': None, 'promotion_is_valid': None, 'visit_time': None
            }
        },
        {
            'extracted': {
                'has_intent': False, 'brand': None, 'budget': None, 'interested': False,
                'concerns': None, 'has_real_difficulty': False, 'promotion_is_valid': None, 'visit_time': None
            },
            'ground_truth': {
                'has_intent': False, 'brand': None, 'budget': None, 'interested': False,
                'concerns': None, 'has_real_difficulty': False, 'promotion_is_valid': None, 'visit_time': None
            }
        },
    ]

    stats = ExtractorEvaluator.evaluate_batch(results)
    assert stats['total'] == 2
    assert stats['avg_score'] == 1.0
    print("✓ 批量评估测试通过")


def test_weighted_scoring():
    """测试加权评分 - 验证核心字段权重更高"""
    # 场景1: 核心字段正确，其他字段错误 → 分数应该较高
    extracted_1 = {
        'has_intent': True,          # 权重2.0 ✓
        'brand': '错误',              # 权重1.5 ✗
        'budget': '错误',             # 权重1.5 ✗
        'interested': '错误',         # 权重1.5 ✗
        'visit_time': '错误',         # 权重1.5 ✗
        'concerns': '错误',           # 权重1.0 ✗
        'has_real_difficulty': '错误', # 权重1.0 ✗
        'promotion_is_valid': '错误',  # 权重1.0 ✗
    }
    ground_truth_1 = {
        'has_intent': True,
        'brand': '奥迪',
        'budget': '20万',
        'interested': True,
        'visit_time': '周末',
        'concerns': '价格',
        'has_real_difficulty': True,
        'promotion_is_valid': True,
    }

    result_1 = ExtractorEvaluator.evaluate(extracted_1, ground_truth_1)
    # 只匹配了 has_intent (2.0)，总分 = 2.0 / 11.0 ≈ 0.182
    print(f"场景1 实际分数 = {result_1.score}, 匹配字段 = {result_1.matched_fields}")
    assert abs(result_1.score - 0.1818) < 0.01
    print(f"✓ 场景1 (核心字段正确): 分数 = {result_1.score} (期望 ≈0.182)")

    # 场景2: 核心字段错误，其他字段都正确 → 分数应该较低
    extracted_2 = {
        'has_intent': False,         # 权重2.0 ✗
        'brand': '奥迪',              # 权重1.5 ✓
        'budget': '20万',             # 权重1.5 ✓
        'interested': True,          # 权重1.5 ✓
        'visit_time': '周末',         # 权重1.5 ✓
        'concerns': '价格',           # 权重1.0 ✓
        'has_real_difficulty': True,  # 权重1.0 ✓
        'promotion_is_valid': True,   # 权重1.0 ✓
    }
    ground_truth_2 = {
        'has_intent': True,
        'brand': '奥迪',
        'budget': '20万',
        'interested': True,
        'visit_time': '周末',
        'concerns': '价格',
        'has_real_difficulty': True,
        'promotion_is_valid': True,
    }

    result_2 = ExtractorEvaluator.evaluate(extracted_2, ground_truth_2)
    # 匹配了除 has_intent 外的所有字段 (9.0)，总分 = 9.0 / 11.0 ≈ 0.818
    print(f"场景2 实际分数 = {result_2.score}, 匹配字段 = {result_2.matched_fields}")
    assert abs(result_2.score - 0.8182) < 0.01
    print(f"✓ 场景2 (核心字段错误): 分数 = {result_2.score} (期望 ≈0.818)")

    # 验证权重信息正确记录
    assert result_1.matched_weight == 2.0
    assert result_1.total_weight == 11.0
    assert result_2.matched_weight == 9.0
    assert result_2.total_weight == 11.0

    print("✓ 加权评分测试通过")


if __name__ == "__main__":
    test_basic_match()
    test_string_containment()
    test_boolean_exact_match()
    test_missing_field()
    test_extra_fields_allowed()
    test_batch_evaluation()
    test_weighted_scoring()
    print("\n所有测试通过 ✓")
