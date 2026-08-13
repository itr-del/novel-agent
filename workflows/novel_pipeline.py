"""
小说 Agent 系统 · 主控流程
LangGraph StateGraph 编排 7 个 Agent
"""

import json
from typing import Literal
from langgraph.graph import StateGraph, END
from state.novel_state import NovelState, get_initial_state
from agents.novel_agents import (
    run_agent1_topic_research,
    run_agent2_policy_analysis,
    run_agent3_planning,
    run_agent4_writing,
    run_agent5_optimizer,
    run_agent6_review,
    run_agent7_compliance,
)
from utils.feishu_base import sync_to_base, update_stage


# ── 路由函数：根据状态决定下一步 ──

def route_after_agent1(state: dict) -> str:
    return "agent2_policy" if state.get("topic_research_notes") else END


def route_after_agent2(state: dict) -> str:
    return "agent3_planning" if state.get("platform_policy") else END


def route_after_agent3(state: dict) -> str:
    return "agent4_writing" if state.get("outline") else END


def route_after_agent4(state: dict) -> str:
    """写作后进入优化。如果章节短于 100 字，跳过优化"""
    content = state.get("last_chapter_content", "")
    if len(content) < 100:
        return END  # 空内容，结束
    return "agent5_optimize"


def route_after_agent5(state: dict) -> str:
    """Agent 5 的路由（量化退出）：
    - 评分 ≥ 8.0 → 审稿
    - 评分 < 8.0 且轮次 ≤ 5 → 回流改写
    - 评分 < 8.0 且轮次 > 5 → 强制进审稿
    """
    if state.get("need_rewrite") and state.get("optimization_round", 0) < 5:
        return "agent4_writing_loop"
    elif state.get("current_stage") == 6:
        return "agent6_review"
    return END


def route_after_agent6(state: dict) -> str:
    """审稿路由：不通过 → 回流修改；通过 → 合规审查"""
    if state.get("current_stage") == 4:
        return "agent4_writing_review"
    elif state.get("current_stage") == 7:
        return "agent7_compliance"
    return END


def route_after_agent7(state: dict) -> str:
    """合规审查完成 → 结束"""
    return END


# ── 写入飞书 Base 的中间步骤 ──

def sync_state_to_base(state: dict) -> dict:
    """将当前 Agent 的输出同步到多维表格"""
    updates = {}

    # 映射 state 字段 → 表格字段名
    field_map = {
        "调研选题笔记": "topic_research_notes",
        "平台政策与策略": "platform_policy",
        "写作计划/大纲": "outline",
        "已写字数": "written_word_count",
        "完成进度%": None,  # 特殊计算
        "Loop优化记录": None,
        "审稿意见": "review_opinion",
        "腰部作品特征提炼": "waist_features",
        "合规状态": "compliance_status",
        "合规审查记录": "compliance_notes",
    }

    # 特殊处理进度
    if state.get("target_word_count", 0) > 0:
        progress = min(100, int(state["written_word_count"] / state["target_word_count"] * 100))
        updates["完成进度%"] = progress

    # 特殊处理质量评分
    if state.get("quality_score", 0) > 0:
        updates["审稿意见"] = f"质量评分: {state['quality_score']}/10\n" + state.get("review_opinion", "")[:3000]

    # 映射
    for table_field, state_key in field_map.items():
        if state_key and state.get(state_key):
            value = state[state_key]
            if isinstance(value, list):
                # Loop优化记录 → 连接成文本
                updates[table_field] = "\n".join(value[-5:]) if state_key == "optimization_history" else value
            elif isinstance(value, str) and len(value) > 50000:
                updates[table_field] = value[:50000]
            elif isinstance(value, (str, int, float)):
                updates[table_field] = value

    # 更新阶段
    update_stage(state.get("record_id", ""), state.get("stage_name", ""))

    # 写回
    if updates and state.get("record_id"):
        sync_to_base(updates, state["record_id"])

    return {}


# ── 构建 LangGraph ──

def build_novel_graph() -> StateGraph:
    """构建小说写作 7-Agent LangGraph"""

    workflow = StateGraph(NovelState)

    # ── 添加节点 ──
    workflow.add_node("agent1_topic_research", run_agent1_topic_research)
    workflow.add_node("agent2_policy", run_agent2_policy_analysis)
    workflow.add_node("agent3_planning", run_agent3_planning)
    workflow.add_node("agent4_writing", run_agent4_writing)
    workflow.add_node("agent4_writing_loop", run_agent4_writing)   # 优化回流写作
    workflow.add_node("agent4_writing_review", run_agent4_writing) # 审稿修改写作
    workflow.add_node("agent5_optimize", run_agent5_optimizer)
    workflow.add_node("agent6_review", run_agent6_review)
    workflow.add_node("agent7_compliance", run_agent7_compliance)
    workflow.add_node("sync", sync_state_to_base)

    # ── 设置入口 ──
    workflow.set_entry_point("agent1_topic_research")

    # ── 连接边 ──
    # ① → ② → ③ → ④
    workflow.add_conditional_edges("agent1_topic_research", route_after_agent1)
    workflow.add_conditional_edges("agent2_policy", route_after_agent2)
    workflow.add_conditional_edges("agent3_planning", route_after_agent3)

    # ④ → ⑤（写作后进入优化）
    workflow.add_conditional_edges("agent4_writing", route_after_agent4)
    # ④(回流) → ⑤
    workflow.add_conditional_edges("agent4_writing_loop", route_after_agent4)
    workflow.add_conditional_edges("agent4_writing_review", route_after_agent4)

    # ⑤ → ④(回流) 或 ⑤ → ⑥(审稿)
    workflow.add_conditional_edges("agent5_optimize", route_after_agent5)

    # ⑥ → ④(审稿不通过) 或 ⑥ → ⑦(合规)
    workflow.add_conditional_edges("agent6_review", route_after_agent6)

    # ⑦ → 结束
    workflow.add_conditional_edges("agent7_compliance", route_after_agent7)

    # 每次 Agent 完成后同步到飞书
    for node in ["agent2_policy", "agent3_planning", "agent4_writing",
                 "agent5_optimize", "agent6_review", "agent7_compliance"]:
        workflow.add_edge(node, "sync")

    workflow.add_edge("sync", END)

    return workflow.compile()


def run_novel_pipeline(project_name: str = "未命名小说",
                       base_token: str = "",
                       record_id: str = "",
                       max_steps: int = 20) -> dict:
    """运行完整的小说写作流水线"""
    graph = build_novel_graph()
    initial = get_initial_state(
        project_name=project_name,
        base_token=base_token,
        record_id=record_id,
    )
    result = graph.invoke(initial, {"recursion_limit": max_steps})
    return result


# ── 命令行入口 ──

if __name__ == "__main__":
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else "测试小说"
    print(f"🚀 启动小说写作流水线: {name}")
    final = run_novel_pipeline(project_name=name)
    print(f"\n✅ 完成！最终阶段: {final.get('stage_name', 'unknown')}")
    print(f"📊 已写: {final.get('written_word_count', 0)} / {final.get('target_word_count', 0)} 字")
    print(f"📝 最后内容: {final.get('last_chapter_content', '')[:100]}...")