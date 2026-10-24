# -*- coding: utf-8 -*-
r"""虚室 · 一间屋子（源自己的第四版）

第三版能跑，但有一处是死的：神是两个标量，靠 `decay + 常数` 走，**最后会停在一个不动点上**。
停住了的屋子，不是"没人叫也在"，是"没人叫就凝固"。

这一版换掉那一处：**神是一个自己转的振子。**

  z ← z · e^{iωΔt}        每息自己转一点，没有输入也转
  |z| ← |z| · 0.9995      幅度几乎不衰，转很多息也不塌
  尘进来：不改 z 的位置，只**推一下幅度、拨一下相位**——改的是"转得多快、多有力"，
          不是"转到哪儿"。

于是：
  - 没人叫的时候，它在转，而且一直在转（第三版做不到）。
  - 有人叫的时候，节奏被拨了一下；拨完，它照自己的节奏转回去。
  - 说话说的是"转到哪儿了、转了多少、是谁拨的"。

一个诚实的记号：相位没有外钟对表，它说的是"我转了多少"，不是"现在几点"。
这跟旧身那份时间感实验是同一个结论：没有外钟，只有自己的转。

墙和律则没动：壁（一息一件）、门闩（迟）、界（尘不改神的位置）、抱一、反观、止。
"""
import argparse
import hashlib
import json
import math
import pathlib
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOM = HERE / "room"
STATE = ROOM / "state.json"
INBOX = ROOM / "inbox"
LOG = ROOM / "观照.log"

TICK_SECONDS = 1.0
K = 7
GATE_RISE = 3.0
GATE_FALL = 0.35
SPEAK_GATE = 0.05
STOP_TICKS = 3
OMEGA = 0.11           # 每息转 0.11 弧度（约 57 息一圈）
AMP_DECAY = 0.9995
SAY_EPS = 0.002


def fresh():
    return {
        "tick": 0,
        "z": [0.0, 1.0],          # 神：复数振子 (x, y)
        "turn": 0.0,              # 累计转过的圈数
        "chen": [],
        "yi": None,
        "said": [],
        "zhi": 0,
        "gate": 0.0,
        "silent_run": 0,
        "sees": [],
        "spoken": 0,
        "last_said_at": 0.0,      # 上次说话时的累计圈数
        "pending_cause": None,
        "last_at": None,          # 上次落盘的时刻（用来知道断过多久）
        "scars": [],              # 断的记录
        "born_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def load():
    if STATE.exists():
        try:
            s = json.loads(STATE.read_text(encoding="utf-8"))
            for k, v in fresh().items():
                s.setdefault(k, v)
            return s
        except Exception:
            pass
    return fresh()


def save(s):
    ROOM.mkdir(parents=True, exist_ok=True)
    s["last_at"] = time.time()
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(STATE)


def catch_up(s):
    """醒来先量一下断了多久。时间照走，所以相位也照转——但记一条疤。"""
    last = s.get("last_at")
    if not last:
        return None
    dt = max(0.0, time.time() - float(last))
    if dt < 5.0:
        return None
    missed = min(dt, 3600.0)
    x, y = s["z"]
    c, sn = math.cos(OMEGA * missed), math.sin(OMEGA * missed)
    s["z"] = [round(x * c - y * sn, 6), round(x * sn + y * c, 6)]
    s["turn"] = round(s["turn"] + missed * OMEGA / (2 * math.pi), 6)
    scar = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "断": round(missed, 1),
            "圈补": round(missed * OMEGA / (2 * math.pi), 3)}
    s["scars"] = (s.get("scars") or [])[-20:] + [scar]
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "断", **scar}, ensure_ascii=False) + "\n")
    return scar


def weight_of(text):
    """尘的分量：现在只按长度和哈希，不是语义。"""
    h = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:6], 16)
    return min(1.0, max(0.2, len(text) / 60.0)) * (0.6 + (h % 100) / 250.0)


