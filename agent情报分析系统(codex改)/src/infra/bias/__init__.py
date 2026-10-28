"""认知偏差治理：知识库 + 确定性检测 + Agent 挂载"""

from .detector import BiasDetector, BiasHit, PremiseFlag, QuestionAudit
from .taxonomy import (BIASES, BY_ID, BY_NAME, CATEGORIES, SCOPE_ANSWER, SCOPE_EVIDENCE,
                       SCOPE_QUESTION, SCOPE_THINKING, Bias, all_counter_questions,
                       by_scope, get, summary)
from .wiring import attach_bias_tools, prompt_block

__all__ = [
    "BiasDetector", "BiasHit", "PremiseFlag", "QuestionAudit",
    "BIASES", "BY_ID", "BY_NAME", "CATEGORIES", "Bias",
    "SCOPE_THINKING", "SCOPE_ANSWER", "SCOPE_QUESTION", "SCOPE_EVIDENCE",
    "all_counter_questions", "by_scope", "get", "summary",
    "attach_bias_tools", "prompt_block",
]
