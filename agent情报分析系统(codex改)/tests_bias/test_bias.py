"""
认知偏差治理层真跑测试

覆盖：
1. 知识库完整性（图面 10 类 40 条位 → 35 条唯一偏差）
2. 每条偏差都能被检测器识别（不漏条）
3. 中性文本不误报（控假阳性）
4. 提问前提审计（预设/假两难/绝对化/幸存者框架/无源数字）
5. 证据结构性检查（幸存者/确认/信息茧房/缺基率）
6. m13 报告谬误检查并入 35 条（旧 6 条 key 不丢）
7. reflection 引擎偏差检查（命中不抬高置信度）
8. 两个 Agent 挂载 bias_audit / question_audit
"""

import pytest

from src.core.schemas import Claim, CommitmentLevel, Evidence, EvidenceQuality
from src.infra.bias import (BIASES, BY_ID, CATEGORIES, SCOPE_ANSWER, SCOPE_EVIDENCE,
                            BiasDetector, all_counter_questions, by_scope, get, summary)


# ---------------------------------------------------------------- 1. 知识库
def test_taxonomy_integrity():
    assert len(BIASES) == 35, f"唯一偏差应为 35 条，实际 {len(BIASES)}"
    assert len(CATEGORIES) == 10
    assert len(BY_ID) == 35
    ids = [b.id for b in BIASES]
    assert len(ids) == len(set(ids)), "bias id 有重复"
    names = [b.name for b in BIASES]
    assert len(names) == len(set(names)), f"bias 名称有重复：{names}"
    for b in BIASES:
        assert b.indicators, f"{b.name} 缺少文本指标"
        assert b.counter_question and b.mitigation, f"{b.name} 缺少自问/对策"
        assert b.scopes, f"{b.name} 缺少作用域"
        assert b.severity in ("review", "downgrade", "block")


def test_taxonomy_dedup_note():
    """图面 40 条位里 4 条跨类重复 + 1 组同义，去重后 35 条"""
    s = summary()
    assert s["raw_slots_in_poster"] == 40
    assert s["unique_count"] == 35
    assert s["dedup_cross_category"] == 4
    assert s["synonym_merged"] >= 1
    # 证实偏差应作为确认偏误的别名，不再单列
    assert "证实偏差" in get("confirmation_bias").aliases
    # 跨类重复的偏差只保留一条
    assert get("anchoring").category in CATEGORIES


def test_scope_partition():
    assert by_scope("question") and by_scope("evidence") and by_scope("answer")
    assert len(all_counter_questions("thinking")) >= 20


# ---------------------------------------------------------------- 2. 逐条可检出
@pytest.mark.parametrize("bias", BIASES, ids=[b.id for b in BIASES])
def test_every_bias_detectable(bias):
    text = "，".join(bias.indicators)
    hits = BiasDetector().audit_text(text, scope=bias.scopes[0])
    assert bias.id in {h.bias_id for h in hits}, f"{bias.name} 未被检出：{text}"


# ---------------------------------------------------------------- 3. 误报控制
def test_neutral_text_no_false_positive():
    text = ("今天天气晴朗，团队按计划完成了三项例行检查。"
            "报告已归档，等待下周复核。会议纪要同步给了所有参会同事。")
    hits = BiasDetector().audit_text(text, scope=SCOPE_ANSWER)
    assert hits == [], f"中性文本误报：{[h.name for h in hits]}"


def test_single_weak_indicator_not_enough():
    """单个弱指标（如单独一个"都"字）不应触发过度概括"""
    hits = BiasDetector().audit_text("这些材料都放在档案室了。", scope=SCOPE_ANSWER)
    assert "overgeneralization" not in {h.bias_id for h in hits}


