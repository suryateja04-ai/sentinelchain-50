"""Patch the built portal bundle from ten agents to three.

usage: python three_agents_patch.py <site folder>
Every replacement must match the expected number of times, otherwise nothing is written.
"""
import hashlib
import json
import os
import re
import shutil
import sys

site = sys.argv[1]
assets = os.path.join(site, "assets")
src = [f for f in os.listdir(assets) if f.startswith("index-") and f.endswith(".js")]
assert len(src) == 1, src
src = os.path.join(assets, src[0])
s = open(src, encoding="utf-8").read()

GROUPS = [
    ("data-agent", "Data Gathering & Preprocessing", ["data-loader", "validation", "preprocessing", "temporal"]),
    ("prediction", "Sepsis Prediction", ["prediction", "alert"]),
    ("explain-agent", "Explainability & Clinical Guidance", ["explanation", "safety", "report"]),
]


def merge(stages):
    out = []
    for gid, name, ids in GROUPS:
        part = [next(x for x in stages if x["id"] == i) for i in ids]
        bad = [x for x in part if x["status"] != "completed"]
        out.append({"id": gid, "name": name, "status": bad[0]["status"] if bad else "completed",
                    "ms": round(sum(float(x["ms"]) for x in part), 2), "input": part[0]["input"],
                    "output": " · ".join(x["output"] for x in part),
                    "errors": [e for x in part for e in x.get("errors", [])]})
    return out


def sub(old, new, count=1):
    global s
    n = s.count(old)
    if n != count:
        raise SystemExit(f"expected {count} match(es), found {n}: {old[:80]!r}")
    s = s.replace(old, new)


# 1. the ten agent definitions -> three
a = s.index('Ot=[{id:"data-loader"')
b = s.index("}];", a) + 3
sub(s[a:b], 'Ot=[{id:"data-agent",name:"Data Gathering & Preprocessing",code:"AGENT 1 · DATA",lane:"ingest",'
    'summary:"Gathers the latest 16-hour window, validates and cleans it, applies the frozen imputer and scaler, '
    'and measures recent trends.",input:"Patient ID, window end hour",output:"Validated, standardised 16 × 39 window '
    'with quality report and trends",baseLatency:24,cpu:12,memory:400},'
    '{id:"prediction",name:"Sepsis Prediction",code:"AGENT 2 · PREDICTION",lane:"analyse",summary:"Runs eight '
    'trained models, isotonic calibration and the weighted ensemble, decides the alert at threshold 0.047 and '
    'reports precision and sensitivity at that threshold.",input:"Standardised window",output:"Calibrated '
    'probability, per-model scores, alert decision",baseLatency:120,cpu:42,memory:1508},'
    '{id:"explain-agent",name:"Explainability & Clinical Guidance",code:"AGENT 3 · GUIDANCE",lane:"govern",'
    'summary:"Occlusion attribution, observational range flags, decision-support wording (never prescribes) and the '
    'clinician report.",input:"Window, prediction, latest values",output:"Signal contributions, flags, guidance and '
    'report",baseLatency:74,cpu:27,memory:402}];')

# 2. recorded runs: merge each run's ten stages into three
key = "BD=JSON.parse('"
a = s.index(key) + len(key)
b = s.index("')", a)
runs = json.loads(s[a:b])
for r in runs:
    assert len(r["stages"]) == 10, r["trace_id"]
    r["stages"] = merge(r["stages"])
body = json.dumps(runs, ensure_ascii=False, separators=(",", ":"))
assert "'" not in body and "\\" not in body
s = s[:a] + body + s[b:]

# 3. live service answers still carry ten stages: merge them on arrival
merge_js = ('const __mergeAgents3=r=>{if(!r||!Array.isArray(r.stages)||r.stages.length<=3)return r;const g=' + json.dumps(GROUPS) +
            ';return{...r,stages:g.map(([id,name,ids])=>{const p=ids.map(x=>r.stages.find(t=>t.id===x)).filter(Boolean),'
            'b=p.find(t=>t.status!=="completed");return{id,name,status:b?b.status:"completed",'
            'ms:+p.reduce((a,t)=>a+(+t.ms||0),0).toFixed(2),input:p[0]?p[0].input:"",'
            'output:p.map(t=>t.output).join(" · "),errors:p.flatMap(t=>t.errors||[])}})}};')
sub('async function qD(e,{live:t}){', merge_js + 'async function qD(e,{live:t}){')
sub('return t?{...await wk("/api/ml/analyze",{method:"POST",body:{sample_id:e}}),label:n.label,category:n.category,source:"live"}:',
    'return t?__mergeAgents3({...await wk("/api/ml/analyze",{method:"POST",body:{sample_id:e}}),label:n.label,category:n.category,source:"live"}):')

