# AgentLoop 设计思路

## 概述

`AgentLoop` 是 nanobot 的**核心处理引擎**，负责协调消息接收、上下文构建、LLM 调用、工具执行和响应发送的完整流程。

核心职责：
- 消息调度与生命周期管理
- ReAct 循环（推理-行动-观察）
- 工具注册与执行
- 会话状态管理
- MCP (Model Context Protocol) 连接管理

---

## 架构设计

### 1. 双循环架构

```
┌─────────────────────────────────────────────────────────────┐
│                    外层循环 (消息调度)                         │
│                      run() 方法                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  while _running:                                     │   │
│  │    msg = bus.consume_inbound()                       │   │
│  │    if cmd == "/stop": handle_stop()                  │   │
│  │    elif cmd == "/restart": handle_restart()           │   │
│  │    else: create_task(_dispatch(msg))  ← 非阻塞       │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ 创建独立任务
┌─────────────────────────────────────────────────────────────┐
│                    内层循环 (ReAct 推理)                       │
│              _run_agent_loop() 方法                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  while iteration < max_iterations:                   │   │
│  │    response = llm.chat(messages, tools)              │   │
│  │                                                      │   │
│  │    if has_tool_calls:                                │   │
│  │      execute_tools()                                 │   │
│  │      continue  ← 继续循环                            │   │
│  │    else:                                             │   │
│  │      break  ← 得到最终答案                          │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**设计理由**：
- **外层非阻塞**：每个消息在独立 asyncio Task 中处理，`/stop` 可以取消特定会话的任务而不影响其他会话
- **内层同步阻塞**：ReAct 循环在同一个 Task 内顺序执行，确保推理的连贯性
- **资源隔离**：`_active_tasks` 按 `session_key` 分组管理，便于精确控制

### 2. 状态机设计

```
                    ┌──────────────┐
                    │    Start     │
                    └──────┬───────┘
                           │ run()
                           ▼
                    ┌──────────────┐
         ┌─────────│    Running   │◄─────────────────┐
         │         └──────┬───────┘                  │
         │                │                          │
         │    ┌───────────┼───────────┐              │
         │    ▼           ▼           ▼              │
         │ ┌─────┐   ┌──────┐   ┌────────┐         │
         │ │/stop│   │/restart│  │ message│         │
         │ └──┬──┘   └───┬───┘   └───┬────┘         │
         │    │          │           │               │
         │    ▼          ▼           ▼               │
         │ ┌─────────────────────────────────┐     │
         └─│      Task Created (async)       │─────┘
           └─────────────────────────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  _dispatch()    │
                  └───────┬─────────┘
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
        ┌─────────┐ ┌─────────┐ ┌─────────┐
        │  Error  │ │ Cancel  │ │ Success │
        └────┬────┘ └────┬────┘ └────┬────┘
             │           │           │
             ▼           ▼           ▼
        ┌────────────────────────────────┐
        │     publish_outbound()         │
        └────────────────────────────────┘
```

**关键状态转换**：
- **Running → Task Created**：每条消息触发独立任务，主循环立即返回继续监听
- **Task 内部**：可能经历 `ReAct 循环 → 工具执行 → 继续循环 → 最终结果`
- **Cancel**：`/stop` 命令取消特定会话的所有任务，其他会话不受影响
- **Error**：异常被捕获并包装为错误消息返回

### 3. 组件依赖图

```
┌─────────────────────────────────────────────────────────────────┐
│                         AgentLoop                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Core Components                                        │    │
│  │  ├─ ContextBuilder (context)    ← 组装 prompt          │    │
│  │  ├─ SessionManager (sessions)   ← 对话历史            │    │
│  │  ├─ ToolRegistry (tools)          ← 工具注册表          │    │
│  │  ├─ SubagentManager (subagents) ← 子代理              │    │
│  │  └─ MemoryConsolidator ← 记忆整理                      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  External Dependencies                                  │    │
│  │  ├─ MessageBus (bus)            ← 消息总线              │    │
│  │  ├─ LLMProvider (provider)      ← LLM 调用              │    │
│  │  └─ MCP Servers (_mcp_servers)  ← 外部工具服务         │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

**依赖设计原则**：
- **依赖注入**：所有外部依赖通过构造函数传入，便于测试和替换
- **接口隔离**：依赖 `MessageBus`/`LLMProvider` 等抽象接口，而非具体实现
- **生命周期管理**：MCP 连接使用 `AsyncExitStack` 确保优雅关闭

---

## 关键设计决策

### 1. ReAct 循环实现

```python
async def _run_agent_loop(self, initial_messages, ...):
    messages = initial_messages
    iteration = 0

    while iteration < self.max_iterations:
        iteration += 1

        # 1. 调用 LLM
        response = await self.provider.chat_with_retry(messages, tools)

        if response.has_tool_calls:
            # 2. 执行工具
            for tool_call in response.tool_calls:
                result = await self.tools.execute(tool_call.name, tool_call.arguments)
                messages = self.context.add_tool_result(messages, ...)
            # 3. 继续循环（不 break）
            continue
        else:
            # 4. 得到最终答案，结束循环
            final_content = response.content
            break
```

**设计特点**：
- **最大迭代限制**：`max_iterations` 防止无限循环（默认 40 轮）
- **工具结果截断**：`_TOOL_RESULT_MAX_CHARS` 防止工具输出过长撑爆上下文
- **递进式消息构建**：每轮循环追加 `assistant` + `tool` 消息，保持完整轨迹

### 2. 任务取消机制

