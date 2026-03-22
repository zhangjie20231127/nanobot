# Nanobot 工具系统架构详解

本文档详细介绍 nanobot 项目中工具（Tool）的定义、注册、调用和管理机制。

---

## 1. 工具系统概览

### 1.1 工具列表

目前 nanobot 共有 **10 个内置工具**:

| 工具名称 | 文件路径 | 功能描述 |
|---------|---------|---------|
| `Bash` | `tools/shell.py` | 执行 bash 命令 |
| `Write` | `tools/filesystem.py` | 写入文件内容 |
| `Edit` | `tools/filesystem.py` | 编辑文件内容 |
| `Glob` | `tools/filesystem.py` | 文件模式匹配 |
| `Grep` | `tools/filesystem.py` | 文件内容搜索 |
| `Read` | `tools/filesystem.py` | 读取文件内容 |
| `NotebookEdit` | `tools/filesystem.py` | 编辑 Jupyter Notebook |
| `WebSearch` | `tools/web.py` | 网页搜索 |
| `WebFetch` | `tools/web.py` | 网页内容获取 |
| `Message` | `tools/message.py` | 发送消息 |
| `CronCreate` | `tools/cron.py` | 创建定时任务 |
| `CronDelete` | `tools/cron.py` | 删除定时任务 |
| `CronList` | `tools/cron.py` | 列出定时任务 |
| `Agent` | `tools/spawn.py` | 生成子代理 |
| `MCP` | `tools/mcp.py` | MCP 工具调用 |

### 1.2 文件结构

```
nanobot/agent/tools/
├── __init__.py          # 工具导出
├── base.py              # 工具基类定义
├── registry.py          # 工具注册中心
├── shell.py             # Bash 工具
├── filesystem.py        # 文件操作工具集
├── web.py               # Web 相关工具
├── message.py           # 消息发送工具
├── cron.py              # 定时任务工具
├── spawn.py             # 子代理工具
└── mcp.py               # MCP 工具
```

---

## 2. 工具定义详解（以 Bash 为例）

### 2.1 必须的结构

每个工具必须继承自 `Tool` 基类，并满足以下结构要求：

#### 2.1.1 基类定义 (`base.py`)

```python
from dataclasses import dataclass, field
from typing import Any, Optional

@dataclass
class Tool:
    """工具基类

    所有工具必须继承此类，并定义以下字段：
    - name: 工具名称（大写驼峰命名）
    - description: 工具功能描述
    - parameters: JSON Schema 格式的参数定义
    - required: 必需参数列表
    """
    name: str
    description: str
    parameters: dict = field(default_factory=dict)
    required: list = field(default_factory=list)

    def __post_init__(self):
        """验证工具定义完整性"""
        if not self.name:
            raise ValueError("Tool name is required")
        if not self.description:
            raise ValueError("Tool description is required")
        if not isinstance(self.parameters, dict):
            raise ValueError("Tool parameters must be a dict")
```

#### 2.1.2 Bash 工具定义 (`shell.py`)

```python
from dataclasses import dataclass
from .base import Tool

@dataclass
class BashTool(Tool):
    """Bash 工具 - 执行 shell 命令"""

    name: str = "Bash"
    description: str = """Execute a given bash command and returns its output.

The shell environment is initialized from the user's profile (bash or zsh).

IMPORTANT: Avoid using this tool to run `find`, `grep`, `cat`, `head`, `tail`, `sed`, `awk`, or `echo` commands, unless explicitly instructed or after you have verified that a dedicated tool cannot accomplish your task. Instead, use the appropriate dedicated tool as this will provide a much better experience for the user.
"""
    parameters: dict = None
    required: list = None

    def __post_init__(self):
        # 参数 JSON Schema 定义
        self.parameters = {
            "type": "object",
            "properties": {
                "command": {
                    "description": "The command to execute",
                    "type": "string"
                },
                "description": {
                    "description": "Clear, concise description of what this command does in active voice...",
                    "type": "string"
                },
                "timeout": {
                    "description": "Optional timeout in milliseconds (max 600000)",
                    "type": "number"
                },
                "run_in_background": {
                    "description": "Set to true to run this command in the background...",
                    "type": "boolean"
                },
                "dangerouslyDisableSandbox": {
                    "description": "Set this to true to dangerously override sandbox mode...",
                    "type": "boolean"
                }
            },
            "required": ["command"],
            "additionalProperties": False
        }
        self.required = ["command"]
```

