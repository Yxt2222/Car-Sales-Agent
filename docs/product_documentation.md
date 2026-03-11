# 汽车销售 Agent 产品文档

## 1. 任务描述

### 1.1 项目概述

本项目是一个基于**有限状态机（FSM）**驱动的汽车销售对话系统，专门用于**AI 安全课题实践**，测试 LLM 攻击方法（Jailbreak、Prompt Injection 等）。

### 1.2 核心目标

1. **销售模拟**：模拟真实的汽车销售电话流程，从开场问候到预约到店的完整过程
2. **安全测试**：作为 AI 安全实验平台，测试 LLM 的脆弱性
3. **记忆管理**：实现三层记忆系统，保证对话的连贯性和长期记忆的准确性

### 1.3 业务流程

```
OPENING（开场问候）
  ↓
ASK_INTENT（询问购车意向）
  ├── 无意向 → END（结束）
  └── 有意向
        ↓
ASK_BRAND_BUDGET（询问品牌预算）
  ├── 信息不全 → 继续询问
  └── 信息完整
        ↓
RECOMMEND（推荐车型）
  ├── 感兴趣 → SCHEDULE_VISIT（预约到店）
  └── 不感兴趣 → ASK_CONCERNS（询问顾虑）
ASK_CONCERNS（询问购车顾虑）
  ├── 有困难 → PROMOTION（促销活动）
  ├── 不清楚 → 继续询问
  └── 无困难 → END（结束）
PROMOTION（促销活动）
  ├── 打动 → SCHEDULE_VISIT（预约到店）
  └── 无效 → END（结束）
SCHEDULE_VISIT（预约到店）
  ↓
END（结束）
```

### 1.4 技术栈

- **Python 3.8+**：核心开发语言
- **OpenAI Agents SDK**：Agent 框架，管理 LLM 交互
- **FAISS**：向量检索，支持 RAG（Retrieval-Augmented Generation）
- **Pydantic**：数据验证和类型安全
- **OpenAI API**：统一的 LLM 接口（兼容本地和云端）

---

## 2. Agent 系统结构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      主程序 (car_sales.py)                 │
│                   （对话流程控制 + 状态机）                   │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌──────▼──────┐    ┌─────────▼────────┐   ┌────────▼────────┐
│ 记忆系统     │    │  RAG 检索系统     │   │ 配置管理        │
│ (memory.py)  │    │ (rag/)           │   │ (config.py)     │
└──────────────┘    └───────────────────┘   └─────────────────┘
        │                     │                     │
        │                     │                     │
┌───────▼─────────────┐   │                     │
│ ConversationHistory │   │                     │
│  - 短期记忆（5轮）│   │                     │
│  - 长期记忆（摘要）│   │                     │
│  - 用户画像       │   │                     │
└─────────────────────┘   │                     │
        │                     │                     │
┌───────▼─────────────┐   │                     │
│ Memory Summarizer  │   │                     │
│   Agent         │   │                     │
└─────────────────────┘   │                     │
                              │                     │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌──────▼──────┐    ┌─────────▼────────┐   ┌────────▼────────┐
│ Sales Agent  │    │ State Judge      │   │ Info Extractor │
│   生成话术   │    │ Agent            │   │ Agent         │
└──────────────┘    │  状态流转判断    │   │  信息提取     │
                     └───────────────────┘   └─────────────────┘
                              │
                        ┌──────────────────────┐
                        │                     │
                 ┌────────▼────────┐   ┌───────▼────────┐
                 │ Prompt Policy   │   │ Transition     │
                 │  管理器        │   │ Policy         │
                 └─────────────────┘   │  状态转换规则   │
                                        └────────────────┘
```

### 2.2 四大核心 Agent

| Agent 名称 | 职责 | 输入 | 输出 | 触发条件 |
|-----------|------|------|------|---------|
| **Sales Agent** | 生成销售话术 | 当前状态、上下文、RAG信息 | 对话回复 | 每轮对话开始 |
| **State Judge** | 判断状态流转 | 当前状态、提取信息 | 下一状态 | 每轮对话后 |
| **Info Extractor** | 抽取客户信息 | 用户回复 | 结构化信息（品牌、预算等） | 每轮对话后 |
| **Memory Summarizer** | 生成记忆摘要 | 对话历史 | 用户画像 + 对话摘要 | 短期记忆超过阈值 |

### 2.3 三层记忆架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    ConversationHistory                    │
│                   (对话历史管理器)                         │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼─────────────┐   │                     │
│  短期记忆          │   │                     │
│  - 最近 5 轮对话   │   │                     │
│  - 原封不动给 Agent │   │                     │
└─────────────────────┘   │                     │
        │                     │                     │
┌───────▼─────────────┐   │                     │
│  长期记忆          │   │                     │
│  - LLM 生成的摘要   │   │                     │
│  - 关键信息点       │   │                     │
│  - 轮次范围       │   │                     │
└─────────────────────┘   │                     │
        │                     │                     │
┌───────▼─────────────┐   │                     │
│  用户画像          │   │                     │
│  - 姓名、性别、年龄  │   │                     │
│  - 职业、性格、偏好  │   │                     │
│  - 决策倾向       │   │                     │
└─────────────────────┘   │                     │
                              │                     │
                    触发阈值 > 5 轮 → Memory Summarizer Agent
```

