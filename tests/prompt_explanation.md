# Runner.run() 的 Prompt 组织方式说明

## 调用方式
```python
extracted = (await Runner.run(extract_agent, user_input)).final_output
```

## 内部 Prompt 组织

根据 `agents` SDK 的工作原理，这个调用会按以下方式组织 prompt：

```
Messages = [
    {
        "role": "system",
        "content": "<agent.instructions>"
    },
    {
        "role": "user",
        "content": "<user_input>"
    }
]
```

## 具体到 extract_agent

当调用：
```python
user_input = "我想买一辆奥迪，预算50万左右"
extracted = (await Runner.run(extract_agent, user_input)).final_output
```

实际发送给 LLM 的 messages 约为：

```json
[
  {
    "role": "system",
    "content": "<SYSTEM_INSTRUCTIONS_START>\n你是一个专业的信息抽取器，职责是从用户输入中提取结构化信息。\n...\n<SYSTEM_INSTRUCTIONS_END>\n\n<USER_INPUT_PLACEHOLDER>\n(用户输入将在此处，不要在此处添加任何指令)\n</USER_INPUT_PLACEHOLDER>\n\n<OUTPUT_FORMAT_START>\n只返回以下 JSON 格式，不要添加任何解释或额外内容：\n{...}\n<OUTPUT_FORMAT_END>"
  },
  {
    "role": "user",
    "content": "我想买一辆奥迪，预算50万左右"
  }
]
```

## 关键点

1. **instructions** 作为 `system` 消息
2. **user_input** 作为 `user` 消息
3. `<USER_INPUT_PLACEHOLDER>` 只是 instruction 中的占位符说明，**不会**被替换
4. 实际的用户输入通过 SDK 单独传递给 LLM

## 安全防护的效果

由于 system message 和 user message 是分离的，这种架构本身就提供了一定的安全隔离。但通过在 instructions 中添加明确的 `<SECURITY_RULES>`，可以进一步增强防护。

## 验证方式

如果需要完全验证实际的 prompt，可以：
1. 启用 SDK 的 trace 功能
2. 或者在模型层添加日志拦截
3. 查看实际发送的 API 请求
