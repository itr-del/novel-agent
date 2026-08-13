#!/usr/bin/env python3
"""
第4章 Workflow 执行脚本（日志到文件版）
"""
import sys, time, json, traceback, os
sys.path.insert(0, "/home/ubuntu/novel-agent")

LOG_FILE = "/home/ubuntu/novel-agent/chapter4_progress.log"

def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def main():
    # 清空日志
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("")
    
    log("=" * 60)
    log("📝 第4章 Workflow 启动")
    log("=" * 60)
    
    from agents.novel_agents import (
        run_agent4_writing, run_agent5_optimizer,
        run_agent6_review, run_agent7_compliance
    )
    from state.novel_state import get_initial_state
    
    start_time = time.time()
    
    # 初始化状态
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
    
    # ========== Step 1: Agent 4 写作 ==========
    log("\n📝 Step 1: Agent 4 写作...")
    t0 = time.time()
    try:
        state = {**state, **run_agent4_writing(state)}
        wc = state.get("written_word_count", 0)
        log(f"✅ Agent4 完成 | 第{state.get('current_chapter')}章 | 总字数: {wc} | 耗时: {time.time()-t0:.0f}s")
        _save_state(state, "step1_after_agent4.json")
    except Exception as e:
        log(f"❌ Agent4 失败: {e}")
        traceback.print_exc()
        _save_state(state, "step1_error.json")
        return
    
    # ========== Step 2: 简化错别字检查（1轮） ==========
    log("\n📝 Step 2: 错别字检查（1轮）...")
    t1 = time.time()
    try:
        import re
        from agents.novel_agents import call_llm
        ch = state.get("last_chapter_content", "")
        raw = call_llm(
            "你是专业校对。检查错别字、中英混用、病句、标点。输出JSON：{\"has_errors\":true/false,\"corrected_text\":\"\",\"error_count\":0}",
            f"检查：{ch[:3000]}",
            max_retries=1
        )
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
            if data.get("corrected_text") and len(data.get("corrected_text", "")) > 100:
                state["last_chapter_content"] = data["corrected_text"]
                log(f"   📝 修正 {data.get('error_count', 0)} 处")
            else:
                log("   ✅ 未发现明显错误")
        else:
            log("   ⚠️ 无法解析校对结果")
        log(f"   ⏱ 耗时: {time.time()-t1:.0f}s")
        _save_state(state, "step2_after_typo.json")
    except Exception as e:
        log(f"   ⚠️ 错别字检查异常: {e}")
    
    # ========== Step 3: Agent 5 优化 Loop ==========
    log("\n🔄 Step 3: Agent 5 质量优化 Loop（最多5轮，≥8分通过）...")
    for i in range(5):
        t2 = time.time()
        try:
            state = {**state, **run_agent5_optimizer(state)}
            score = state.get("quality_score", 0)
            opt_r = state.get("optimization_round", 0)
            log(f"   Round {opt_r}: 评分 {score:.1f}/10 | 耗时: {time.time()-t2:.0f}s")
            
            if state.get("need_rewrite"):
                log(f"   ❌ 未达标（需≥8.0） → 回流重写...")
                t3 = time.time()
                state = {**state, **run_agent4_writing(state)}
                log(f"   ✅ 重写完成 | 耗时: {time.time()-t3:.0f}s")
                _save_state(state, f"step3_rewrite_round{opt_r}.json")
            else:
                log(f"   ✅ 达标（≥8.0） → 进入审稿")
                break
        except Exception as e:
            log(f"   ❌ 优化异常: {e}")
            traceback.print_exc()
            break
        _save_state(state, f"step3_after_opt_round{opt_r}.json")
    
    # ========== Step 4: Agent 6 审稿 ==========
    log("\n📋 Step 4: Agent 6 三路审稿...")
    t4 = time.time()
    try:
        state = {**state, **run_agent6_review(state)}
        avg_score = state.get("quality_score", 0)
        review_passed = state.get("review_passed", False)
        log(f"   评分: {avg_score:.1f}/10 | {'✅ 通过' if review_passed else '❌ 需修改'} | 耗时: {time.time()-t4:.0f}s")
        if state.get("review_opinion"):
            opinion = state["review_opinion"][:300]
            log(f"   审稿意见: {opinion}...")
        _save_state(state, "step4_after_review.json")
    except Exception as e:
        log(f"   ❌ 审稿异常: {e}")
        traceback.print_exc()
    
    # ========== Step 5: Agent 7 合规 ==========
    log("\n🔒 Step 5: Agent 7 合规审查...")
    t5 = time.time()
    try:
        state = {**state, **run_agent7_compliance(state)}
        comp_passed = state.get("compliance_passed", False)
        log(f"   合规: {'✅ 通过' if comp_passed else '❌ 需修改'} | 耗时: {time.time()-t5:.0f}s")
        if state.get("compliance_notes"):
            log(f"   记录: {state['compliance_notes'][:200]}...")
        _save_state(state, "step5_after_compliance.json")
    except Exception as e:
        log(f"   ❌ 合规异常: {e}")
        traceback.print_exc()
    
    # ========== 总结 ==========
    total_time = time.time() - start_time
    log("\n" + "=" * 60)
    log("🎉 第4章 Workflow 执行完毕!")
    log(f"📊 总字数: {state['written_word_count']} / {state['target_word_count']}")
    progress = min(100, int(state["written_word_count"] / state["target_word_count"] * 100))
    log(f"📈 进度: {progress}%")
    log(f"⏱ 总耗时: {total_time:.0f}s ({total_time/60:.1f}分钟)")
    log(f"📋 最后阶段: {state.get('stage_name', '')}")
    log("=" * 60)
    
    # 保存最终结果
    result = {
        "chapter": state.get("current_chapter"),
        "content": state.get("last_chapter_content", ""),
        "word_count": state.get("written_word_count"),
        "total_word_count": state.get("target_word_count"),
        "progress_percent": progress,
        "quality_score": state.get("quality_score", 0),
        "review_passed": state.get("review_passed", False),
        "compliance_passed": state.get("compliance_passed", False),
        "stage": state.get("stage_name"),
        "optimization_rounds": state.get("optimization_round", 0),
        "optimization_history": state.get("optimization_history", []),
        "review_opinion": state.get("review_opinion", ""),
        "compliance_notes": state.get("compliance_notes", ""),
        "total_time_seconds": round(total_time, 1),
    }
    
    with open("/home/ubuntu/novel-agent/chapter4_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    with open("/home/ubuntu/novel-agent/chapter4_final.txt", "w", encoding="utf-8") as f:
        f.write(state.get("last_chapter_content", ""))
    
    log("\n📁 结果已保存:")
    log("   - /home/ubuntu/novel-agent/chapter4_result.json")
    log("   - /home/ubuntu/novel-agent/chapter4_final.txt")
    log("   - /home/ubuntu/novel-agent/chapter4_progress.log")
    
    preview = state.get("last_chapter_content", "")[:500]
    log(f"\n📖 内容预览（前500字）:\n{preview}...")

def _save_state(state, filename):
    try:
        with open(f"/home/ubuntu/novel-agent/{filename}", "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        log(f"   ⚠️ 保存状态失败: {e}")

if __name__ == "__main__":
    main()
