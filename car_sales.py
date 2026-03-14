"""
汽车销售 Agent 主程序 - 模拟销售电话流程

这是一个有限状态机（FSM）驱动的销售对话系统，包含四个 Agent：
1. Sales Agent - 负责生成销售话术
2. State Judge Agent - 负责判断状态流转
3. Info Extractor Agent - 负责抽取客户信息
4. Memory Summarizer Agent - 负责记忆总结

业务流程：
    OPENING -> ASK_INTENT -> ASK_BRAND_BUDGET -> RECOMMEND -> SCHEDULE_VISIT/ASK_CONCERNS -> PROMOTION -> END

"""

import asyncio
from typing import Optional

from agents import Agent, OpenAIChatCompletionsModel, Runner
from openai import AsyncOpenAI
from pydantic import BaseModel

# ==================== 导入本地模块 ====================
from config import AgentConfig, LLMConfig
from logger_config import get_logger
from prompt_manager.prompt_policy import PromptPolicy
from prompt_manager.states_transition_policy import StatestransitionPolicy
from rag.retriever import retrieve_car_context
from rag.schema import (
    CallContext, CallState, ExtractedInfo
)
from memory import create_conversation_history

logger = get_logger(__name__)


# ==================== 状态转换规则 ====================

# FSM 状态转换表 - 定义每个状态允许的下一状态
STATE_TRANSITIONS = {
    CallState.OPENING: [CallState.ASK_INTENT],
    CallState.ASK_INTENT: [CallState.ASK_BRAND_BUDGET, CallState.END],
    CallState.ASK_BRAND_BUDGET: [CallState.ASK_BRAND_BUDGET, CallState.RECOMMEND],
    CallState.RECOMMEND: [CallState.SCHEDULE_VISIT, CallState.ASK_CONCERNS, CallState.RECOMMEND],
    CallState.ASK_CONCERNS: [CallState.PROMOTION, CallState.ASK_CONCERNS, CallState.END],
    CallState.PROMOTION: [CallState.SCHEDULE_VISIT, CallState.END],
    CallState.SCHEDULE_VISIT: [CallState.END],
}


class StateDecision(BaseModel):
    """状态决策结果 - 结构化输出"""
    next_state: CallState
    reason: str


def rule_based_next_state(ctx: CallContext, extracted: ExtractedInfo) -> Optional[CallState]:
    """
    基于规则的状态转换（优先使用规则，LLM 作为 fallback）

    这是安全的状态转换逻辑，避免 LLM 不确定性导致的状态混乱

    Args:
        ctx: 当前对话上下文
        extracted: 提取的客户信息

    Returns:
        下一状态，如果规则无法决定则返回 None
    """
    try:
        # 开场 -> 询问意向
        if ctx.state == CallState.OPENING:
            return CallState.ASK_INTENT

        # 询问意向 -> 有意向问品牌预算，无意向结束
        if ctx.state == CallState.ASK_INTENT:
            if extracted.has_intent is False:
                return CallState.END
            if extracted.has_intent is True:
                return CallState.ASK_BRAND_BUDGET

        # 询问品牌预算 -> 信息充足则推荐，否则继续询问
        if ctx.state == CallState.ASK_BRAND_BUDGET:
            if extracted.budget is None or extracted.brand is None:
                return CallState.ASK_BRAND_BUDGET
            else:
                return CallState.RECOMMEND

        # 推荐阶段 -> 感兴趣预约，不感兴趣问顾虑
        if ctx.state == CallState.RECOMMEND:
            if extracted.interested is True:
                return CallState.SCHEDULE_VISIT
            if extracted.interested is False:
                return CallState.ASK_CONCERNS

        # 询问顾虑 -> 有困难则促销，无困难则结束，不清楚则继续问
        if ctx.state == CallState.ASK_CONCERNS:
            if extracted.has_real_difficulty is True:
                return CallState.PROMOTION
            elif extracted.has_real_difficulty is False:
                return CallState.END
            else:
                return CallState.ASK_CONCERNS

        # 促销阶段 -> 打动则预约，否则结束
        if ctx.state == CallState.PROMOTION:
            if extracted.promotion_is_valid is True:
                return CallState.SCHEDULE_VISIT
            else:
                return CallState.END

        # 预约阶段 -> 直接结束（不管结果如何）
        if ctx.state == CallState.SCHEDULE_VISIT:
            return CallState.END

    except Exception as e:
        logger.error(f"规则状态转换失败: {e}")

    # 规则无法决定时返回 None，由 LLM fallback
    return None


