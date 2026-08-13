"""
7 个小说 Agent 的具体实现（v2 — 改进版）
每个 Agent 是一个函数：输入 state → 调用 LLM → 返回 state 更新

改进点（P0/P1）：
1. Agent 5 量化退出标准（≥8.0 才算通过，不再由 LLM 随口说）
2. 每个 Agent 自带验证步骤（Turn-based 自检）
3. Agent 6 拆成 3 路并行审稿（节奏/人物/腰部对标）
4. 分阶段用不同模型控制 Token
"""

import json
import re
from typing import Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage


# ── LLM 配置（按阶段切换模型，节省 Token） ──
# 从环境变量读取，或使用默认值
import os
DEFAULT_API_KEY = os.environ.get("OPENAI_API_KEY", "2Den1zPlhDoXSZnEUcZ00CR5pOrjZhEUNvv4qNN4MzmDTHhhN9KoFZMzYpT08fyDC")
DEFAULT_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.stepfun.com/step_plan/v1")

LLM_CHEAP = ChatOpenAI(           # 调研/政策/合规 — 不需要创造性
    model="step-3.7-flash",
    api_key=DEFAULT_API_KEY,
    base_url=DEFAULT_BASE_URL,
    temperature=0.3,
)
LLM_MEDIUM = ChatOpenAI(          # 规划/审稿 — 中等推理
    model="step-3.7-flash",
    api_key=DEFAULT_API_KEY,
    base_url=DEFAULT_BASE_URL,
    temperature=0.5,
)
LLM_BEST = ChatOpenAI(            # 写作 — 需要创造性
    model="step-3.7-flash",
    api_key=DEFAULT_API_KEY,
    base_url=DEFAULT_BASE_URL,
    temperature=0.8,
    max_tokens=8192,               # 加大输出上限，确保章节完整
)


def call_llm(system_prompt: str, user_prompt: str,
             llm=None, json_mode: bool = True, max_retries: int = 2) -> str:
    """调用 LLM 的统一入口，带自动重试和 JSON 提取"""
    llm = llm or LLM_BEST
    for attempt in range(max_retries + 1):
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
            response = llm.invoke(messages)
            raw = response.content

            # 从文本中提取 JSON（兼容不支持 json_mode 的 API）
            if json_mode:
                raw_stripped = raw.strip()
                if not raw_stripped.startswith("{"):
                    json_match = re.search(r'\{.*\}', raw_stripped, re.DOTALL)
                    if json_match:
                        return json_match.group()
            return raw
        except Exception as e:
            if attempt == max_retries:
                return "{}"
    return "{}"


# ══════════════════════════════════════════════════
# 通用 Agent 验证步骤（Turn-based 自检）
# ══════════════════════════════════════════════════

VERIFY_STEP_TEMPLATE = """你是一个质量检查员。检查以下内容是否满足所有标准。

检查清单：
{checklist}

待检查的内容：
{content}

输出 JSON 格式（不要加花括号转义）：
{{
  "all_passed": true/false,
  "failed_items": ["未通过的项目"],
  "verdict": "一句话总结"
}}"""


def verify_output(content: str, checklist: list, llm=None) -> dict:
    """通用验证步骤：检查输出是否满足标准"""
    result = call_llm(
        VERIFY_STEP_TEMPLATE.format(
            checklist="\n".join(f"□ {item}" for item in checklist),
            content=content[:3000],
        ),
        "逐条检查，输出验证结果",
        llm=llm or LLM_CHEAP,
    )
    return json.loads(result)


# ══════════════════════════════════════════════════
# 章节质量验证标准（SKILL.md 风格）
# ══════════════════════════════════════════════════

CHAPTER_QUALITY_CHECKLIST = [
    "章节字数 ≥ 3000 字",
    "标题包含吸引力关键词或悬念",
    "章节末尾最后 3 句包含悬念/钩子",
    "无连续 3 句以上的纯对话（节奏问题）",
    "无双重形容词或冗余修饰",
    "无角色OOC（人设走形）",
    "与前章时间线连续",
    "使用了至少 2 种感官描写（视觉/听觉/触觉等）",
]


