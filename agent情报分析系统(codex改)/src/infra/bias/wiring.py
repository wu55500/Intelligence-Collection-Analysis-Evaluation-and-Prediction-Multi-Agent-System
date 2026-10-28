"""
认知偏差工具挂载（懒加载 + 安全降级）

与 m23 的 attach_reverse_tool 同一模式：
- Agent 构造末尾调用 attach_bias_tools(self)
- 依赖缺失/异常时只打印不抛，绝不拖垮 Agent 主流程
- 工具本体只读、确定性、不调 LLM，因此无 key 也能用

注册的两个工具：
  question_audit(question)   审计提问本身的前提假设，返回澄清项与建议问法
  bias_audit(...)            审计回答/证据中的偏差，返回分级命中
"""

from typing import Any, Dict, List, Optional

TOOL_QUESTION_AUDIT = "question_audit"
TOOL_BIAS_AUDIT = "bias_audit"


def prompt_block(scope: str = "thinking") -> str:
    """生成可注入 system prompt 的偏差自检块（供 M24 角色 / 报告生成器使用）"""
    from .taxonomy import all_counter_questions

    lines = [
        "【认知偏差自检（回答前逐条过一遍，命中项必须在正文里显式交代）】",
    ]
    lines.extend(f"- {q}" for q in all_counter_questions(scope))
    lines.append("【输出纪律】区分事实/推断/未知；不确定就说不确定；不给无来源的精确数字。")
    return "\n".join(lines)


def attach_bias_tools(agent: Any) -> bool:
    """
    给 Agent 挂载认知偏差工具。

    Returns:
        True=已挂载；False=跳过（Agent 不支持 register_tool）
    """
    if not hasattr(agent, "register_tool"):
        return False

    async def question_audit(question: str = "", **_kw) -> Dict[str, Any]:
        """审计用户提问的前提假设（预设/假两难/绝对化/无源数字/幸存者框架等）"""
        if not question:
            return {"ok": False, "error": "缺少 question 参数"}
        try:
            from .detector import BiasDetector

            audit = BiasDetector().audit_question(question)
            return {
                "ok": True,
                "risk_level": audit.risk_level,
                "passed": audit.passed,
                "flags": [f.to_dict() for f in audit.flags],
                "assumptions": audit.assumptions,
                "suggested_questions": audit.suggested_questions,
                "self_check_text": audit.to_text(),
            }
        except Exception as exc:  # 安全降级
            return {"ok": False, "error": f"偏差审计失败: {exc}"}

    async def bias_audit(
        text: str = "",
        question: str = "",
        claims: Optional[List[Any]] = None,
        evidence: Optional[List[Any]] = None,
        **_kw,
    ) -> Dict[str, Any]:
        """审计回答正文/证据集里的认知偏差（确定性，不调 LLM）"""
        try:
            from .detector import BiasDetector

            result = BiasDetector().full_audit(
                question=question or None,
                answer_text=text or None,
                claims=claims or (),
                evidence=evidence or (),
            )
            result["ok"] = True
            return result
        except Exception as exc:
            return {"ok": False, "error": f"偏差审计失败: {exc}"}

    agent.register_tool(TOOL_QUESTION_AUDIT, question_audit)
    agent.register_tool(TOOL_BIAS_AUDIT, bias_audit)
    return True
