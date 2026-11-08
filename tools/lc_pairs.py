"""컬렉션 일본어 mpak 스크립트 ↔ 한국어 빌드 스크립트(같은 묶음·번호) -> 일본어 글자열: 한국어 글자열 사전."""
import sys,collections,io,contextlib,json; sys.path.insert(0,'tools'); sys.stdout.reconfigure(encoding='utf-8')
import build_game as B
from game_cfg import GAMES
from krsrc import read_map, lc_tokenizer, cut_at_end
from bnscript import archive_table, load_tbl
NL=chr(92)+'n'; X='&#xA;'
pairs=collections.defaultdict(collections.Counter)
for key in ('exe1','exe2','exe3w','exe3b'):
    cfg=GAMES[key]; ldec,_=load_tbl(cfg.lc_jp_tbl); lc=lc_tokenizer(cfg,dec=ldec)
    with contextlib.redirect_stdout(io.StringIO()): parsed,ents,u,c=B.parse(cfg)
    m={a:(o,s) for a,o,s in read_map(cfg.game_dir/'data/msg/message_jap.map')}
    p=(cfg.game_dir/'data/msg/message_jap.mpak').read_bytes()
    for a,(tbl,sp,spans,dl) in parsed.items():
        if a not in m: continue
        o,s=m[a]; d=p[o:o+s]
        try: t=archive_table(d)
        except Exception: continue
        if len(t)!=len(tbl): continue
        st=sorted(set(t))+[len(d)]
        for i in range(len(t)):
            e=min([x for x in st if x>t[i]] or [len(d)])
            jtoks=cut_at_end(lc.tokens(d,t[i],e))
            if tbl[i] not in spans: continue
            ktoks=spans[tbl[i]]
            # 글자 구간 단위로 맞대기(명령 수가 같을 때)
            def runs(toks):
                out,cur=[], ''
                for k,b,x in toks:
                    if k=='chr': cur+= (X if x==NL else x)
                    else:
                        if cur: out.append(cur); cur=''
                if cur: out.append(cur)
                return out
            jr,kr=runs(jtoks),runs(ktoks)
            whole_j=X.join(jr); whole_k=X.join(kr)
            if jr and kr: pairs[whole_j.strip()][whole_k.strip()]+=1
            if len(jr)==len(kr):
                for x,y in zip(jr,kr): pairs[x.strip()][y.strip()]+=1
out={k:v.most_common(1)[0][0] for k,v in pairs.items() if k}
json.dump(out,open('work/lc_jp_ko.json','w',encoding='utf-8'),ensure_ascii=False,indent=0)
print(len(out))