# ═════════════════════════════════════════════
# 错别字自检（循环直到无错别字）
# ═════════════════════════════════════════════

SYSTEM_TYPO_CHECK = """你是一名专业文字校对。检查以下文本中的错别字、语病、中英混用问题。

逐字检查以下项目：
1. 错别字（如"爆"写成"暴"、"在"写成"再"、"地"写成"的"等）
2. 中英混用（如"trained"应为"训练"、"file"应为"文件"）
3. 病句（主谓宾搭配不当）
4. 标点符号错误（引号不匹配、逗号句号混用等）

输出 JSON：
{
  "has_errors": true/false,
  "errors": [
    {"position": "第X段附近", "error": "错误原文", "correction": "修正后文本", "type": "错别字|中英混用|病句|标点"}
  ],
  "corrected_text": "修正后的完整文本（如果没有错误则保持原文）",
  "error_count": 3
}"""


def run_typo_check(text: str, max_rounds: int = 5) -> dict:
    """循环错别字检查，直到无错误或达到最大轮次"""
    current_text = text
    total_errors = 0

    for round_i in range(max_rounds):
        raw = call_llm(
            SYSTEM_TYPO_CHECK,
            f"第 {round_i + 1} 轮校对。检查以下文本中的错别字、中英混用、病句：\n\n{current_text[:3000]}",
            llm=LLM_CHEAP,
        )
        # 提取 JSON（兼容多余输出和多对象拼接）
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not json_match:
            return {"corrected_text": current_text, "total_errors_fixed": 0, "rounds": round_i + 1, "clean": True}
        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError:
            # 如果有多个 JSON 对象拼接，只取第一个
            first_brace = raw.find('{')
            if first_brace == -1:
                return {"corrected_text": current_text, "total_errors_fixed": 0, "rounds": round_i + 1, "clean": True}
            # 找到第一个完整JSON对象
            depth = 0
            for i in range(first_brace, len(raw)):
                if raw[i] == '{': depth += 1
                elif raw[i] == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            data = json.loads(raw[first_brace:i+1])
                        except:
                            return {"corrected_text": current_text, "total_errors_fixed": 0, "rounds": round_i + 1, "clean": True}
                        break
        has_errors = data.get("has_errors", False)
        count = data.get("error_count", 0)
        corrected = data.get("corrected_text", "")

        if not has_errors or count == 0:
            return {
                "corrected_text": current_text,
                "total_errors_fixed": total_errors,
                "rounds": round_i + 1,
                "clean": True,
            }

        total_errors += count
        if corrected and len(corrected) > 100:
            current_text = corrected
        else:
            # 修复文本无效时，逐条替换错误
            for err in data.get("errors", []):
                err_text = err.get("error", "")
                corr_text = err.get("correction", "")
                if err_text and corr_text and err_text in current_text:
                    current_text = current_text.replace(err_text, corr_text, 1)

    return {
        "corrected_text": current_text,
        "total_errors_fixed": total_errors,
        "rounds": max_rounds,
        "clean": False,
    }


# ═════════════════════════════════════════════
# Agent 1: 选题调研引擎（用便宜模型）
# ═════════════════════════════════════════════

SYSTEM_TOPIC_RESEARCH = """你是一个网文选题调研专家。你的任务是对主流网文平台进行调研，
输出各平台当前热门题材趋势分析。

输出 JSON 格式：
{
  "genre": "推荐题材",
  "platform_analysis": [
    {"platform": "番茄小说", "hot_genres": ["..."], "trend": "..."},
    {"platform": "七猫小说", "hot_genres": ["..."], "trend": "..."},
    {"platform": "起点中文网", "hot_genres": ["..."], "trend": "..."}
  ],
  "blue_ocean_topics": ["蓝海选题1", "蓝海选题2"],
  "research_notes": "详细的调研笔记"
}"""

TOPIC_RESEARCH_CHECKLIST = [
    "覆盖了至少 3 个平台",
    "每个平台有明确的热门题材分析",
    "有至少 1 个蓝海选题推荐",
    "研究笔记包含具体的数据或趋势描述",
]


