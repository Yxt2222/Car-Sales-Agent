"""
RAG 索引模块 - 负责构建和管理向量索引
职责范围：
1. 将车型数据向量化
2. 构建 FAISS 索引
3. 提供懒加载的单例模式访问

支持本地 Ollama 和云端 API 两种模式
"""

import json
import logging
from pathlib import Path
from typing import List, Optional, Union

import faiss
import numpy as np
from openai import OpenAI

from config import LLMConfig
from rag.schema import CarProfile

# 设置日志 - 用于调试和追踪 Agent 行为
logger = logging.getLogger(__name__)


class EmbeddingClient:
    """
    嵌入模型客户端 - 支持本地 Ollama 和云端 API
    根据 config.py 中的 MODEL_MODE 自动选择
    """

    def __init__(self, model: str = ""):
        """
        初始化嵌入模型客户端

        Args:
            model: 模型名称，默认使用配置文件中的值
        """
        config = LLMConfig.get_config()

        if config["mode"] == "local":
            # 本地 Ollama 模式
            self.client = OpenAI(
                api_key=config["api_key"],
                base_url=config["base_url"]
            )
            self.model = model or config["embedding_model"]
            logger.info(f"📦 使用本地模式: Ollama {self.model}")

        elif config["mode"] == "cloud":
            # 云端 API 模式
            self.client = OpenAI(
                api_key=config["api_key"],
                base_url=config["base_url"]
            )
            self.model = model or config["embedding_model"]
            provider = config.get("provider", "unknown")
            logger.info(f"☁️  使用云端模式: {provider} {self.model}")

    def embed(self, texts: str | List[str]) -> np.ndarray:
        """
        将文本转换为向量

        Args:
            texts: 单个文本或文本列表

        Returns:
            向量数组，形状为 (n, embedding_dim)

        Raises:
            Exception: 当 API 调用失败时
        """
        if isinstance(texts, str):
            texts = [texts]

        try:
            res = self.client.embeddings.create(
                model=self.model,
                input=texts
            )
            embs = np.array([d.embedding for d in res.data], dtype=np.float32)
            logger.debug(f"成功生成 {len(embs)} 个向量，维度: {embs.shape[1]}")
            return embs
        except Exception as e:
            logger.error(f"生成向量失败: {e}")
            raise


# ==================== 模块级全局变量（懒加载） ====================
car_profiles: Optional[List[CarProfile]] = None  # 车型档案列表
documents: Optional[List[str]] = None              # 文本表示
embed_model: Optional[EmbeddingClient] = None     # 嵌入模型客户端
embeddings: Optional[np.ndarray] = None           # 向量矩阵
index: Optional[faiss.Index] = None               # FAISS 索引


# ==================== 数据加载函数 ====================

def _default_data_path() -> Path:
    """获取默认数据文件路径"""
    return Path(__file__).parent / "data" / "car.jsonl"