### 2.2 关键组成部分说明

| 组成部分 | 类型 | 说明 |
|---------|-----|------|
| `name` | `str` | 工具名称，必须大写驼峰命名（如 `Bash`, `WebSearch`） |
| `description` | `str` | 详细描述工具功能，LLM 使用此描述决定何时调用该工具 |
| `parameters` | `dict` | 符合 JSON Schema 的参数定义，描述输入参数结构 |
| `required` | `list` | 必需参数名列表 |

---

## 3. 工具注册机制

### 3.1 注册中心 (`registry.py`)

```python
from typing import Dict, Type, Optional
import logging

from .base import Tool

logger = logging.getLogger(__name__)

class ToolRegistry:
    """工具注册中心 - 管理所有可用工具"""

    _tools: Dict[str, Tool] = {}

    @classmethod
    def register(cls, tool_instance: Tool) -> None:
        """注册工具实例"""
        name = tool_instance.name
        if name in cls._tools:
            logger.warning(f"Tool '{name}' is already registered, overwriting")
        cls._tools[name] = tool_instance
        logger.debug(f"Registered tool: {name}")

    @classmethod
    def get(cls, name: str) -> Optional[Tool]:
        """获取工具实例"""
        return cls._tools.get(name)

    @classmethod
    def get_all(cls) -> Dict[str, Tool]:
        """获取所有注册的工具"""
        return cls._tools.copy()

    @classmethod
    def clear(cls) -> None:
        """清空注册表（主要用于测试）"""
        cls._tools.clear()


def register_tool(tool_class: Type[Tool]) -> Type[Tool]:
    """装饰器：自动实例化并注册工具类

    用法:
        @register_tool
        @dataclass
        class MyTool(Tool):
            name: str = "MyTool"
            ...
    """
    try:
        instance = tool_class()
        ToolRegistry.register(instance)
    except Exception as e:
        logger.error(f"Failed to register tool {tool_class.__name__}: {e}")
    return tool_class
```

### 3.2 Bash 工具的注册 (`shell.py`)

```python
from .registry import register_tool
from .base import Tool

@register_tool
@dataclass
class BashTool(Tool):
    """Bash 工具定义..."""
    name: str = "Bash"
    description: str = "..."
    ...
```

### 3.3 注册流程图

```
┌─────────────────┐
│ @register_tool  │  装饰器装饰工具类
│   (装饰器)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ tool_class()    │  实例化工具类
│   (实例化)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ ToolRegistry    │  注册到全局注册中心
│ .register()     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ _tools[name] =  │  存储到内存字典
│   instance      │
└─────────────────┘
```

---

## 4. 工具调用机制

### 4.1 调用流程

```
┌─────────────────────────────────────────────────────────────┐
│                        Agent Loop                           │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐ │
│  │  Build      │───▶│  Call LLM   │───▶│  Parse Response │ │
│  │  Context    │    │             │    │  (Tool Calls)   │ │
│  └─────────────┘    └─────────────┘    └────────┬────────┘ │
│                                                  │          │
└──────────────────────────────────────────────────┼──────────┘
                                                   │
                                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Tool Dispatcher                             │
│  ┌─────────────────┐    ┌─────────────┐    ┌─────────────────┐│
│  │ Lookup tool in  │───▶│  Validate   │───▶│  Execute tool   ││
│  │ ToolRegistry    │    │  parameters │    │  function       ││
│  └─────────────────┘    └─────────────┘    └────────┬────────┘│
└─────────────────────────────────────────────────────┼─────────┘
                                                      │
                                                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Result Handling                            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │  Format     │───▶│  Add to     │───▶│  Return to Agent    │ │
│  │  result     │    │  context    │    │  Loop               │ │
│  └─────────────┘    └─────────────┘    └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 调用核心代码 (`agent/loop.py`)

```python
class AgentLoop:
    """Agent 主循环"""

    async def _execute_tool_call(
        self,
        tool_call: dict,
        context: Context
    ) -> ToolResult:
        """执行单个工具调用"""

        # 1. 获取工具名称和参数
        tool_name = tool_call.get("name")
        parameters = tool_call.get("parameters", {})

        # 2. 从注册中心查找工具
        from .tools.registry import ToolRegistry
        tool = ToolRegistry.get(tool_name)

        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' not found"
            )

        # 3. 参数验证（根据 JSON Schema）
        try:
            import jsonschema
            jsonschema.validate(
                instance=parameters,
                schema=tool.parameters
            )
        except jsonschema.ValidationError as e:
            return ToolResult(
                success=False,
                error=f"Parameter validation failed: {e.message}"
            )

        # 4. 执行工具
        try:
            result = await self._run_tool(tool, parameters, context)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Tool execution failed: {str(e)}"
            )

    async def _run_tool(
        self,
        tool: Tool,
        parameters: dict,
        context: Context
    ) -> Any:
        """根据工具类型分发到具体执行器"""

        tool_name = tool.name

        if tool_name == "Bash":
            return await self._execute_bash(parameters, context)
        elif tool_name == "Read":
            return await self._execute_read(parameters, context)
        elif tool_name == "Write":
            return await self._execute_write(parameters, context)
        # ... 其他工具的分发
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
```

---

## 5. Bash 工具完整实现解析

### 5.1 定义 (`shell.py`)

```python
"""Shell 执行工具"""