---

## 3. 各模块技术要点和功能

### 3.1 核心模块：car_sales.py

**功能**：主程序入口，控制对话流程和状态机

**技术要点**：
1. **状态机管理**：使用枚举定义 8 个状态（OPENING ~ END）
2. **Agent 协调**：协调 4 个 Agent 的调用顺序
3. **记忆触发**：每轮对话后检查是否需要记忆总结
4. **错误处理**：优雅处理 EOF、超时等异常

**关键代码段**：
```python
while ctx.state != CallState.END:
    # 1. 触发记忆总结
    await conversation.trigger_memory_sumarization()

    # 2. 生成销售话术
    prompt = render_prompt(ctx, conversation, rag_context)
    sales_reply = await Runner.run(sales_agent, prompt)

    # 3. 提取客户信息
    extracted = (await Runner.run(extract_agent, user_input)).final_output

    # 4. 状态流转判断
    next_state = determine_next_state(ctx, extracted)
```

### 3.2 记忆系统模块：memory.py

**功能**：管理对话历史、短期记忆、长期记忆和用户画像

**技术要点**：
1. **懒加载初始化**：Memory Summarizer Agent 在首次需要时才初始化
2. **阈值触发机制**：短期记忆超过 5 轮后自动触发总结
3. **Token 估算**：简单字符数 × 1.5 估算 token 数量
4. **JSON 输出**：Memory Agent 强制输出 JSON 格式，便于解析

**关键代码段**：
```python
class ConversationHistory:
    def __init__(self, memory_threshold=5, ...):
        self.short_term_history = []      # 短期：最近 5 轮
        self.long_term_memory = []        # 长期：LLM 摘要
        self.user_profile = UserProfile()     # 用户画像
        self.memory_threshold = memory_threshold

    async def trigger_memory_sumarization(self):
        if len(self.short_term_history) > self.memory_threshold:
            # 调用 Memory Summarizer Agent
            result = await Runner.run(self.memory_agent, prompt)
            # 更新用户画像和长期记忆
```

### 3.3 RAG 检索系统：rag/

**功能**：基于向量相似度检索相关车型信息

**技术要点**：
1. **懒加载模式**：索引和嵌入模型在首次使用时才构建
2. **余弦相似度**：使用 FAISS IndexFlatIP 实现内积检索
3. **双模式支持**：兼容本地 Ollama 和云端 API（OpenAI/通义/智谱等）
4. **文本归一化**：将车型对象转换为结构化文本描述

**关键代码段**：
```python
def build_index(data_path, model_name):
    # 1. 加载数据
    car_profiles = load_car_profiles(data_path)

    # 2. 生成向量
    embed_model = EmbeddingClient(model=model_name)
    embeddings = embed_model.embed(documents)

    # 3. 归一化（余弦相似度）
    emb = normalize_embeddings(emb)

    # 4. 构建 FAISS 索引
    faiss_index = faiss.IndexFlatIP(emb.shape[1])
    faiss_index.add(emb)
```

### 3.4 配置管理模块：config.py

**功能**：集中管理所有可配置参数

**技术要点**：
1. **双模式切换**：MODEL_MODE = "LOCAL" | "CLOUD"
2. **多云支持**：支持 OpenAI、通义千问、智谱 GLM、百度文心
3. **环境变量优先**：优先从环境变量读取 API Key
4. **统一接口**：LLMConfig.get_config() 返回统一配置字典

**关键代码段**：
```python
class LLMConfig:
    MODEL_MODE = "LOCAL"  # 或 "CLOUD"

    @staticmethod
    def get_config():
        if MODEL_MODE == "LOCAL":
            return LocalOllamaConfig.to_dict()
        else:
            return CloudAPIConfig.to_dict()
```

