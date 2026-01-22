"""
Claude History Viewer - FastAPI Backend
读取和分析Claude Code的历史对话记录
"""
import os
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Optional
import shutil
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from openai import OpenAI

app = FastAPI(title="Claude History Viewer", version="1.0.0")

# Claude配置目录
CLAUDE_DIR = Path.home() / ".claude"
HISTORY_FILE = CLAUDE_DIR / "history.jsonl"
PROJECTS_DIR = CLAUDE_DIR / "projects"

# 应用配置目录
APP_DIR = Path(__file__).parent
CONFIG_FILE = APP_DIR / "config.json"
REPORTS_DIR = APP_DIR / "reports"


def load_config():
    """加载配置文件"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "openai": {
            "api_key": "",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini"
        }
    }


def save_config(config):
    """保存配置文件"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def get_openai_client():
    """获取OpenAI客户端"""
    config = load_config()
    openai_config = config.get("openai", {})

    if not openai_config.get("api_key"):
        return None

    return OpenAI(
        api_key=openai_config["api_key"],
        base_url=openai_config.get("base_url", "https://api.openai.com/v1")
    )


def get_claude_dir():
    """获取Claude配置目录"""
    return CLAUDE_DIR


def read_history_file():
    """读取主历史文件"""
    history = []
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    history.append(data)
                except json.JSONDecodeError:
                    continue
    return history


def get_all_projects():
    """获取所有项目"""
    projects = []
    if PROJECTS_DIR.exists():
        for project_dir in PROJECTS_DIR.iterdir():
            if project_dir.is_dir():
                # 将目录名转换回路径格式
                project_name = project_dir.name.replace('--', ':\\').replace('-', '\\')
                if project_name.startswith('C:\\') or project_name.startswith('D:\\'):
                    pass
                else:
                    project_name = project_dir.name.replace('--', '/').replace('-', '/')

                # 统计会话数量
                session_count = len(list(project_dir.glob("*.jsonl")))
                projects.append({
                    "id": project_dir.name,
                    "name": project_name,
                    "path": str(project_dir),
                    "session_count": session_count
                })
    return sorted(projects, key=lambda x: x["session_count"], reverse=True)


