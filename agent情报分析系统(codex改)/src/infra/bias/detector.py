"""
认知偏差检测器（确定性，零 LLM 依赖）

三层能力：
1. audit_text()      文本层：回答/思考稿里出现了哪些偏差的**语言特征**
2. audit_evidence()  证据层：样本结构性问题（幸存者、确认偏误、茧房、缺基率）
3. audit_question()  提问层：主人问题本身的前提假设（预设、假两难、绝对化、无源数字…）

重要边界：
- 本检测器只产出"提示 + 自问 + 对策"，不自动改判结论、不自动改写问题。
- 命中 ≠ 错误。偏差是系统性倾向，最终由证据与人工裁决。
- 采用两档指标：强指标（≥3 字，区分度高）单独命中；弱指标（常见词）需 ≥2 个不同
  弱指标在同一句内共现才命中，以压低误报。
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from . import taxonomy as T

# 分句：中文句末标点 + 换行
_SENT_SPLIT = re.compile(r"[。！？；!?;\n]+")


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text or "") if s and s.strip()]


def _is_strong(ind: str) -> bool:
    return len(ind) >= 3


@dataclass
class BiasHit:
    """一次偏差命中"""
    bias_id: str
    name: str
    category: str
    severity: str
    matched: List[str]
    context: str
    counter_question: str
    mitigation: str
    strength: str = "strong"      # strong / weak

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bias_id": self.bias_id, "name": self.name, "category": self.category,
            "severity": self.severity, "matched": self.matched, "context": self.context,
            "counter_question": self.counter_question, "mitigation": self.mitigation,
            "strength": self.strength,
        }


@dataclass
class PremiseFlag:
    """提问前提问题"""
    code: str
    label: str
    matched: str
    why: str
    clarification: str

    def to_dict(self) -> Dict[str, Any]:
        return {"code": self.code, "label": self.label, "matched": self.matched,
                "why": self.why, "clarification": self.clarification}


@dataclass
class QuestionAudit:
    """提问审计结果"""
    original: str
    flags: List[PremiseFlag] = field(default_factory=list)
    bias_hits: List[BiasHit] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    suggested_questions: List[str] = field(default_factory=list)
    risk_level: str = "low"

    @property
    def passed(self) -> bool:
        return self.risk_level == "low"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original": self.original,
            "risk_level": self.risk_level,
            "flags": [f.to_dict() for f in self.flags],
            "bias_hits": [h.to_dict() for h in self.bias_hits],
            "assumptions": self.assumptions,
            "suggested_questions": self.suggested_questions,
        }

    def to_text(self) -> str:
        """给 Agent 回填到回答前的自查块"""
        if not self.flags and not self.bias_hits:
            return ""
        lines = [f"【提问前提自查｜风险 {self.risk_level}】"]
        for f in self.flags:
            lines.append(f"- [{f.label}] 命中“{f.matched}”：{f.why} → 需澄清：{f.clarification}")
        for h in self.bias_hits:
            lines.append(f"- [偏差:{h.name}] 命中“{'/'.join(h.matched)}” → 自问：{h.counter_question}")
        if self.assumptions:
            lines.append("- 我识别到的未确认前提：" + "；".join(self.assumptions))
        return "\n".join(lines)


# ============ 提问层模式表 ============
# (code, label, 正则, why, clarification)
_QUESTION_PATTERNS: Tuple[Tuple[str, str, str, str, str], ...] = (
    ("presupposition", "预设前提", r"既然|都已经|明明|连.{0,8}都",
     "问题把一个尚未验证的判断当成了既定事实",
     "如果这个前提不成立，问题应该怎么问？请先确认该前提是否成立"),
    ("false_dichotomy", "假两难", r"要么.{0,20}要么|是不是只能|只有.{0,12}(和|或|跟).{0,12}(两条|两种|一个)|二选一",
     "把多种可能压缩成两个选项",
     "除了这两个选项，还有第三种可能吗？各自的前提条件是什么"),
    ("absolute", "绝对化表述", r"一定|必然|肯定|绝对|永远|从不|全部|所有|任何|百分百|百分之百",
     "用绝对量词替代了有条件的判断",
     "这个“一定/都”的依据是什么？有没有例外或边界条件"),
    ("survivorship_frame", "幸存者框架", r"为什么.{0,10}成功|做得好的都|那些成功的|头部.{0,6}都",
     "只以成功样本提问，缺失失败样本与分母",
     "失败/退出样本有多少？完整分母是多少"),
    ("authority_appeal", "诉诸权威", r"专家|大佬|官方|权威|领导说|某某说",
     "以身份替代证据",
     "该说法的一手出处是什么？此人在该领域有资质吗？有无利益关系"),
    ("causal_claim", "因果断言", r"导致|造成|是因为|是不是因为|引起了",
     "直接断言因果，未区分相关/因果",
     "有没有对照组或混杂因素排查？时间先后是否被当成因果"),
    ("base_rate_missing", "缺基率", r"概率|几率|可能性|比例|多少成",
     "问概率但未给分母/样本",
     "基率（分母）是多少？样本来自哪里"),
    ("unsourced_number", "无源数字", r"\d+(\.\d+)?\s*(%|％|倍|万|亿|元|块)",
     "引用具体数字但未说明来源",
     "这个数字来自哪份原始材料？口径与时间范围是什么"),
    ("scope_missing", "口径缺失", r"^(?!.*(多少|几|哪|何时|谁|什么|怎么|如何|为什么|是否|能否|可否)).{0,40}(好不好|行不行|值不值|靠不靠谱|怎么样|咋样)",
     "问题未限定对象/时间/口径，答案会漂移",
     "具体对象、时间范围、评判口径分别是什么"),
    ("emotion_loaded", "情绪化措辞", r"垃圾|烂|屎|废物|必须|居然|竟然|简直",
     "措辞带强烈情绪，可能夹带未经验证的否定判断",
     "去掉情绪词后，事实陈述是什么？依据有哪些"),
)

_SOURCE_MARKERS = ("据", "来源", "出自", "报告", "年报", "公告", "论文", "官方数据", "统计")
_BASE_RATE_MARKERS = ("分母", "样本", "总共", "基数", "总量", "n=", "N=")


class BiasDetector:
    """确定性认知偏差检测器"""

    def __init__(self, min_context_len: int = 4):
        self.min_context_len = min_context_len

    # ---------- 1. 文本层 ----------
    def audit_text(self, text: str, scope: str = T.SCOPE_ANSWER) -> List[BiasHit]:
        """扫描文本中的偏差语言特征，只检查该 scope 下生效的偏差"""
        hits: List[BiasHit] = []
        candidates = T.by_scope(scope)
        for sent in _sentences(text):
            if len(sent) < self.min_context_len:
                continue
            for bias in candidates:
                if not bias.indicators:
                    continue
                strong = [i for i in bias.indicators if _is_strong(i) and i in sent]
                weak = [i for i in bias.indicators if not _is_strong(i) and i in sent]
                if strong:
                    hits.append(self._hit(bias, strong + weak, sent, "strong"))
                elif len(set(weak)) >= 2:
                    hits.append(self._hit(bias, weak, sent, "weak"))
        return hits

    @staticmethod
    def _hit(bias: T.Bias, matched: Iterable[str], sent: str, strength: str) -> BiasHit:
        return BiasHit(
            bias_id=bias.id, name=bias.name, category=bias.category,
            severity=bias.severity, matched=list(dict.fromkeys(matched)),
            context=sent[:200], counter_question=bias.counter_question,
            mitigation=bias.mitigation, strength=strength,
        )

    # ---------- 2. 证据层 ----------
    def audit_evidence(
        self,
        claims: Sequence[Any] = (),
        evidence: Sequence[Any] = (),
    ) -> List[BiasHit]:
        """
        结构性检查（不看措辞，看样本/来源结构是否已经带偏）

        claims:  Claim 对象或字符串
        evidence: Evidence 对象或 dict（尽量读 domain/url/stance/quality）
        """
        hits: List[BiasHit] = []
        ev = list(evidence)

        def _field(e: Any, key: str, default=None):
            if isinstance(e, dict):
                return e.get(key, default)
            return getattr(e, key, default)

        # 1) 幸存者偏差：完全没有失败/反证样本
        negative = 0
        for e in ev:
            if bool(_field(e, "is_contradictory", False)):
                negative += 1
                continue
            stance = str(_field(e, "stance", "") or "").lower()
            q = _field(e, "quality", None) or _field(e, "source_quality", None)
            qv = getattr(q, "value", q)
            if any(k in stance for k in ("neg", "contra", "反", "against")) or str(qv).lower() in ("d", "e", "low", "poor"):
                negative += 1
        if ev and negative == 0:
            hits.append(self._structural(
                "survivorship_bias",
                "证据集里没有任何失败/反证/低质量样本，无法排除只采到成功面",
                f"共 {len(ev)} 条证据，负面/反证 0 条",
            ))

        # 2) 确认偏误：反证占比过低
        if ev and negative / max(len(ev), 1) < 0.2 and len(ev) >= 3:
            hits.append(self._structural(
                "confirmation_bias",
                f"反证仅占 {negative}/{len(ev)}，低于 20%，需反向检索",
                f"反证 {negative} / 共 {len(ev)}",
            ))

        # 3) 信息茧房：来源域名过于集中
        domains = set()
        for e in ev:
            d = _field(e, "domain", None)
            if not d:
                url = str(_field(e, "url", "") or _field(e, "source_url", "") or "")
                m = re.match(r"https?://([^/]+)", url)
                d = m.group(1) if m else None
            if d:
                domains.add(d)
        if len(ev) >= 3 and len(domains) <= 1:
            hits.append(self._structural(
                "information_cocoon", "全部证据来自同一来源域名，观点未经跨源检验",
                f"域名数 {len(domains)}，证据 {len(ev)} 条"))

        # 4) 可得性/缺基率：多条证据但没有任何分母信息
        texts = " ".join(str(_field(e, "raw_content", "") or _field(e, "content", "") or "") for e in ev)
        if ev and not any(m in texts for m in _BASE_RATE_MARKERS):
            hits.append(self._structural(
                "availability_heuristic", "证据中未见基率/分母信息，比例类结论可能只凭印象",
                "未检出分母/样本量标记"))

        # 5) 文本层：claims 里的过度概括/因果混淆
        claim_text = " ".join(str(c if isinstance(c, str) else getattr(c, "content", "")) for c in claims)
        if claim_text:
            for h in self.audit_text(claim_text, scope=T.SCOPE_EVIDENCE):
                hits.append(h)
        return hits

    def _structural(self, bias_id: str, why: str, context: str) -> BiasHit:
        b = T.get(bias_id)
        return BiasHit(bias_id=b.id, name=b.name, category=b.category, severity=b.severity,
                       matched=[why], context=context, counter_question=b.counter_question,
                       mitigation=b.mitigation, strength="structural")

    # ---------- 3. 提问层 ----------
    def audit_question(self, question: str) -> QuestionAudit:
        """审计问题本身的前提假设，返回需澄清项与建议问法"""
        q = question or ""
        flags: List[PremiseFlag] = []
        for code, label, pattern, why, clar in _QUESTION_PATTERNS:
            m = re.search(pattern, q)
            if not m:
                continue
            # 无源数字：若同句已带来源标记，则不报
            if code == "unsourced_number" and any(s in q for s in _SOURCE_MARKERS):
                continue
            # 缺基率：若已给了分母标记，则不报
            if code == "base_rate_missing" and any(s in q for s in _BASE_RATE_MARKERS):
                continue
            flags.append(PremiseFlag(code=code, label=label, matched=m.group(0), why=why, clarification=clar))

        bias_hits = self.audit_text(q, scope=T.SCOPE_QUESTION)

        assumptions: List[str] = []
        if any(f.code == "presupposition" for f in flags):
            assumptions.append("问题中已把某个判断当作成立的前提")
        if any(f.code == "survivorship_frame" for f in flags):
            assumptions.append("默认只有成功样本值得研究")
        if any(f.code == "false_dichotomy" for f in flags):
            assumptions.append("可选方案只有问题里列出的那些")
        if any(f.code == "causal_claim" for f in flags):
            assumptions.append("已假定存在因果关系")

        # 风险分级：结构性前提问题 or 命中≥3 项 → high
        hard = {"presupposition", "false_dichotomy", "survivorship_frame"}
        if any(f.code in hard for f in flags) or len(flags) >= 3:
            risk = "high"
        elif flags:
            risk = "medium"
        else:
            risk = "low"

        return QuestionAudit(original=q, flags=flags, bias_hits=bias_hits,
                             assumptions=assumptions,
                             suggested_questions=[f.clarification for f in flags],
                             risk_level=risk)

    # ---------- 4. 给 Agent 的一体化入口 ----------
    def full_audit(
        self,
        question: Optional[str] = None,
        answer_text: Optional[str] = None,
        claims: Sequence[Any] = (),
        evidence: Sequence[Any] = (),
    ) -> Dict[str, Any]:
        qa = self.audit_question(question) if question else None
        text_hits = self.audit_text(answer_text, scope=T.SCOPE_ANSWER) if answer_text else []
        ev_hits = self.audit_evidence(claims=claims, evidence=evidence) if (claims or evidence) else []
        all_hits = text_hits + ev_hits
        # 去重（同一偏差只留最严重的一条）
        uniq: Dict[str, BiasHit] = {}
        for h in all_hits:
            if h.bias_id not in uniq or h.strength == "strong":
                uniq[h.bias_id] = h
        block = [h.to_dict() for h in uniq.values() if h.severity == T.SEV_BLOCK]
        downgrade = [h.to_dict() for h in uniq.values() if h.severity == T.SEV_DOWNGRADE]
        review = [h.to_dict() for h in uniq.values() if h.severity == T.SEV_REVIEW]
        return {
            "question_audit": qa.to_dict() if qa else None,
            "hits": {"block": block, "downgrade": downgrade, "review": review},
            "summary": {
                "question_risk": qa.risk_level if qa else None,
                "hit_count": len(uniq),
                "block_count": len(block),
                "downgrade_count": len(downgrade),
            },
        }