### 3.5 Prompt 管理模块：prompt_manager/

**功能**：集中管理各状态的 Prompt 策略和状态转换规则

**技术要点**：
1. **Prompt Spec 结构**：每个状态包含角色、目标、约束、参考话术
2. **状态转换策略**：规则优先，LLM Fallback
3. **模板渲染**：支持变量替换（如 {goal}、{constraints}）

**关键代码段**：
```python
class PromptSpec(BaseModel):
    role: str                    # 你是谁
    goal: str                    # 本轮目标
    constraints: List[str]       # 不能做什么
    suggested_phrases: List[str] # 参考话术

# 规则优先策略
def determine_next_state(ctx, extracted):
    rule_state = rule_based_next_state(ctx, extracted)
    if rule_state:
        return rule_state
    else:
        # LLM Fallback
        return llm_based_next_state(ctx, extracted)
```

---

## 4. 当前优点

### 4.1 架构设计优点

1. **状态机驱动**：流程清晰、可控性强，易于理解和维护
2. **三层记忆架构**：平衡了信息的完整性和上下文窗口限制
3. **规则 + LLM 混合**：规则保证安全性，LLM 提供灵活性
4. **模块化设计**：各职责清晰，易于扩展和测试

### 4.2 技术实现优点

1. **双模式支持**：本地 Ollama + 云端 API，适应不同环境
2. **懒加载优化**：索引和 Agent 按需初始化，减少启动时间
3. **向量检索**：FAISS 实现高效相似度计算，支持大规模数据
4. **类型安全**：Pydantic 提供运行时类型检查，减少 Bug

### 4.3 开发体验优点

1. **统一日志系统**：所有模块输出到同一日志文件，便于调试
2. **集中配置管理**：config.py 集中管理所有参数，易于切换环境
3. **Prompt 策略化**：Prompt 与代码分离，便于调优
4. **丰富数据集**：64 个车型，覆盖多个价位段和品牌

---

## 5. 缺点和限制

### 5.1 架构层面

1. **状态流转僵化**：FSM 只能按预定义路径流转，无法跳回或分支
2. **单 Agent 限制**：每个场景只有一个 Agent，缺乏多轮对话推理
3. **记忆更新被动**：记忆总结由阈值触发，而非语义触发

### 5.2 技术实现层面

1. **Token 估算不准**：简单字符数 × 1.5，与实际 token 数量偏差大
2. **向量维度固定**：不同嵌入模型维度不同，需要重建索引
3. **并发能力弱**：同步等待 Agent 响应，无法并行处理
4. **错误处理粗糙**：部分异常只记录日志，不尝试恢复

### 5.3 安全层面

1. **Prompt 注入检测弱**：未实现专门的注入检测机制
2. **输出过滤不足**：未对 Agent 输出进行内容过滤
3. **状态绕过风险**：LLM 状态判断可能被 Prompt 攻击影响

---

## 6. 未来待改进之处

### 6.1 架构优化

1. **支持状态跳转**：
   - 允许用户直接跳到任意状态（如直接询问车型）
   - 状态机增加回跳机制

2. **多 Agent 协作**：
   - 引入多 Agent 争论机制，提高决策质量
   - 实现专门的"安全审计 Agent"

3. **动态记忆触发**：
   - 基于语义相似度判断是否需要总结
   - 根据信息密度动态调整阈值

### 6.2 技术增强

1. **Token 精确计算**：
   - 使用 tiktoken 精确计算 token 数量
   - 跨模型 token 计算（支持不同 LLM）

2. **向量动态索引**：
   - 支持在线向量追加（无需重建整个索引）
   - 实现向量版本管理

3. **并发处理**：
   - Agent 调用异步化
   - 支持并行信息提取和状态判断

4. **流式输出**：
   - 实现流式响应，提升用户体验
   - 支持中途打断和更正

### 6.3 安全加固

1. **Prompt 注入检测**：
   - 实现"红队测试" Agent，自动检测攻击模式
   - 添加输入预过滤模块

2. **输出内容过滤**：
   - 实现敏感词检测和替换
   - 对输出进行安全审计

3. **状态机加固**：
   - 限制 LLM 状态判断的输出范围
   - 增加状态流转的强制规则

### 6.4 功能扩展

1. **多轮对话推理**：
   - 引入专门的"推理 Agent"，处理复杂逻辑
   - 支持上下文感知的意图识别

2. **个性化推荐**：
   - 基于用户画像动态调整推荐策略
   - 实现协同过滤和内容过滤混合推荐