def get_project_sessions(project_id: str):
    """获取项目的所有会话"""
    project_dir = PROJECTS_DIR / project_id
    sessions = []

    if project_dir.exists():
        for session_file in project_dir.glob("*.jsonl"):
            session_id = session_file.stem
            # 读取会话文件获取基本信息
            messages = []
            first_timestamp = None
            last_timestamp = None
            message_count = 0

            with open(session_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        if data.get("type") in ["user", "assistant"]:
                            message_count += 1
                            ts = data.get("timestamp")
                            if ts:
                                if first_timestamp is None:
                                    first_timestamp = ts
                                last_timestamp = ts
                    except json.JSONDecodeError:
                        continue

            sessions.append({
                "id": session_id,
                "file": str(session_file),
                "message_count": message_count,
                "first_timestamp": first_timestamp,
                "last_timestamp": last_timestamp
            })

    return sorted(sessions, key=lambda x: x.get("last_timestamp") or "", reverse=True)


def get_session_messages(project_id: str, session_id: str):
    """获取会话的所有消息"""
    session_file = PROJECTS_DIR / project_id / f"{session_id}.jsonl"
    messages = []

    if session_file.exists():
        with open(session_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    msg_type = data.get("type")
                    if msg_type in ["user", "assistant"]:
                        message = data.get("message", {})
                        content = message.get("content", "")

                        # 处理content可能是列表的情况
                        if isinstance(content, list):
                            text_parts = []
                            for item in content:
                                if isinstance(item, dict):
                                    item_type = item.get("type", "")
                                    if item_type == "text":
                                        text_parts.append(item.get("text", ""))
                                    elif item_type == "thinking":
                                        thinking_text = item.get("thinking", "")
                                        if thinking_text:
                                            text_parts.append(f"💭 思考过程:\n{thinking_text}")
                                    elif item_type == "tool_use":
                                        tool_name = item.get("name", "unknown")
                                        tool_input = item.get("input", {})
                                        tool_desc = ""
                                        if isinstance(tool_input, dict):
                                            if "command" in tool_input:
                                                tool_desc = f": {tool_input.get('command', '')[:100]}"
                                            elif "file_path" in tool_input:
                                                tool_desc = f": {tool_input.get('file_path', '')}"
                                            elif "pattern" in tool_input:
                                                tool_desc = f": {tool_input.get('pattern', '')}"
                                        text_parts.append(f"🔧 [{tool_name}{tool_desc}]")
                                    elif item_type == "tool_result":
                                        result_content = item.get("content", "")
                                        if result_content:
                                            # 截断过长的工具结果
                                            if len(result_content) > 500:
                                                result_content = result_content[:500] + "..."
                                            text_parts.append(f"📋 工具结果:\n{result_content}")
                                elif isinstance(item, str):
                                    text_parts.append(item)
                            content = "\n".join(filter(None, text_parts))

                        # 如果content仍然为空，尝试从其他字段获取
                        if not content and isinstance(message, dict):
                            # 尝试获取role为user时的直接content
                            if message.get("role") == "user" and isinstance(message.get("content"), str):
                                content = message.get("content", "")

                        # 跳过空消息
                        if not content or not content.strip():
                            continue

                        messages.append({
                            "type": msg_type,
                            "content": content,
                            "timestamp": data.get("timestamp"),
                            "uuid": data.get("uuid"),
                            "cwd": data.get("cwd", ""),
                            "model": message.get("model", "") if isinstance(message, dict) else ""
                        })
                except json.JSONDecodeError:
                    continue

    return messages


def get_statistics():
    """获取统计信息"""
    stats = {
        "total_projects": 0,
        "total_sessions": 0,
        "total_messages": 0,
        "projects_by_activity": [],
        "daily_activity": defaultdict(int),
        "hourly_activity": defaultdict(int),
        "model_usage": defaultdict(int),
        "tool_usage": defaultdict(int)
    }

    history = read_history_file()
    stats["total_history_entries"] = len(history)

    # 分析历史记录
    for entry in history:
        ts = entry.get("timestamp")
        if ts:
            dt = datetime.fromtimestamp(ts / 1000)
            date_str = dt.strftime("%Y-%m-%d")
            hour = dt.hour
            stats["daily_activity"][date_str] += 1
            stats["hourly_activity"][hour] += 1

    # 统计项目
    projects = get_all_projects()
    stats["total_projects"] = len(projects)

    for project in projects:
        project_dir = PROJECTS_DIR / project["id"]
        session_files = list(project_dir.glob("*.jsonl"))
        stats["total_sessions"] += len(session_files)

        project_messages = 0
        for session_file in session_files:
            with open(session_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        if data.get("type") in ["user", "assistant"]:
                            project_messages += 1
                            stats["total_messages"] += 1

                        # 统计模型使用
                        msg = data.get("message", {})
                        if isinstance(msg, dict):
                            model = msg.get("model")
                            if model:
                                stats["model_usage"][model] += 1

                            # 统计工具使用
                            content = msg.get("content", [])
                            if isinstance(content, list):
                                for item in content:
                                    if isinstance(item, dict) and item.get("type") == "tool_use":
                                        tool_name = item.get("name", "unknown")
                                        stats["tool_usage"][tool_name] += 1
                    except json.JSONDecodeError:
                        continue

        stats["projects_by_activity"].append({
            "name": project["name"],
            "id": project["id"],
            "messages": project_messages
        })

    # 排序
    stats["projects_by_activity"] = sorted(
        stats["projects_by_activity"],
        key=lambda x: x["messages"],
        reverse=True
    )[:10]

    # 转换defaultdict为普通dict
    stats["daily_activity"] = dict(sorted(stats["daily_activity"].items())[-30:])
    stats["hourly_activity"] = dict(sorted(stats["hourly_activity"].items()))
    stats["model_usage"] = dict(stats["model_usage"])
    stats["tool_usage"] = dict(sorted(stats["tool_usage"].items(), key=lambda x: x[1], reverse=True)[:20])

    return stats


# API路由
@app.get("/")
async def root():
    """返回主页"""
    return FileResponse("static/index.html")


@app.get("/api/projects")
async def api_projects():
    """获取所有项目列表"""
    return get_all_projects()


@app.get("/api/projects/{project_id}/sessions")
async def api_project_sessions(project_id: str):
    """获取项目的会话列表"""
    return get_project_sessions(project_id)


@app.get("/api/projects/{project_id}/sessions/{session_id}")
async def api_session_messages(project_id: str, session_id: str):
    """获取会话的消息列表"""
    session_file = PROJECTS_DIR / project_id / f"{session_id}.jsonl"
    return {
        "messages": get_session_messages(project_id, session_id),
        "source_file": str(session_file) if session_file.exists() else None,
        "project_id": project_id,
        "session_id": session_id
    }


@app.get("/api/statistics")
async def api_statistics():
    """获取统计信息"""
    return get_statistics()


@app.get("/api/history")
async def api_history(limit: int = 100, offset: int = 0):
    """获取历史记录"""
    history = read_history_file()
    return {
        "total": len(history),
        "items": history[offset:offset + limit]
    }


@app.delete("/api/projects/{project_id}/sessions/{session_id}")
async def api_delete_session(project_id: str, session_id: str):
    """删除会话"""
    session_file = PROJECTS_DIR / project_id / f"{session_id}.jsonl"
    session_dir = PROJECTS_DIR / project_id / session_id

    deleted_files = []
    errors = []

    # 删除会话文件
    if session_file.exists():
        try:
            session_file.unlink()
            deleted_files.append(str(session_file))
        except Exception as e:
            errors.append(f"删除文件失败: {str(e)}")

    # 删除会话目录（如果存在）
    if session_dir.exists() and session_dir.is_dir():
        try:
            shutil.rmtree(session_dir)
            deleted_files.append(str(session_dir))
        except Exception as e:
            errors.append(f"删除目录失败: {str(e)}")

    if not deleted_files and not errors:
        raise HTTPException(status_code=404, detail="会话不存在")

    return {
        "success": len(errors) == 0,
        "deleted": deleted_files,
        "errors": errors
    }


@app.delete("/api/projects/{project_id}")
async def api_delete_project(project_id: str):
    """删除整个项目"""
    project_dir = PROJECTS_DIR / project_id

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="项目不存在")

    try:
        shutil.rmtree(project_dir)
        return {
            "success": True,
            "deleted": str(project_dir)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


# ============ AI分析相关API ============

class ConfigUpdate(BaseModel):
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"


@app.get("/api/config")
async def api_get_config():
    """获取配置（隐藏API密钥）"""
    config = load_config()
    openai_config = config.get("openai", {})
    return {
        "api_key": "***" + openai_config.get("api_key", "")[-4:] if openai_config.get("api_key") else "",
        "base_url": openai_config.get("base_url", "https://api.openai.com/v1"),
        "model": openai_config.get("model", "gpt-4o-mini"),
        "configured": bool(openai_config.get("api_key"))
    }


@app.post("/api/config")
async def api_update_config(config_update: ConfigUpdate):
    """更新配置"""
    config = load_config()
    config["openai"] = {
        "api_key": config_update.api_key,
        "base_url": config_update.base_url,
        "model": config_update.model
    }
    save_config(config)
    return {"success": True}


ANALYSIS_PROMPT = """你是一个专业的用户行为分析师，专门分析开发者与AI助手的对话记录，从中提取用户的技术偏好、编程习惯、决策模式和工作风格。

请分析以下对话记录，提取用户的技术偏好，并生成个性化的AI Rules。

## 分析维度

1. **技术栈偏好**: 编程语言、框架、数据库、工具链
2. **编码风格偏好**: 命名规范、注释习惯、代码简洁度
3. **工作流程偏好**: 开发方式、迭代风格、沟通方式
4. **明确排斥**: 用户不喜欢或拒绝的做法

## 输出格式

请按以下Markdown格式输出分析报告：

```markdown
# 用户技术偏好分析报告

## 分析概要
[简要总结用户的主要技术偏好特征]

## 核心偏好 (高置信度)
- **[偏好类别]**: [具体偏好] - [证据/出现次数]

## 一般偏好 (中置信度)
- **[偏好类别]**: [具体偏好] - [证据]

## 明确排斥
- [用户不喜欢的做法] - [证据]

---

# 推荐的 AI Rules

以下规则可添加到 `~/.claude/CLAUDE.md` 或项目的 `CLAUDE.md` 文件中：

## 语言与交互
- [交互偏好规则]

## 技术栈
- [技术选型规则]

## 编码规范
- [编码风格规则]

## 工作方式
- [工作流程规则]

## 禁止事项
- [不要做的事情]
```

## 对话记录

"""


@app.post("/api/analyze/{project_id}/sessions/{session_id}")
async def api_analyze_session(project_id: str, session_id: str):
    """分析单个会话"""
    client = get_openai_client()
    if not client:
        raise HTTPException(status_code=400, detail="请先配置OpenAI API密钥")

    messages = get_session_messages(project_id, session_id)
    if not messages:
        raise HTTPException(status_code=404, detail="会话不存在或没有消息")

    # 构建对话内容
    conversation = []
    for msg in messages[:100]:  # 限制消息数量避免超长
        role = "用户" if msg["type"] == "user" else "AI助手"
        content = msg["content"][:1000]  # 截断过长内容
        conversation.append(f"**{role}**: {content}")

    conversation_text = "\n\n".join(conversation)

    # 调用AI分析
    config = load_config()
    model = config.get("openai", {}).get("model", "gpt-4o-mini")

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个专业的用户行为分析师，擅长从对话中提取用户偏好。请用中文回复。"},
                {"role": "user", "content": ANALYSIS_PROMPT + conversation_text}
            ],
            max_tokens=4000
        )

        analysis_result = response.choices[0].message.content

        # 保存报告
        REPORTS_DIR.mkdir(exist_ok=True)
        report_filename = f"{project_id}_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report_path = REPORTS_DIR / report_filename

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"# 会话分析报告\n\n")
            f.write(f"- **项目**: {project_id}\n")
            f.write(f"- **会话**: {session_id}\n")
            f.write(f"- **分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **消息数量**: {len(messages)}\n\n")
            f.write("---\n\n")
            f.write(analysis_result)

        return {
            "success": True,
            "report": analysis_result,
            "report_file": report_filename
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@app.post("/api/analyze/{project_id}")
async def api_analyze_project(project_id: str):
    """分析整个项目的所有会话"""
    client = get_openai_client()
    if not client:
        raise HTTPException(status_code=400, detail="请先配置OpenAI API密钥")

    sessions = get_project_sessions(project_id)
    if not sessions:
        raise HTTPException(status_code=404, detail="项目不存在或没有会话")

    # 收集所有会话的消息
    all_messages = []
    for session in sessions[:10]:  # 限制会话数量
        messages = get_session_messages(project_id, session["id"])
        all_messages.extend(messages[:20])  # 每个会话取前20条

    if not all_messages:
        raise HTTPException(status_code=404, detail="没有找到消息")

    # 构建对话内容
    conversation = []
    for msg in all_messages[:200]:  # 总共限制200条
        role = "用户" if msg["type"] == "user" else "AI助手"
        content = msg["content"][:500]
        conversation.append(f"**{role}**: {content}")

    conversation_text = "\n\n".join(conversation)

    # 调用AI分析
    config = load_config()
    model = config.get("openai", {}).get("model", "gpt-4o-mini")

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个专业的用户行为分析师，擅长从对话中提取用户偏好。请用中文回复。"},
                {"role": "user", "content": ANALYSIS_PROMPT + conversation_text}
            ],
            max_tokens=4000
        )

        analysis_result = response.choices[0].message.content

        # 保存报告
        REPORTS_DIR.mkdir(exist_ok=True)
        report_filename = f"{project_id}_full_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report_path = REPORTS_DIR / report_filename

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"# 项目分析报告\n\n")
            f.write(f"- **项目**: {project_id}\n")
            f.write(f"- **分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **会话数量**: {len(sessions)}\n")
            f.write(f"- **分析消息数**: {len(all_messages)}\n\n")
            f.write("---\n\n")
            f.write(analysis_result)

        return {
            "success": True,
            "report": analysis_result,
            "report_file": report_filename
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@app.get("/api/reports")
async def api_list_reports():
    """获取所有分析报告列表"""
    REPORTS_DIR.mkdir(exist_ok=True)
    reports = []
    for report_file in REPORTS_DIR.glob("*.md"):
        stat = report_file.stat()
        reports.append({
            "filename": report_file.name,
            "size": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_mtime).isoformat()
        })
    return sorted(reports, key=lambda x: x["created"], reverse=True)


@app.get("/api/reports/{filename}")
async def api_get_report(filename: str):
    """获取分析报告内容"""
    report_path = REPORTS_DIR / filename
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="报告不存在")

    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()

    return {
        "filename": filename,
        "content": content
    }


@app.delete("/api/reports/{filename}")
async def api_delete_report(filename: str):
    """删除分析报告"""
    report_path = REPORTS_DIR / filename
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="报告不存在")

    report_path.unlink()
    return {"success": True}


# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    # 确保static目录存在
    os.makedirs("static", exist_ok=True)
    uvicorn.run(app, host="0.0.0.0", port=8000)