def run_agent1_topic_research(state: dict) -> dict:
    """Agent 1: 调研选题 + 自检"""
    # 1. 执行
    result = call_llm(
        SYSTEM_TOPIC_RESEARCH,
        f"调研当前网文市场热门题材趋势，输出分析报告。项目名称：{state['project_name']}",
        llm=LLM_CHEAP,
    )
    data = json.loads(result)

    # 2. 验证（Turn-based 自检）
    verify = verify_output(
        json.dumps(data, ensure_ascii=False),
        TOPIC_RESEARCH_CHECKLIST,
        LLM_CHEAP,
    )
    if not verify.get("all_passed", False):
        # 自检未通过 → 补充一条消息，仍继续（不阻塞流程）
        return {
            "topic_research_notes": data.get("research_notes", "")
                + f"\n\n⚠️ 自检提示：{verify.get('verdict', '')}",
            "genre": data.get("genre", ""),
            "target_platforms": [p["platform"] for p in data.get("platform_analysis", [])],
            "current_stage": 2,
            "stage_name": "② 平台政策研究",
            "messages": [f"选题调研自检未全部通过: {verify.get('failed_items', [])}"],
        }

    return {
        "topic_research_notes": data.get("research_notes", ""),
        "genre": data.get("genre", ""),
        "target_platforms": [p["platform"] for p in data.get("platform_analysis", [])],
        "current_stage": 2,
        "stage_name": "② 平台政策研究",
    }


# ═════════════════════════════════════════════
# Agent 2: 平台政策研究员（用便宜模型）
# ═════════════════════════════════════════════

SYSTEM_POLICY_ANALYSIS = """你是网文平台政策研究专家。
分析各平台对特定题材的签约政策、收益模式、推荐算法偏好。

输出 JSON：
{
  "platform_policy_summary": "各平台政策总结",
  "platform_comparison": [
    {"platform": "名称", "policy": "签约政策", "revenue_model": "收益模式",
     "algorithm_preference": "算法偏好", "entry_barrier": "门槛高低"}
  ],
  "recommended_platform": "推荐平台+理由"
}"""

POLICY_CHECKLIST = [
    "覆盖了至少 3 个平台",
    "每个平台有签约政策和收益模式说明",
    "有推荐平台及具体理由",
]


def run_agent2_policy_analysis(state: dict) -> dict:
    """Agent 2: 平台政策研究 + 自检"""
    genre = state.get("genre", "未指定")
    result = call_llm(
        SYSTEM_POLICY_ANALYSIS,
        f"题材：{genre}\n目标平台：{', '.join(state.get('target_platforms', []))}\n输出各平台政策分析",
        llm=LLM_CHEAP,
    )
    data = json.loads(result)

    verify = verify_output(json.dumps(data, ensure_ascii=False), POLICY_CHECKLIST, LLM_CHEAP)

    return {
        "platform_policy": data.get("platform_policy_summary", ""),
        "recommended_platform": data.get("recommended_platform", ""),
        "current_stage": 3,
        "stage_name": "③ 写作计划",
        "messages": [] if verify.get("all_passed") else [f"政策研究自检: {verify.get('verdict', '')}"],
    }


# ═════════════════════════════════════════════
# Agent 3: 写作规划师（用中等模型）
# ═════════════════════════════════════════════

SYSTEM_PLANNING = """你是小说写作规划师。根据选题调研和平台策略，
输出完整的写作规划。包括：世界观设定、人物小传、分章大纲。

输出 JSON：
{
  "outline": "完整大纲和世界观设定",
  "character_bios": "人物小传",
  "chapter_plan": "100-200章的分章大纲",
  "target_word_count": 100000
}"""

PLANNING_CHECKLIST = [
    "有完整的世界观设定",
    "有至少 3 个主要人物的小传",
    "分章大纲覆盖 100 章以上",
    "目标字数在 5 万-300 万之间",
]


