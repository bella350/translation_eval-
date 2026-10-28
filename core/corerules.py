import re
from sacrebleu.metrics import BLEU, CHRF

def _is_ru(text: str) -> bool:
    return any("а" <= ch.lower() <= "я" or ch in "ёЁ" for ch in text)

def check_length(src, tgt):
    sl, tl = len(src), len(tgt)
    ratio = tl / max(sl, 1)
    score = 10
    note = f"长度：原文{sl}字符 / 译文{tl}字符（比例{ratio:.2f}）"
    if ratio < 0.35 or ratio > 1.4:
        score -= 3
        note += "｜差异偏大，需人工核对漏/增译"
    return {"score": max(0, score), "note": note}

def check_numbers(src, tgt):
    nums_s = set(re.findall(r'\d+', src))
    nums_t = set(re.findall(r'\d+', tgt))
    miss = nums_s - nums_t
    score = 20
    note = f"数字一致性：原文{len(nums_s)}处，译文命中{len(nums_s)-len(miss)}处"
    if miss:
        score -= min(10, 2 * len(miss))
        note += f"｜疑似缺失: {sorted(miss)}"
    return {"score": max(0, score), "note": note}

def check_punctuation(src, tgt):
    pairs = [('«','»'),('("','")'),('(',')'),('[',']'),(':',':')]
    score = 10
    note = "标点大致一致"
    for a,b in pairs:
        if (a in src or b in src) and not (a in tgt or b in tgt):
            score -= 1
            note = "标点/括号/引号可能存在不一致（提示）"
    return {"score": max(0, score), "note": note}

def check_terminology(tgt, glossary=None):
    if not glossary:
        return {"score": 20, "note": "无术语表（默认满分）"}
    hit = [w for w in glossary if w in tgt]
    miss = [w for w in glossary if w not in tgt]
    score = 20 - 2 * len(miss)
    return {"score": max(0, score), "note": f"术语命中{len(hit)}/{len(glossary)}；缺失{miss}"}

def rule_evaluate(src, tgt, glossary=None):
    length = check_length(src, tgt)
    numbers = check_numbers(src, tgt)
    punct = check_punctuation(src, tgt)
    term = check_terminology(tgt, glossary)
    details = [length, numbers, punct, term]
    raw = sum(d["score"] for d in details) / 60.0
    rule_score_60 = round(raw * 60, 1)
    return {
        "rule_score_60": rule_score_60,
        "details": details,
        "notes": [d["note"] for d in details],
    }

# ========== 多维加权评分 ==========

def dimension_accuracy(src, tgt):
    score = 30
    notes = []
    ratio = len(tgt) / max(len(src), 1)
    if ratio < 0.3:
        score -= 15
        notes.append("译文过短，疑似严重漏译")
    elif ratio < 0.5:
        score -= 8
        notes.append("译文偏短，可能有漏译")
    elif ratio > 2.5:
        score -= 5
        notes.append("译文过长，可能有增译")
    nums_s = set(re.findall(r'\d+', src))
    nums_t = set(re.findall(r'\d+', tgt))
    miss = nums_s - nums_t
    if miss:
        penalty = min(10, 2 * len(miss))
        score -= penalty
        notes.append(f"数字遗漏: {sorted(miss)}")
    if not notes:
        notes.append("信息传达基本完整")
    return {"dimension": "准确性/忠实度", "weight": 30, "score": max(0, score), "notes": notes}

def dimension_fluency(tgt):
    score = 20
    notes = []
    if len(tgt) < 5:
        score -= 15
        notes.append("译文过短，无法判断流畅度")
    repeats = re.findall(r'(.{2,})\1{2,}', tgt)
    if repeats:
        score -= 5
        notes.append("译文存在异常重复，可能为机翻错误")
    # 修复：同时支持中/西文标点
    punct_count = len(re.findall(r'[，。！？；：、,.!?;:]', tgt))
    if len(tgt) > 20 and punct_count == 0:
        score -= 3
        notes.append("长句无标点，流畅度存疑")
    if not notes:
        if _is_ru(tgt):
            notes.append("俄文表达基本流畅")
        else:
            notes.append("中文表达基本流畅")
    return {"dimension": "流畅度", "weight": 20, "score": max(0, score), "notes": notes}

