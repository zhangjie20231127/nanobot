# 如何添加新的 Tool - 完整指南

本文档详细介绍如何在 nanobot 项目中添加一个新的 Tool。

## 目录

1. [Tool 系统架构回顾](#1-tool-系统架构回顾)
2. [创建新 Tool 的步骤](#2-创建新-tool-的步骤)
3. [完整示例：创建一个 HttpRequestTool](#3-完整示例创建一个-httprequesttool)
4. [在 Agent Loop 中注册 Tool](#4-在-agent-loop-中注册-tool)
5. [测试你的 Tool](#5-测试你的-tool)
6. [最佳实践和注意事项](#6-最佳实践和注意事项)

---

## 1. Tool 系统架构回顾

在开始之前，让我们回顾一下 Tool 系统的核心组件：

```
┌─────────────────────────────────────────────────────────────┐
│                        Tool 系统架构                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   Tool      │◄───│  Tool      │◄───│  Tool       │     │
│  │   (基类)     │    │  Registry  │    │  (具体实现)  │     │
│  │   base.py   │    │  registry  │    │  shell.py   │     │
│  └──────┬──────┘    │  .py       │    └──────┬──────┘     │
│         ▲           └──────┬──────┘           ▲            │
│         │                │                    │            │
│         └────────────────┘                    │            │
│                                               │            │
│                              ┌────────────────┘            │
│                              │                             │
│                         ┌────┴────┐                        │
│                         │ 其他    │                        │
│                         │ web.py  │                        │
│                         │ filesystem.py                   │
│                         └─────────┘                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 核心文件说明

| 文件路径 | 作用 |
|---------|------|
| `tools/base.py` | Tool 抽象基类，定义所有 Tool 必须实现的接口 |
| `tools/registry.py` | Tool 注册中心，管理所有 Tool 的注册和查询 |
| `tools/shell.py` | ExecTool 实现（Bash 命令执行） |
| `tools/filesystem.py` | 文件系统工具（Read、Write、Edit 等） |
| `tools/web.py` | Web 工具（WebSearch、WebFetch） |

---

## 2. 创建新 Tool 的步骤

添加一个新 Tool 需要完成以下步骤：

### 步骤清单

1. **创建 Tool 类文件** 或 **添加到现有文件**
   - 如果是一个全新的功能类别，创建新的 `.py` 文件
   - 如果是同类功能，添加到现有文件（如添加到 `filesystem.py`）

2. **继承 `Tool` 基类**
   - 实现 `name` 属性（Tool 唯一标识符）
   - 实现 `description` 属性（Tool 功能描述）
   - 实现 `parameters` 属性（JSON Schema 参数定义）
   - 实现 `execute()` 方法（Tool 执行逻辑）

3. **在 `AgentLoop` 中注册 Tool**
   - 编辑 `nanobot/agent/loop.py`
   - 在 `_register_default_tools()` 方法中实例化并注册 Tool

4. **添加测试**（可选但推荐）
   - 在 `tests/` 目录下添加单元测试

---

## 3. 完整示例：创建一个 HttpRequestTool

让我们通过创建一个 **HTTP 请求工具** 来演示完整过程。这个工具可以让 Agent 发送 HTTP GET/POST 请求。

### 3.1 创建新文件 `http.py`

在 `nanobot/agent/tools/` 目录下创建新文件 `http.py`：

```python
"""HTTP request tool for making web API calls."""

from __future__ import annotations

import json
from typing import Any

import httpx

from nanobot.agent.tools.base import Tool


class HttpRequestTool(Tool):
    """
    发送 HTTP 请求（GET/POST/PUT/DELETE 等）

    用于调用 Web API、获取 JSON 数据、发送表单等。
    支持自定义请求头、请求体、超时设置。

    Examples:
        GET 请求:
        {
            "url": "https://api.example.com/users",
            "method": "GET",
            "headers": {"Authorization": "Bearer token123"}
        }

        POST JSON:
        {
            "url": "https://api.example.com/users",
            "method": "POST",
            "json": {"name": "John", "email": "john@example.com"}
        }
    """

    def __init__(self, timeout: int = 30, max_retries: int = 2):
        self.timeout = timeout
        self.max_retries = max_retries

    @property
    def name(self) -> str:
        """Tool 名称 - 用于 LLM 识别和调用"""
        return "http_request"

    @property
    def description(self) -> str:
        """
        Tool 描述 - 帮助 LLM 理解何时使用此工具

        描述应该:
        1. 清晰说明工具的功能
        2. 说明适用场景
        3. 给出使用示例（可选）
        """
        return (
            "Send HTTP requests (GET, POST, PUT, DELETE, etc.) to web APIs. "
            "Useful for fetching data from REST APIs, submitting forms, or "
            "making webhook calls. Supports JSON body, custom headers, and timeout."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        """
        JSON Schema 格式的参数定义

        定义了 Tool 接受的所有参数:
        - type: 参数类型 (object, string, integer, boolean, array 等)
        - properties: 每个参数的定义
            - type: 参数类型
            - description: 参数描述
            - enum: 枚举值（可选）
            - default: 默认值（可选）
        - required: 必需参数列表
        """
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full URL to request (e.g., https://api.example.com/data)",
                },
                "method": {
                    "type": "string",
                    "description": "HTTP method (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS)",
                    "enum": ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
                    "default": "GET",
                },
                "headers": {
                    "type": "object",
                    "description": "Optional request headers as key-value pairs (e.g., {'Authorization': 'Bearer token'})",
                    "additionalProperties": {"type": "string"},
                },
                "json": {
                    "type": "object",
                    "description": "JSON body for POST/PUT requests (will be serialized to JSON string)",
                },
                "data": {
                    "type": "string",
                    "description": "Raw request body as string (for non-JSON content)",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Request timeout in seconds (default 30, max 120)",
                    "minimum": 1,
                    "maximum": 120,
                    "default": 30,
                },
            },
            "required": ["url"],
        }

    async def execute(
        self,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        data: str | None = None,
        timeout: int | None = None,
        **kwargs: Any,
    ) -> str:
        """
        执行 HTTP 请求

        Args:
            url: 请求 URL
            method: HTTP 方法
            headers: 请求头
            json: JSON 请求体
            data: 原始请求体
            timeout: 超时时间
            **kwargs: 其他参数（忽略）

        Returns:
            格式化后的响应字符串
        """
        effective_timeout = min(timeout or self.timeout, 120)
        request_headers = headers or {}

        # 构建请求参数
        request_kwargs = {
            "method": method.upper(),
            "url": url,
            "headers": request_headers,
            "timeout": effective_timeout,
            "follow_redirects": True,
        }

        # 处理请求体
        if json is not None:
            request_kwargs["json"] = json
        elif data is not None:
            request_kwargs["content"] = data.encode("utf-8") if isinstance(data, str) else data

        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(**request_kwargs)

            # 格式化响应
            result_parts = [
                f"Status: {response.status_code} {response.reason_phrase}",
                f"URL: {response.url}",
            ]

            # 响应头（可选，最多显示10个）
            if response.headers:
                result_parts.append("\nHeaders:")
                for key, value in list(response.headers.items())[:10]:
                    result_parts.append(f"  {key}: {value}")

            # 响应体
            try:
                # 尝试解析为 JSON
                json_data = response.json()
                result_parts.append("\nBody (JSON):")
                result_parts.append(json.dumps(json_data, indent=2, ensure_ascii=False))
            except ValueError:
                # 普通文本
                text = response.text
                if len(text) > 5000:
                    text = text[:5000] + f"\n... ({len(text) - 5000} chars truncated)"
                if text.strip():
                    result_parts.append("\nBody:")
                    result_parts.append(text)

            return "\n".join(result_parts)

        except httpx.TimeoutException:
            return f"Error: Request timed out after {effective_timeout} seconds"
        except httpx.NetworkError as e:
            return f"Error: Network error - {str(e)}"
        except httpx.HTTPStatusError as e:
            return f"Error: HTTP error {e.response.status_code} - {e.response.reason_phrase}"
        except Exception as e:
            return f"Error: {type(e).__name__} - {str(e)}"
```

### 3.2 代码结构说明

上面的代码展示了一个完整的 Tool 实现，主要包含以下几个部分：

| 部分 | 说明 |
|-----|------|
| 类定义 | 继承 `Tool` 基类 |
| `__init__` | 初始化配置（超时、重试等） |
| `name` 属性 | Tool 唯一标识符 |
| `description` 属性 | 帮助 LLM 理解 Tool 功能 |
| `parameters` 属性 | JSON Schema 参数定义 |
| `execute()` 方法 | Tool 执行逻辑 |

---

## 4. 在 Agent Loop 中注册 Tool

创建好 Tool 类后，需要在 `AgentLoop` 中注册它，这样 Agent 才能使用它。

### 4.1 编辑 `nanobot/agent/loop.py`

找到 `_register_default_tools()` 方法，添加你的 Tool 注册代码：

```python
# 文件: nanobot/agent/loop.py

# 1. 在文件顶部导入你的 Tool
from nanobot.agent.tools.http import HttpRequestTool  # 添加这行

class AgentLoop:
    # ... 其他代码 ...

    def _register_default_tools(self) -> None:
        """Register the default set of tools."""

        # ... 现有的 Tool 注册代码 ...

        # 2. 注册你的新 Tool
        self.tools.register(HttpRequestTool(
            timeout=30,
            max_retries=2
        ))
```

### 4.2 注册代码说明

```python
# 创建 Tool 实例并注册到 ToolRegistry
self.tools.register(HttpRequestTool(
    timeout=30,        # 设置超时时间为 30 秒
    max_retries=2      # 设置最大重试次数为 2 次
))
```

| 参数 | 说明 |
|-----|------|
| `timeout` | HTTP 请求超时时间（秒） |
| `max_retries` | 请求失败时的最大重试次数 |

---

## 5. 测试你的 Tool

注册完成后，你可以通过以下方式测试你的 Tool：

### 5.1 编写单元测试

创建测试文件 `tests/test_http_tool.py`：

```python
"""Tests for HttpRequestTool."""

import pytest

from nanobot.agent.tools.http import HttpRequestTool


@pytest.fixture
def http_tool():
    """Create a HttpRequestTool instance for testing."""
    return HttpRequestTool(timeout=10, max_retries=1)


class TestHttpRequestTool:
    """Test cases for HttpRequestTool."""

    def test_name(self, http_tool):
        """Test tool name."""
        assert http_tool.name == "http_request"

    def test_description(self, http_tool):
        """Test tool has a description."""
        assert len(http_tool.description) > 0

    def test_parameters_schema(self, http_tool):
        """Test parameters schema is valid."""
        schema = http_tool.parameters
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "url" in schema["properties"]
        assert "required" in schema
        assert "url" in schema["required"]

    @pytest.mark.asyncio
    async def test_execute_get_request(self, http_tool):
        """Test executing a GET request."""
        # 使用 httpbin.org 进行测试
        result = await http_tool.execute(
            url="https://httpbin.org/get",
            method="GET"
        )

        # 验证响应
        assert "Status: 200" in result
        assert "https://httpbin.org/get" in result

    @pytest.mark.asyncio
    async def test_execute_post_json(self, http_tool):
        """Test executing a POST request with JSON body."""
        result = await http_tool.execute(
            url="https://httpbin.org/post",
            method="POST",
            json={"key": "value", "number": 42}
        )

        assert "Status: 200" in result
        assert '"key": "value"' in result or "key": "value" in result

    @pytest.mark.asyncio
    async def test_execute_with_headers(self, http_tool):
        """Test executing a request with custom headers."""
        result = await http_tool.execute(
            url="https://httpbin.org/headers",
            method="GET",
            headers={"X-Custom-Header": "test-value"}
        )

        assert "Status: 200" in result

    @pytest.mark.asyncio
    async def test_execute_timeout(self, http_tool):
        """Test that timeout is handled correctly."""
        # httpbin.org 的 /delay 端点可以模拟延迟
        result = await http_tool.execute(
            url="https://httpbin.org/delay/15",  # 延迟 15 秒
            method="GET",
            timeout=2  # 但我们只等 2 秒
        )

        assert "Error:" in result
        assert "timed out" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_invalid_url(self, http_tool):
        """Test handling of invalid URL."""
        result = await http_tool.execute(
            url="not-a-valid-url",
            method="GET"
        )

        assert "Error:" in result

    @pytest.mark.asyncio
    async def test_execute_404(self, http_tool):
        """Test handling of 404 response."""
        result = await http_tool.execute(
            url="https://httpbin.org/status/404",
            method="GET"
        )

        assert "Status: 404" in result
```

### 5.2 运行测试

```bash
# 运行所有测试
pytest tests/test_http_tool.py

# 运行特定测试
pytest tests/test_http_tool.py::TestHttpRequestTool::test_execute_get_request -v

# 运行测试并显示输出
pytest tests/test_http_tool.py -v -s
```

### 5.3 手动测试

你也可以通过运行 nanobot 来手动测试：

```bash
# 启动 nanobot
nanobot run

# 然后向它发送消息，比如：
# "帮我发送一个 GET 请求到 https://api.github.com/users/github"
```

---

## 6. 最佳实践和注意事项

### 6.1 命名规范

| 项目 | 规范 | 示例 |
|-----|------|-----|
| 类名 | `XXXTool` | `HttpRequestTool`, `DatabaseQueryTool` |
| name 属性 | snake_case | `http_request`, `database_query` |
| 参数名 | snake_case | `file_path`, `timeout_seconds` |
| 描述 | 清晰、简洁 | "Send HTTP requests to web APIs" |

### 6.2 参数设计原则

```python
@property
def parameters(self) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            # 1. 必需参数放在前面
            "url": {
                "type": "string",
                "description": "...",  # 描述要具体、清晰
            },
            # 2. 有默认值的参数
            "method": {
                "type": "string",
                "enum": ["GET", "POST"],  # 使用 enum 限制可选值
                "default": "GET",  # 明确默认值
            },
            # 3. 数值参数要定义范围
            "timeout": {
                "type": "integer",
                "minimum": 1,
                "maximum": 300,
                "default": 30,
            },
        },
        "required": ["url"],  # 只标记真正必需的参数
    }
```

### 6.3 错误处理规范

```python
async def execute(self, url: str, **kwargs) -> str:
    try:
        # 1. 参数预处理
        if not url.startswith(("http://", "https://")):
            return "Error: URL must start with http:// or https://"

        # 2. 核心逻辑
        result = await self._do_request(url, **kwargs)
        return result

    except TimeoutError as e:
        # 3. 已知的特定异常
        return f"Error: Request timed out - {str(e)}"
    except ValueError as e:
        return f"Error: Invalid parameter - {str(e)}"
    except Exception as e:
        # 4. 未知异常（记录详细信息，返回简洁错误）
        logger.error(f"HttpRequestTool failed: {type(e).__name__}: {e}", exc_info=True)
        return f"Error: Request failed ({type(e).__name__})"
```

### 6.4 安全注意事项

```python
class HttpRequestTool(Tool):
    def __init__(self, allowed_hosts: list[str] | None = None, block_private_ips: bool = True):
        self.allowed_hosts = allowed_hosts  # 允许的主机白名单
        self.block_private_ips = block_private_ips  # 是否阻止内网 IP

    def _validate_url(self, url: str) -> tuple[bool, str]:
        """验证 URL 是否允许访问"""
        from urllib.parse import urlparse

        parsed = urlparse(url)

        # 1. 只允许 http/https
        if parsed.scheme not in ("http", "https"):
            return False, f"Scheme '{parsed.scheme}' is not allowed"

        # 2. 检查主机白名单
        if self.allowed_hosts and parsed.hostname not in self.allowed_hosts:
            return False, f"Host '{parsed.hostname}' is not in the allowed list"

        # 3. 阻止内网 IP（防止 SSRF）
        if self.block_private_ips:
            import socket
            import ipaddress

            try:
                ip = socket.getaddrinfo(parsed.hostname, None)[0][4][0]
                ip_obj = ipaddress.ip_address(ip)

                # 检查是否是私有 IP
                if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved:
                    return False, f"Access to internal IP {ip} is blocked"
            except Exception:
                pass  # 如果无法解析，继续执行

        return True, ""
```

### 6.5 性能优化建议

```python
class HttpRequestTool(Tool):
    def __init__(self, ...):
        # 复用 HTTP Client（如果可能）
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP Client"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30,
                follow_redirects=True,
                limits=httpx.Limits(max_connections=10)
            )
        return self._client

    async def execute(self, ...):
        client = await self._get_client()
        # 使用 client 发送请求
        ...
```

---

## 7. 总结

添加一个新 Tool 的核心步骤：

1. **创建 Tool 类**
   - 继承 `Tool` 基类
   - 实现 `name`、`description`、`parameters` 属性和 `execute()` 方法

2. **注册 Tool**
   - 在 `AgentLoop._register_default_tools()` 中实例化并注册

3. **测试**
   - 编写单元测试
   - 手动测试验证功能

**关键文件**：
- `tools/base.py` - Tool 基类
- `tools/registry.py` - Tool 注册中心
- `tools/shell.py` - ExecTool 示例
- `agent/loop.py` - Agent 主循环，注册 Tool 的地方

祝你的新 Tool 开发顺利！