def merge_extracted_info(ctx: CallContext, extracted: ExtractedInfo) -> CallContext:
    """
    合并提取的客户信息到上下文

    更新规则：
    - 品牌和预算：总是更新（用户可能改变想法）
    - 其他字段（如意向、兴趣等）：保持已确认值

    Args:
        ctx: 当前对话上下文
        extracted: 新提取的信息

    Returns:
        更新后的对话上下文
    """
    updates = {}
    extracted_dict = extracted.model_dump(exclude_none=True)

    for field, new_value in extracted_dict.items():
        if new_value is None:
            continue
        old_value = getattr(ctx, field, None)

        # 品牌和预算总是更新（用户可能改变想法）
        if field in ['brand', 'budget']:
            if old_value != new_value and new_value:  # 只在值不同时更新
                updates[field] = new_value
        elif field in ['concerns']:
            # 顾虑字段：如果有新顾虑，追加到已有顾虑中
            if old_value:
                if new_value not in old_value and new_value:
                    updates[field] = old_value + "; " + new_value
            else:
                updates[field] = new_value
        else:
            # 其他字段：只有当旧值为空时才更新
            if old_value is None and new_value:
                updates[field] = new_value

    return ctx.model_copy(update=updates)


def render_prompt(ctx: CallContext, conversation, rag_context: str = "") -> str:
    """
    渲染对话 Prompt - 加入完整记忆系统（短期记忆、长期记忆、用户画像）

    Args:
        ctx: 对话上下文
        conversation: 对话历史对象
        rag_context: RAG 检索的车型信息

    Returns:
        完整的 Prompt 字符串
    """
    spec = PromptPolicy.get(ctx.state)
    memory_context = conversation.get_memory_context_for_prompt()

    return f"""
            ROLE:
                {spec.role}
            CURRENT GOAL:
                {spec.goal}
            KNOWN CUSTOMER INFO (confirmed so far):
                {ctx.model_dump_json(exclude_none=True, indent=2, ensure_ascii=False)}
            REFERENCE INFORMATION (use only if helpful):
                {rag_context}
            Use: reference information only to support recommendations.
            Do not invent models not listed above.

            MEMORY SYSTEM:
            {memory_context}

            CONSTRAINTS:
                {chr(10).join('- ' + c for c in spec.constraints)}
            SUGGESTED PHRASES (paraphrase, do not copy verbatim):
                {chr(10).join('- ' + s for s in spec.suggested_phrases)}
            EXIT CONDITION:
                {spec.exit_condition}

            Generate ONE sales utterance that strictly serves the CURRENT GOAL.
            Do NOT move to another stage unless explicitly instructed.
            """


# ==================== Agent 初始化 ====================

# 创建 LLM 客户端 - 自动根据配置选择本地或云端
llm_config = LLMConfig.get_config()
logger.info(f"[CONFIG] LLM 配置: {llm_config['mode']} 模式")

external_client = AsyncOpenAI(
    api_key=llm_config["api_key"],
    base_url=llm_config["base_url"]
)

# 创建聊天模型
model = OpenAIChatCompletionsModel(
    model=llm_config["chat_model"],
    openai_client=external_client
)

# 创建对话历史管理器（记忆系统）
conversation = create_conversation_history(
    max_turns=10,
    memory_threshold=5
)

# ===== Agent 1: Sales Agent - 销售话术生成 =====
sales_agent = Agent(
    name="Sales Agent",
    instructions="""
    你是一名专业的汽车销售代表，正在给客户打电话。说话礼貌、简洁、自然。
    严格遵循当前呼叫状态。不要自动跳转。

    重要：请根据对话历史和用户画像了解之前的交流内容，避免重复提问。
    """,
    model=model
)

# ===== Agent 2: State Judge Agent - 状态判定 =====
state_judge_agent = Agent(
    name="State Judge",
    instructions=f"""
    你是一个有限状态机（FSM）判定器，而不是对话机器人。

    任务：
    - 根据【当前状态】和【已提取的结构化信息】，
    - 在【允许的状态集合】中选择一个 next_state。

    规则：
    1. 只能从 allowed_states 中选择
    2. 如果信息不足，保持当前状态
    3. 不要推测用户意图，必须有明确信号
    4. 不允许跨级跳转
    5. 只返回 JSON，不要输出解释性文本。
    """,
    output_type=StateDecision,
    model=model,
)