def load_car_profiles(path: str | Path = "") -> List[CarProfile]:
    """
    从 JSONL 文件加载车型数据

    Args:
        path: 数据文件路径，默认使用配置中的路径

    Returns:
        车型档案列表

    Raises:
        FileNotFoundError: 当数据文件不存在时
        json.JSONDecodeError: 当数据格式错误时
    """
    if path is None or path == "":
        path = _default_data_path()
    else:
        path = Path(path)

    logger.info(f"开始加载车型数据: {path}")

    if not path.exists():
        logger.error(f"数据文件不存在: {path}")
        raise FileNotFoundError(f"车型数据文件不存在: {path}")

    cars = []
    try:
        with open(path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    car_data = json.loads(line)
                    cars.append(CarProfile(**car_data))
                except Exception as e:
                    logger.warning(f"解析第 {line_num} 行失败: {e}")
                    continue

        logger.info(f"成功加载 {len(cars)} 个车型")
        return cars

    except Exception as e:
        logger.error(f"加载数据文件失败: {e}")
        raise


def car_to_text(car: CarProfile) -> str:
    """
    将车型对象转换为用于检索的文本描述

    Args:
        car: 车型对象

    Returns:
        文本描述
    """
    tags_str = '、'.join(car.tags) if car.tags else ""
    target_users_str = f" 目标人群：{car.target_users}" if car.target_users else ""

    return f"""车型：{car.model}
品牌：{car.brand}
价格区间：{car.price_low}-{car.price_high}万
标签：{tags_str}
卖点：{'；'.join(car.selling_points)}{target_users_str}"""


# ==================== 索引构建函数 ====================

def build_index(data_path: str | Path = "", model_name: str = ""):
    """
    构建向量索引（懒加载模式）

    注意：这是一个昂贵的操作，只在首次调用时执行

    Args:
        data_path: 数据文件路径
        model_name: 嵌入模型名称

    Returns:
        FAISS 索引对象

    Raises:
        Exception: 当构建索引失败时
    """
    global car_profiles, documents, embed_model, embeddings, index

    logger.info("开始构建向量索引...")

    if data_path is None or data_path == "":
        data_path = _default_data_path()

    config = LLMConfig.get_config()
    if model_name is None:
        model_name = config["embedding_model"]

    try:
        # 1. 加载数据
        car_profiles = load_car_profiles(data_path)
        documents = [car_to_text(c) for c in car_profiles]

        # 2. 生成向量
        embed_model = EmbeddingClient(model=model_name)
        embeddings = embed_model.embed(documents)

        # 3. 归一化（用于余弦相似度）
        emb = np.asarray(embeddings, dtype=np.float32)
        if emb.ndim == 1:
            emb = emb.reshape(1, -1)

        emb = normalize_embeddings(emb)
        emb = np.ascontiguousarray(emb)

        # 4. 构建 FAISS 索引
        faiss_index = faiss.IndexFlatIP(emb.shape[1])  # IP = Inner Product (余弦相似度)
        faiss_index.add(emb)
        index = faiss_index

        logger.info(f"索引构建完成：{len(car_profiles)} 个车型，向量维度 {emb.shape[1]}")
        return index

    except Exception as e:
        logger.error(f"构建索引失败: {e}")
        raise


def ensure_index(data_path: str | Path = "", model_name: str = ""):
    """
    确保索引已初始化（懒加载）

    Args:
        data_path: 数据文件路径
        model_name: 嵌入模型名称
    """
    global index
    if index is None:
        logger.debug("索引未初始化，开始构建...")
        build_index(data_path=data_path, model_name=model_name)
    else:
        logger.debug("索引已存在，跳过构建")


def normalize_embeddings(emb: np.ndarray) -> np.ndarray:
    """
    L2 归一化向量（用于余弦相似度计算）

    Args:
        emb: 向量矩阵，形状为 (n, d)

    Returns:
        归一化后的向量矩阵
    """
    if emb.ndim == 1:
        emb = emb.reshape(1, -1)
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    # 避免除以零
    norms[norms == 0] = 1.0
    return emb / norms


# ==================== 访问函数 ====================

def get_index(data_path: str | Path = "", model_name: str = "") -> Optional[faiss.Index]:
    """
    获取 FAISS 索引（确保已初始化）

    Args:
        data_path: 数据文件路径
        model_name: 嵌入模型名称

    Returns:
        FAISS 索引对象
    """
    ensure_index(data_path=data_path, model_name=model_name)
    return index


def get_embed_model(data_path: str | Path = "", model_name: str = "") -> Optional[EmbeddingClient]:
    """
    获取嵌入模型（确保已初始化）

    Args:
        data_path: 数据文件路径
        model_name: 嵌入模型名称

    Returns:
        嵌入模型客户端对象
    """
    ensure_index(data_path=data_path, model_name=model_name)
    return embed_model


def get_car_profiles(data_path: str | Path = "") -> Optional[List[CarProfile]]:
    """
    获取车型档案列表（确保已初始化）

    Args:
        data_path: 数据文件路径

    Returns:
        车型档案列表
    """
    ensure_index(data_path=data_path)
    return car_profiles