# 4. run animation: agent 1, then prediction, then agent 3 (was 4 + 1 + 5 by position)
sub("for(let re=0;re<4;re+=1){", "for(let re=0;re<1;re+=1){")
sub("prediction:V.stages[4].status", 'prediction:(V.stages.find(t=>t.id==="prediction")||{status:"completed"}).status')
sub("for(let re=5;re<Ot.length;re+=1)", "for(let re=2;re<Ot.length;re+=1)")
sub("await D1(re===5?620:360)", "await D1(re===2?620:360)")
sub("[Ot[re].id]:V.stages[re].status", '[Ot[re].id]:(V.stages.find(t=>t.id===Ot[re].id)||{status:"completed"}).status')

# 5. ward event log keyed by agent
a = s.index('i={"data-loader":["Loaded observation window"')
b = s.index("]};", a) + 3
sub(s[a:b], 'i={"data-agent":["Prepared observation window","Patient ICU-2047, 16 h","Standardised 16×39 tensor · 1 '
    'validation warning (temporal gap) · RR +6/min over 4 h"],prediction:["Generated risk score and alert",'
    '"Standardised tensor","Risk 72% · routed to clinician queue"],"explain-agent":["Explained risk and added '
    'guidance","Prediction + window","RR, Lactate, HR ↑ · Clinical review recommended · Report RPT-2047"]};')
sub('id:u===4?"SC-2047-9F2A":void 0', 'id:u===1?"SC-2047-9F2A":void 0')
sub('status:u===1?"warning":"success",at:t-240*1e3+u*18', 'status:u===0?"warning":"success",at:t-240*1e3+u*18')

# 6. event labels that used the old agent names
sub('agent:"Validation"', 'agent:"Data Gathering & Preprocessing"', 2)
sub('agent:"Prediction"', 'agent:"Sepsis Prediction"', 3)
sub('agent:"Alert"', 'agent:"Sepsis Prediction"', 3)
sub('agent:"Audit"', 'agent:"Orchestrator"', 1)
sub('agent:"Report"', 'agent:"Explainability & Clinical Guidance"', 2)

# 7. texts
sub("A ten-agent pipeline turns", "A three-agent pipeline turns")
sub("Runtime health and resource use of the ten orchestrated agents.",
    "Runtime health and resource use of the three orchestrated agents.")
sub("Ten agents turn a 16-hour observation window", "Three agents turn a 16-hour observation window")
sub("then ten agents validate, explain, safety-check, report and audit it.",
    "then three agents prepare the data, predict the risk, and explain it with clinical guidance.")
sub('children:"Ten agents"', 'children:"Three agents"')
sub("10/10 agents completed", "3/3 agents completed", 2)
sub('title:"Explanation agent"', 'title:"Agent 3 · Explanation"')
sub('title:"Clinical safety agent"', 'title:"Agent 3 · Clinical guidance"')
sub('title:"Temporal analysis agent"', 'title:"Agent 1 · Temporal trends"')
sub('"Validation agent findings"', '"Agent 1 · Validation findings"')

sub('"Data validation & temporal analysis"', '"Agent 1 · Data gathering & preprocessing"')
sub('"Eight-model calibrated ensemble"', '"Agent 2 · Sepsis prediction (eight-model calibrated ensemble)"')
sub('"Explanation, safety review & audit trail"', '"Agent 3 · Explainability & clinical guidance"')

left = [w for w in ("Ten agents", "ten agents", "10/10", "ten-agent", 'id:"data-loader"', "stages[4]")
        if w in s]
assert not left, left

# write under a new content hash so browsers do not keep the old file
h = hashlib.sha256(s.encode()).hexdigest()[:8]
new = os.path.join(assets, f"index-{h}.js")
old_name = os.path.basename(src)
with open(new, "w", encoding="utf-8") as f:
    f.write(s)
os.remove(src)
# one row of three agents, lane labels in thirds, no U-turn to a second row
css = [f for f in os.listdir(assets) if f.startswith("index-") and f.endswith(".css")]
assert len(css) == 1, css
css_path = os.path.join(assets, css[0])
c = open(css_path, encoding="utf-8").read()
c += (".orch-row{grid-template-columns:repeat(auto-fit,minmax(180px,1fr))}"
      ".orch-lanes{grid-template-columns:1fr 1fr 1fr}"
      ".orch-turn,.orch-row--reverse{display:none}")
css_new = os.path.join(assets, f"index-{hashlib.sha256(c.encode()).hexdigest()[:8]}.css")
with open(css_new, "w", encoding="utf-8") as f:
    f.write(c)
os.remove(css_path)
for page in ("index.html", "404.html"):
    p = os.path.join(site, page)
    t = open(p, encoding="utf-8").read()
    assert css[0] in t, page
    open(p, "w", encoding="utf-8").write(t.replace(css[0], os.path.basename(css_new)))
for page in ("index.html", "404.html"):
    p = os.path.join(site, page)
    t = open(p, encoding="utf-8").read()
    assert old_name in t, page
    open(p, "w", encoding="utf-8").write(t.replace(old_name, os.path.basename(new)))
print("patched", old_name, "->", os.path.basename(new), "| runs:",
      [(r["trace_id"], [x["ms"] for x in r["stages"]], r["total_ms"]) for r in runs])