import logging
from dataclasses import dataclass, field

from .base import Tool
from .registry import register_tool

logger = logging.getLogger(__name__)


@register_tool  # ← 装饰器：自动注册到 ToolRegistry
@dataclass      # ← dataclass：自动生成 __init__ 等方法
class BashTool(Tool):
    """Bash 工具 - 执行 shell 命令

    功能：执行 bash 命令并返回输出结果。
    shell 环境从用户的 profile（bash 或 zsh）初始化。

    设计原则：
    1. 尽量避免使用此工具运行 find/grep/cat 等命令
    2. 优先使用专用的工具（如 Glob/Grep/Read 等）
    3. 这些专用工具提供更好的用户体验
    """

    # === 工具元数据 ===
    name: str = "Bash"  # ← 工具唯一标识符（必须大写驼峰）

    description: str = """\
Execute a given bash command and returns its output.

The shell environment is initialized from the user's profile (bash or zsh).

IMPORTANT: Avoid using this tool to run `find`, `grep`, `cat`, `head`, `tail`, `sed`, `awk`, or `echo` commands, unless explicitly instructed or after you have verified that a dedicated tool cannot accomplish your task. Instead, use the appropriate dedicated tool as this will provide a much better experience for the user:

 - File search: Use Glob (NOT find or ls)
 - Content search: Use Grep (NOT grep or rg)
 - Read files: Use Read (NOT cat/head/tail)
 - Edit files: Use Edit (NOT sed/awk)
 - Write files: Use Write (NOT echo >/cat <<EOF)
 - Communication: Output text directly (NOT echo/printf)
While the Bash tool can do similar things, it's better to use the built-in tools as they provide a better experience for the user and make it easier to review tool calls and give permission.

Usage notes:
- If your command will create new directories or files, first use this tool to run `ls` to verify the parent directory exists and is the correct location.
- Always quote file paths that contain spaces with double quotes in your command (e.g., cd "path with spaces/file.txt")
- Try to maintain your current working directory throughout the session by using absolute paths and avoiding usage of `cd`. You may use `cd` if the User explicitly requests it.
- You may specify an optional timeout in milliseconds (up to 600000ms / 10 minutes). By default, your command will timeout after 120000ms (2 minutes).
- You can use the `run_in_background` parameter to run the command in the background. Only use this if you don't need the result immediately and are OK being notified when it completes later. You do not need to check the output right away - you'll be notified when it finishes. You do not need to use '&' at the end of the command when using this parameter.
- **Foreground vs background**: Use foreground (default) when you need the command's results before you can proceed — e.g., research commands whose findings inform your next steps. Use background when you have genuinely independent work to do in parallel.
"""  # ← 详细描述帮助 LLM 理解何时使用此工具

    # === 参数定义（JSON Schema 格式）===
    parameters: dict = None
    required: list = None

    def __post_init__(self):
        """初始化参数定义

        在 dataclass 实例化后调用，设置 JSON Schema 参数定义。
        """
        self.parameters = {
            "type": "object",  # ← 参数整体是一个对象
            "properties": {      # ← 定义各个参数
                "command": {
                    "description": "The command to execute",
                    "type": "string"
                },
                "description": {
                    "description": "Clear, concise description of what this command does in active voice...",
                    "type": "string"
                },
                "timeout": {
                    "description": "Optional timeout in milliseconds (max 600000)",
                    "type": "number"
                },
                "run_in_background": {
                    "description": "Set to true to run this command in the background...",
                    "type": "boolean"
                },
                "dangerouslyDisableSandbox": {
                    "description": "Set this to true to dangerously override sandbox mode...",
                    "type": "boolean"
                }
            },
            "required": ["command"],  # ← 必需参数
            "additionalProperties": False  # ← 不允许额外参数
        }
        self.required = ["command"]
