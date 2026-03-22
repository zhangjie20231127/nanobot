# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

nanobot is an ultra-lightweight personal AI assistant (Python 3.11+). It connects to various messaging platforms (channels) and uses LLM providers to process messages and execute tools.

## Common Commands

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run a single test file
pytest tests/test_filename.py

# Run a single test function
pytest tests/test_filename.py::test_function_name

# Lint code
ruff check nanobot/

# Format code
ruff format nanobot/
```

## Architecture

The codebase has five main components:

1. **Agent** (`nanobot/agent/`) - The core processing engine. `loop.py` is the main entry point that receives messages, builds context, calls the LLM, and executes tools.

2. **Channels** (`nanobot/channels/`) - Messaging platform integrations. Each channel (telegram, discord, slack, feishu, dingtalk, whatsapp, qq, wecom, email, matrix, mochat) implements the `Channel` base class to send/receive messages.

3. **Providers** (`nanobot/providers/`) - LLM backends. Supports anthropic, openai, openrouter, azure openai, deepseek, grok, gemini, zhipu, dashscope, vllm, ollama, and custom OpenAI-compatible endpoints.

4. **Tools** (`nanobot/agent/tools/`) - Agent capabilities including filesystem operations, shell execution, web search/fetch, message sending, cron scheduling, subagent spawning, and MCP integration.

5. **Skills** (`nanobot/skills/`) - Extensible skill system. Each skill is a directory with `SKILL.md` containing YAML frontmatter and instructions. Built-in skills: github, weather, summarize, tmux, clawhub, skill-creator.

### Configuration

Config is defined in `nanobot/config/schema.py` using Pydantic. Configuration loads from:
1. Default values
2. `~/.nanobot/config.yaml` (user config)
3. `./nanobot.yaml` (project config)
4. Environment variables

### Message Flow

```
Channel → MessageBus → AgentLoop → LLM Provider → Tools → Response → Channel
```

The `MessageBus` (`nanobot/bus/`) decouples channels from the agent. Channels publish `InboundMessage` events; the agent processes them and publishes `OutboundMessage` events back.

### Key Files

- `nanobot/cli/commands.py` - CLI entry point with `nanobot` command
- `nanobot/agent/loop.py` - Core agent loop implementation
- `nanobot/config/schema.py` - Pydantic configuration schema
- `nanobot/channels/base.py` - Base channel class
- `nanobot/providers/registry.py` - Provider registry

### Branch Strategy

- `main` - Stable releases
- `nightly` - Experimental features

Target `nightly` for new features, `main` for bug fixes.

### Bridge (WhatsApp)

The `bridge/` directory contains a TypeScript/Node.js bridge for WhatsApp support. It interfaces with the Python core via WebSocket.