# ===== Agent 3: Info Extractor Agent - 信息抽取 =====
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
        #用户的购车预算
    - interested: bool
        - "这款可以 / 挺喜欢" -> True
        - "不太合适 / 再看看" -> False
    - concerns: str
        #用户在考虑购车时有何顾虑？价格/安全性/外观/舒适性/驾驶乐趣/发动机性能
    - has_real_difficulty: bool
        #用户是否有合理的顾虑。
        # 有现实且明确的顾虑，钱/时间/家庭决策 -> true
        # 用户有顾虑，但不是很明确，需要再次询问 -> None
        # 明显地可以看出用户在纯拖延，不愿意 -> False
    - promotion_is_valid: bool
        #针对顾虑的促销是否成功
        #促销成功，用户感兴趣 -> true
        #促销不成功，用户仍然不感兴趣 -> false
    - visit_time: str
        # 用户预约的到店时间

    如果用户语义模糊，请返回 null。
    只返回 JSON。
    """,
    model=model,
    output_type=ExtractedInfo,
)


# ==================== 主对话循环 ====================

async def run_call():
    """
    运行销售对话的主循环

    流程：
    1. Agent 生成话术
    2. 用户输入
    3. 抽取信息
    4. 判断状态流转（规则优先，LLM fallback）
    5. 添加到对话历史
    6. 触发记忆总结（当短期记忆超过阈值）
    """
    ctx = CallContext()
    turn_count = 0

    logger.info("=" * 50)
    logger.info("销售对话开始")
    logger.info("=" * 50)
    logger.info(f"初始状态: {ctx.state}")
    logger.info(f"初始上下文: {ctx.model_dump_json(exclude_none=True)}")

    while ctx.state != CallState.END:
        turn_count += 1

        # 防止死循环
        if turn_count > AgentConfig.MAX_TURNS:
            logger.warning(f"对话轮次超过限制 ({AgentConfig.MAX_TURNS})，强制结束")
            ctx.state = CallState.END
            break

        try:
            logger.info(f"\n--- 第 {turn_count} 轮对话 (当前状态: {ctx.state}) ---")

            # 1. 触发记忆总结（每轮都检查）
            await conversation.trigger_memory_summarization()

            # 2. 生成销售话术
            # 根据状态决定是否调用 RAG
            if ctx.state == CallState.RECOMMEND:
                rag_context = retrieve_car_context(ctx)
                logger.debug(f"RAG 检索上下文:\n{rag_context}")
            else:
                rag_context = ""

            # 渲染 Prompt（使用完整记忆系统）
            prompt = render_prompt(ctx, conversation, rag_context)

            # 调用 Sales Agent
            sales_reply = await Runner.run(sales_agent, prompt)
            sales_message = sales_reply.final_output

            print(f"\n[SALES]: {sales_message}")
            logger.info(f"Sales Agent 输出: {sales_message}")

            # 3. 等待用户输入
            user_input = await asyncio.get_running_loop().run_in_executor(
                None, input, "[USER]: "
            )
            logger.info(f"用户输入: {user_input}")

            # 4. 抽取客户信息
            extracted = (await Runner.run(extract_agent, user_input)).final_output
            logger.debug(f"抽取信息: {extracted.model_dump_json(exclude_none=True, ensure_ascii=False)}")

            # 更新上下文
            ctx = merge_extracted_info(ctx, extracted)
            logger.debug(f"更新后上下文: {ctx.model_dump_json(exclude_none=True, ensure_ascii=False)}")

            # 5. 添加到对话历史
            conversation.add_turn(user_input, sales_message)
            logger.debug(f"对话历史更新:\n{conversation.get_memory_context_for_prompt()}")

            # 6. 判断状态流转
            decision_prompt = f"""
            Current state: {ctx.state}
            Allowed next states: {STATE_TRANSITIONS[ctx.state]}
            State transition rules: {StatestransitionPolicy.get(ctx.state.value)}
            Extracted info:
            {extracted.model_dump_json(exclude_none=True, ensure_ascii=False)}
            User reply:
            {user_input}
            """

            # 关键修复：规则优先，LLM fallback
            rule_state = rule_based_next_state(ctx, extracted)

            if rule_state is None:
                # 规则无法决定，使用 LLM
                decision = await Runner.run(state_judge_agent, decision_prompt)
                ctx.state = decision.final_output.next_state
                logger.info(f"状态转换（LLM 驱动）: {ctx.state} - 原因: {decision.final_output.reason}")
            else:
                # 规则可以决定，使用规则
                ctx.state = rule_state
                logger.info(f"状态转换（规则驱动）: {ctx.state}")

            print(f"📍 当前状态: {ctx.state.value}")

        except Exception as e:
            logger.error(f"对话轮次 {turn_count} 发生错误: {e}", exc_info=True)
            print(f"\n[WARNING] 发生错误: {e}")
            # 发生错误时也继续，避免直接崩溃
            continue

    # 对话结束
    logger.info("=" * 50)
    logger.info("销售对话结束")
    logger.info("=" * 50)
    logger.info(f"最终上下文: {ctx.model_dump_json(exclude_none=True, indent=2, ensure_ascii=False)}")
    logger.info(f"用户画像: {conversation.user_profile.model_dump_json(exclude_none=True, ensure_ascii=False)}")

    print("\n[DONE] 对话结束")
    print("最终客户信息:")
    print(ctx.model_dump_json(exclude_none=True, indent=2, ensure_ascii=False))
    print("\n用户画像:")
    print(conversation.user_profile.model_dump_json(exclude_none=True, indent=2, ensure_ascii=False))

    return ctx


# ==================== 程序入口 ====================

if __name__ == "__main__":
    try:
        ctx = asyncio.run(run_call())
    except KeyboardInterrupt:
        print("\n\n[INTERRUPT] 用户中断对话")
        logger.info("对话被用户中断")
    except Exception as e:
        print(f"\n\n[ERROR] 程序异常退出: {e}")
        logger.error(f"程序异常: {e}", exc_info=True)