```

### 5.2 注册流程

```python
# 1. 装饰器装饰
@register_tool    # ← 第二步：实例化后自动注册
@dataclass        # ← 第一步：生成 __init__ 等方法
class BashTool(Tool):
    ...

# 2. 装饰器内部实现 (@register_tool)
def register_tool(tool_class: Type[Tool]) -> Type[Tool]:
    try:
        # 实例化工具类
        instance = tool_class()
        # 注册到全局注册中心
        ToolRegistry.register(instance)
    except Exception as e:
        logger.error(f"Failed to register tool {tool_class.__name__}: {e}")
    return tool_class

# 3. 注册到内存字典
class ToolRegistry:
    _tools: Dict[str, Tool] = {}

    @classmethod
    def register(cls, tool_instance: Tool) -> None:
        name = tool_instance.name
        if name in cls._tools:
            logger.warning(f"Tool '{name}' is already registered, overwriting")
        cls._tools[name] = tool_instance  # ← 存储到内存
```

### 5.3 调用执行流程

```python
# 1. LLM 返回工具调用请求
{
    "name": "Bash",
    "parameters": {
        "command": "ls -la",
        "description": "List files in current directory"
    }
}

# 2. Agent Loop 调用工具
tool_result = await self._execute_tool_call(tool_call, context)

# 3. 查找工具
from .tools.registry import ToolRegistry
tool = ToolRegistry.get("Bash")  # ← 从注册中心获取

# 4. 参数验证
import jsonschema
jsonschema.validate(
    instance=parameters,
    schema=tool.parameters
)

# 5. 执行工具（工具特定的执行逻辑）
async def _execute_bash(self, parameters: dict, context: Context) -> dict:
    import asyncio
    import subprocess

    command = parameters["command"]
    timeout = parameters.get("timeout", 120000)  # 默认 2 分钟

    # 执行命令
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=context.working_directory  # 使用上下文中保存的工作目录
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout / 1000  # 转换为秒
        )
    except asyncio.TimeoutError:
        process.kill()
        raise TimeoutError(f"Command timed out after {timeout}ms")

    # 返回结果
    return {
        "exit_code": process.returncode,
        "stdout": stdout.decode("utf-8", errors="replace"),
        "stderr": stderr.decode("utf-8", errors="replace")
    }
```

---

## 6. 上下文管理

### 6.1 上下文数据结构

```python
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

@dataclass
class Message:
    """对话消息"""
    role: str  # "user", "assistant", "system", "tool"
    content: Any  # 消息内容（字符串或结构化数据）
    timestamp: datetime = field(default_factory=datetime.now)
    tool_calls: Optional[List[dict]] = None  # 工具调用请求
    tool_results: Optional[List[dict]] = None  # 工具执行结果

