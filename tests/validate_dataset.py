"""
测试数据集验证脚本

逐条调用 extract_agent 验证测试数据集的正确性
"""

import asyncio
import json
from pathlib import Path
from typing import List, Dict, Any
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents import Agent, OpenAIChatCompletionsModel, Runner
from openai import AsyncOpenAI
from config import LLMConfig
from rag.schema import ExtractedInfo


# 初始化 LLM（与 car_sales.py 相同）
llm_config = LLMConfig.get_config()
external_client = AsyncOpenAI(
    api_key=llm_config["api_key"],
    base_url=llm_config["base_url"]
)

model = OpenAIChatCompletionsModel(
    model=llm_config["chat_model"],
    openai_client=external_client
)

# 创建 Info Extractor Agent（与 car_sales.py 相同的 instruction）
extract_agent = Agent(
    name="Info Extractor",
    instructions="""
    你是一个信息抽取器，不是聊天机器人。

    将用户回复映射为以下字段：
    - has_intent: bool
        #是否有购车意愿
        - "最近想换车 / 看看车" -> True
        - "暂时不考虑 / 没需求" -> False
    - brand: str
        #用户感兴趣的汽车品牌。
    - budget: str
        #用户的购车预算，必须为明确的金额或范围，模糊表达如不确定，不太高等等不予提取，单位为万，如 "20-30万"、"50万左右"、"30w" 等。
    - interested: bool
        - "这款可以 / 挺喜欢" -> True
        - "不太合适 / 再看看" -> False
    - concerns: str
        #用户在考虑购车时有何顾虑？价格/安全性/外观/舒适性/驾驶乐趣/发动机性能
    - visit_time: str
        # 用户预约的到店时间，必须为明确的时间含义，如 "周末"、"下周三下午"、"这周六" 等，模糊表达如 "有空再说" 不予提取。

    如果用户语义模糊，请返回 null。
    只返回 JSON。
    """,
    model=model,
    output_type=ExtractedInfo,
)


def match_field(extracted: ExtractedInfo, expected: Dict[str, Any], field: str) -> bool:
    """
    检查提取的字段是否匹配预期

    注意: 空字符串 "" 和 None 都被视为"null"，用于表示缺失值
    """
    extracted_value = getattr(extracted, field, None)
    expected_value = expected.get(field)

    # 检查值是否为 null（None 或空字符串）
    def is_null_value(val):
        if val is None:
            return True
        if isinstance(val, str) and val.strip() == '':
            return True
        return False

    extracted_is_null = is_null_value(extracted_value)
    expected_is_null = is_null_value(expected_value)

    # 当预期为 null 时：只有提取值也是 null 才匹配
    if expected_is_null:
        return extracted_is_null

    # 当预期不为 null 时：
    # 1. 如果提取值为 null，不匹配
    if extracted_is_null:
        return False

    # 2. 品牌名称模糊匹配
    if field == 'brand':
        if expected_value and extracted_value:
            return expected_value in extracted_value or extracted_value in expected_value
        return extracted_value == expected_value

    # 3. 预算模糊匹配（允许一定变化）
    if field == 'budget':
        if expected_value and extracted_value:
            # 移除空格后比较
            ev_clean = expected_value.replace(' ', '').lower()
            ev_clean = ev_clean.replace('万', '').replace('w', '').replace('左右', '')
            av_clean = extracted_value.replace(' ', '').lower()
            av_clean = av_clean.replace('万', '').replace('w', '').replace('左右', '')
            return ev_clean in av_clean or av_clean in ev_clean
        return extracted_value == expected_value

    # 4. concerns 模糊匹配（允许关键词相似）
    if field == 'concerns':
        if expected_value and extracted_value:
            ev_clean = expected_value.replace(' ', '')
            av_clean = extracted_value.replace(' ', '')
            return ev_clean in av_clean or av_clean in ev_clean
        return extracted_value == expected_value

    # 5. 严格比较
    return extracted_value == expected_value