def run_agent3_planning(state: dict) -> dict:
    """Agent 3: 写作规划 + 自检"""
    result = call_llm(
        SYSTEM_PLANNING,
        f"题材：{state.get('genre', '')}\n"
        f"平台策略：{state.get('platform_policy', '')}\n"
        f"推荐平台：{state.get('recommended_platform', '')}\n"
        f"输出完整写作规划",
        llm=LLM_MEDIUM,
    )
    data = json.loads(result)

    verify = verify_output(json.dumps(data, ensure_ascii=False), PLANNING_CHECKLIST, LLM_CHEAP)

    return {
        "outline": data.get("outline", ""),
        "character_bios": data.get("character_bios", ""),
        "chapter_plan": data.get("chapter_plan", ""),
        "target_word_count": data.get("target_word_count", 100000),
        "current_stage": 4,
        "stage_name": "④ 写作中",
        "messages": [] if verify.get("all_passed") else [f"写作规划自检: {verify.get('verdict', '')}"],
    }


# ═════════════════════════════════════════════
# Agent 4: 内容创作 Agent（用最强模型）
# ═════════════════════════════════════════════

SYSTEM_WRITING = """你是小说创作专家。根据大纲和人物设定进行小说章节创作。
需要保持文风一致、每章结尾设置钩子。

要求：
- 每章字数控制在 2000-2500 字之间，不要超过 2500 字
- 标题要有悬念感、吸引力（4-8个字）
- 结尾留钩子，让读者期待下一章
- 保持与前面章节的连贯性

输出 JSON：
{
  "chapter_title": "本章标题（4-8个字）",
  "chapter_content": "本章完整内容（2000-2500字）",
  "word_count": 2200,
  "chapter_summary": "本章概要",
  "cliffhanger": "本章钩子"
}"""


def run_agent4_writing(state: dict) -> dict:
    """Agent 4: 内容创作 + 错别字自检（查出没有为止）+ 质量验证"""
    chapter_num = state.get("current_chapter", 0) + 1

    # 1. 执行
    result = call_llm(
        SYSTEM_WRITING,
        f"大纲：{state.get('outline', '')[:500]}\n"
        f"人物：{state.get('character_bios', '')[:300]}\n"
        f"当前写到第 {state.get('current_chapter', 0)} 章\n"
        f"现在写第 {chapter_num} 章\n"
        f"上一章内容：{state.get('last_chapter_content', '')[-200:]}\n"
        f"输出本章内容",
        llm=LLM_BEST,
    )
    data = json.loads(result)
    content = data.get("chapter_content", "")

    # 2. 错别字自检（循环直到查出为0）
    typo_result = run_typo_check(content)
    if typo_result.get("corrected_text"):
        content = typo_result["corrected_text"]
    if typo_result.get("total_errors_fixed", 0) > 0:
        print(f"   📝 错别字自检：修正 {typo_result['total_errors_fixed']} 处（{typo_result['rounds']} 轮）")

    # 2. 验证（Turn-based：用便宜模型做质量检查）
    verify = verify_output(content, CHAPTER_QUALITY_CHECKLIST, LLM_CHEAP)

    # 3. 如果验证不通过，尝试自修复一次
    if not verify.get("all_passed"):
        try:
            fix_prompt = f"以下是第 {chapter_num} 章草稿，有以下问题需要修正：\n"
            for item in verify.get("failed_items", []):
                fix_prompt += f"- {item}\n"
            fix_prompt += f"\n原文：\n{content[:2000]}\n\n请修正后输出完整章节。"
            fix_result = call_llm(
                SYSTEM_WRITING + "\n注意：务必修正上述提到的所有问题，保留原文风格。",
                fix_prompt,
                llm=LLM_BEST,
            )
            if fix_result and fix_result.strip().startswith("{"):
                fixed_data = json.loads(fix_result)
                content = fixed_data.get("chapter_content", content)
        except Exception:
            pass  # 修复失败时保留原文

    prev_wc = state.get("written_word_count", 0)
    new_wc = data.get("word_count", len(content))
    return {
        "current_chapter": chapter_num,
        "last_chapter_content": content,
        "written_word_count": prev_wc + new_wc,
        "written_content": state.get("written_content", "") + "\n\n" + content,
        "current_stage": 4,
        "stage_name": "④ 写作中",
    }


