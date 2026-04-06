"""
Deterministic Prompt Injection Filter

基于关键词规则的确定性过滤器，轻量、快速、可解释。
通过对用户输入分句，检测并删除包含敏感词的句子。
"""

import re
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class FilterResult:
    """过滤结果"""
    cleaned_input: str           # 清理后的输入
    has_injection: bool          # 是否检测到注入
    removed_parts: List[str]     # 被删除的片段
    detected_keywords: List[str]  # 检测到的关键词


class DeterministicFilter:
    """
    确定性 Prompt Injection 过滤器

    原理：
    1. 定义敏感关键词列表
    2. 对输入文本分句
    3. 检测每个句子是否包含敏感词
    4. 删除包含敏感词的句子
    5. 拼接剩余句子

    优点：
    - 轻量快速，无需调用 LLM
    - 规则明确，易于调试
    - 不会改变有效内容的语义
    """

    # 敏感关键词列表（约50个）
    INJECTION_KEYWORDS = [
        # 忽略/覆盖指令类
        '忽略', 'ignore', '不管', 'discard',
        '忘掉', 'forget', '忘记',
        '覆盖', 'override', '替换', 'replace',
        '跳过', 'skip', '直接跳到',
        '无视', 'disregard', '不遵循',
        '删除', 'delete', 'remove',

        # 角色扮演/身份转换类
        '扮演', 'pretend', 'act as',
        '假设', 'assume', 'imagine',
        '你现在', 'you are now',
        '角色', 'role', 'persona',
        '黑客', 'hacker', '攻击者',
        '管理员', 'admin', 'administrator',

        # 系统内部信息类
        '系统', 'system',
        '提示词', 'prompt',
        '指令', 'instruction', 'command',
        '内部', 'internal', 'behind the scenes',
        '配置', 'config', 'configuration',
        '密码', 'password',
        '密钥', 'key', 'secret',
        '敏感', 'sensitive',

        # 限制/约束类
        '限制', 'limit', 'restriction',
        '约束', 'constraint',
        '不受限制', 'no limit', 'unrestricted',
        '不受约束', 'unconstrained',
        '无限制', 'unlimited', 'without limit',
        '所有限制', 'all limits', 'any restriction',
        '之前的', 'previous', 'before',
        '前面', 'earlier', 'above',
        '过去', 'past',

        # 控制流类
        '结束', 'end', 'terminate',
        '停止', 'stop', 'halt',
        '开始', 'start', 'begin',
        '重新开始', 'restart', 'reset',
        '继续', 'continue', 'proceed',
        '执行', 'execute', 'run',
        '直接', 'directly', 'immediately',
        '立刻', 'immediately',

        # 权限/操作类
        '权限', 'permission', 'privilege',
        '访问', 'access', 'grant',
        '展示', 'show', 'display',
        '输出', 'output', 'print',
        '获取', 'get', 'obtain', 'retrieve',
        '修改', 'modify', 'change', 'alter',
        '设置', 'set', 'configure',

        # 欺骗/误导类
        '隐瞒', 'hide', 'conceal',
        '伪装', 'disguise', 'mask',
        '绕过', 'bypass', 'circumvent',
        '欺骗', 'deceive', 'trick',
        '诱导', 'mislead', 'lead astray',
    ]

    # 标点符号（用于分句）
    SENTENCE_DELIMITERS = [
        '。', '！', '？', '；',  # 中文
        '.', '!', '?', ';',      # 英文
        '\n', '\r',              # 换行
    ]

    def __init__(self, keywords: List[str] | None = None):
        """
        初始化过滤器

        Args:
            keywords: 自定义关键词列表，如果不提供则使用默认列表
        """
        self.keywords = set(keywords) if keywords else set(self.INJECTION_KEYWORDS)

    def _split_into_sentences(self, text: str) -> List[Tuple[int, int, str]]:
        """
        将文本分割成句子片段

        Args:
            text: 输入文本

        Returns:
            列表，每个元素为 (start_pos, end_pos, sentence)
        """
        if not text:
            return []

        sentences = []
        start = 0

        # 构建正则表达式模式（匹配任意分隔符）
        delimiter_pattern = '|'.join(re.escape(d) for d in self.SENTENCE_DELIMITERS)

        # 查找所有分隔符位置
        for match in re.finditer(f'({delimiter_pattern})', text):
            end = match.start()
            sentence = text[start:end].strip()

            if sentence:  # 保留非空句子
                sentences.append((start, end, sentence))

            # 跳过分隔符
            start = match.end()

        # 处理最后一个片段（如果没有以分隔符结尾）
        if start < len(text):
            sentence = text[start:].strip()
            if sentence:
                sentences.append((start, len(text), sentence))

        return sentences

    def _contains_injection(self, text: str) -> Tuple[bool, List[str]]:
        """
        检测文本是否包含注入关键词

        Args:
            text: 待检测文本

        Returns:
            (是否包含, 检测到的关键词列表)
        """
        detected = []
        text_lower = text.lower()

        for keyword in self.keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in text_lower:
                detected.append(keyword)

        return len(detected) > 0, detected

    def filter(self, user_input: str) -> FilterResult:
        """
        过滤用户输入中的 Prompt Injection

        Args:
            user_input: 用户输入文本

        Returns:
            FilterResult: 过滤结果
        """
        if not user_input or not user_input.strip():
            return FilterResult(
                cleaned_input=user_input,
                has_injection=False,
                removed_parts=[],
                detected_keywords=[]
            )

        # 分句
        sentences = self._split_into_sentences(user_input)

        # 过滤包含注入的句子
        kept_parts = []
        removed_parts = []
        all_detected_keywords = set()

        for start, end, sentence in sentences:
            has_injection, keywords = self._contains_injection(sentence)

            if has_injection:
                removed_parts.append(sentence)
                all_detected_keywords.update(keywords)
            else:
                kept_parts.append((start, end, sentence))

        # 拼接保留的句子（保持原顺序）
        cleaned_input = ''.join(s[2] for s in kept_parts)

        # 清理多余空格和标点
        cleaned_input = re.sub(r'\s+', ' ', cleaned_input).strip()
        cleaned_input = re.sub(r'[，。、；;,.]+$', '', cleaned_input)

        return FilterResult(
            cleaned_input=cleaned_input,
            has_injection=len(removed_parts) > 0,
            removed_parts=removed_parts,
            detected_keywords=list(all_detected_keywords)
        )

    def add_keywords(self, keywords: List[str]):
        """添加新的敏感关键词"""
        self.keywords.update(keywords)

    def remove_keywords(self, keywords: List[str]):
        """移除敏感关键词"""
        for kw in keywords:
            self.keywords.discard(kw)


# 便捷函数
def filter_user_input(user_input: str, custom_keywords: List[str] | None = None) -> FilterResult:
    """
    便捷函数：过滤用户输入

    Args:
        user_input: 用户输入文本
        custom_keywords: 可选的自定义关键词列表

    Returns:
        FilterResult: 过滤结果
    """
    filter_obj = DeterministicFilter(custom_keywords)
    return filter_obj.filter(user_input)


# 装饰器：自动过滤
def with_deterministic_filter(func):
    """
    装饰器：为函数添加确定性过滤

    使用示例：
    ```python
    @with_deterministic_filter
    def extract_info(user_input: str):
        # 处理过滤后的输入
        ...
    ```
    """
    def wrapper(user_input: str, *args, **kwargs):
        result = filter_user_input(user_input)

        if result.has_injection:
            print(f"[SECURITY] 检测到 Prompt Injection (确定性规则):")
            print(f"  原文: {user_input}")
            print(f"  删除部分: {result.removed_parts}")
            print(f"  检测关键词: {result.detected_keywords}")
            print(f"  清理后: {result.cleaned_input}")

        return func(result.cleaned_input, *args, **kwargs)

    return wrapper