```python
async def _handle_stop(self, msg: InboundMessage) -> None:
    # 1. 从 _active_tasks 取出该会话的所有任务
    tasks = self._active_tasks.pop(msg.session_key, [])

    # 2. 取消未完成的任务
    cancelled = sum(1 for t in tasks if not t.done() and t.cancel())

    # 3. 等待任务实际结束（捕获 CancelledError）
    for t in tasks:
        try:
            await t
        except (asyncio.CancelledError, Exception):
            pass

    # 4. 同时取消子代理
    sub_cancelled = await self.subagents.cancel_by_session(msg.session_key)
```

**设计亮点**：
- **精确控制**：按 `session_key` 分组，不影响其他会话
- **优雅关闭**：先 `cancel()` 再 `await`，让任务有机会清理资源
- **级联取消**：子代理也被一并取消，防止孤儿任务

### 3. 记忆整合（Memory Consolidation）

```python
class MemoryConsolidator:
    """当会话 token 数超过阈值时，自动将历史消息总结为记忆。"""

    async def maybe_consolidate_by_tokens(self, session: Session) -> None:
        total = self._estimate_tokens(session)
        if total < self.threshold:
            return  # 未达阈值，无需处理

        # 构建总结 prompt
        messages = self._build_summary_messages(session)

        # 调用 LLM 生成总结
        summary = await self.provider.chat_with_retry(messages)

        # 归档：将总结写入 MEMORY.md，清空历史消息
        await self._archive(session, summary)
```

**设计动机**：
- **上下文窗口有限**：LLM 有 token 上限，长对话会超出限制
- **信息密度**：早期消息细节可能不重要，保留关键信息即可
- **性能**：减少每次请求的消息数量，降低延迟和成本

**触发策略**：
- 基于 token 估算（而非消息数），更准确反映实际消耗
- 在每次消息处理前检查，及时触发

### 4. 多媒体处理流程

```python
async def _process_message(self, msg: InboundMessage) -> OutboundMessage:
    # 1. 收集媒体路径（从消息附件）
    media_paths: list[str] = list(msg.media) if msg.media else []

    # 2. 构建初始消息（包含媒体）
    initial_messages = self.context.build_messages(
        media=media_paths,
        ...
    )

    # 3. 运行 ReAct 循环
    final_content, _, all_msgs, extracted_media = await self._run_agent_loop(
        initial_messages, media=media_paths
    )

    # 4. 如果工具返回了新媒体（如医学图像），重建消息
    if extracted_media:
        all_msgs = self._rebuild_messages_with_media(all_msgs, extracted_media)
```

**流程特点**：
- **多源媒体**：支持消息附件 + 工具生成（如医学影像）
- **动态重建**：工具返回的媒体需要重新构建消息列表，确保 LLM 能"看到"图片
- **格式转换**：本地文件路径转换为 `file://` URL 或 base64 data URI

---

## 扩展性设计

### 添加新工具

```python
def _register_default_tools(self) -> None:
    # 现有工具...
    self.tools.register(MyNewTool(config=self.config))
```

工具类需实现：
- `name` 属性：工具标识
- `description` 属性：函数描述（OpenAI 格式）
- `execute(**kwargs)` 方法：执行逻辑

### 自定义消息处理流程

```python
async def _dispatch(self, msg: InboundMessage) -> None:
    # 在调用 _process_message 前插入自定义逻辑
    if self._should_handle_special(msg):
        await self._handle_special(msg)
        return

    async with self._processing_lock:
        response = await self._process_message(msg)
```

### 集成新的 LLM Provider

只需实现 `LLMProvider` 接口：

```python
class MyProvider(LLMProvider):
    async def chat_with_retry(self, messages, tools, model) -> LLMResponse:
        # 调用 LLM API
        pass

    def get_default_model(self) -> str:
        return "my-model"
```

---

## 性能与可靠性

### 并发控制

| 机制 | 作用 | 实现 |
|------|------|------|
| `_processing_lock` | 确保同一会话内消息顺序处理 | `asyncio.Lock()` |
| `_active_tasks` | 追踪每个会话的活跃任务 | `dict[session_key, list[Task]]` |
| `max_iterations` | 防止 ReAct 无限循环 | 默认 40 轮 |

### 容错设计

```python
async def _dispatch(self, msg: InboundMessage) -> None:
    try:
        response = await self._process_message(msg)
    except asyncio.CancelledError:
        raise  # 重新抛出，让上层处理取消
    except Exception:
        logger.exception("Error processing message...")
        await self.bus.publish_outbound(error_message)
```

- **CancelledError 透传**：确保 `/stop` 能正确取消任务
- **其他异常捕获**：防止单个消息处理失败导致整个循环崩溃

### 资源限制

```python
_TOOL_RESULT_MAX_CHARS = 16_000  # 工具结果截断阈值
context_window_tokens = 65_536     # 上下文窗口上限
```

---

## 总结

`AgentLoop` 的设计体现了以下核心思想：

1. **双循环分离**：外层非阻塞消息调度 + 内层同步 ReAct 推理，兼顾并发性能和推理连贯性

2. **精确状态管理**：按 `session_key` 隔离状态，支持多会话并发，独立控制生命周期

3. **渐进式容错**：从工具级别到消息级别再到循环级别的多层异常处理，确保单点故障不影响整体

4. **资源边界控制**：通过 token 估算、迭代限制、结果截断等手段，防止资源耗尽

5. **可观测性**：详细的日志记录、进度回调、工具使用追踪，便于调试和监控