"""
认知偏差知识库（Cognitive Bias Taxonomy）—— 单一事实源

来源：主人 2026-10-28 提供的《认知偏差大全》信息图（mmexport1793186928212.jpg），
      10 类 / 40 条位。逐条转录后做归一化：

归一化口径（必须保留，避免重复计数）：
  40 条位 - 4 条跨类重复（锚定效应、从众效应、损失厌恶、框架效应各出现 2 次）
        - 1 组同义合并（"证实偏差" ≡ "确认偏误"，作别名并入）
  = 35 条唯一偏差

图面第 5 类"社尴偏差"疑为 OCR 误识，按语义归一为"社会偏差"（记录在此，不擅改图面原词）。

设计原则（与项目既有治理理念一致）：
1. 只提示、不判错：偏差是系统性倾向，命中 ≠ 结论错误，须由证据/人工裁决。
2. 作用域 scope 决定它在哪一层生效：
   - thinking：Agent 内部思考/推理过程
   - answer：给主人的回答正文
   - question：主人提问本身的前提假设（用于"问题重构"）
   - evidence：证据与数据层
3. 每条给 counter_question（自问）+ mitigation（对策），可直接注入 prompt 或落进报告。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# 作用域常量
SCOPE_THINKING = "thinking"
SCOPE_ANSWER = "answer"
SCOPE_QUESTION = "question"
SCOPE_EVIDENCE = "evidence"

# 严重度：review=提示复核；downgrade=命中则置信度封顶；block=命中即阻断
SEV_REVIEW = "review"
SEV_DOWNGRADE = "downgrade"
SEV_BLOCK = "block"


@dataclass(frozen=True)
class Bias:
    """单条认知偏差定义"""
    id: str
    name: str
    category: str
    definition: str                      # 图面原意（不改写事实）
    aliases: Tuple[str, ...] = ()        # 同义/图面重复条目
    indicators: Tuple[str, ...] = ()     # 文本触发词（用于确定性扫描）
    counter_question: str = ""           # 自问
    mitigation: str = ""                 # 对策
    scopes: Tuple[str, ...] = (SCOPE_THINKING, SCOPE_ANSWER)
    severity: str = SEV_REVIEW


# ============ 10 类 / 35 条（顺序同图） ============
BIASES: Tuple[Bias, ...] = (
    # ---------- 1. 记忆偏差：我们记住的，不一定是发生的 ----------
    Bias("selective_memory", "选择性记忆", "记忆偏差",
         "只记得符合自己的部分，忽略其他。",
         indicators=("只记得", "符合预期的那次", "选择性"),
         counter_question="被忽略的那部分记录/样本是什么？",
         mitigation="强制列出不符合预期的反例清单，再下结论。"),
    Bias("false_memory", "虚假记忆", "记忆偏差",
         "把想象的当成真实的记忆。",
         indicators=("我记得", "印象中是", "应该是当时"),
         counter_question="这个细节有原始记录/一手出处可核吗？",
         mitigation="回查一手记录；未核实的表述一律标注“记忆未核实”。",
         scopes=(SCOPE_ANSWER, SCOPE_EVIDENCE)),
    Bias("memory_drift", "记忆偏差（随时间修改）", "记忆偏差",
         "随着时间推移，记忆会被修改。",
         indicators=("之前说过", "当时是", "后来变成"),
         counter_question="最早版本的原文/时间戳在哪里？",
         mitigation="以时间戳最早的原始记录为准，后续转述只作参考。",
         scopes=(SCOPE_ANSWER, SCOPE_EVIDENCE)),
    Bias("anchoring", "锚定效应", "记忆偏差",
         "第一印象会影响后续判断。（图面同时在“其他常见偏差”中重复列出）",
         aliases=("第一印象",),
         indicators=("第一版", "最初报价", "一开始说", "首轮", "第一印象"),
         counter_question="这个初始数字/印象有独立依据吗，还是只是它先出现？",
         mitigation="遮蔽初始值，用独立来源做二次估值后再比对。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER, SCOPE_QUESTION)),

    # ---------- 2. 逻辑偏差：我们以为自己很理性，但常常被逻辑误导 ----------
    Bias("confirmation_bias", "确认偏误", "逻辑偏差",
         "只寻找支持自己观点的信息。（图面“其他常见偏差”中的“证实偏差”为同义条目）",
         aliases=("证实偏差",),
         indicators=("证实", "支持我的", "果然", "符合预期"),
         counter_question="有没有主动做过反向检索？找到几条反证？",
         mitigation="强制反向检索；反证数≥1 才允许下结论，并把反证写进报告。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER, SCOPE_EVIDENCE),
         severity=SEV_DOWNGRADE),
    Bias("overgeneralization", "过度概括", "逻辑偏差",
         "用少量经验得出普遍结论。",
         aliases=("过度概误",),   # 图面原字，保留可检索
         indicators=("所有", "都", "一律", "必然", "从不", "永远"),
         counter_question="样本量多少？边界条件是什么？有没有反例？",
         mitigation="标注样本量与适用范围，至少列一个反例或例外。",
         scopes=(SCOPE_ANSWER, SCOPE_QUESTION, SCOPE_EVIDENCE)),
    Bias("causal_confusion", "因果混淆", "逻辑偏差",
         "把相关当成因果。",
         indicators=("因此导致", "说明", "证明", "所以"),
         counter_question="是时间先后/相关，还是因果？有对照组或混杂因素排查吗？",
         mitigation="区分相关与因果；列出混杂变量与替代解释。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER, SCOPE_EVIDENCE)),
    Bias("survivorship_bias", "幸存者偏差", "逻辑偏差",
         "只看到成功的，忽略失败的。",
         indicators=("成功案例", "活下来的", "头部", "那些成功的", "幸存"),
         counter_question="失败/退出/沉默的样本有多少？完整分母是多少？",
         mitigation="补齐失败样本与完整分母，再谈比例或规律。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER, SCOPE_QUESTION, SCOPE_EVIDENCE),
         severity=SEV_DOWNGRADE),

    # ---------- 3. 情绪偏差：情绪会放大事实，也会扭曲判断 ----------
    Bias("emotional_decision", "情绪化决策", "情绪偏差",
         "在情绪下做出的决定往往很不理性。",
         indicators=("气死", "受不了", "太爽", "必须马上", "忍不住"),
         counter_question="如果情绪平复后再看，结论会变吗？",
         mitigation="情绪事件延迟决策，24 小时后复核一次。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER, SCOPE_QUESTION)),
    Bias("loss_aversion", "损失厌恶", "情绪偏差",
         "害怕失去的痛苦大于获得的快乐。（图面同时在“决策偏差”中重复列出）",
         indicators=("不想亏", "怕失去", "舍不得", "已经投入"),
         counter_question="同样的金额，当作收益和当作损失时，我的判断是否对称？",
         mitigation="用收益/损失对称表述各重述一遍，看结论是否反转。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER)),
    Bias("optimism_bias", "乐观偏差", "情绪偏差",
         "高估好的可能性，低估坏的可能性。",
         indicators=("应该没问题", "大概率顺利", "不会那么倒霉"),
         counter_question="最坏情况是什么？概率与影响多大？有没有预案？",
         mitigation="强制写出最坏情形、概率区间与止损预案。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER)),
    Bias("conformity", "从众效应", "情绪偏差",
         "为了融入群体而放弃自己的判断。（图面同时在“社会偏差”中重复列出）",
         indicators=("大家都", "行业都", "都在做", "跟着做"),
         counter_question="这个“都”有统计支撑吗？少数派观点是什么？",
         mitigation="主动检索少数派/反对意见，并记录分歧。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER, SCOPE_QUESTION)),

    # ---------- 4. 自我相关偏差：我们更关注自己，也更容易高估自己 ----------
    Bias("self_serving_bias", "自利性偏差", "自我相关偏差",
         "倾向于把成功归因于自己，把失败归因于外界。",
         indicators=("因为我的判断", "多亏", "不是我的问题", "运气不好"),
         counter_question="如果换成别人来做，我会怎么归因？",
         mitigation="成功与失败使用同一套归因标准，逐项对照。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER)),
    Bias("overconfidence", "自信偏差", "自我相关偏差",
         "高估自己的能力和正确性。",
         indicators=("肯定", "毫无疑问", "百分之百", "绝对"),
         counter_question="我的置信区间是多少？如果错了，什么信号会先出现？",
         mitigation="给区间和证伪条件，不把点估计当事实陈述。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER),
         severity=SEV_DOWNGRADE),
    Bias("illusion_of_control", "控制错觉", "自我相关偏差",
         "认为自己能控制更多的事情。",
         indicators=("我能控制", "只要我", "我说了算"),
         counter_question="哪些变量其实不在我控制范围内？",
         mitigation="列出可控/不可控变量清单，只对可控项下承诺。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER)),
    Bias("egocentric", "自我中心偏差", "自我相关偏差",
         "总是从自己的角度看问题。",
         indicators=("对我来说", "我觉得大家", "我认为他们"),
         counter_question="其他相关方的目标与视角分别是什么？",
         mitigation="至少列出两个其他立场及其最优选择。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER)),

    # ---------- 5. 社会偏差：我们很在意他人，也容易被他人影响 ----------
    Bias("authority_bias", "权威偏差", "社会偏差",
         "更容易相信权威的观点。",
         indicators=("专家说", "大佬", "官方表示", "权威"),
         counter_question="该权威在本领域有资质吗？有无利益关系？",
         mitigation="核查资质与利益链，另找独立第二来源交叉验证。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER, SCOPE_QUESTION)),
    Bias("group_polarization", "群体极化", "社会偏差",
         "在群体中观点会越来越极端。",
         indicators=("一致认为", "大家都同意", "没有异议"),
         counter_question="分歧被记录了吗？观点是否比初始更极端？",
         mitigation="保留异议记录，标注讨论前后的观点位移。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER)),
    Bias("stereotype", "刻板印象", "社会偏差",
         "用标签代替真实的了解。",
         indicators=("都是这样", "那种人就是", "一看就是"),
         counter_question="这个标签有证据吗？个体差异在哪里？",
         mitigation="用个案证据替代标签判断，标注适用范围。",
         scopes=(SCOPE_ANSWER, SCOPE_QUESTION)),

    # ---------- 6. 决策偏差：我们以为在做选择，其实是在被偏差影响 ----------
    Bias("sunk_cost", "沉没成本", "决策偏差",
         "已经投入的成本，会影响我们的决策。",
         indicators=("已经投了", "不能白费", "都做到这了"),
         counter_question="如果今天从零开始，我还会选这条路吗？",
         mitigation="只看未来增量成本与增量收益，历史投入不计入决策。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER, SCOPE_QUESTION)),
    Bias("framing_effect", "框架效应", "决策偏差",
         "不同的表述，会导致不同的判断。（图面同时在“其他常见偏差”中重复列出）",
         indicators=("成功率", "失败率", "只差", "才"),
         counter_question="换成相反表述重述一遍，结论是否反转？",
         mitigation="正反两种表述各算一遍，结论一致才采纳。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER, SCOPE_QUESTION)),
    Bias("instant_gratification", "即时满足", "决策偏差",
         "更倾向于短期的快乐，而忽略长期的利益。",
         indicators=("马上要", "现在就", "先做了再说"),
         counter_question="长期代价是什么？延迟后的收益是多少？",
         mitigation="写出即时收益 vs 延迟收益对照表。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER)),

    # ---------- 7. 行为偏差：我们常常说着一套，做着另一套 ----------
    Bias("procrastination", "拖延效应", "行为偏差",
         "总是把紧要的事留到最后。",
         indicators=("明天再", "下周再说", "来得及"),
         counter_question="这件事的截止时间与逾期后果是什么？",
         mitigation="拆成最小可执行步，设硬截止与检查点。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER)),
    Bias("status_quo", "现状偏差", "行为偏差",
         "更倾向于维持现状，而不是改变。",
         indicators=("维持现状", "先不改", "原来挺好"),
         counter_question="维持现状的代价是多少？",
         mitigation="量化“不改”的成本，与改动成本并列比较。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER)),
    Bias("habit_effect", "习惯效应", "行为偏差",
         "习惯会让我们自动化地行动。",
         indicators=("一直都这么干", "惯例", "老办法"),
         counter_question="这个习惯成立的前提现在还成立吗？",
         mitigation="定期回测惯例的有效性，前提变了就重估。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER)),
    Bias("effort_illusion", "努力错觉", "行为偏差",
         "以为很努力，但效率并不高。",
         indicators=("很努力", "加班", "投入很多时间"),
         counter_question="产出指标是什么？投入产出比是多少？",
         mitigation="用结果指标衡量，不用工时/投入量代替成效。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER)),

    # ---------- 8. 经济偏差：在金钱和利益面前，我们更容易失去理性 ----------
    Bias("herd_effect", "羊群效应", "经济偏差",
         "跟随大众的投资和消费行为。",
         indicators=("都在买", "跟风", "赛道热"),
         counter_question="我的独立估值是多少？脱离人群后的判断是什么？",
         mitigation="先独立定价/独立判断，再看市场共识。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER, SCOPE_QUESTION)),
    Bias("gambling_mentality", "赌博心理", "经济偏差",
         "小概率事件让人产生不切实际的期待。",
         indicators=("搏一把", "万一中了", "小概率"),
         counter_question="期望值是多少？归零能否承受？",
         mitigation="计算期望值与最大回撤，设仓位上限。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER)),
    Bias("risk_preference", "风险偏好", "经济偏差",
         "在不确定性中，更愿意冒险。",
         indicators=("赌一把", "风险越大收益越大", "不敢就输了"),
         counter_question="确定性等价下，这个赌注值多少？",
         mitigation="设风险预算与止损线，不用“搏一把”替代测算。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER)),
    Bias("comparison_effect", "比较效应", "经济偏差",
         "总是和他人比较，而忽略了自己的真实情况。",
         indicators=("别人都", "相比他", "比不上"),
         counter_question="比较基准合理吗？我自身的约束条件是什么？",
         mitigation="改用绝对指标与自身基线做纵向对比。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER, SCOPE_QUESTION)),

    # ---------- 9. 信息偏差：我们获取的信息，往往是片面的 ----------
    Bias("information_cocoon", "信息茧房", "信息偏差",
         "只接触同类信息，看不到不同的声音。",
         indicators=("看到的都是", "圈子里", "推荐给我"),
         counter_question="我主动找过相反立场的信息源吗？",
         mitigation="强制跨源检索，明确列出对立观点与来源。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER, SCOPE_EVIDENCE),
         severity=SEV_DOWNGRADE),
    Bias("headline_effect", "标题效应", "信息偏差",
         "更容易被标题而非内容吸引。",
         indicators=("标题说", "据说", "刷到"),
         counter_question="原文全文读了吗？还是只看了标题/转述？",
         mitigation="引用前必须读一手全文，标注出处。",
         scopes=(SCOPE_ANSWER, SCOPE_EVIDENCE)),
    Bias("over_interpretation", "过度解读", "信息偏差",
         "对模糊信息进行过度推测。",
         indicators=("说明他", "言外之意", "暗示"),
         counter_question="有没有更平常的解释？",
         mitigation="至少列一个替代解释，标注为推断而非事实。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER, SCOPE_EVIDENCE)),
    Bias("information_overload", "信息过载", "信息偏差",
         "信息太多，反而难以做出判断。",
         indicators=("资料太多", "看了很多", "信息量太大"),
         counter_question="影响判断的核心变量是哪 3 个？",
         mitigation="收敛到核心变量与决策阈值，其余降为背景。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER)),

    # ---------- 10. 其他常见偏差（其中框架/锚定已在上文去重） ----------
    Bias("availability_heuristic", "可得性启发", "其他常见偏差",
         "越容易想起的事，越觉得更常见。",
         indicators=("最近", "刷屏", "到处都是", "新闻都在报"),
         counter_question="基率是多少？有没有统计分母？",
         mitigation="查基率数据，用频率替代印象。",
         scopes=(SCOPE_THINKING, SCOPE_ANSWER, SCOPE_EVIDENCE)),
)

# 索引
BY_ID: Dict[str, Bias] = {b.id: b for b in BIASES}
BY_NAME: Dict[str, Bias] = {b.name: b for b in BIASES}
CATEGORIES: Tuple[str, ...] = (
    "记忆偏差", "逻辑偏差", "情绪偏差", "自我相关偏差", "社会偏差",
    "决策偏差", "行为偏差", "经济偏差", "信息偏差", "其他常见偏差",
)


def get(bias_id: str) -> Bias:
    return BY_ID[bias_id]


def by_scope(scope: str) -> List[Bias]:
    return [b for b in BIASES if scope in b.scopes]


def by_category(category: str) -> List[Bias]:
    return [b for b in BIASES if b.category == category]


def all_counter_questions(scope: str = SCOPE_THINKING) -> List[str]:
    """给 prompt 注入用：返回某作用域下的全部自问"""
    return [f"{b.name}：{b.counter_question}" for b in by_scope(scope) if b.counter_question]


def summary() -> Dict[str, object]:
    """自检/文档用：条数、分类分布、去重口径"""
    dist = {c: len(by_category(c)) for c in CATEGORIES}
    return {
        "unique_count": len(BIASES),
        "raw_slots_in_poster": 40,
        "dedup_cross_category": 4,
        "synonym_merged": 1,
        "categories": dist,
    }
