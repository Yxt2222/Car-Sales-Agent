"""
RAG 检索器模块 - 根据用户需求检索相关车型
职责范围：
1. 接收业务查询条件（来自 CallContext）
2. 调用 SQL 数据库找到匹配的车型
3. 将结果格式化为 LLM 可用的参考文本
"""

import logging
import re
from typing import List, Optional

from config import RAGConfig
from rag.database import get_database
from rag.schema import CallContext, CarProfile

# 设置日志
logger = logging.getLogger(__name__)


def extract_budget_from_string(budget_str: str) -> Optional[tuple[float, float]]:
    """
    从预算字符串中提取价格范围（单位：万）

    Args:
        budget_str: 预算字符串，如 "50w"、"50万"、"50左右"、"15-20"

    Returns:
        (min_price, max_price) 元组，如果无法解析则返回 None
    """
    if not budget_str:
        return None

    # 标准化：去除空格，转小写
    budget_str = budget_str.strip().lower()

    # 匹配 "15-20"、"15-20万"、"15~20万"、"15w-20w" 等格式
    range_pattern = r'(\d+)\s*[-~]\s*(\d+)(?:w|万)?'
    range_match = re.search(range_pattern, budget_str)

    if range_match:
        try:
            min_price = float(range_match.group(1))
            max_price = float(range_match.group(2))
            # 确保 min <= max
            if min_price > max_price:
                min_price, max_price = max_price, min_price
            return (min_price, max_price)
        except (ValueError, IndexError):
            pass

    # 匹配 "50w"、"50万"、"50左右"、"50~" 等格式（单一数字）
    single_pattern = r'(\d+)(?:w|万|~|左右)?'
    single_match = re.search(single_pattern, budget_str)

    if single_match:
        try:
            center = float(single_match.group(1))
            # 解析范围：允许 ±5 万的误差
            return (max(0, center - 5), center + 5)
        except (ValueError, IndexError):
            logger.warning(f"无法解析预算: {budget_str}")
            return None

    logger.warning(f"无法解析预算字符串: {budget_str}")
    return None


def extract_tags_from_query(query: str) -> List[str]:
    """
    从用户查询中提取标签关键词

    Args:
        query: 用户查询字符串

    Returns:
        标签列表
    """
    # 常见汽车标签映射
    tag_keywords = {
        "混动": ["混动", "混动suv", "dm-i", "dht", "混动轿车"],
        "纯电动": ["电动", "纯电", "ev", "电车", "新能源", "电动车"],
        "SUV": ["suv", "越野车", "越野", "硬派"],
        "紧凑型": ["紧凑", "小型", "a级"],
        "豪华": ["豪华", "高端", "旗舰"],
        "运动": ["运动", "操控", "驾驶乐趣"],
        "家用": ["家用", "家庭", "通勤", "日常"],
        "商务": ["商务", "行政", "公司"],
        "省油": ["省油", "油耗", "经济", "燃油"],
        "智能": ["智能", "科技", "自动驾驶", "辅助驾驶"],
        "空间": ["空间", "大空间", "宽敞", "六座", "七座"],
        "安全": ["安全", "可靠", "保值"],
    }

    query_lower = query.lower()
    matched_tags = []

    for tag, keywords in tag_keywords.items():
        for keyword in keywords:
            if keyword in query_lower:
                matched_tags.append(tag)
                break

    return matched_tags


