"""
RAG 数据库模块 - 使用 SQLite 存储和检索车型数据
职责范围：
1. 定义数据库模型
2. 初始化数据库和数据导入
3. 提供结构化查询接口
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import List, Optional

from rag.schema import CarProfile

# 设置日志
logger = logging.getLogger(__name__)

# 数据库文件路径
DATABASE_PATH = Path(__file__).parent.parent / "car_sales.db"

# 数据文件路径
DATA_PATH = Path(__file__).parent / "data" / "car.jsonl"


class CarDatabase:
    """汽车数据库类 - 使用 SQLite 进行结构化存储和查询"""

    def __init__(self, db_path: Optional[Path] = None):
        """
        初始化数据库连接

        Args:
            db_path: 数据库文件路径，默认为项目根目录下的 car_sales.db
        """
        self.db_path = db_path or DATABASE_PATH
        self.conn = None
        self._connect()

    def _connect(self):
        """建立数据库连接"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # 支持字典式访问
        logger.info(f"数据库连接已建立: {self.db_path}")

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("数据库连接已关闭")

    def init_tables(self):
        """初始化数据库表结构"""
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model TEXT NOT NULL,
                brand TEXT NOT NULL,
                price_low REAL NOT NULL,
                price_high REAL NOT NULL,
                tags TEXT NOT NULL,
                selling_points TEXT NOT NULL,
                target_users TEXT
            )
        """)

        # 创建索引以优化查询性能
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_brand ON cars(brand)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_low ON cars(price_low)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_high ON cars(price_high)")

        self.conn.commit()
        logger.info("数据库表结构初始化完成")

    def _car_to_row(self, car: CarProfile) -> tuple:
        """
        将 CarProfile 转换为数据库行元组

        Args:
            car: 车型对象

        Returns:
            数据库行元组
        """
        return (
            car.model,
            car.brand,
            car.price_low,
            car.price_high,
            json.dumps(car.tags, ensure_ascii=False),
            json.dumps(car.selling_points, ensure_ascii=False),
            car.target_users
        )

    def _row_to_car(self, row: sqlite3.Row) -> CarProfile:
        """
        将数据库行转换为 CarProfile

        Args:
            row: 数据库行

        Returns:
            车型对象
        """
        return CarProfile(
            model=row["model"],
            brand=row["brand"],
            price_low=row["price_low"],
            price_high=row["price_high"],
            tags=json.loads(row["tags"]),
            selling_points=json.loads(row["selling_points"]),
            target_users=row["target_users"]
        )

    def load_from_jsonl(self, jsonl_path: Optional[Path] = None):
        """
        从 JSONL 文件加载数据到数据库

        Args:
            jsonl_path: JSONL 文件路径，默认使用 DATA_PATH
        """
        if jsonl_path is None:
            jsonl_path = DATA_PATH

        if not jsonl_path.exists():
            logger.error(f"数据文件不存在: {jsonl_path}")
            raise FileNotFoundError(f"数据文件不存在: {jsonl_path}")

        cursor = self.conn.cursor()

        # 先清空现有数据
        cursor.execute("DELETE FROM cars")
        self.conn.commit()
        logger.info("已清空现有数据")

        # 读取 JSONL 文件并插入数据
        count = 0
        with open(jsonl_path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    car_data = json.loads(line)
                    car = CarProfile(**car_data)
                    cursor.execute("""
                        INSERT INTO cars (model, brand, price_low, price_high, tags, selling_points, target_users)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, self._car_to_row(car))
                    count += 1
                except Exception as e:
                    logger.warning(f"解析第 {line_num} 行失败: {e}")
                    continue

        self.conn.commit()
        logger.info(f"成功导入 {count} 个车型数据到数据库")

    def get_all_cars(self) -> List[CarProfile]:
        """
        获取所有车型

        Returns:
            车型列表
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM cars")
        rows = cursor.fetchall()
        return [self._row_to_car(row) for row in rows]

    def search_by_brand(self, brand: str) -> List[CarProfile]:
        """
        按品牌搜索车型

        Args:
            brand: 品牌名称（支持模糊匹配）

        Returns:
            匹配的车型列表
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM cars WHERE brand LIKE ?",
            (f"%{brand}%",)
        )
        rows = cursor.fetchall()
        return [self._row_to_car(row) for row in rows]

    def search_by_price_range(self, min_price: float, max_price: float) -> List[CarProfile]:
        """
        按价格范围搜索车型

        Args:
            min_price: 最低价格（万）
            max_price: 最高价格（万）

        Returns:
            匹配的车型列表
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM cars
            WHERE price_low <= ? AND price_high >= ?
            ORDER BY ABS(price_low - ?) ASC
        """, (max_price, min_price, min_price))
        rows = cursor.fetchall()
        return [self._row_to_car(row) for row in rows]

    def search_by_tags(self, tags: List[str]) -> List[CarProfile]:
        """
        按标签搜索车型（支持OR匹配）

        Args:
            tags: 标签列表

        Returns:
            匹配的车型列表
        """
        cursor = self.conn.cursor()
        results = []
        for tag in tags:
            cursor.execute(
                "SELECT * FROM cars WHERE tags LIKE ?",
                (f"%{tag}%",)
            )
            rows = cursor.fetchall()
            for row in rows:
                car = self._row_to_car(row)
                # 去重
                if car not in results:
                    results.append(car)
        return results

    def search_combined(
        self,
        brand: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[CarProfile]:
        """
        组合查询 - 支持多条件组合搜索

        Args:
            brand: 品牌名称（可选）
            min_price: 最低价格（可选）
            max_price: 最高价格（可选）
            tags: 标签列表（可选）
            limit: 返回结果数量限制

        Returns:
            匹配的车型列表
        """
        query = "SELECT * FROM cars WHERE 1=1"
        params = []

        if brand:
            query += " AND brand LIKE ?"
            params.append(f"%{brand}%")

        if min_price is not None and max_price is not None:
            query += " AND price_low <= ? AND price_high >= ?"
            params.extend([max_price, min_price])

        # 标签过滤在Python中实现，因为SQLite的JSON支持有限
        cursor = self.conn.cursor()
        query += " LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        cars = [self._row_to_car(row) for row in rows]

        # 如果有标签条件，进一步过滤
        if tags:
            filtered_cars = []
            for car in cars:
                # 检查是否包含任意一个标签
                if any(tag in car.tags for tag in tags):
                    filtered_cars.append(car)
            cars = filtered_cars

        return cars

    def get_count(self) -> int:
        """
        获取数据库中车型数量

        Returns:
            车型数量
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cars")
        return cursor.fetchone()[0]


# ==================== 模块级全局变量（单例模式） ====================
_db_instance: Optional[CarDatabase] = None
_initialized: bool = False  # 追踪是否已初始化


def get_database(db_path: Optional[Path] = None, force_reinit: bool = False) -> CarDatabase:
    """
    获取数据库实例（单例模式）

    Args:
        db_path: 数据库文件路径
        force_reinit: 是否强制重新初始化

    Returns:
        数据库实例
    """
    global _db_instance, _initialized

    if _db_instance is None or force_reinit or not _initialized:
        logger.info(f"初始化数据库... (路径: {db_path or DATABASE_PATH})")
        _db_instance = CarDatabase(db_path=db_path)

        # 检查数据库是否已初始化
        cursor = _db_instance.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='cars'"
        )
        if not cursor.fetchone():
            # 数据库未初始化，执行初始化
            logger.info("数据库表不存在，创建表结构...")
            _db_instance.init_tables()
            _db_instance.load_from_jsonl()
        else:
            # 数据库已存在，检查数据
            count = _db_instance.get_count()
            if count == 0:
                logger.warning("数据库存在但无数据，重新导入")
                _db_instance.load_from_jsonl()
            else:
                logger.info(f"数据库已就绪，共 {count} 个车型")

        _initialized = True
    else:
        logger.debug(f"使用已缓存的数据库实例（{_db_instance.get_count()} 个车型）")

    return _db_instance


def close_database():
    """关闭数据库连接"""
    global _db_instance, _initialized
    if _db_instance is not None:
        _db_instance.close()
        _db_instance = None
        _initialized = False
        logger.info("数据库连接已关闭")


def init_database(jsonl_path: Optional[Path] = None):
    """
    初始化数据库（重新创建表和导入数据）

    Args:
        jsonl_path: JSONL 文件路径
    """
    global _db_instance, _initialized
    if _db_instance:
        close_database()

    logger.info("重新初始化数据库...")
    _db_instance = CarDatabase()
    _db_instance.init_tables()
    _db_instance.load_from_jsonl(jsonl_path)
    _initialized = True
    logger.info("数据库初始化完成")


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)

    # 初始化数据库
    init_database()

    # 获取数据库实例
    db = get_database()

    # 测试查询
    print("\n=== 所有车型数量 ===")
    print(f"总计: {db.get_count()} 个车型")

    print("\n=== 按品牌搜索 (比亚迪) ===")
    for car in db.search_by_brand("比亚迪"):
        print(f"  {car.model} - {car.price_low}-{car.price_high}万")

    print("\n=== 按价格搜索 (15-20万) ===")
    for car in db.search_by_price_range(15, 20):
        print(f"  {car.model} - {car.brand} - {car.price_low}-{car.price_high}万")

    print("\n=== 组合查询 (品牌=比亚迪, 价格=10-18万) ===")
    for car in db.search_combined(brand="比亚迪", min_price=10, max_price=18):
        print(f"  {car.model} - {car.price_low}-{car.price_high}万 - {car.tags}")

    # 关闭数据库
    close_database()
