"""
飞书多维表格读写工具
支持将 Agent 的运行状态同步到小说Agent工作台 Base
"""

import subprocess
import json
import os
from typing import Optional


BASE_TOKEN = "WKu4bv99ia7Z7ys1ztXcuWFXnce"
TABLE_ID = "tbl2JPk0wavufExa"


def _run_lark(args: list, desc: str = "") -> dict:
    """执行 lark-cli 命令并返回解析后的 JSON"""
    cmd = ["lark-cli", "base"] + args + ["--as", "user", "--format", "json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr}
        return json.loads(result.stdout)
    except Exception as e:
        return {"ok": False, "error": str(e)}


def sync_to_base(field_updates: dict, record_id: str) -> bool:
    """将字段更新同步到多维表格。field_updates: {字段名: 值}"""
    # 构建 upsert payload：字段名 → 值
    payload = {"fields": list(field_updates.keys()), "rows": []}

    row = []
    for field_name, value in field_updates.items():
        # 处理 select 类型
        if isinstance(value, list) and all(isinstance(v, str) for v in value):
            row.append(value)  # 多选
        elif isinstance(value, str) and value in ["① 调研选题", "② 平台政策研究", "③ 写作计划",
                                                    "④ 写作中", "⑤ Loop优化", "⑥ 审稿",
                                                    "⑦ 合规审查", "✅ 完结"]:
            row.append([value])  # 单选
        elif isinstance(value, str):
            row.append(value)
        elif isinstance(value, int):
            row.append(value)
        elif isinstance(value, float):
            row.append(value)
        else:
            row.append(str(value) if value else None)

    payload["rows"].append(row)

    # 如果是更新已有记录，用 field_id_list 模式
    cmd = ["+record-upsert", "--base-token", BASE_TOKEN,
           "--table-id", TABLE_ID,
           "--json", json.dumps(payload, ensure_ascii=False)]

    # 如果有 record_id 则更新指定记录
    if record_id:
        cmd += ["--record-id", record_id]

    result = _run_lark(cmd, "sync_to_base")
    return result.get("ok", False)


def update_stage(record_id: str, stage_name: str) -> bool:
    """更新阶段字段"""
    return sync_to_base({"阶段": stage_name}, record_id)


def get_record(record_id: str) -> Optional[dict]:
    """读取多维表格中的记录"""
    # 用 record-list 查
    return None  # 简化版本


def get_all_records() -> list:
    """获取所有记录列表"""
    cmd = ["+record-list", "--base-token", BASE_TOKEN,
           "--table-id", TABLE_ID, "--limit", "50"]
    result = _run_lark(cmd, "get_all_records")
    if result.get("ok"):
        return result.get("data", {}).get("items", [])
    return []