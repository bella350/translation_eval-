import os, json, re
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)
MODEL = os.getenv("DASHSCOPE_MODEL", "qwen3.7-plus")

SYS = """你是严格的翻译质量评审专家，熟悉 WMT/MQM，精通中英、中俄互译。
重点查：漏译/增译/误译/否定反了/数量错；俄语格、体、数、性、语序；术语语境变形；流畅与风格。
只输出严格 JSON，不要散文。"""

def _user(src, tgt, glossary, ref):
    g = "\n".join(f"{k} → {v}" for k,v in (glossary or {}).items())
    r = f"参考译文：{ref}\n" if ref else "参考译文：无\n"
    return f"""原文：
{src}

译文：
{tgt}

术语表：
{g}
{r}
返回JSON：
{{
 "dimensions":[
  {{"dimension":"准确性","score":0-10,"weight":30,"notes":[]}},
  {{"dimension":"流畅度","score":0-10,"weight":20,"notes":[]}},
  {{"dimension":"术语一致性","score":0-10,"weight":15,"notes":[]}},
  {{"dimension":"语法正确","score":0-10,"weight":15,"notes":[]}},
  {{"dimension":"风格得体","score":0-10,"weight":20,"notes":[]}}
 ],
 "summary":"一句话总评"
}}"""

def llm_judge(src, tgt, glossary=None, ref=None):
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[
            {"role":"system","content":SYS},
            {"role":"user","content":_user(src,tgt,glossary,ref)}
        ],
        extra_body={"enable_thinking": False},
    )
    content = resp.choices[0].message.content
    try:
        data = json.loads(content)
    except Exception:
        m = re.search(r"\{.*\}", content, re.S)
        data = json.loads(m.group(0))

    total = sum(d["weight"] for d in data["dimensions"])
    got = sum(d["score"]*d["weight"] for d in data["dimensions"])
    final = round(got/total*10, 1)   # 归到 0-100

    return {
        "final_score": final,
        "dimensions": data["dimensions"],
        "summary": data.get("summary",""),
        "llm_raw": content,
    }