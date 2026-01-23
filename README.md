# Claude History Viewer

一个用于查看和分析 Claude Code 对话历史的 Web 应用。支持浏览历史会话、多维度数据统计，以及 AI 驱动的用户技术偏好分析。

## 功能特性

- **会话浏览** - 按项目和会话组织，查看完整对话内容
- **数据统计** - 每日活动趋势、每小时分布、工具使用统计、项目活跃度排行
- **AI 分析** - 基于对话记录分析用户技术偏好，生成个性化 AI Rules
- **会话管理** - 支持删除不需要的会话和项目
- **源文件定位** - 显示会话源文件路径，方便跳转查看

## 截图预览

### 项目列表与对话查看
三栏布局：项目列表 → 会话列表 → 对话内容

### 数据分析
- 总项目数、会话数、消息数统计
- 每日活动趋势图
- 每小时活动分布图
- 工具使用统计饼图
- 项目活跃度 Top 10

### AI 偏好分析
分析对话记录，提取：
- 技术栈偏好（语言、框架、工具）
- 编码风格偏好
- 工作流程偏好
- 生成可用的 AI Rules

## 快速开始

### 安装依赖

```bash
git clone https://github.com/meetshawn/claude-history.git
cd claude-history
pip install -r requirements.txt
```

### 启动服务

```bash
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

或使用启动脚本（Windows）：

```bash
start.bat
```

然后访问 http://localhost:8000

### 配置 AI 分析（可选）

1. 点击页面右上角的齿轮图标
2. 填写 API 配置：
   - **API Base URL**: OpenAI API 地址（支持兼容 API）
   - **API Key**: 你的 API 密钥
   - **模型**: 使用的模型名称（如 `gpt-4o-mini`）
3. 点击保存

配置示例：
```json
{
    "openai": {
        "api_key": "your-api-key",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini"
    }
}
```

## 技术栈

- **后端**: Python, FastAPI
- **前端**: HTML, JavaScript, Tailwind CSS
- **图表**: Chart.js
- **Markdown 渲染**: marked.js
- **AI 集成**: OpenAI API（兼容接口）

## 项目结构

```
claude-history/
├── app.py              # FastAPI 后端服务
├── requirements.txt    # Python 依赖
├── config.json         # API 配置（自动生成，已忽略）
├── config.example.json # 配置示例
├── start.bat           # Windows 启动脚本
├── static/
│   └── index.html      # 前端页面
├── reports/            # AI 分析报告存储目录
└── prompts/            # 分析提示词模板
    ├── README.md
    └── analyze_preferences.md
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects` | 获取项目列表 |
| GET | `/api/projects/{id}/sessions` | 获取会话列表 |
| GET | `/api/projects/{id}/sessions/{sid}` | 获取会话消息 |
| DELETE | `/api/projects/{id}/sessions/{sid}` | 删除会话 |
| DELETE | `/api/projects/{id}` | 删除项目 |
| GET | `/api/statistics` | 获取统计数据 |
| GET | `/api/config` | 获取 API 配置 |
| POST | `/api/config` | 更新 API 配置 |
| POST | `/api/analyze/{id}/sessions/{sid}` | 分析单个会话 |
| POST | `/api/analyze/{id}` | 分析整个项目 |
| GET | `/api/reports` | 获取报告列表 |
| GET | `/api/reports/{filename}` | 获取报告内容 |
| DELETE | `/api/reports/{filename}` | 删除报告 |

## 数据来源

本应用读取 Claude Code 的本地历史数据：

- **历史文件**: `~/.claude/history.jsonl`
- **项目目录**: `~/.claude/projects/`
- **会话文件**: `~/.claude/projects/{project_id}/{session_id}.jsonl`

## 注意事项

- 删除操作不可恢复，请谨慎操作
- API 密钥保存在本地 `config.json`，不会上传
- 分析报告保存在 `reports/` 目录

## License

MIT
