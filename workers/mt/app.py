import ctranslate2 as ct2
from transformers import AutoTokenizer
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# NLLB model paths (existing and working)
TOK_PATH = "/models/mt/nllb_src"
CT2_PATH = "/models/mt/nllb_ct2"

tokenizer = AutoTokenizer.from_pretrained(TOK_PATH, use_fast=False)
translator = ct2.Translator(CT2_PATH, device="cpu", compute_type="int8")

LANGS = {"pl": "pol_Latn", "en": "eng_Latn"}

def _lang_token(code: str) -> str:
    v = tokenizer.get_vocab()
    candidates = [f"<2{code}>", f"__{code}__", code, f"<<{code}>>"]
    extra = getattr(tokenizer, "additional_special_tokens", None) or []
    candidates.extend([t for t in extra if code in t])
    for t in candidates:
        if t in v:
            return t
    if hasattr(tokenizer, "lang_code_to_id") and code in tokenizer.lang_code_to_id:
        tid = tokenizer.lang_code_to_id[code]
        tok = tokenizer.convert_ids_to_tokens(tid)
        if tok:
            return tok
    raise KeyError(f"Missing language token for {code}")

def _best(res):
    r0 = res[0]
    if hasattr(r0, "hypotheses"):
        return r0.hypotheses[0]
    if hasattr(r0, "sequences"):
        return r0.sequences[0]
    if hasattr(r0, "tokens"):
        return r0.tokens[0]
    raise RuntimeError("Unknown TranslationResult fields")

def _translate(text: str, src: str, tgt: str, *, beam: int, rep_pen: float) -> str:
    if src not in LANGS or tgt not in LANGS:
        raise HTTPException(status_code=400, detail=f"Unsupported {src}->{tgt}")
    tgt_tok = _lang_token(LANGS[tgt])

    toks = []
    if tokenizer.bos_token:
        toks.append(tokenizer.bos_token)
    toks += tokenizer.tokenize(text)
    if tokenizer.eos_token:
        toks.append(tokenizer.eos_token)

    # CT2 4.2.x: avoid no_repeat_ngram_size
    res = translator.translate_batch(
        [toks],
        target_prefix=[[tgt_tok]],
        beam_size=beam,
        repetition_penalty=rep_pen,
        max_decoding_length=min(160, len(toks) * 3),
        end_token=tokenizer.eos_token or "</s>",
        disable_unk=True,
    )
    out = _best(res)
    if out and out[0] == tgt_tok:
        out = out[1:]
    ids = tokenizer.convert_tokens_to_ids(out)
    return tokenizer.decode(ids, skip_special_tokens=True).strip()

app = FastAPI(title="MT Worker")

class Req(BaseModel):
    src: str
    tgt: str
    text: str

@app.get("/health")
def health():
    return {"status": "ok", "family": "nllb"}

@app.post("/translate/fast")
def translate_fast(r: Req):
    return {"text": _translate(r.text, r.src, r.tgt, beam=4, rep_pen=1.2), "mode": "fast"}

@app.post("/translate/final")
def translate_final(r: Req):
    return {"text": _translate(r.text, r.src, r.tgt, beam=8, rep_pen=1.1), "mode": "final"}
