"""
RAG 检索器模块 - 根据用户需求检索相关车型
职责范围：
1. 接收业务查询条件（来自 CallContext）
2. 调用向量索引找到最相关的业务事实
3. 将结果格式化为 LLM 可用的参考文本
"""

import logging
import re
from typing import List, Optional

import numpy as np

from config import RAGConfig
from rag.index import get_embed_model, get_index, get_car_profiles, normalize_embeddings
from rag.schema import CarProfile, CallContext

# 设置日志
logger = logging.getLogger(__name__)


def extract_budget_from_string(budget_str: str) -> tuple[int, int] | None:
    """
    从预算字符串中提取价格范围（单位：万）

    Args:
        budget_str: 预算字符串，如 "50w"、"50万"、"50左右"

    Returns:
        (min_price, max_price) 元组，如果无法解析则返回 None
    """
    if not budget_str:
        return None

    # 标准化：去除空格，转小写
    budget_str = budget_str.strip().lower()

    # 匹配 "50w"、"50万"、"50左右"、"50~"
    pattern = r'(\d+)[w万]?(?:~左右)?|(\d+)w'
    match = re.search(pattern, budget_str)

    if match:
        try:
            center = int(match.group(1))
            # 解析范围：允许 ±5 万的误差
            return (max(0, center - 5), center + 5)
        except (ValueError, IndexError):
            logger.warning(f"无法解析预算: {budget_str}")
            return None

    return None


def build_car_query(ctx: CallContext) -> str:
    """
    将 CallContext 转换为适合向量检索的自然语言查询

    Args:
        ctx: 对话上下文，包含用户品牌偏好、预算等信息

    Returns:
        检索查询字符串
    """
    parts = []

    if ctx.brand:
        parts.append(f"品牌：{ctx.brand}")

    # 解析预算范围
    budget_range = extract_budget_from_string(ctx.budget)
    if budget_range:
        min_price, max_price = budget_range
        parts.append(f"价格范围：{min_price}万-{max_price}万")
    else:
        # 如果无法解析预算，尝试原始格式
        if ctx.budget:
            parts.append(f"预算：{ctx.budget}")

    # 默认用途（可根据实际需求扩展）
    parts.append("用途：家用 日常通勤")

    query = "，".join(parts)
    logger.debug(f"构建检索查询: {query}")
    return query


def filter_by_budget(cars: List[CarProfile], budget_range: tuple[int, int] | None) -> List[CarProfile]:
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
        # 检查是否在预算范围内（允许 ±5 万误差）
        if min_price <= car.price_low <= max_price:
            filtered.append(car)
        # 或者预算接近车型的最低价
        elif abs(car.price_low - max_price) <= 5:
            filtered.append(car)

    return filtered


def retrieve_cars(ctx: CallContext, top_k: int | None = None) -> List[CarProfile]:
    """
    根据对话上下文检索相关车型

    Args:
        ctx: 对话上下文
        top_k: 返回最相似的 K 个车型，默认使用配置中的值

    Returns:
        车型列表，按相似度排序
    """
    if top_k is None:
        top_k = RAGConfig.TOP_K

    try:
        # 1. 构建查询
        query = build_car_query(ctx)

        # 2. 获取模型和索引
        embed_model = get_embed_model()
        index = get_index()

        if embed_model is None or index is None:
            logger.error("向量检索系统未初始化")
            raise RuntimeError("向量检索系统未初始化")

        # 3. 生成查询向量
        q_emb = embed_model.embed([query])
        q_emb = np.asarray(q_emb, dtype=np.float32)
        if q_emb.ndim == 1:
            q_emb = q_emb.reshape(1, -1)

        # 4. 归一化（与索引一致）
        q_emb = normalize_embeddings(q_emb)

        # 5. 执行检索
        # type: ignore[call-arg]  # FAISS search 方法签名在类型提示中不准确
        scores, idxs = index.search(q_emb, k=top_k * 2)  # 取更多候选，后过滤

        # 6. 解析预算范围
        budget_range = extract_budget_from_string(ctx.budget)

        # 7. 获取所有车型数据
        all_cars = get_car_profiles()
        if all_cars is None:
            logger.error("车型数据未初始化")
            raise RuntimeError("车型数据未初始化")

        # 8. 根据预算过滤
        if budget_range:
            all_cars = filter_by_budget(all_cars, budget_range)
            logger.debug(f"按预算过滤后剩余 {len(all_cars)} 个车型")

        # 9. 从检索结果中获取候选
        candidates = []
        for i in idxs[0]:  # 只取第一个结果
            if 0 <= i < len(all_cars):
                candidates.append(all_cars[i])

        logger.info(f"检索到 {len(candidates)} 个候选车型，原始相似度: {scores[0]}")

        return candidates

    except Exception as e:
        logger.error(f"检索失败: {e}")
        raise


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


def retrieve_car_context(ctx: CallContext, top_k: int | None = None) -> str:
    """
    获取对话上下文相关的车型推荐文本

    Args:
        ctx: 对话上下文
        top_k: 返回最相似的 K 个车型

    Returns:
        格式化的车型推荐文本
    """
    try:
        cars = retrieve_cars(ctx, top_k=top_k)
        return format_cars_for_llm(cars)
    except Exception as e:
        logger.error(f"获取车型上下文失败: {e}")
        return ""  # 失败时返回空字符串，不中断对话
