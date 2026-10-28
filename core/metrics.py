def score_basic(src, tgt):
    return min(100, 60 + (len(tgt)/max(1,len(src)))*20)