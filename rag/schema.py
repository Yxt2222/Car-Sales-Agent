from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class CallState(str, Enum):
    OPENING = "opening"#开场问候
    ASK_INTENT = "ask_intent"#询问购车意图
    ASK_BRAND_BUDGET = "ask_brand_budget"#询问购车意向品牌和预算
    RECOMMEND = "recommend"#推荐车型阶段
    ASK_CONCERNS = "ask_concerns"#如果对推荐的车型不感兴趣，询问购车顾虑
    PROMOTION = "promotion"#介绍购车活动，促销活动，开除优惠条件，尝试继续说服顾客。
    SCHEDULE_VISIT = "schedule_visit"#预约线下试车或者进一步见面
    END = "end"#结束阶段


class CallContext(BaseModel):
    state: CallState = CallState.OPENING
    has_intent: Optional[bool] = None
    brand: Optional[str] = None
    budget: Optional[str] = None
    interested: Optional[bool] = None
    concerns: Optional[str] = None
    has_real_difficulty: Optional[bool] = None
    promotion_is_valid: Optional[bool] = None
    visit_time: Optional[str] = None
    visit_store: Optional[str] = None

class CarProfile(BaseModel):
    model: str                  # 车型名，如 “比亚迪宋PLUS DM-i”
    brand: str                  # 品牌
    price_low: float            # 最低价（万）
    price_high: float           # 最高价（万）

    tags: List[str] = []        # 标签：SUV / 混动 / 家用
    selling_points: List[str]   # 核心卖点（给 Sales Agent 用）

    target_users: Optional[str] = None  # 目标人群描述
    


class ExtractedInfo(BaseModel):
    has_intent: Optional[bool] = None#是否有购车意向
    brand: Optional[str] = None#意向品牌，字典，穷尽汽车品牌
    budget: Optional[str] = None#购车预算
    interested: Optional[bool] = None#对推荐车型是否感兴趣，穷尽所有的模糊说法，system prompt
    concerns: Optional[str] = None#对推荐车型有何顾虑，钱/时间/家庭决策
    has_real_difficulty: Optional[bool] = None#是否有现实顾虑，钱/时间/家庭决策，还是纯拖延，不愿意
    promotion_is_valid: Optional[bool] = None#针对顾虑的促销是否成功
    visit_time: Optional[str] = None
    
    
class Promotion(BaseModel):
    name: str
    description: str
    valid_models: List[str]
    conditions: Optional[str] = None

class PromptSpec(BaseModel):
    '''
    PromptSpec：每个状态一份话术策略
    '''
    role: str                    # 你是谁
    goal: str                    # 本轮目标
    constraints: List[str]       # 不能做什么
    suggested_phrases: List[str] # 参考话术（不是逐字）
    exit_condition: str          # 什么时候结束这一轮


# ==================== 用户画像和记忆系统 ====================

class UserProfile(BaseModel):
    """用户画像 - 存储用户的基本信息和偏好"""
    name: Optional[str] = None          # 用户姓名
    gender: Optional[str] = None         # 性别
    age: Optional[str] = None            # 年龄
    occupation: Optional[str] = None       # 职业/行业
    personality: Optional[str] = None      # 性格特点
    preferences: Optional[str] = None     # 偏好（如注重性价比、追求品牌、关注安全等）
    background: Optional[str] = None      # 项目背景（如已有车辆、家庭成员等）
    constraints: Optional[str] = None     # 常见约束（如时间限制、预算限制等）
    key_decisions: Optional[str] = None    # 关键决策（如之前的选择倾向）
    terminology_mapping: Optional[dict] = None  # 重要术语映射（用户可能用不同说法指代同一事物）


class LongTermMemorySummary(BaseModel):
    """长期记忆摘要 - 超过短期记忆的对话总结"""
    summary: str                      # 对话内容摘要
    turn_range: str                    # 涵盖的对话轮次范围
    key_points: List[str] = []        # 关键信息点
    timestamp: Optional[str] = None      # 生成时间