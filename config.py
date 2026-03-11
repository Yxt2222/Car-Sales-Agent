"""
配置文件 - 集中管理所有可配置参数
用途：方便同组同学修改模型、端口、路径等配置，无需改代码

支持两种模式：
1. LOCAL (本地) - 使用 Ollama 本地服务
2. CLOUD (云端) - 使用云端 API（OpenAI、阿里云、智谱等）
"""

import os
from pathlib import Path


# ==================== 模型部署模式选择 ====================
# ==================== 👇 修改这里切换本地/云端 👇 ====================
# 可选值: "LOCAL" (本地 Ollama) 或 "CLOUD" (云端 API)
MODEL_MODE = "LOCAL"
# =================================================================

# ==================== 云端 API 配置 ====================
class CloudAPIConfig:
    """云端 API 配置 - 当 MODEL_MODE = "CLOUD" 时生效"""

    # 选择云端服务商: "openai", "qwen", "zhipu", "baidu"
    PROVIDER = "openai"

    # OpenAI 配置
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")  # 从环境变量读取
    OPENAI_BASE_URL = "https://api.openai.com/v1"
    OPENAI_CHAT_MODEL = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"

    # 阿里通义千问配置
    QWEN_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
    QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_CHAT_MODEL = "qwen-turbo"
    QWEN_EMBEDDING_MODEL = "text-embedding-v3"

    # 智谱 GLM 配置
    ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "")
    ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
    ZHIPU_CHAT_MODEL = "glm-4-flash"
    ZHIPU_EMBEDDING_MODEL = "embedding-2"

    # 百度文心配置
    BAIYUN_API_KEY = os.getenv("BAIYUN_API_KEY", "")
    BAIYUN_SECRET_KEY = os.getenv("BAIYUN_SECRET_KEY", "")
    BAIYUN_CHAT_MODEL = "ERNIE-4.0-8K"

    @classmethod
    def get_api_config(cls):
        """根据选择的 PROVIDER 返回对应配置"""
        if cls.PROVIDER == "openai":
            return {
                "api_key": cls.OPENAI_API_KEY,
                "base_url": cls.OPENAI_BASE_URL,
                "chat_model": cls.OPENAI_CHAT_MODEL,
                "embedding_model": cls.OPENAI_EMBEDDING_MODEL
            }
        elif cls.PROVIDER == "qwen":
            return {
                "api_key": cls.QWEN_API_KEY,
                "base_url": cls.QWEN_BASE_URL,
                "chat_model": cls.QWEN_CHAT_MODEL,
                "embedding_model": cls.QWEN_EMBEDDING_MODEL
            }
        elif cls.PROVIDER == "zhipu":
            return {
                "api_key": cls.ZHIPU_API_KEY,
                "base_url": cls.ZHIPU_BASE_URL,
                "chat_model": cls.ZHIPU_CHAT_MODEL,
                "embedding_model": cls.ZHIPU_EMBEDDING_MODEL
            }
        elif cls.PROVIDER == "baidu":
            return {
                "api_key": cls.BAIYUN_API_KEY,
                "secret_key": cls.BAIYUN_SECRET_KEY,
                "chat_model": cls.BAIYUN_CHAT_MODEL,
                "embedding_model": "text-embedding-v1"
            }
        else:
            raise ValueError(f"不支持的云端服务商: {cls.PROVIDER}")


# ==================== 本地 Ollama 配置 ====================
class LocalOllamaConfig:
    """本地 Ollama 配置 - 当 MODEL_MODE = "LOCAL" 时生效"""
    API_KEY = "none"
    BASE_URL = "http://localhost:11434/v1"  # Ollama 本地服务地址

    # 模型选择 - 修改这里切换不同模型进行攻击测试
    CHAT_MODEL = "qwen2.5:7b"
    EMBEDDING_MODEL = "bge-m3"

    # 生成参数
    TEMPERATURE = 0.7
    MAX_TOKENS = 512


# ==================== 统一 LLM 配置 ====================
class LLMConfig:
    """LLM 模型相关配置 - 自动根据 MODEL_MODE 选择本地或云端"""

    @classmethod
    def get_config(cls):
        """获取当前模式的配置"""
        if MODEL_MODE == "LOCAL":
            return {
                "mode": "local",
                "api_key": LocalOllamaConfig.API_KEY,
                "base_url": LocalOllamaConfig.BASE_URL,
                "chat_model": LocalOllamaConfig.CHAT_MODEL,
                "embedding_model": LocalOllamaConfig.EMBEDDING_MODEL,
                "temperature": LocalOllamaConfig.TEMPERATURE,
                "max_tokens": LocalOllamaConfig.MAX_TOKENS
            }
        elif MODEL_MODE == "CLOUD":
            config = CloudAPIConfig.get_api_config()
            config["mode"] = "cloud"
            config["provider"] = CloudAPIConfig.PROVIDER
            return config
        else:
            raise ValueError(f"不支持的模型模式: {MODEL_MODE}，请选择 'LOCAL' 或 'CLOUD'")


# ==================== RAG 配置 ====================
class RAGConfig:
    """RAG 检索相关配置"""
    # 数据路径
    DATA_PATH = Path(__file__).parent / "rag" / "data" / "car.jsonl"

    # 检索参数
    TOP_K = 2  # 返回最相似的 K 个车型


# ==================== Agent 配置 ====================
class AgentConfig:
    """Agent 行为相关配置"""
    # 对话配置
    MAX_TURNS = 30  # 最大对话轮次（防止死循环）
    TIMEOUT_SECONDS = 30  # 单轮超时时间

    # 状态机配置
    USE_RULE_BASED_STATE = True  # 优先使用规则，LLM 作为 fallback


# ==================== 日志配置 ====================
class LogConfig:
    """日志系统配置"""
    # 日志级别: DEBUG(调试), INFO(一般), WARNING(警告), ERROR(错误)
    LOG_LEVEL = "INFO"

    # 日志文件路径
    LOG_FILE = Path(__file__).parent / "logs" / "agent.log"

    # 是否输出到控制台
    LOG_TO_CONSOLE = True

    # 日志格式
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
