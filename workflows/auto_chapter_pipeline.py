"""
第二章全自动写作流水线
从现有大纲自动：创作 → Loop优化 → 回流 → 审稿 → 合规 → 写回飞书
"""

import json, subprocess, time, os, sys
sys.path.insert(0, "/home/ubuntu/novel-agent")

from agents.novel_agents import (
    run_agent4_writing, run_agent5_optimizer,
    run_agent6_review, run_agent7_compliance,
)
from state.novel_state import get_initial_state

# ── 配置 ──
BASE_TOKEN = "WKu4bv99ia7Z7ys1ztXcuWFXnce"
TABLE_ID = "tbl2JPk0wavufExa"
RECORD_ID = "recvoHcf1Q1qbj"
MAX_CHAPTERS = 3       # 本次自动写几章

def feishu_save(updates: dict):
    """写回飞书"""
    cmd = ["lark-cli", "base", "+record-upsert",
           "--base-token", BASE_TOKEN, "--table-id", TABLE_ID,
           "--record-id", RECORD_ID,
           "--json", json.dumps(updates, ensure_ascii=False),
           "--as", "user"]
    subprocess.run(cmd, capture_output=True, text=True, timeout=30)

def run_auto_pipeline():
    state = get_initial_state(project_name="都市悬疑小说（市异局）")
    state["genre"] = "都市悬疑"
    state["target_platforms"] = ["番茄小说", "七猫小说", "起点中文网"]
    state["outline"] = """
【世界观】市井异常事务处理局（市异局），处理都市异常事件
【男主】林深，24岁，共感能力者，奶奶尿毒症需透析
【女主】苏晓，27岁，前刑警，市异局外勤
【主线】150章/10万字，适配番茄节奏
""".strip()
    state["character_bios"] = "林深: 共感能力者/社畜; 苏晓: 前刑警/外勤"
    state["written_content"] = "第一章已写完（梧桐巷的怨血）"

    for ch in range(2, MAX_CHAPTERS + 1):
        print(f"\n{'='*50}")
        print(f"📝 第 {ch} 章 开始创作...")
        print(f"{'='*50}")

        # ── Step 1: 创作 ──
        t0 = time.time()
        state = {**state, **run_agent4_writing(state)}
        ch_content = state.get("last_chapter_content", "")
        wc = state.get("written_word_count", 0)
        print(f"✅ 第 {ch} 章 完成  |  总字数: {wc}  |  耗时: {time.time()-t0:.0f}s")
        feishu_save({"已写字数": wc, "最后更新时间": "2026-07-07 18:30"})

        # ── Step 2: Loop 优化（最多5轮） ──
        for round_i in range(5):
            t1 = time.time()
            state = {**state, **run_agent5_optimizer(state)}
            score = state.get("quality_score", 0)
            opt_r = state.get("optimization_round", 0)
            print(f"🔄 优化 Round {opt_r}: 评分 {score}/10  |  耗时: {time.time()-t1:.0f}s")

            if state.get("need_rewrite"):
                print(f"   ❌ 未达标 → 回流重写...")
                state = {**state, **run_agent4_writing(state)}
                new_wc = state.get("written_word_count", 0)
                print(f"   ✅ 重写完成  总字数: {new_wc}")
                feishu_save({"已写字数": new_wc, "最后更新时间": "2026-07-07 18:30"})
            else:
                print(f"   ✅ 达标 → 进入审稿")
                break

        # ── Step 3: 审稿 ──
        t2 = time.time()
        state = {**state, **run_agent6_review(state)}
        review_passed = state.get("review_passed", False)
        avg_score = state.get("quality_score", 0)
        print(f"📋 审稿: 评分 {avg_score}/10  |  {'✅通过' if review_passed else '❌需修改'}  |  耗时: {time.time()-t2:.0f}s")

        # ── Step 4: 合规 ──
        t3 = time.time()
        state = {**state, **run_agent7_compliance(state)}
        comp_passed = state.get("compliance_passed", False)
        print(f"🔒 合规: {'✅通过' if comp_passed else '❌需修改'}  |  耗时: {time.time()-t3:.0f}s")

        # ── 写入飞书 ──
        progress = min(100, int(state["written_word_count"] / state["target_word_count"] * 100))
        feishu_save({
            "已写字数": state["written_word_count"],
            "完成进度%": progress,
            "审稿意见": f"第{ch}章: 优化评分{state.get('quality_score',0)}/10 | 审稿{'✅' if review_passed else '❌'} | 合规{'✅' if comp_passed else '❌'}",
            "合规状态": "✅ 通过" if comp_passed else "审查中",
            "最后更新时间": "2026-07-07 18:30",
        })
        print(f"\n📊 进度: {progress}% ({state['written_word_count']}/{state['target_word_count']})")

    print(f"\n{'='*50}")
    print(f"🎉 完成! 共写 {MAX_CHAPTERS-1} 章")
    print(f"📊 总字数: {state['written_word_count']} / {state['target_word_count']}")
    print(f"📈 进度: {int(state['written_word_count']/state['target_word_count']*100)}%")

if __name__ == "__main__":
    run_auto_pipeline()