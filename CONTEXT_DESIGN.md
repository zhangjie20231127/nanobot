# ContextBuilder 设计思路

## 概述

`ContextBuilder` 是 nanobot 智能体的"大脑上下文组装器"，负责将分散在各处的配置、记忆、技能、运行时信息整合成 LLM 可理解的完整上下文。

核心职责：
- 构建系统提示词（System Prompt）
- 组装对话历史（Messages）
- 处理多媒体输入（图片等）
- 管理工具调用结果

---

## 架构设计

### 1. 分层构建模型

系统提示词采用**分层叠加**的设计，从内到外依次是：

```
┌─────────────────────────────────────────────┐
│  1. Identity (核心身份标识)                  │  ← 我是谁、运行环境
├─────────────────────────────────────────────┤
│  2. Bootstrap Files (启动引导文件)           │  ← AGENTS.md, SOUL.md...
├─────────────────────────────────────────────┤
│  3. Memory (长期记忆)                        │  ← 用户偏好、历史事实
├─────────────────────────────────────────────┤
│  4. Skills (技能系统)                        │  ← 当前激活的技能
└─────────────────────────────────────────────┘
```

这种设计的优势：
- **优先级清晰**：越内层的指令越核心，外层不能覆盖内层
- **动态组装**：Memory 和 Skills 可以运行时变化，其他层相对稳定
- **可调试**：每一层用 `---` 分隔，方便查看最终 prompt

### 2. 运行时上下文分离

```python
_RUNTIME_CONTEXT_TAG = "[Runtime Context — metadata only, not instructions]"
```

**关键设计决策**：将"当前时间、频道信息"等运行时元数据放在**用户消息之前**，而不是系统提示词中。

原因：
1. **准确性**：系统 prompt 是静态缓存的，时间等动态信息必须在每次请求时更新
2. **语义清晰**：用 `[Runtime Context]` 标签明确区分这是元数据，不是用户指令
3. **兼容性**：一些 provider 对系统 prompt 长度有限制，避免在其中放入可变内容

### 3. 多媒体内容处理

图片处理采用**双路径**策略：

**路径 A - PIL 压缩（默认）**
```python
with Image.open(p) as img:
    # 转换为 RGB，处理透明通道
    # 等比例缩放到 1024px 以内
    # JPEG 压缩质量 85%
```

**路径 B - 原始数据（Fallback）**
```python
# 当 PIL 不可用或处理失败时
# 直接读取文件 base64 编码
# 使用 mimetypes 猜测 MIME 类型
```

设计考量：
- **成本控制**：大图片会导致 token 激增，压缩是必须的
- **兼容性**：LLM 通常限制单张图片尺寸（如 1024x1024）
- **健壮性**：PIL 可能缺失或损坏，需要 fallback

---

## 关键接口设计

### 构造方法

```python
def __init__(self, workspace: Path):
    self.workspace = workspace
    self.memory = MemoryStore(workspace)
    self.skills = SkillsLoader(workspace)
```

- **显式依赖**：需要外部传入 workspace，而不是硬编码路径
- **延迟加载**：Memory 和 Skills 在构建时不加载数据，使用时才加载

### 核心方法

```python
def build_system_prompt(self, skill_names: list[str] | None = None) -> str:
    """构建系统提示词"""

def build_messages(self, history, current_message, ...) -> list[dict]:
    """构建完整消息列表（系统 + 历史 + 当前）"""
```

- **关注点分离**：`build_system_prompt` 只负责静态内容，`build_messages` 处理动态对话
- **技能参数**：`skill_names` 允许调用方指定本次请求需要激活的技能

### 工具结果管理

```python
def add_tool_result(self, messages, tool_call_id, tool_name, result) -> list:
def add_assistant_message(self, messages, content, tool_calls, ...) -> list:
```

- **纯函数风格**：输入 messages，返回新的 messages，便于链式调用
- **完整参数**：支持 reasoning_content、thinking_blocks 等高级 provider 特性

---

## 扩展性设计

### 新增 Bootstrap 文件

要添加新的启动文件类型：

```python
# 修改 BOOTSTRAP_FILES 列表
BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md", "NEW.md"]
```

### 自定义 Identity

`_get_identity()` 方法可以被子类覆盖：

```python
class CustomContextBuilder(ContextBuilder):
    def _get_identity(self) -> str:
        return "# Custom Assistant\n\nYou are a specialized bot..."
```

### 多媒体扩展

当前支持图片，要添加视频/音频：

```python
def _build_user_content(self, text, media):
    # 检测文件类型
    # 视频 -> 提取关键帧或转码
    # 音频 -> 转文本或压缩
```

---

## 与其他组件的关系

```
┌──────────────────────────────────────────────┐
│              Agent Loop                        │
│  (nanobot/agent/loop.py)                       │
│  - 调用 ContextBuilder                        │
│  - 管理对话生命周期                            │
└──────────────────┬───────────────────────────┘
                   │ 使用
                   ▼
┌──────────────────────────────────────────────┐
│           ContextBuilder                       │
│  (nanobot/agent/context.py)                    │
│  - 组装系统提示词                              │
│  - 构建消息列表                                │
└──────────────────┬───────────────────────────┘
                   │ 依赖
        ┌──────────┴──────────┐
        ▼                     ▼
┌───────────────┐    ┌───────────────┐
│  MemoryStore  │    │ SkillsLoader  │
│  (memory/)    │    │ (skills/)     │
└───────────────┘    └───────────────┘
```

---

## 设计原则总结

1. **分层清晰**：系统提示词分层构建，优先级明确
2. **动静分离**：静态身份与动态运行时数据分离
3. **健壮优先**：图片处理双路径，PIL 失败有 fallback
4. **纯函数接口**：方法输入输出明确，易于测试和链式调用
5. **开放扩展**：Bootstrap 文件列表、Identity、多媒体处理都易于扩展