def retrieve_cars(ctx: CallContext, top_k: Optional[int] = None) -> List[CarProfile]:
    """
    根据对话上下文检索相关车型

    Args:
        ctx: 对话上下文
        top_k: 返回最相关的 K 个车型，默认使用配置中的值

    Returns:
        车型列表，按匹配度排序
    """
    if top_k is None:
        top_k = RAGConfig.TOP_K

    try:
        # 获取数据库实例
        db = get_database()

        # 记录数据库信息
        logger.info(f"当前数据库中共有 {db.get_count()} 个车型")

        # 解析查询条件
        brand = ctx.brand if ctx.brand else None

        # 解析预算范围
        budget_range = extract_budget_from_string(ctx.budget) if ctx.budget else None
        min_price, max_price = budget_range if budget_range else (None, None)

        # 从预算字符串中提取可能的标签
        tags = []
        if ctx.budget:
            tags.extend(extract_tags_from_query(ctx.budget))

        logger.info(f"[检索] 品牌={brand}, 预算={ctx.budget} -> 价格范围=({min_price}, {max_price}), 标签={tags}")

        # 如果有品牌，先验证数据库中是否有该品牌的车
        if brand:
            brand_cars = db.search_by_brand(brand)
            logger.info(f"[检索] 数据库中'{brand}'品牌的车型数量: {len(brand_cars)}")
            if brand_cars:
                logger.info(f"[检索] '{brand}'品牌车型示例: {[f'{c.model}({c.price_low}-{c.price_high})' for c in brand_cars[:3]]}")

        # 执行组合查询
        cars = db.search_combined(
            brand=brand,
            min_price=min_price,
            max_price=max_price,
            tags=tags,
            limit=top_k * 2  # 获取更多候选用于后续排序
        )

        logger.info(f"[检索] 组合查询返回 {len(cars)} 个车型")

        # 简单排序：优先匹配品牌，其次价格接近度
        def score_car(car: CarProfile) -> float:
            score = 0.0

            # 品牌匹配加分
            if brand and brand.lower() in car.brand.lower():
                score += 100
                logger.debug(f"[评分] {car.model} 品牌匹配加分 +100")

            # 价格接近度加分（价格越接近预算中心分越高）
            if min_price is not None and max_price is not None:
                center = (min_price + max_price) / 2
                car_price = (car.price_low + car.price_high) / 2
                distance = abs(car_price - center)
                price_score = max(0, 50 - distance)
                score += price_score
                logger.debug(f"[评分] {car.model} 价格距离={distance:.1f}, 加分={price_score:.1f}")

            # 标签匹配加分
            if tags:
                for tag in tags:
                    if tag in car.tags:
                        score += 10
                        logger.debug(f"[评分] {car.model} 标签'{tag}'匹配加分 +10")

            return score

        # 按得分排序
        cars.sort(key=score_car, reverse=True)

        # 返回前 top_k 个结果
        result = cars[:top_k]
        logger.info(f"[检索] 最终返回 {len(result)} 个候选车型:")
        for c in result:
            logger.info(f"[检索]   - {c.model} ({c.brand}) 价格: {c.price_low}-{c.price_high}万")
        return result

    except Exception as e:
        logger.error(f"检索失败: {e}")
        raise


def filter_by_budget(cars: List[CarProfile], budget_range: Optional[tuple[float, float]]) -> List[CarProfile]:
    """
    根据预算范围过滤车型

    Args:
        cars: 车型列表
        budget_range: (min_price, max_price) 预算范围，None 表示无限制

    Returns:
        过滤后的车型列表
    """
    if budget_range is None:
        return cars

    min_price, max_price = budget_range
    filtered = []

    for car in cars:
        # 检查是否在预算范围内
        if min_price <= car.price_low <= max_price:
            filtered.append(car)
        # 或者预算接近车型的最低价
        elif abs(car.price_low - max_price) <= 5:
            filtered.append(car)

    return filtered


def format_cars_for_llm(cars: List[CarProfile]) -> str:
    """
    将车型列表格式化为 LLM 可读的文本

    Args:
        cars: 车型列表

    Returns:
        格式化的文本字符串
    """
    if not cars:
        logger.warning("车型列表为空")
        return ""

    blocks = []

    for car in cars:
        blocks.append(
            f"""【车型】{car.model}
【价格】{car.price_low}-{car.price_high} 万
【卖点】{'；'.join(car.selling_points)}
"""
        )

    result = "\n".join(blocks)
    logger.debug(f"格式化车型信息:\n{result}")
    return result


def retrieve_car_context(ctx: CallContext, top_k: Optional[int] = None) -> str:
    """
    获取对话上下文相关的车型推荐文本

    Args:
        ctx: 对话上下文
        top_k: 返回最相关的 K 个车型

    Returns:
        格式化的车型推荐文本
    """
    try:
        cars = retrieve_cars(ctx, top_k=top_k)
        return format_cars_for_llm(cars)
    except Exception as e:
        logger.error(f"获取车型上下文失败: {e}")
        return ""  # 失败时返回空字符串，不中断对话


def build_car_query(ctx: CallContext) -> str:
    """
    将 CallContext 转换为查询字符串（用于日志和调试）

    Args:
        ctx: 对话上下文，包含用户品牌偏好、预算等信息

    Returns:
        查询字符串
    """
    parts = []

    if ctx.brand:
        parts.append(f"品牌：{ctx.brand}")

    # 解析预算范围
    budget_range = extract_budget_from_string(ctx.budget) if ctx.budget else None
    if budget_range:
        min_price, max_price = budget_range
        parts.append(f"价格范围：{min_price}万-{max_price}万")
    else:
        # 如果无法解析预算，尝试原始格式
        if ctx.budget:
            parts.append(f"预算：{ctx.budget}")

    query = "，".join(parts)
    logger.debug(f"构建检索查询: {query}")
    return query


# 以下函数保留用于兼容性
def filter_by_price_range(cars: List[CarProfile], min_price: float, max_price: float) -> List[CarProfile]:
    """
    根据价格范围过滤车型

    Args:
        cars: 车型列表
        min_price: 最低价格
        max_price: 最高价格

    Returns:
        过滤后的车型列表
    """
    return filter_by_budget(cars, (min_price, max_price))