# ---------------------------------------------------------------- 4. 提问审计
def test_question_presupposition_high_risk():
    q = "既然A公司已经失败了，是不是说明这个方向一定不行？"
    a = BiasDetector().audit_question(q)
    codes = {f.code for f in a.flags}
    assert "presupposition" in codes
    assert "absolute" in codes or "false_dichotomy" in codes
    assert a.risk_level == "high"
    assert a.passed is False
    assert a.suggested_questions, "应给出澄清问法"
    assert a.assumptions


def test_question_survivorship_frame():
    a = BiasDetector().audit_question("为什么头部主播都赚钱？")
    codes = {f.code for f in a.flags}
    assert "survivorship_frame" in codes
    assert a.risk_level == "high"
    assert any("失败" in s or "分母" in s for s in a.suggested_questions)


def test_question_unsourced_number():
    a = BiasDetector().audit_question("这个市场是不是有3000亿规模？")
    assert "unsourced_number" in {f.code for f in a.flags}
    # 带来源标记则不报
    b = BiasDetector().audit_question("据艾瑞2025年报告，这个市场有3000亿规模吗？")
    assert "unsourced_number" not in {f.code for f in b.flags}


def test_question_neutral_low_risk():
    a = BiasDetector().audit_question("2025年国内新能源汽车的销量是多少？")
    assert a.risk_level == "low"
    assert a.passed is True


def test_question_base_rate_missing():
    a = BiasDetector().audit_question("这类创业成功的概率有多大？")
    assert "base_rate_missing" in {f.code for f in a.flags}
    b = BiasDetector().audit_question("这类创业成功的概率有多大？样本总共200家。")
    assert "base_rate_missing" not in {f.code for f in b.flags}


# ---------------------------------------------------------------- 5. 证据结构
def _ev(i, url, quality=EvidenceQuality.B, contradictory=False, content="常规披露"):
    return Evidence(
        evidence_id=f"e{i}", source_url=url, source_quality=quality,
        content_hash=f"h{i}", raw_content=content,
        credibility_score=0.8, relevance_score=0.8, diagnostic_score=0.7,
        is_contradictory=contradictory, task_id="t1",
    )


def test_evidence_survivorship_and_cocoon():
    evs = [_ev(1, "https://a.com/x"), _ev(2, "https://a.com/y"), _ev(3, "https://a.com/z")]
    hits = {h.bias_id for h in BiasDetector().audit_evidence(evidence=evs)}
    assert "survivorship_bias" in hits
    assert "confirmation_bias" in hits
    assert "information_cocoon" in hits
    assert "availability_heuristic" in hits


def test_evidence_balanced_not_flagged():
    evs = [
        _ev(1, "https://a.com/x", EvidenceQuality.A),
        _ev(2, "https://b.com/y", EvidenceQuality.B),
        _ev(3, "https://c.com/z", EvidenceQuality.C, contradictory=True),
        _ev(4, "https://d.com/w", EvidenceQuality.B, content="样本量 N=1200"),
    ]
    hits = {h.bias_id for h in BiasDetector().audit_evidence(evidence=evs)}
    assert "survivorship_bias" not in hits
    assert "confirmation_bias" not in hits
    assert "information_cocoon" not in hits


def test_claims_overgeneralization():
    hits = {h.bias_id for h in BiasDetector().audit_evidence(claims=["所有竞品都成功了，因此这条路必然可行"])}
    assert "overgeneralization" in hits or "causal_confusion" in hits


# ---------------------------------------------------------------- 6. m13 集成
def test_m13_fallacy_expanded_and_legacy_kept():
    from src.modules.m13_report.reporter import ReportGenerator

    patterns = ReportGenerator.FALLACY_PATTERNS
    # 6 条历史谬误 + 35 条知识库 − 2 条同名重叠（幸存者/确认偏误以知识库版本为准）= 39
    assert len(patterns) == 6 + 35 - 2, f"谬误检查应并入偏差库，实际 {len(patterns)}"
    from src.infra.bias import BY_ID
    assert set(BY_ID) <= set(patterns), "知识库偏差未全部并入 m13"
    for legacy in ("survivorship_bias", "confirmation_bias", "post_hoc",
                   "availability_bias", "base_rate_neglect", "circular_reasoning"):
        assert legacy in patterns, f"历史谬误 {legacy} 丢失"
    assert "overgeneralization" in patterns and "anchoring" in patterns