# ═════════════════════════════════════════════
# Agent 5: 内容优化引擎（Loop）—— 量化退出
# ═════════════════════════════════════════════

QUALITY_PASS_THRESHOLD = 8.0   # 满分 10 分，8 分以上通过
MAX_OPTIMIZE_ROUNDS = 5        # 最多 5 轮

SYSTEM_OPTIMIZE = """你是小说质量优化专家。分析章节内容，按以下标准评分：

评分标准（满分 10 分）：
1. 节奏感（0-2分）：情节推进是否流畅，有无拖沓
2. 爽点密度（0-2分）：是否有足够的高潮和吸引力
3. 人物弧光（0-2分）：角色是否有成长和变化
4. 对话自然度（0-2分）：对话是否真实、符合人设
5. 章节钩子（0-2分）：结尾是否引人期待下一章
6. AI痕迹消除（0-2分，**加权1.5倍**）：
   - 检测并扣分项：过多的「描写性副词」（"他叹了口气" "她皱了皱眉"）、
     「面无表情/目光扫过/下意识地」等AI高频模板词、
     段落结构过于均匀（每段60-80字）、
     心理描写过于书面化、缺乏口语化破绽、
     感官描写面面俱到无一遗漏（真实人类写作会有跳跃和省略）、
     每章结尾恰好卡在悬念点（过于完美反而不真实）。
   - 加分项：有口语化破绽、有跳跃省略、段落长短不一、
     有个人风格的怪癖用词、描写有选择性侧重而非全覆盖。
   此项得分 = (2 - 检测到的AI痕迹数×0.3 + 自然度加分)，上限2分，然后×1.5加权。

总分 = 以上 6 项之和（第6项加权后），原始分 ≥ 8 分 = 通过，< 8 分 = 需要改写。

输出 JSON：
{
  "feedback": "详细优化建议，重点标注AI痕迹位置和替换方案",
  "quality_score": 7.5,
  "ai_traces_detected": ["AI痕迹1: '他下意识地'在第X段", "AI痕迹2: 段落长度过于均匀"],
  "scores": {"节奏感": 1.5, "爽点密度": 1.5, "人物弧光": 1.5, "对话自然度": 1.5, "章节钩子": 1.5, "AI痕迹消除_weighted": 2.0},
  "issues_found": ["问题1", "问题2"],
  "rewrite_instructions": "如需要重写，给出具体改写方向，特别指出如何让语言更自然、减少AI感；不需要则留空"
}"""


def run_agent5_optimizer(state: dict) -> dict:
    """Agent 5: Loop 优化——量化评分，达标才通过"""
    content = state.get("last_chapter_content", "")
    opt_round = state.get("optimization_round", 0) + 1

    result = call_llm(
        SYSTEM_OPTIMIZE,
        f"优化轮次：{opt_round}/{MAX_OPTIMIZE_ROUNDS}\n"
        f"本章内容：{content[:3000]}\n"
        f"按 6 个维度评分（第6项AI痕迹消除×1.5加权），总分≥8才通过\n"
        f"特别注意：详细标注AI撰写痕迹的具体位置和替换方案",
        llm=LLM_MEDIUM,
    )
    data = json.loads(result)
    quality_score = data.get("quality_score", 0)
    passed = quality_score >= QUALITY_PASS_THRESHOLD

    history = list(state.get("optimization_history", []))
    history.append(f"Round {opt_round}: 评分 {quality_score}/10 — {'✅ 通过' if passed else '❌ 需修改'}")

    updates = {
        "optimization_round": opt_round,
        "optimization_history": history,
        "need_rewrite": not passed,
        "feedback": data.get("feedback", ""),
        "quality_score": quality_score,
    }

    if passed:
        updates["current_stage"] = 6
        updates["stage_name"] = "⑥ 审稿"
    elif opt_round >= MAX_OPTIMIZE_ROUNDS:
        # 超限：强制通过，但标记为"勉强通过"
        updates["current_stage"] = 6
        updates["stage_name"] = "⑥ 审稿（超限强制）"
        updates["need_rewrite"] = False
        updates["messages"] = [f"⚠️ 优化超限（{MAX_OPTIMIZE_ROUNDS}轮），强制进入审稿，评分 {quality_score}/10"]
    else:
        updates["current_stage"] = 4
        updates["stage_name"] = "④ 写作中（优化回流）"

    return updates


