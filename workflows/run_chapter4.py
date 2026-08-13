import sys, time, subprocess, json, re
sys.path.insert(0, "/home/ubuntu/novel-agent")

from agents.novel_agents import (
    run_agent4_writing, run_agent5_optimizer,
    run_agent6_review, run_agent7_compliance, run_typo_check
)
from state.novel_state import get_initial_state

state = get_initial_state(project_name="我在市异局当共感破案人")
state["genre"] = "都市悬疑"
state["target_platforms"] = ["番茄小说", "七猫小说", "起点中文网"]
state["outline"] = "市井异常事务处理局（市异局）林深共感能力者 苏晓前刑警 梧桐巷怨血案 凶手蝎子纹身"
state["character_bios"] = "林深: 共感能力者/社畜; 苏晓: 前刑警/市异局外勤"
state["written_content"] = """第一章已写完（梧桐巷的怨血）
第二章已写完（怨血初体验）
第三章已写完（蝎子纹身）"""
state["written_word_count"] = 8795
state["current_chapter"] = 3
state["last_chapter_content"] = "黑暗里传来一声轻笑，苏晓举枪对着巷子深处，凶手就在不到十米的黑暗里，已经盯上了苏晓。"

print("="*50)
print("📝 第4章 开始全自动创作...")
print("="*50)

# Step 1: 创作
t0 = time.time()
state = {**state, **run_agent4_writing(state)}
ch_content = state.get("last_chapter_content", "")
wc = state.get("written_word_count", 0)
print(f"✅ 第{state.get('current_chapter')}章 完成 | 总字数: {wc} | 耗时: {time.time()-t0:.0f}s")

# 错别字自检
typo = run_typo_check(ch_content)
if typo.get("total_errors_fixed", 0) > 0:
    print(f"   📝 错别字自检: 修正 {typo['total_errors_fixed']} 处")
    state["last_chapter_content"] = typo["corrected_text"]

# Step 2: Loop优化
for i in range(5):
    t1 = time.time()
    state = {**state, **run_agent5_optimizer(state)}
    score = state.get("quality_score", 0)
    opt_r = state.get("optimization_round", 0)
    print(f"🔄 优化 Round {opt_r}: 评分 {score}/10 | 耗时: {time.time()-t1:.0f}s")
    if state.get("need_rewrite"):
        print(f"   ❌ 未达标 → 回流重写...")
        state = {**state, **run_agent4_writing(state)}
        print(f"   ✅ 重写完成")
    else:
        print(f"   ✅ 达标 → 进入审稿")
        break

# Step 3: 审稿
t2 = time.time()
state = {**state, **run_agent6_review(state)}
avg_score = state.get("quality_score", 0)
review_passed = state.get("review_passed", False)
print(f"📋 审稿: 评分 {avg_score}/10 | {'✅通过' if review_passed else '❌需修改'} | 耗时: {time.time()-t2:.0f}s")

# Step 4: 合规
t3 = time.time()
state = {**state, **run_agent7_compliance(state)}
comp_passed = state.get("compliance_passed", False)
print(f"🔒 合规: {'✅通过' if comp_passed else '❌需修改'} | 耗时: {time.time()-t3:.0f}s")

# 写入飞书
progress = min(100, int(state["written_word_count"] / state["target_word_count"] * 100))
update_payload = {
    "fields": ["已写字数", "完成进度%", "审稿意见", "合规状态", "最后更新时间"],
    "rows": [[
        state["written_word_count"],
        progress,
        f"第{state.get('current_chapter')}章: 优化{state.get('quality_score',0)}/10 审稿{avg_score}/10 合规{'✅' if comp_passed else '❌'}",
        "✅ 通过" if comp_passed else "审查中",
        "2026-07-07 22:00"
    ]]
}
cmd = [
    "lark-cli", "base", "+record-upsert",
    "--base-token", "WKu4bv99ia7Z7ys1ztXcuWFXnce",
    "--table-id", "tbl2JPk0wavufExa",
    "--record-id", "recvoHcf1Q1qbj",
    "--json", json.dumps(update_payload, ensure_ascii=False),
    "--as", "user"
]
r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
try:
    result = json.loads(r.stdout)
    print(f"\n📊 飞书更新: {'✅' if result.get('ok') else '❌'}")
except:
    print(f"\n📊 飞书更新: 响应异常")

print(f"\n{'='*50}")
print(f"🎉 第4章 全自动流程完成!")
print(f"📊 总字数: {state['written_word_count']} / {state['target_word_count']}")
print(f"📈 进度: {progress}%")
PYEOF