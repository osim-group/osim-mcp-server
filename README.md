# OSIM MCP Server

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.0+-green.svg)](https://github.com/jlowin/fastmcp)

基于 FastMCP 的 Model Context Protocol (MCP) 服务器，提供 OSIM (Open Security Information Model) 数据标准 schema 的查询和访问能力。

## 🚀 快速开始

### 使用 uvx（推荐，无需安装）

包已发布到 PyPI，可以直接使用 `uvx` 运行：

```bash
uvx osim-mcp-server
```

### 在 MCP 客户端中配置

#### Claude Desktop

在配置文件（`~/Library/Application Support/Claude/claude_desktop_config.json`）中添加：

```json
{
  "mcpServers": {
    "osim-mcp-server": {
      "command": "uvx",
      "args": ["osim-mcp-server"]
    }
  }
}
```

#### Cursor

在 MCP 设置中添加：

```json
{
  "mcpServers": {
    "osim-mcp-server": {
      "command": "uvx",
      "args": ["osim-mcp-server"]
    }
  }
}
```

### 从源码运行

```bash
# 克隆仓库
git clone https://github.com/osim-group/osim-mcp-server.git
cd osim-mcp-server

# 首先获取 schemas（必需）
# 确保已安装 git
python update_schemas.py

# 安装依赖并运行
uv sync
uv run python server.py
```

> **重要**：仓库本身不包含 schemas 目录，需要先运行 `update_schemas.py` 获取 schemas 文件才能正常运行。

### 更新 Schemas

项目中的 schemas 文件来源于 [OSIM Schema 仓库](https://github.com/osim-group/osim-schema/tree/main/schemas)。如果需要获取或更新最新的 schemas，可以使用项目提供的更新脚本：

```bash
# 确保已安装 git
python update_schemas.py
```

脚本会自动：
- 从 GitHub 仓库克隆最新的 schemas
- 备份现有的 schemas（如果存在）
- 更新本地 schemas 目录
- 验证更新结果

> **注意**：更新脚本需要系统已安装 git 命令。

## 📚 功能特性

### MCP 工具

1. **`list_schema_names`** - 列出所有可用的数据标准 schema 名称
   - 返回格式：`{group}.{category}.{title}`
   - 示例：`log.network_session_audit.http_audit`

2. **`describe_schemas`** - 获取指定 schema 的描述信息
   - 参数：`schema_names` (List[str])
   - 返回：字典，键为 schema 名称，值为描述信息

3. **`get_schema`** - 获取指定 schema 的完整字段定义
   - 参数：`schema_path` (str)，格式为 `{group}.{category}.{title}`
   - 返回：字段定义字典，包含字段名、标签、类型、要求、描述等信息

### MCP 资源

通过资源 URI 访问 schema 文件内容：

- **URI 格式**：`data-standard://{group}/{category}/{title}`
- **示例**：
  - `data-standard://log/network_session_audit/http_audit`
  - `data-standard://alert/network_attack/apt_attack`
  - `data-standard://asset/business_asset/web_application`

## 📊 数据标准分类

项目提供完整的 OSIM 数据标准支持，包括：

- **告警 (Alert)**：异常行为、数据安全、恶意软件、网络攻击等
- **资产 (Asset)**：业务资产、云资产、数据资产、网络资产等
- **日志 (Log)**：账户操作审计、数据安全审计、主机行为审计、网络会话审计等
- **事件 (Incident)**：安全事件记录和分类
- **设备检测 (Device Detection)**：EDR、防火墙、WAF、IDS/IPS 等各类安全设备

> **数据来源**：所有 schema 文件均来源于 [OSIM Schema 仓库](https://github.com/osim-group/osim-schema/tree/main/schemas)

## 🛠️ 开发

### 获取/更新 Schemas

项目提供了脚本用于从 GitHub 仓库同步最新的 schemas：

```bash
python update_schemas.py
```

> **注意**：构建分发包前需要先获取 schemas，因为分发包需要包含 schemas 文件。

### 构建分发包

```bash
# 确保已获取 schemas
python update_schemas.py

# 构建分发包
uv build
```

### 发布到 PyPI

```bash
# 安装 twine
uv pip install twine

# 上传到 PyPI
uv run twine upload dist/*
```

发布后即可通过 `uvx osim-mcp-server` 使用。

## 📝 许可证

Apache License 2.0

## 🙏 致谢

- [FastMCP](https://github.com/jlowin/fastmcp) - MCP 服务器框架
- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP 协议规范
- [OSIM Schema 仓库](https://github.com/osim-group/osim-schema) - 数据标准 schema 文件资源