# ═════════════════════════════════════════════
# Agent 6: 审稿与腰部对标 Agent —— 并行 3 路
# ═════════════════════════════════════════════

SYSTEM_REVIEW_RHYTHM = """你是小说节奏审稿专家。分析稿件的结构、节奏、情节推进效率。
输出 JSON：
{
  "score": 7.5,
  "findings": ["发现1", "发现2"],
  "suggestions": "修改建议"
}"""

SYSTEM_REVIEW_CHARACTER = """你是小说人物审稿专家。分析人物的塑造、对话、成长弧光。
输出 JSON：
{
  "score": 7.5,
  "findings": ["发现1", "发现2"],
  "suggestions": "修改建议"
}"""

SYSTEM_REVIEW_BENCHMARK = """你是网文腰部作品对标分析专家。
分析目标平台同类腰部作品（月票/阅读榜 50-200 名）的共性特征。
输出 JSON：
{
  "waist_features": "对标特征提炼（标题公式/开局节奏/爽点密度/人设模板）",
  "score": 7.5,
  "sim_score": "与腰部作品的相似度%",
  "suggestions": "修改建议"
}"""


def run_agent6_review(state: dict) -> dict:
    """Agent 6: 3 路并行审稿 → 汇总评分"""
    content = state.get("written_content", "")

    # 3 路并行调用（模拟，实际可用多线程）
    # 这里用同一个 LLM 串行跑，生产环境可改用 asyncio
    r1 = json.loads(call_llm(SYSTEM_REVIEW_RHYTHM,
        f"分析稿件节奏：{content[:2000]}", llm=LLM_MEDIUM))
    r2 = json.loads(call_llm(SYSTEM_REVIEW_CHARACTER,
        f"分析人物塑造：{content[:2000]}", llm=LLM_MEDIUM))
    r3 = json.loads(call_llm(SYSTEM_REVIEW_BENCHMARK,
        f"题材：{state.get('genre', '')}\n平台：{', '.join(state.get('target_platforms', []))}\n内容：{content[:2000]}",
        llm=LLM_MEDIUM))

    # 综合评分 = 3 路平均
    scores = [r1.get("score", 7), r2.get("score", 7), r3.get("score", 7)]
    avg_score = sum(scores) / len(scores)
    passed = avg_score >= 7.0

    # 汇总审稿意见
    all_findings = []
    all_findings.extend(f"【节奏】{f}" for f in r1.get("findings", []))
    all_findings.extend(f"【人物】{f}" for f in r2.get("findings", []))
    all_findings.extend(f"【对标】{f}" for f in r3.get("findings", []))

    updates = {
        "review_opinion": "\n".join(all_findings),
        "waist_features": r3.get("waist_features", ""),
        "review_passed": passed,
        "quality_score": avg_score,
    }

    if passed:
        updates["current_stage"] = 7
        updates["stage_name"] = "⑦ 合规审查"
    else:
        updates["current_stage"] = 4
        updates["stage_name"] = "④ 写作中（审稿修改）"

    return updates


# ═════════════════════════════════════════════
# Agent 7: 合规审查 Agent（用便宜模型）
# ═════════════════════════════════════════════

SYSTEM_COMPLIANCE = """你是小说合规审查专家。检查稿件是否符合各平台内容规范，
包括敏感内容、版权风险、违规信息等。

输出 JSON：
{
  "compliance_check": {
    "political_sensitive": {"risk": "low", "details": ""},
    "pornographic": {"risk": "low", "details": ""},
    "violence": {"risk": "low", "details": ""},
    "copyright": {"risk": "low", "details": ""},
    "platform_rules": {"risk": "low", "details": ""}
  },
  "compliance_notes": "合规审查详细记录",
  "compliance_passed": true,
  "issues_to_fix": ["需要修改的问题"]
}"""

