"""
记忆系统模块 - 殡理对话历史、短期记忆、长期记忆和用户画像

职责：
1. ConversationHistory - 对话历史管理器
2. 短期记忆：最近 5 轮对话
3. 长期记忆：超过 5 轮的记忆用 LLM 总结
4. 用户画像：用户特征信息

用途：用于 AI 安全课题实践，测试 LLM 攻击方法
"""

import asyncio
import json
import logging
from typing import List

from agents import Agent, Runner
from pydantic import BaseModel

from config import LLMConfig
from logger_config import get_logger
from rag.schema import (
    UserProfile, LongTermMemorySummary
)

logger = get_logger(__name__)


# ==================== 数据模型（已在 rag/schema.py 中定义）====================
# UserProfile - 用户画像
# LongTermMemorySummary - 长期记忆摘要


# ==================== 对话历史管理（记忆系统）====================

class ConversationHistory:
    """
    对话历史管理器 - 实现三层记忆架构

    功能：
    1. 短期记忆：最近 5 轮对话原封不动给 Agent
    2. 长期记忆：超过 5 轮的记忆用 LLM 总结
    3. 用户画像：用户特征信息
    """

    def __init__(
        self,
        max_turns: int = 10,
        memory_threshold: int = 5,
        token_limit: int = 2000,
        memory_agent=None
    ):
        """
        初始化对话历史

        Args:
            max_turns: 最多保存的对话轮次
            memory_threshold: 超过此轮数后触发记忆总结（默认 5）
            token_limit: 触发总结的 token 阈值（默认 2000）
            memory_agent: 专用于记忆总结的 Agent（可选）
        """
        self.history = []  # [(user_msg, agent_msg), ...]
        self.max_turns = max_turns
        self.memory_threshold = memory_threshold
        self.token_limit = token_limit

        # 短期记忆：最近 5 轮
        self.short_term_history = []

        # 长期记忆：对话摘要列表
        self.long_term_memory: list[LongTermMemorySummary] = []

        # 用户画像
        self.user_profile = UserProfile()

        # Token 估算（简单按字符数估算）
        self.total_tokens = 0

        logger.debug(f"对话历史管理器初始化，最大轮次: {max_turns}，记忆阈值: {memory_threshold}")

        # 初始化记忆 Agent（如果提供）
        if memory_agent is not None:
            self._init_memory_agent()

    def _init_memory_agent(self):
        """初始化记忆总结 Agent"""
        try:
            # 获取 LLM 配置
            llm_config = LLMConfig.get_config()

            # 创建 LLM 客户端
            from openai import AsyncOpenAI
            external_client = AsyncOpenAI(
                api_key=llm_config["api_key"],
                base_url=llm_config["base_url"]
            )
            from agents import OpenAIChatCompletionsModel
            model = OpenAIChatCompletionsModel(
                model=llm_config["chat_model"],
                openai_client=external_client
            )

            # 创建记忆 Agent
            self.memory_agent = Agent(
                name="Memory Summarizer",
                instructions="""
你是一个对话记忆总结专家。你的任务是：

1. 从对话历史中提取用户画像信息：
   - 姓名、性别、年龄、职业/行业
   - 性格特点、偏好
   - 项目背景、常见约束
   - 关键决策倾向

2. 生成简洁的对话摘要：
   - 涵盖的对话轮次范围
   - 关键信息点（用户诉求、顾虑、偏好）
   - 用户态度变化

重要提示：
- 只提取对话中明确提到的信息
- 如果信息模糊，返回 null
- JSON 格式输出
""",
                model=model,
            )
            logger.info("记忆 Agent 初始化完成")

        except Exception as e:
            logger.error(f"记忆 Agent 初始化失败: {e}")
            self.memory_agent = None

    def add_turn(self, user_msg: str, agent_msg: str):
        """
        添加一轮对话

        Args:
            user_msg: 用户消息
            agent_msg: Agent 回复
        """
        turn_data = (user_msg, agent_msg)
        self.history.append(turn_data)
        self.short_term_history.append(turn_data)

        # 更新 token 估算（简单估算：中文字符数 * 1.5）
        turn_tokens = len(user_msg) * 1.5 + len(agent_msg) * 1.5
        self.total_tokens += turn_tokens

        # 限制总历史长度
        if len(self.history) > self.max_turns:
            self.history = self.history[-self.max_turns:]

        logger.debug(f"添加对话轮次，短期记忆: {len(self.short_term_history)}，长期记忆数: {len(self.long_term_memory)}")

    async def trigger_memory_summarization(self):
        """
        触发长期记忆生成（需要在主循环中 await 调用）

        当短期记忆超过阈值时自动触发
        """
        if len(self.short_term_history) <= self.memory_threshold:
            logger.debug("短期记忆未超过阈值，跳过总结")
            return

        if self.memory_agent is None:
            logger.warning("记忆 Agent 未初始化，跳过总结")
            return

        try:
            # 需要总结的历史内容
            old_history = self.short_term_history[:-self.memory_threshold]

            # 格式化历史
            history_str = self._format_history_for_summary(old_history)

            prompt = f"""
你是一个对话记忆总结专家。请根据以下对话历史，生成一份简洁的摘要。

对话历史：
{history_str}

请提取以下信息（如果对话中没有，返回 null）：

1. 用户画像更新：
   - 姓名
   - 性别
   - 年龄
   - 职业/行业
   - 性格特点
   - 偏好
   - 项目背景
   - 常见约束
   - 关键决策倾向

2. 对话摘要：
   - 涵盖的对话轮次范围
   - 关键信息点（用户诉求、顾虑、偏好）
   - 用户的真实态度变化

请以 JSON 格式返回，包含以下字段：
{{
  "profile_update": {{"字段": "值", ...}},
  "summary": "对话摘要",
  "key_points": ["关键点1", "关键点2", ...],
  "turn_range": "第X轮-第Y轮"
}}

只返回 JSON，不要有任何解释。
"""

            # 调用记忆 Agent 生成总结
            result = await Runner.run(self.memory_agent, prompt)

            try:
                memory_data = json.loads(result.final_output)
                logger.debug(f"记忆总结数据: {memory_data}")

                # 更新用户画像
                if "profile_update" in memory_data:
                    profile_data = memory_data["profile_update"]
                    for key, value in profile_data.items():
                        if value is not None:
                            setattr(self.user_profile, key, value)
                    logger.info(f"用户画像更新: {profile_data}")

                # 创建长期记忆摘要
                summary_obj = LongTermMemorySummary(
                    summary=memory_data.get("summary", ""),
                    turn_range=memory_data.get("turn_range", ""),
                    key_points=memory_data.get("key_points", [])
                )
                self.long_term_memory.append(summary_obj)

                # 清空短期记忆（因为已经总结到长期记忆）
                self.short_term_history = []
                logger.info(f"长期记忆已生成，短期记忆已清空")

            except json.JSONDecodeError as e:
                logger.error(f"记忆总结 JSON 解析失败: {e}")

        except Exception as e:
            logger.error(f"长期记忆生成失败: {e}")

    def _format_history_for_summary(self, history: list) -> str:
        """
        格式化历史用于总结

        Args:
            history: 历史数据列表

        Returns:
            格式化的历史字符串
        """
        lines = []
        start_turn = len(self.history) - len(history) + 1
        for i, (user_msg, agent_msg) in enumerate(history, start_turn):
            lines.append(f"第{i}轮:")
            lines.append(f"  用户：{user_msg}")
            lines.append(f"  销售：{agent_msg}")
        return "\n".join(lines)

    def get_short_term_history_str(self) -> str:
        """
        获取短期记忆的字符串表示（最近 5 轮）

        Returns:
            格式化的短期记忆
        """
        if not self.short_term_history:
            return "（暂无短期记忆）"

        lines = []
        for i, (user_msg, agent_msg) in enumerate(self.short_term_history, 1):
            lines.append(f"第{i}轮:")
            lines.append(f"  用户：{user_msg}")
            lines.append(f" 销售：{agent_msg}")

        return "\n".join(lines)

    def get_long_term_memory_str(self) -> str:
        """
        获取长期记忆的字符串表示

        Returns:
            格式化的长期记忆
        """
        if not self.long_term_memory:
            return "（暂无长期记忆）"

        lines = []
        for memory in self.long_term_memory:
            lines.append(f"【{memory.turn_range}】")
            lines.append(f"摘要：{memory.summary}")
            if memory.key_points:
                lines.append(f"关键点：{'; '.join(memory.key_points)}")
            lines.append("")

        return "\n".join(lines)

    def get_user_profile_str(self) -> str:
        """
        获取用户画像的字符串表示

        Returns:
            格式化的用户画像
        """
        profile = self.user_profile.model_dump(exclude_none=True, exclude_unset=True)

        if not profile:
            return "（暂无用户画像信息）"

        lines = []
        for key, value in profile.items():
            # 格式化中文键名
            key_mapping = {
                "name": "姓名",
                "gender": "性别",
                "age": "年龄",
                "occupation": "职业/行业",
                "personality": "性格特点",
                "preferences": "偏好",
                "background": "项目背景",
                "constraints": "常见约束",
                "key_decisions": "决策倾向",
                "terminology_mapping": "术语映射"
            }
            key_name = key_mapping.get(key, key)
            lines.append(f"  {key_name}：{value}")

        return "\n".join(lines)

    def get_memory_context_for_prompt(self) -> str:
        """
        获取用于 Agent Prompt 的记忆上下文

        Returns:
            包含长期记忆和用户画像的字符串
        """
        sections = []

        # 用户画像
        profile_str = self.get_user_profile_str()
        if profile_str != "（暂无用户画像信息）":
            sections.append("【用户画像】")
            sections.append(profile_str)
            sections.append("")

        # 长期记忆
        memory_str = self.get_long_term_memory_str()
        if memory_str != "（暂无长期记忆）":
            sections.append("【长期记忆】")
            sections.append(memory_str)
            sections.append("")

        # 短期记忆
        short_term_str = self.get_short_term_history_str()
        if short_term_str:
            sections.append("【近期对话】")
            sections.append(short_term_str)

        return "\n".join(sections) if sections else "（暂无记忆信息）"

    def get_total_tokens(self) -> int:
        """
        获取累积的 token 数量

        Returns:
            当前总 token 数
        """
        return int(self.total_tokens)

    def should_trigger_memory_summary(self) -> bool:
        """
        判断是否应该触发记忆总结

        Returns:
            是否应该触发总结
        """
        return len(self.short_term_history) > self.memory_threshold


def create_conversation_history(memory_agent=None, max_turns=10, memory_threshold=5):
    """
    工厂函数：创建对话历史管理器

    Args:
        memory_agent: 专用于记忆总结的 Agent（可选）

    Returns:
        ConversationHistory 实例
    """
    return ConversationHistory(
        max_turns=max_turns,
        memory_threshold=memory_threshold,
        memory_agent=memory_agent
    )
