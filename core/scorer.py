from core.corerules import rule_evaluate, evaluate_dimensions
from core.llm_judge import llm_judge

def evaluate(src, tgt, glossary=None, scenario="通用", ref=None):
    """
    优先用 LLM 评判，失败回退到规则版。
    返回格式与前端兼容，无需改 UI。
    """
    try:
        llm_result = llm_judge(src, tgt, glossary, ref)
        return {
            "final_score": llm_result["final_score"],
            "dimensions": llm_result["dimensions"],
            "total_weighted": None,
            "max_possible": None,
            "notes": [f"{d['dimension']}: {d['score']}/{d['weight']}" 
                      for d in llm_result["dimensions"] if d.get("weight", 0) > 0],
            "mode": "llm-judge(v3)",
            "scenario": scenario,
            "summary": llm_result.get("summary", ""),
        }
    except Exception as e:
        # 规则版兜底，保证平台不崩
        dim_result = evaluate_dimensions(src, tgt, glossary, scenario, ref)
        return {
            "final_score": dim_result["final_score"],
            "dimensions": dim_result["dimensions"],
            "total_weighted": dim_result["total_weighted"],
            "max_possible": dim_result["max_possible"],
            "notes": [f"{d['dimension']}: {d['score']}/{d['weight']}" 
                      for d in dim_result["dimensions"] if d["weight"] > 0],
            "mode": "dimension-weighted(v2)",
            "scenario": scenario,
        }