def test_m13_detects_bias_in_report():
    from src.modules.m13_report.reporter import ReportGenerator

    claims = [Claim(claim_id="c1", claim_type="inference",
                    content="所有头部公司都成功了，因此这个方向必然可行",
                    commitment_level=CommitmentLevel.B, evidence_ids=["e1"],
                    falsifiable_anchor=None, verification_suggestion=None, task_id="t1")]
    evs = [_ev(1, "https://a.com/x"), _ev(2, "https://a.com/y"), _ev(3, "https://a.com/z")]
    checks = ReportGenerator()._check_fallacies(claims, evs)
    detected = {c.fallacy_type for c in checks if c.detected}
    assert "overgeneralization" in detected
    assert "survivorship_bias" in detected
    assert all(c.counter_question or c.fallacy_type in
               ("post_hoc", "circular_reasoning", "availability_bias", "base_rate_neglect")
               for c in checks if c.detected)


# ---------------------------------------------------------------- 7. reflection 集成
def test_reflection_bias_check_and_confidence():
    from src.infra.reflection.engine import ReflectionEngine

    eng = ReflectionEngine()
    biased = "所有头部公司都成功了，所以这条路一定没问题，肯定能复制。"
    r = eng.reflect("analysis", biased, {}, confidence=0.6)
    assert any("认知偏差" in i for i in r.issues_found), r.issues_found
    assert r.confidence_after <= 0.6, "偏差命中不应抬高置信度"

    clean = ("根据2025年年报披露，该公司营收同比增长12%，样本为全部36个省级分部。"
             "需要说明的是，这一增速低于行业均值，具体原因尚待验证。")
    r2 = eng.reflect("analysis", clean, {}, confidence=0.6)
    assert not any("认知偏差" in i for i in r2.issues_found), r2.issues_found


# ---------------------------------------------------------------- 8. Agent 挂载
@pytest.mark.asyncio
async def test_agents_have_bias_tools():
    from src.agents.analysis_agent import AnalysisAgent
    from src.agents.research_agent import ResearchAgent

    for ag in (ResearchAgent(), AnalysisAgent()):
        assert "bias_audit" in ag.tools
        assert "question_audit" in ag.tools


@pytest.mark.asyncio
async def test_agent_question_audit_live():
    from src.agents.research_agent import ResearchAgent

    ag = ResearchAgent()
    out = await ag.tools["question_audit"](question="既然他都成功了，是不是说明我也一定能成？")
    assert out["ok"] is True
    assert out["risk_level"] == "high"
    assert out["suggested_questions"]

    empty = await ag.tools["question_audit"](question="")
    assert empty["ok"] is False and "缺少" in empty["error"]


@pytest.mark.asyncio
async def test_agent_bias_audit_live():
    from src.agents.analysis_agent import AnalysisAgent

    ag = AnalysisAgent()
    out = await ag.tools["bias_audit"](text="所有竞品都成功了，因此必然可行。")
    assert out["ok"] is True
    grouped = out["hits"]  # {"block": [...], "downgrade": [...], "review": [...]}
    all_hits = grouped["block"] + grouped["downgrade"] + grouped["review"]
    ids = {h["bias_id"] for h in all_hits}
    assert "overgeneralization" in ids or "causal_confusion" in ids
    assert out["summary"]["hit_count"] == len(all_hits)


def test_prompt_block_injectable():
    from src.infra.bias import prompt_block

    block = prompt_block("thinking")
    assert "认知偏差自检" in block
    assert block.count("- ") >= 20
