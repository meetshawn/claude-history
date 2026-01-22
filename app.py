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
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

app = FastAPI(title="Claude History Viewer", version="1.0.0")

# Claude配置目录
CLAUDE_DIR = Path.home() / ".claude"
HISTORY_FILE = CLAUDE_DIR / "history.jsonl"
PROJECTS_DIR = CLAUDE_DIR / "projects"


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


# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    # 确保static目录存在
    os.makedirs("static", exist_ok=True)
    uvicorn.run(app, host="0.0.0.0", port=8000)
