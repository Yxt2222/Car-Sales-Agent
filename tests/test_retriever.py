# tests/test_retriever.py

from rag.schema import CallContext, CallState
from rag.retriever import (
    build_car_query,
    retrieve_cars,
    format_cars_for_llm,
    retrieve_car_context,
    extract_budget_from_string,
    extract_tags_from_query,
)


# ==================== 预算解析测试 ====================

def test_extract_budget_range():
    """测试预算范围解析"""
    # 格式: 15-20万
    result = extract_budget_from_string("15-20万")
    assert result is not None
    assert result == (15.0, 20.0)
    print("✓ test_extract_budget_range: 15-20万 -> (15.0, 20.0)")

def test_extract_budget_single():
    """测试单一预算解析"""
    # 格式: 50w
    result = extract_budget_from_string("50w")
    assert result is not None
    min_price, max_price = result
    assert min_price == 45.0  # 50 - 5
    assert max_price == 55.0  # 50 + 5
    print("✓ test_extract_budget_single: 50w -> (45.0, 55.0)")

def test_extract_budget_zuoyou():
    """测试'左右'预算解析"""
    result = extract_budget_from_string("40左右")
    assert result is not None
    min_price, max_price = result
    assert min_price == 35.0  # 40 - 5
    assert max_price == 45.0  # 40 + 5
    print("✓ test_extract_budget_zuoyou: 40左右 -> (35.0, 45.0)")

def test_extract_budget_invalid():
    """测试无效预算"""
    result = extract_budget_from_string("随便看看")
    assert result is None
    print("✓ test_extract_budget_invalid: '随便看看' -> None")


# ==================== 标签提取测试 ====================

def test_extract_tags_electric():
    """测试电动标签提取"""
    tags = extract_tags_from_query("我想要一辆电动车")
    assert "纯电动" in tags
    print(f"✓ test_extract_tags_electric: '电动车' -> {tags}")

def test_extract_tags_suv():
    """测试SUV标签提取"""
    tags = extract_tags_from_query("想要个SUV")
    assert "SUV" in tags
    print(f"✓ test_extract_tags_suv: 'SUV' -> {tags}")


# ==================== 检索功能测试 ====================

def test_retrieve_by_brand():
    """测试按品牌检索"""
    ctx = CallContext(
        state=CallState.RECOMMEND,
        brand="奥迪",
        budget=None
    )

    cars = retrieve_cars(ctx, top_k=3)

    print("=== test_retrieve_by_brand ===")
    for c in cars:
        print(f"  {c.model} - {c.brand} - {c.price_low}-{c.price_high}万")

    assert len(cars) > 0
    assert all(c.brand == "奥迪" for c in cars)
    print("✓ test_retrieve_by_brand: 所有结果都是奥迪")

def test_retrieve_by_price():
    """测试按价格检索"""
    ctx = CallContext(
        state=CallState.RECOMMEND,
        brand=None,
        budget="40-50万"
    )

    cars = retrieve_cars(ctx, top_k=3)

    print("=== test_retrieve_by_price ===")
    for c in cars:
        print(f"  {c.model} - {c.price_low}-{c.price_high}万")

    assert len(cars) > 0
    # 验证价格在范围内
    for c in cars:
        # 价格范围应该与预算有重叠
        assert c.price_low <= 50 and c.price_high >= 40
    print("✓ test_retrieve_by_price: 价格在预算范围内")

def test_retrieve_combined():
    """测试组合检索（品牌+价格）"""
    ctx = CallContext(
        state=CallState.RECOMMEND,
        brand="比亚迪",
        budget="15-20万"
    )

    cars = retrieve_cars(ctx, top_k=2)

    print("=== test_retrieve_combined ===")
    for c in cars:
        print(f"  {c.model} - {c.price_low}-{c.price_high}万")

    assert len(cars) > 0
    # 验证品牌匹配
    assert all("比亚迪" in c.brand for c in cars)
    # 验证价格在范围内
    for c in cars:
        assert c.price_low <= 20 and c.price_high >= 15
    print("✓ test_retrieve_combined: 品牌和价格都匹配")

def test_retrieve_volvo():
    """测试沃尔沃品牌检索"""
    ctx = CallContext(
        state=CallState.RECOMMEND,
        brand="沃尔沃",
        budget="40万左右"
    )

    cars = retrieve_cars(ctx, top_k=3)

    print("=== test_retrieve_volvo ===")
    for c in cars:
        print(f"  {c.model} - {c.price_low}-{c.price_high}万 - {c.tags}")

    assert len(cars) > 0
    # 验证品牌匹配
    assert all("沃尔沃" in c.brand for c in cars)
    # 验证价格在解析的范围内 (35-45)
    for c in cars:
        assert c.price_low <= 45 and c.price_high >= 35
    print("✓ test_retrieve_volvo: 沃尔沃检索正常")


# ==================== 格式化测试 ====================

def test_format_for_llm():
    """测试LLM上下文格式化"""
    ctx = CallContext(
        state=CallState.RECOMMEND,
        brand="奥迪",
        budget="40万左右"
    )

    cars = retrieve_cars(ctx, top_k=1)
    text = format_cars_for_llm(cars)

    print("=== test_format_for_llm ===")
    print(text)

    # 验证格式化内容
    assert "车型" in text or "【车型】" in text
    assert "价格" in text or "【价格】" in text
    assert "卖点" in text or "【卖点】" in text
    print("✓ test_format_for_llm: 格式化正确")

def test_full_pipeline():
    """测试完整检索流程"""
    ctx = CallContext(
        state=CallState.RECOMMEND,
        brand="特斯拉",
        budget="30-40万"
    )

    context = retrieve_car_context(ctx)

    print("=== test_full_pipeline ===")
    print(context)

    assert context.strip() != ""
    assert "特斯拉" in context
    print("✓ test_full_pipeline: 完整流程正常")


# ==================== 运行所有测试 ====================

if __name__ == "__main__":
    print("=" * 50)
    print("运行 RAG 检索模块测试")
    print("=" * 50)

    # 预算解析测试
    print("\n【预算解析测试】")
    test_extract_budget_range()
    test_extract_budget_single()
    test_extract_budget_zuoyou()
    test_extract_budget_invalid()

    # 标签提取测试
    print("\n【标签提取测试】")
    test_extract_tags_electric()
    test_extract_tags_suv()

    # 检索功能测试
    print("\n【检索功能测试】")
    test_retrieve_by_brand()
    test_retrieve_by_price()
    test_retrieve_combined()
    test_retrieve_volvo()

    # 格式化测试
    print("\n【格式化测试】")
    test_format_for_llm()

    # 完整流程测试
    print("\n【完整流程测试】")
    test_full_pipeline()

    print("\n" + "=" * 50)
    print("所有测试完成！")
    print("=" * 50)
