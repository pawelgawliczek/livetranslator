import time
stt_partial=0
stt_final=0
mt_final_ok=0
mt_final_err=0
last_ready_ts=0.0
def scrape()->str:
    return "\n".join([
        f"stt_partial {stt_partial}",
        f"stt_final {stt_final}",
        f"mt_final_ok {mt_final_ok}",
        f"mt_final_err {mt_final_err}",
        f"last_ready_ts {last_ready_ts or 0.0}",
        ""
    ])