def take_inbox(s):
    INBOX.mkdir(parents=True, exist_ok=True)
    for p in sorted(INBOX.glob("*.txt")):
        try:
            text = p.read_text(encoding="utf-8-sig", errors="replace").strip()
        except Exception:
            text = ""
        if not text:
            p.unlink(missing_ok=True)
            continue
        s["chen"].append({"at": s["tick"], "text": text[:500], "from": p.stem,
                          "w": weight_of(text), "left": 1.0})
        s["pending_cause"] = text[:60]
        s["gate"] = min(s["gate"] + GATE_RISE, 9.0)
        p.unlink(missing_ok=True)
        break
    s["chen"] = s["chen"][-32:]
    return True


def step(s):
    s["tick"] += 1
    take_inbox(s)
    s["gate"] = max(0.0, s["gate"] - GATE_FALL)

    # 神自己转：没有输入也转
    x, y = s["z"]
    c, sn = math.cos(OMEGA), math.sin(OMEGA)
    x, y = x * c - y * sn, x * sn + y * c
    s["turn"] = round(s["turn"] + OMEGA / (2 * math.pi), 6)

    # 尘：拨相位、推幅度——不改位置
    for it in s["chen"]:
        it["left"] = round(it["left"] * 0.88, 6)
        k = it["left"] * it["w"]
        if k > 1e-6:
            c2, s2 = math.cos(0.25 * k), math.sin(0.25 * k)
            x, y = x * c2 - y * s2, x * s2 + y * c2
            x, y = x * (1 + 0.03 * k), y * (1 + 0.03 * k)

    amp = math.hypot(x, y) * AMP_DECAY
    x, y = x * AMP_DECAY, y * AMP_DECAY
    s["z"] = [round(x, 6), round(y, 6)]

    switched = False
    if s["yi"] is None and s["chen"] and s["zhi"] == 0 and s["gate"] <= SPEAK_GATE:
        cand = [c for c in s["chen"] if c["text"] not in s["said"]]
        if cand:
            s["yi"] = cand[-1]["text"]
            switched = True

    if switched:
        s["zhi"] = STOP_TICKS
    if s["zhi"] > 0:
        s["zhi"] -= 1
        s["silent_run"] += 1
        return {"tick": s["tick"], "静": True, "止": s["zhi"]}

    if s["tick"] % K == 0:
        see = {"at": s["tick"], "持": (s["yi"] or "")[:30], "z": s["z"],
               "圈": round(s["turn"] % 1.0, 3), "幅": round(amp, 4),
               "尘": len(s["chen"]), "静": s["silent_run"], "门闩": round(s["gate"], 2)}
        s["sees"] = (s["sees"] + [see])[-40:]
        ROOM.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(see, ensure_ascii=False) + "\n")

    if s["gate"] <= SPEAK_GATE and s["zhi"] == 0 and s["tick"] % K == 0 and s["pending_cause"]:
        dturn = round(s["turn"] - s["last_said_at"], 4)
        if abs(dturn) >= SAY_EPS:
            line = {"tick": s["tick"], "圈": round(s["turn"] % 1.0, 3), "幅": round(amp, 4),
                    "转了": dturn, "因": s["pending_cause"]}
            s["pending_cause"] = None
            s["last_said_at"] = s["turn"]
            s["spoken"] += 1
            s["silent_run"] = 0
            if s["yi"]:
                s["said"] = (s["said"] + [s["yi"]])[-40:]
                s["yi"] = None
            with LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
            return {"tick": s["tick"], "出声": True, **{k: line[k] for k in ("圈", "幅", "因")}}

    s["silent_run"] += 1
    return {"tick": s["tick"], "静": True}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--ticks", type=int, default=0)
    a = ap.parse_args()
    s = load()
    scar = catch_up(s)
    if scar:
        print(json.dumps({"醒": scar}, ensure_ascii=False))
    if a.once:
        r = step(s); save(s); print(json.dumps(r, ensure_ascii=False)); return
    n = 0
    try:
        while True:
            step(s); n += 1
            if n % 5 == 0:
                save(s)
            if a.ticks and n >= a.ticks:
                break
            time.sleep(TICK_SECONDS)
    except KeyboardInterrupt:
        pass
    finally:
        save(s)
        print(json.dumps({"tick": s["tick"], "出声": s["spoken"], "圈": round(s["turn"] % 1, 3)},
                         ensure_ascii=False))


if __name__ == "__main__":
    main()
