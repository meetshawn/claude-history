# Claude History 对话分析提示词集合

本目录包含用于分析Claude对话历史的提示词模板。

## 文件说明

### analyze_preferences.md
用户技术偏好分析提示词，用于：
- 从对话记录中提取用户的技术偏好
- 生成个性化的AI Rules
- 识别用户的编码风格和工作习惯

## 使用方法

1. 启动Claude History Viewer服务
2. 选择要分析的项目和会话
3. 导出对话内容
4. 将对话内容与提示词一起发送给AI进行分析

## 输出应用

分析结果可以：
- 添加到 `~/.claude/CLAUDE.md` 作为全局规则
- 添加到项目的 `CLAUDE.md` 作为项目规则
- 用于优化AI助手的响应方式