def dimension_terminology(tgt, glossary=None):
    score = 15
    notes = []
    if not glossary:
        notes.append("未提供术语表（默认满分）")
        return {"dimension": "术语一致性", "weight": 15, "score": score, "notes": notes}
    hit = []
    miss = []
    for src_term, tgt_term in glossary.items():
        if not tgt_term.strip():
            continue
        if tgt_term in tgt:
            hit.append(f"{src_term}→{tgt_term}")
        else:
            stem = re.sub(r'(?:[аяоеёуыиюьй]+)$', '', tgt_term.lower())
            if stem and len(stem) > 2 and stem in tgt.lower():
                hit.append(f"{src_term}→{tgt_term}（词根匹配）")
            else:
                miss.append(f"{src_term}→{tgt_term}")
    if hit:
        notes.append(f"✅ 命中 {len(hit)} 个: {', '.join(hit[:6])}")
    if miss:
        penalty = min(10, 3 * len(miss))
        score -= penalty
        notes.append(f"❌ 未命中 {len(miss)} 个: {', '.join(miss[:6])}")
    return {"dimension": "术语一致性", "weight": 15, "score": max(0, score), "notes": notes}

def dimension_grammar(tgt):
    score = 15
    notes = []
    if tgt.count('(') != tgt.count(')') or tgt.count('（') != tgt.count('）'):
        score -= 3
        notes.append("括号不匹配")
    if tgt.count('"') % 2 != 0:
        score -= 2
        notes.append("引号未闭合")
    if re.search(r'[，。！？；：、,.!?]{2,}', tgt):
        score -= 3
        notes.append("存在连续标点")
    if not notes:
        notes.append("语法和拼写基本正确")
    return {"dimension": "语法/拼写", "weight": 15, "score": max(0, score), "notes": notes}

def dimension_style(tgt, scenario="通用"):
    score = 20
    notes = []
    if scenario in ["学术", "翻译理论", "论文"]:
        academic_markers = ["因此", "然而", "基于", "通过", "分析", "研究", "表明"]
        if any(m in tgt for m in academic_markers):
            notes.append("译文使用了学术表达，语域匹配")
        else:
            score -= 5
            notes.append("学术文本但译文偏口语化，风格可优化")
    else:
        notes.append("通用场景，风格无明显偏差")
    return {"dimension": "文体风格", "weight": 20, "score": max(0, score), "notes": notes}

def dimension_reference_alignment(tgt, ref):
    if not ref or not ref.strip():
        return {"dimension": "参考对齐(BLEU/chrF)", "weight": 0, "score": 0,
                "notes": ["未提供参考译文（仅展示）"], "bleu": None, "chrf": None}
    bleu = BLEU(effective_order=True)
    chrf = CHRF()
    bleu_score = bleu.corpus_score([tgt], [[ref]]).score
    chrf_score = chrf.corpus_score([tgt], [[ref]]).score
    notes = [
        f"BLEU={bleu_score:.2f}",
        f"chrF={chrf_score:.2f}",
        "（参考对齐仅展示，不计入总分）"
    ]
    return {"dimension": "参考对齐(BLEU/chrF)", "weight": 0, "score": 0,
            "notes": notes, "bleu": bleu_score, "chrf": chrf_score}

def evaluate_dimensions(src, tgt, glossary=None, scenario="通用", ref=None):
    dims = [
        dimension_accuracy(src, tgt),
        dimension_fluency(tgt),
        dimension_terminology(tgt, glossary),
        dimension_grammar(tgt),
        dimension_style(tgt, scenario),
        dimension_reference_alignment(tgt, ref),
    ]
    base_dims = [d for d in dims if d["weight"] > 0]
    total_weighted = sum(d["score"] for d in base_dims)
    max_possible = sum(d["weight"] for d in base_dims)
    final_score = round(total_weighted / max_possible * 100, 1) if max_possible > 0 else 0
    return {
        "final_score": final_score,
        "dimensions": dims,
        "total_weighted": total_weighted,
        "max_possible": max_possible,
    }