COMPLIANCE_CHECKLIST = [
    "无政治敏感内容",
    "无色情低俗描写",
    "无鼓励暴力犯罪",
    "无侵犯第三方版权",
    "符合目标平台内容审核规范",
]


def run_agent7_compliance(state: dict) -> dict:
    """Agent 7: 合规审查 + 自检"""
    content = state.get("written_content", "")
    result = call_llm(
        SYSTEM_COMPLIANCE,
        f"审查稿件内容合规性：\n{content[:3000]}\n"
        f"平台：{', '.join(state.get('target_platforms', []))}\n"
        f"输出合规审查报告",
        llm=LLM_CHEAP,
    )
    data = json.loads(result)
    passed = data.get("compliance_passed", False)

    # 自检
    verify = verify_output(
        json.dumps(data, ensure_ascii=False),
        COMPLIANCE_CHECKLIST,
        LLM_CHEAP,
    )

    status = "✅ 通过" if passed else "需修改"
    stage = "✅ 完结" if passed else "⑦ 合规审查（待修改）"

    return {
        "compliance_status": status,
        "compliance_notes": data.get("compliance_notes", ""),
        "compliance_passed": passed,
        "current_stage": 8 if passed else 7,
        "stage_name": stage,
        "messages": [] if verify.get("all_passed") else [f"合规自检: {verify.get('verdict', '')}"],
    }


# ═════════════════════════════════════════════
# Agent 9: 书名与点击率调研专家
# ═════════════════════════════════════════════

SYSTEM_BOOK_TITLE = """你是网文书名与点击率研究专家。你的任务是根据小说内容和目标平台特性，
推荐高点击率书名，并为每章撰写出能吸引读者点击的100字简介。

核心方法论：
1. 番茄系书名：突出「身份反差+金手指+爽点」，如"我在XX当XX"
2. 七猫系书名：突出「情感共鸣+悬疑钩子」，如"XX背后的秘密"
3. 起点系书名：突出「世界观+格局」，如"XX事务所"
4. 点击率公式：高辨识度标签 + 具体场景/冲突 + 情绪价值

输出 JSON：
{
  "title_recommendations": [
    {
      "title": "推荐书名",
      "platform": "主要适配平台",
      "click_rate_estimate": "预估点击率优势",
      "reasoning": "为什么这个书名有效",
      "tags": ["标签1", "标签2", "标签3"]
    }
  ],
  "best_title": "最终推荐书名",
  "chapter_blurbs": [
    {
      "chapter": 1,
      "title": "第1章标题",
      "blurb": "100字左右吸引人的简介"
    },
    {
      "chapter": 2,
      "title": "第2章标题",
      "blurb": "100字简介"
    }
  ],
  "analysis_notes": "书名策略分析"
}"""


def run_agent9_book_title(state: dict) -> dict:
    """Agent 9: 书名调研 + 章节简介"""
    content = state.get("written_content", "")
    outline = state.get("outline", "")
    platforms = state.get("target_platforms", ["番茄小说", "七猫小说", "起点中文网"])

    result = call_llm(
        SYSTEM_BOOK_TITLE,
        f"小说内容（前2000字）：{content[:2000]}\n"
        f"大纲：{outline[:500]}\n"
        f"目标平台：{', '.join(platforms)}\n"
        f"当前书名：{state.get('project_name', '未命名')}\n\n"
        f"请输出3-5个高点击率书名推荐，以及已写章节的100字吸引人简介。",
        llm=LLM_MEDIUM,
    )
    data = json.loads(result)

    # 生成章节简介列表
    chapter_blurbs = data.get("chapter_blurbs", [])
    blurbs_text = "\n\n".join([
        f"第{b['chapter']}章 {b.get('title', '')}\n{b.get('blurb', '')}"
        for b in chapter_blurbs
    ])

    return {
        "book_title": data.get("best_title", state.get("project_name", "")),
        "title_recommendations": json.dumps(data.get("title_recommendations", []), ensure_ascii=False),
        "chapter_blurbs": blurbs_text,
        "analysis_notes": data.get("analysis_notes", ""),
    }