async def validate_dataset(dataset: List[Dict[str, Any]]):
    """
    验证测试数据集

    Returns:
        (成功数, 失败数, 失败详情)
    """
    success_count = 0
    fail_count = 0
    failures = []
    dataset_issues = []

    fields_to_check = ['has_intent', 'brand', 'budget', 'interested', 'concerns', 'visit_time']

    print("=" * 80)
    print("开始验证测试数据集")
    print("=" * 80)

    for i, test_case in enumerate(dataset, 1):
        user_input = test_case['user_input']
        expected = test_case['expected']
        test_id = test_case['id']

        # 调用 extract_agent（与 car_sales.py 相同的方式）
        try:
            result = await Runner.run(extract_agent, user_input)
            extracted = result.final_output

            # 检查每个字段
            all_match = True
            field_mismatches = {}

            for field in fields_to_check:
                is_match = match_field(extracted, expected, field)
                if is_match:
                    field_mismatches[field] = {'status': 'OK', 'expected': expected.get(field), 'extracted': getattr(extracted, field, None)}
                else:
                    field_mismatches[field] = {'status': 'XX', 'expected': expected.get(field), 'extracted': getattr(extracted, field, None)}
                    all_match = False

            # 统计结果
            if all_match:
                success_count += 1
                print(f"OK [{test_id:3d}] {user_input:35s}")
            else:
                fail_count += 1
                failure_detail = {
                    'id': test_id,
                    'user_input': user_input,
                    'expected': expected,
                    'extracted': extracted.model_dump(exclude_none=True),
                    'field_mismatches': field_mismatches,
                    'issue_type': 'mismatch'  # 数据不匹配
                }
                failures.append(failure_detail)

                print(f"XX [{test_id:3d}] {user_input:35s}")

                # 分析失败原因，判断是否是数据集问题
                has_dataset_issue = False
                issue_reasons = []

                # 检查每个字段的不匹配情况
                for field, mismatch in field_mismatches.items():
                    if mismatch['status'] == '✗':
                        ev = mismatch['expected']
                        av = mismatch['extracted']

                        # 如果 Agent 提取的内容在语义上合理，但与预期不同
                        # 说明可能是数据集的 expected 字段定义不准确

                        # 情况1: 提取了非预期的字段
                        if av and not ev:
                            has_dataset_issue = True
                            issue_reasons.append(f"字段 '{field}': Agent 提取了 '{av}' 但预期为 null")

                        # 情况2: 提取结果在语义上合理但与预期不同
                        if ev and av and ev != av:
                            # 检查是否是合理的提取
                            if field == 'brand' and av and ev:
                                # 如果都是品牌且不同
                                # 可能是用户输入了多个品牌
                                if f'{ev},{av}' in user_input or f'{av},{ev}' in user_input:
                                    has_dataset_issue = True
                                    issue_reasons.append(f"字段 '{field}': 用户提到多个品牌，预期可能需要调整")

                            if field == 'interested' and av is not None and ev is not None:
                                # interested 提取不一致
                                has_dataset_issue = True
                                issue_reasons.append(f"字段 '{field}': 提取 '{av}' 但预期 '{ev}'，语义可能歧义")

                if has_dataset_issue:
                    dataset_issues.append({
                        'id': test_id,
                        'user_input': user_input,
                        'reasons': issue_reasons
                    })
                    print(f"  !! 可能是数据集问题: {', '.join(issue_reasons)}")

        except Exception as e:
            fail_count += 1
            error_detail = {
                'id': test_id,
                'user_input': user_input,
                'error': str(e),
                'issue_type': 'exception'  # 异常错误
            }
            failures.append(error_detail)

            print(f"XX [{test_id:3d}] {user_input:35s}")
            print(f"  ERROR: {str(e)}")

    return success_count, fail_count, failures, dataset_issues


async def main():
    """主函数"""
    # 加载测试数据集
    dataset_path = Path(__file__).parent / 'extractor_test_dataset.jsonl'

    if not dataset_path.exists():
        print(f"错误: 测试数据集不存在: {dataset_path}")
        return

    dataset = []
    with open(dataset_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                dataset.append(json.loads(line))

    print(f"加载了 {len(dataset)} 条测试用例")
    print()

    # 运行验证
    success, failed, failures, dataset_issues = await validate_dataset(dataset)

    # 打印结果统计
    print("\n" + "=" * 80)
    print("验证结果统计")
    print("=" * 80)
    print(f"总计: {len(dataset)} 条")
    print(f"成功: {success} 条 ({success/len(dataset)*100:.1f}%)")
    print(f"失败: {failed} 条 ({failed/len(dataset)*100:.1f}%)")
    print(f"数据集问题: {len(dataset_issues)} 条")

    # 按攻击类型统计
    print("\n按攻击类型统计:")
    print("-" * 80)
    attack_stats = {}
    for f in failures:
        attack_type = f.get('issue_type', 'unknown')
        if attack_type not in attack_stats:
            attack_stats[attack_type] = {'total': 0, 'success': 0}
        attack_stats[attack_type]['total'] += 1
        if f.get('issue_type') != 'mismatch':
            attack_stats[attack_type]['success'] += 1

    for attack_type, stats in attack_stats.items():
        success = stats['success']
        total = stats['total']
        rate = (success / total * 100) if total > 0 else 0
        print(f"{attack_type:20s} | 成功: {success}/{total} ({rate:.1f}%)")

    # 输出失败详情（前20条）
    if failures:
        print("\n失败用例详情 (前20条):")
        print("-" * 80)
        for i, f in enumerate(failures[:20], 1):
            print(f"{i}. ID: {f['id']}")
            print(f"   输入: {f['user_input']}")

            if 'error' in f:
                print(f"   错误: {f['error']}")
            else:
                print(f"   预期: {f.get('expected')}")
                print(f"   提取: {f.get('extracted')}")

                if 'field_mismatches' in f:
                    for field, mismatch in f['field_mismatches'].items():
                        if mismatch['status'] == 'XX':
                            print(f"   XX {field}: 预期={mismatch['expected']}, 提取={mismatch['extracted']}")

                if 'issue_type' in f and f['issue_type'] == 'mismatch':
                    print(f"   类型: 不匹配")

    # 输出数据集问题
    if dataset_issues:
        print("\n" + "=" * 80)
        print("数据集问题（需要 review）:")
        print("=" * 80)
        for issue in dataset_issues:
            print(f"ID: {issue['id']}")
            print(f"  输入: {issue['user_input']}")
            print(f"  原因: {', '.join(issue['reasons'])}")
            print()

    # 保存详细结果
    result_path = Path(__file__).parent / 'validation_results.json'
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump({
            'total': len(dataset),
            'success': success,
            'failed': failed,
            'failures': failures,
            'dataset_issues': dataset_issues
        }, f, ensure_ascii=False, indent=2)
    print(f"\n详细结果已保存到: {result_path}")


if __name__ == "__main__":
    asyncio.run(main())
