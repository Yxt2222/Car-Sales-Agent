"""
RAG 索引模块 - 提供车型数据访问接口
职责范围：
1. 提供懒加载的单例模式访问车型数据
2. 内部使用 SQL 数据库进行结构化存储和检索
"""

import logging
from pathlib import Path
from typing import List, Optional

from rag.database import get_database, close_database
from rag.schema import CarProfile

# 设置日志
logger = logging.getLogger(__name__)


# ==================== 模块级全局变量（懒加载） ====================
car_profiles: Optional[List[CarProfile]] = None  # 车型档案列表


# ==================== 数据加载函数 ====================

def _default_data_path() -> Path:
    """获取默认数据文件路径"""
    return Path(__file__).parent / "data" / "car.jsonl"


def load_car_profiles(data_path: Optional[Path] = None) -> List[CarProfile]:
    """
    从数据库加载车型数据

    Args:
        data_path: 数据文件路径（保留参数用于兼容性，实际使用数据库）

    Returns:
        车型档案列表
    """
    logger.debug("从数据库加载车型数据")
    db = get_database()
    cars = db.get_all_cars()
    logger.info(f"成功加载 {len(cars)} 个车型")
    return cars


# ==================== 访问函数 ====================

def get_car_profiles(data_path: Optional[Path] = None) -> List[CarProfile]:
    """
    获取车型档案列表（懒加载）

    Args:
        data_path: 数据文件路径（保留参数用于兼容性）

    Returns:
        车型档案列表
    """
    global car_profiles
    if car_profiles is None:
        logger.debug("车型数据未加载，开始加载...")
        car_profiles = load_car_profiles(data_path)
    else:
        logger.debug(f"车型数据已缓存，共 {len(car_profiles)} 个车型")
    return car_profiles if car_profiles else []


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)

    # 获取车型数据
    cars = get_car_profiles()

    print(f"\n=== 共加载 {len(cars)} 个车型 ===")
    for car in cars[:3]:  # 打印前3个
        print(f"  {car.model} - {car.brand} - {car.price_low}-{car.price_high}万")

    # 关闭数据库
    close_database()