@dataclass
class Context:
    """对话上下文 - 在会话期间持续存在"""

    # === 会话标识 ===
    session_id: str
    user_id: Optional[str] = None

    # === 对话历史 ===
    messages: List[Message] = field(default_factory=list)
    max_history: int = 100  # 最大保留消息数

    # === 工作目录状态 ===
    working_directory: str = field(default_factory=lambda: os.getcwd())

    # === 工具执行上下文 ===
    tool_executions: Dict[str, Any] = field(default_factory=dict)
    background_tasks: Dict[str, Any] = field(default_factory=dict)

    # === 用户偏好/状态 ===
    preferences: Dict[str, Any] = field(default_factory=dict)
    last_active: datetime = field(default_factory=datetime.now)

    def add_message(self, role: str, content: Any, **kwargs):
        """添加消息到历史记录"""
        message = Message(role=role, content=content, **kwargs)
        self.messages.append(message)

        # 裁剪历史记录
        if len(self.messages) > self.max_history:
            # 保留系统消息和最近的消息
            system_msgs = [m for m in self.messages if m.role == "system"]
            other_msgs = [m for m in self.messages if m.role != "system"]
            keep_count = self.max_history - len(system_msgs)
            self.messages = system_msgs + other_msgs[-keep_count:]

        self.last_active = datetime.now()

    def get_recent_messages(self, n: int = 10) -> List[Message]:
        """获取最近的 n 条消息"""
        return self.messages[-n:]

    def update_working_directory(self, path: str):
        """更新工作目录"""
        self.working_directory = os.path.abspath(path)

    def to_dict(self) -> dict:
        """序列化为字典（用于持久化）"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat(),
                    "tool_calls": m.tool_calls,
                    "tool_results": m.tool_results
                }
                for m in self.messages
            ],
            "working_directory": self.working_directory,
            "preferences": self.preferences,
            "last_active": self.last_active.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Context":
        """从字典反序列化"""
        ctx = cls(
            session_id=data["session_id"],
            user_id=data.get("user_id"),
            working_directory=data.get("working_directory", os.getcwd()),
            preferences=data.get("preferences", {})
        )

        # 恢复消息
        for m_data in data.get("messages", []):
            ctx.add_message(
                role=m_data["role"],
                content=m_data["content"],
                timestamp=datetime.fromisoformat(m_data["timestamp"]),
                tool_calls=m_data.get("tool_calls"),
                tool_results=m_data.get("tool_results")
            )

        if "last_active" in data:
            ctx.last_active = datetime.fromisoformat(data["last_active"])

        return ctx
```

### 6.2 上下文在工具调用中的传递

```python
async def execute_tool_with_context(
    tool_name: str,
    parameters: dict,
    context: Context
) -> ToolResult:
    """在上下文中执行工具"""

    # 1. 获取工具
    tool = ToolRegistry.get(tool_name)

    # 2. 构建工具执行上下文
    execution_ctx = {
        # 工作目录：工具在此目录下执行
        "working_directory": context.working_directory,

        # 用户偏好：如语言、时区等
        "preferences": context.preferences,

        # 会话信息
        "session_id": context.session_id,
        "user_id": context.user_id,

        # 工具特定上下文
        "tool_executions": context.tool_executions,
        "background_tasks": context.background_tasks
    }

    # 3. 执行前：记录到上下文
    execution_id = f"{tool_name}_{datetime.now().timestamp()}"
    context.tool_executions[execution_id] = {
        "tool": tool_name,
        "parameters": parameters,
        "status": "running",
        "started_at": datetime.now()
    }

    try:
        # 4. 实际执行（以 Bash 为例）
        if tool_name == "Bash":
            result = await _execute_bash_with_context(
                parameters,
                execution_ctx
            )
        # ... 其他工具

        # 5. 执行成功：更新上下文
        context.tool_executions[execution_id].update({
            "status": "completed",
            "result": result,
            "completed_at": datetime.now()
        })

        # 6. 更新工作目录（如果命令改变了目录）
        if tool_name == "Bash" and "cd " in parameters.get("command", ""):
            new_dir = await _get_current_directory(execution_ctx)
            context.update_working_directory(new_dir)

        return ToolResult(success=True, data=result)

    except Exception as e:
        # 执行失败：更新上下文
        context.tool_executions[execution_id].update({
            "status": "failed",
            "error": str(e),
            "failed_at": datetime.now()
        })
        return ToolResult(success=False, error=str(e))


async def _execute_bash_with_context(
    parameters: dict,
    execution_ctx: dict
) -> dict:
    """在指定上下文中执行 bash 命令"""
    import asyncio
    import subprocess

    command = parameters["command"]
    timeout = parameters.get("timeout", 120000)

    # 获取工作目录（来自上下文）
    cwd = execution_ctx.get("working_directory", os.getcwd())

    # 执行命令
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd  # ← 使用上下文中的工作目录
    )

    stdout, stderr = await asyncio.wait_for(
        process.communicate(),
        timeout=timeout / 1000
    )

    return {
        "exit_code": process.returncode,
        "stdout": stdout.decode("utf-8", errors="replace"),
        "stderr": stderr.decode("utf-8", errors="replace")
    }
```

---

## 7. 结果返回与上下文管理

### 7.1 结果数据结构

```python
from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool           # 是否成功
    data: Any = None        # 成功时的返回数据
    error: Optional[str] = None  # 失败时的错误信息

    def to_dict(self) -> dict:
        """转换为字典（用于添加到上下文）"""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error
        }
```

### 7.2 结果添加到上下文

```python
async def process_tool_result(
    self,
    tool_call: dict,
    result: ToolResult,
    context: Context
):
    """处理工具执行结果并更新上下文"""

    # 1. 构建结果消息
    result_message = {
        "role": "tool",
        "tool_call_id": tool_call.get("id"),
        "name": tool_call.get("name"),
        "content": result.to_dict()
    }

    # 2. 添加到上下文的消息历史
    context.add_message(
        role="tool",
        content=result_message,
        tool_results=[result.to_dict()]
    )

    # 3. 如果成功执行了目录切换命令，更新工作目录
    if (tool_call.get("name") == "Bash" and
        result.success and
        "cd " in tool_call.get("parameters", {}).get("command", "")):

        new_dir = await self._resolve_directory_from_cd(
            tool_call["parameters"]["command"],
            context.working_directory
        )
        context.update_working_directory(new_dir)
```

### 7.3 上下文序列化与持久化

```python
class ContextManager:
    """上下文管理器 - 负责保存和恢复会话上下文"""

    def __init__(self, storage_path: str = "~/.nanobot/sessions"):
        self.storage_path = os.path.expanduser(storage_path)
        os.makedirs(self.storage_path, exist_ok=True)

    def save_context(self, context: Context) -> str:
        """保存上下文到磁盘"""
        session_file = os.path.join(
            self.storage_path,
            f"{context.session_id}.json"
        )

        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(context.to_dict(), f, indent=2)

        return session_file

    def load_context(self, session_id: str) -> Optional[Context]:
        """从磁盘加载上下文"""
        session_file = os.path.join(self.storage_path, f"{session_id}.json")

        if not os.path.exists(session_file):
            return None

        with open(session_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return Context.from_dict(data)

    def list_sessions(self, user_id: Optional[str] = None) -> List[str]:
        """列出所有会话"""
        sessions = []
        for filename in os.listdir(self.storage_path):
            if filename.endswith('.json'):
                session_id = filename[:-5]
                if user_id is None:
                    sessions.append(session_id)
                else:
                    # 加载并检查 user_id
                    ctx = self.load_context(session_id)
                    if ctx and ctx.user_id == user_id:
                        sessions.append(session_id)
        return sessions
```

---

## 8. 工具定义的最佳实践

### 8.1 命名规范

| 项目 | 规范 | 示例 |
|-----|------|-----|
| 工具类名 | `XXXTool` | `BashTool`, `WebSearchTool` |
| 工具名称 | 大写驼峰 | `Bash`, `WebSearch` |
| 参数名 | snake_case | `working_directory`, `file_path` |
| 描述 | 清晰、具体 | "Execute bash command..." |

### 8.2 参数设计原则

```python
# 好的示例：参数有明确的描述和类型
{
    "properties": {
        "file_path": {
            "description": "The absolute path to the file to read",
            "type": "string"
        },
        "limit": {
            "description": "Maximum number of lines to read",
            "type": "integer",
            "minimum": 1,
            "default": 1000
        }
    },
    "required": ["file_path"]
}

# 不好的示例：参数描述模糊，类型不明确
{
    "properties": {
        "path": {"type": "string"},  # 缺少描述
        "count": {"type": "number"}  # 不明确的描述
    }
}
```

### 8.3 错误处理规范

```python
async def execute_tool(...) -> ToolResult:
    try:
        # 1. 参数验证
        if not validate_params(parameters):
            return ToolResult(
                success=False,
                error="Invalid parameters: missing required field 'xxx'"
            )

        # 2. 权限检查
        if not has_permission(tool_name, context):
            return ToolResult(
                success=False,
                error=f"Permission denied: {tool_name}"
            )

        # 3. 执行工具
        result = await do_execute(parameters, context)

        # 4. 返回成功结果
        return ToolResult(success=True, data=result)

    except TimeoutError as e:
        return ToolResult(
            success=False,
            error=f"Timeout: {str(e)}"
        )
    except Exception as e:
        # 未知错误
        return ToolResult(
            success=False,
            error=f"Unexpected error: {str(e)}"
        )
```

---

## 9. 总结

Nanobot 的工具系统设计简洁而强大：

1. **定义简单**：使用 `@dataclass` + 继承 `Tool` 基类即可定义新工具
2. **自动注册**：`@register_tool` 装饰器实现自动注册
3. **类型安全**：使用 JSON Schema 定义参数，支持自动验证
4. **上下文感知**：通过 `Context` 对象管理会话状态
5. **可扩展性强**：支持动态注册和 MCP 外部工具

这种设计使得添加新工具变得非常简单，同时保持了类型安全和良好的可维护性。
