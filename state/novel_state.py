"""
小说 Agent 系统的全局状态定义
LangGraph 的 StateGraph 通过 TypedDict 驱动状态流转
"""

from typing import TypedDict, Optional, List, Annotated
import operator


class NovelState(TypedDict):
    # ── 项目基本信息 ──
    project_name: str
    base_token: str                     # 飞书多维表格 base_token
    record_id: str                      # 当前项目在表格中的 record_id

    # ── Agent 1: 调研选题 ──
    topic_research_notes: str           # 调研选题笔记
    target_platforms: List[str]         # 目标平台
    genre: str                          # 类型/题材

    # ── Agent 2: 平台政策 ──
    platform_policy: str                # 平台政策与策略
    recommended_platform: str           # 推荐首发平台

    # ── Agent 3: 写作计划 ──
    outline: str                        # 写作计划/大纲
    target_word_count: int              # 目标字数
    character_bios: str                 # 人物小传
    chapter_plan: str                   # 分章大纲

    # ── Agent 4: 写作 ──
    current_chapter: int                # 当前写到第几章
    written_content: str                # 已写内容
    written_word_count: int             # 已写字数
    last_chapter_content: str           # 最新一章内容

    # ── Agent 5: 优化(Loop) ──
    optimization_round: int             # 当前优化轮次
    optimization_history: List[str]     # 优化历史记录
    need_rewrite: bool                  # 是否需要重写
    feedback: str                       # 最新反馈意见
    quality_score: float                # 质量评分（0-10，≥8 通过）

    # ── Agent 6: 审稿 ──
    review_opinion: str                 # 审稿意见
    waist_features: str                 # 腰部作品特征提炼
    review_passed: bool                 # 审稿是否通过

    # ── Agent 7: 合规 ──
    compliance_status: str              # 合规状态
    compliance_notes: str               # 合规审查记录
    compliance_passed: bool             # 合规是否通过

    # ── 控制流 ──
    current_stage: int                  # 当前阶段 1-7
    stage_name: str                     # 阶段名称
    error: Optional[str]                # 错误信息
    messages: List[str]                 # 日志/消息


def get_initial_state(project_name: str = "未命名小说",
                      base_token: str = "",
                      record_id: str = "") -> NovelState:
    """创建初始状态"""
    return {
        "project_name": project_name,
        "base_token": base_token,
        "record_id": record_id,

        "topic_research_notes": "",
        "target_platforms": [],
        "genre": "",

        "platform_policy": "",
        "recommended_platform": "",

        "outline": "",
        "target_word_count": 100000,
        "character_bios": "",
        "chapter_plan": "",

        "current_chapter": 0,
        "written_content": "",
        "written_word_count": 0,
        "last_chapter_content": "",

        "optimization_round": 0,
        "optimization_history": [],
        "need_rewrite": False,
        "feedback": "",
        "quality_score": 0.0,

        "review_opinion": "",
        "waist_features": "",
        "review_passed": False,

        "compliance_status": "未审查",
        "compliance_notes": "",
        "compliance_passed": False,

        "current_stage": 1,
        "stage_name": "① 调研选题",
        "error": None,
        "messages": [],
    }