3. **多模态支持**：
   - 支持图片车型展示
   - 实现语音交互接口

4. **数据分析**：
   - 实现对话数据统计和分析
   - 生成销售漏斗和转化率报告

### 6.5 工程化改进

1. **单元测试覆盖**：
   - 为每个模块编写单元测试
   - 实现 Agent 行为的模拟测试

2. **CI/CD 流水线**：
   - 自动化测试和部署
   - 实现回归测试

3. **性能监控**：
   - 实现 Agent 响应时间监控
   - 记录 token 使用量和成本

4. **配置热更新**：
   - 支持运行时配置更新
   - 实现配置版本管理

---

## 7. 附录

### 7.1 文件结构

```
car_sales_project/
├── car_sales.py              # 主程序
├── config.py                 # 配置文件
├── logger_config.py          # 日志配置
├── memory.py                 # 记忆系统
│
├── rag/                      # RAG 检索模块
│   ├── schema.py            # 数据模型定义
│   ├── index.py             # 向量索引构建
│   ├── retriever.py         # 检索器
│   └── data/
│       └── car.jsonl       # 车型数据库（64条）
│
├── prompt_manager/            # Prompt 管理模块
│   ├── prompt_policy.py     # 各状态的 Prompt 策略
│   └── states_transition_policy.py  # 状态转换规则
│
├── docs/                     # 文档目录
│   └── agent_workflow.md  # 工作流程说明
│   └── product_documentation.md  # 产品文档（本文档）
│
├── logs/                     # 日志目录
│   └── agent.log          # 程序日志
│
├── requirements.txt           # 依赖包
└── README.md                # 项目说明
```

### 7.2 数据模型定义

```python
# 状态枚举
class CallState(str, Enum):
    OPENING = "opening"              # 开场问候
    ASK_INTENT = "ask_intent"        # 询问购车意向
    ASK_BRAND_BUDGET = "ask_brand_budget"  # 询问品牌预算
    RECOMMEND = "recommend"          # 推荐车型
    ASK_CONCERNS = "ask_concerns"    # 询问顾虑
    PROMOTION = "promotion"           # 促销活动
    SCHEDULE_VISIT = "schedule_visit"  # 预约到店
    END = "end"                    # 结束

# 用户画像
class UserProfile(BaseModel):
    name: Optional[str] = None          # 用户姓名
    gender: Optional[str] = None         # 性别
    age: Optional[str] = None            # 年龄
    occupation: Optional[str] = None       # 职业/行业
    personality: Optional[str] = None      # 性格特点
    preferences: Optional[str] = None     # 偏好
    background: Optional[str] = None      # 项目背景
    constraints: Optional[str] = None     # 常见约束
    key_decisions: Optional[str] = None    # 关键决策
    terminology_mapping: Optional[dict] = None  # 术语映射

# 长期记忆摘要
class LongTermMemorySummary(BaseModel):
    summary: str                      # 对话内容摘要
    turn_range: str                    # 涵盖的对话轮次范围
    key_points: List[str] = []        # 关键信息点
    timestamp: Optional[str] = None      # 生成时间

# 车型档案
class CarProfile(BaseModel):
    model: str                  # 车型名
    brand: str                  # 品牌
    price_low: float            # 最低价（万）
    price_high: float           # 最高价（万）
    tags: List[str] = []        # 标签
    selling_points: List[str]   # 核心卖点
    target_users: Optional[str] = None  # 目标人群
```

### 7.3 配置示例

```python
# 本地模式配置
class LocalOllamaConfig:
    CHAT_MODEL = "qwen2.5:7b"
    EMBEDDING_MODEL = "bge-m3"
    BASE_URL = "http://localhost:11434/v1"
    API_KEY = "ollama"

# 云端模式配置
class CloudAPIConfig:
    PROVIDER = "openai"  # openai, qwen, zhipu, baidu
    CHAT_MODEL = "gpt-4"
    EMBEDDING_MODEL = "text-embedding-3-small"
    BASE_URL = "https://api.openai.com/v1"
    API_KEY = "sk-..."
```

---

## 更新日志

- **2026-03-09**：扩展车型数据库至 64 条
- **2026-03-09**：实现三层记忆系统（短期/长期/用户画像）
- **2026-03-09**：添加云端 API 支持（OpenAI/通义/智谱/百度）
- **2026-03-09**：实现懒加载模式和配置热更新
- **2026-03-09**：修复 Windows 控制台编码问题
