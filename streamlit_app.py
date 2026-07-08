# 단어친구 웹 (WordFriend Web)
# - 학습/퀴즈: 아이용. 저장소 안의 words.csv + audio/*.mp3 를 그대로 사용
# - 관리: 보호자용. 단어 목록 저장 시 새 단어의 원어민 MP3(edge-tts)를 자동 생성해
#   words.csv 와 함께 GitHub 에 한 번의 커밋으로 반영 → 웹/안드로이드 앱 모두에 적용됨

import asyncio
import base64
import csv
import io
import os
import random
import re
import tempfile

import requests
import streamlit as st

st.set_page_config(page_title="단어친구", page_icon="🦓", layout="centered")

PRAISES = ["Good job!", "Excellent!", "Great!", "Perfect!", "Wonderful!"]

SUPA_URL = "https://mztadmbkbrsvqmsqojcp.supabase.co"
SUPA_KEY = "sb_publishable_Za91TlCA4yg1crtS2-VHHg_r6BOi0an"

VOICES = [
    "en-US-JennyNeural",   # 여성, 또렷하고 자연스러움 (기본)
    "en-US-AnaNeural",     # 어린이 목소리
    "en-US-GuyNeural",     # 남성
    "en-GB-SoniaNeural",   # 영국식
]


# ---------- 공통 ----------

def slug(en: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", en.lower()).strip("_")


def load_words():
    words = []
    if not os.path.exists("words.csv"):
        return words
    with open("words.csv", encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row or row[0].strip() in ("", "en"):
                continue
            row = [c.strip() for c in row] + ["", "", ""]
            words.append({"en": row[0], "ko": row[1], "emoji": row[2], "group": row[3]})
    return words


def audio_path(en: str):
    p = os.path.join("audio", slug(en) + ".mp3")
    return p if os.path.exists(p) else None


def play(en: str, autoplay=False):
    p = audio_path(en)
    if p:
        st.audio(p, autoplay=autoplay)
    else:
        st.caption("🔇 아직 발음 파일이 없어요 (관리 페이지에서 저장하면 생성됩니다)")


def big_card(word):
    st.markdown(
        f"""
        <div style="background:#fff;border-radius:28px;padding:36px 16px;text-align:center;
                    box-shadow:0 4px 14px rgba(0,0,0,.08);margin-bottom:12px;">
          <div style="font-size:64px;line-height:1.1;">{word['emoji']}</div>
          <div style="font-size:52px;font-weight:800;color:#3E3A39;">{word['en']}</div>
          <div style="font-size:26px;color:#8A8580;margin-top:6px;">{word['ko']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------- 학습 ----------

def page_learn(words):
    st.subheader("📖 단어 배우기")
    seen = []
    for w in words:
        if w["group"] and w["group"] not in seen:
            seen.append(w["group"])
    groups = ["🌈 전체"] + seen
    g = st.selectbox("범위", groups)
    cur = [w for w in words if g == "🌈 전체" or w["group"] == g]
    if not cur:
        st.info("단어가 없어요.")
        return

    key = f"learn_idx_{g}"
    idx = st.session_state.get(key, 0) % len(cur)
    w = cur[idx]

    st.caption(f"{idx + 1} / {len(cur)}")
    big_card(w)
    play(w["en"], autoplay=True)

    c1, c2 = st.columns(2)
    if c1.button("◀ 이전", use_container_width=True):
        st.session_state[key] = (idx - 1) % len(cur)
        st.rerun()
    if c2.button("다음 ▶", use_container_width=True, type="primary"):
        st.session_state[key] = (idx + 1) % len(cur)
        st.rerun()


# ---------- 퀴즈 ----------

def make_questions(words, mode):
    pool = random.sample(words, min(10, len(words)))
    qs = []
    for w in pool:
        m = mode if mode != "MIX" else random.choice(["LISTEN", "EN_KO", "KO_EN"])
        use_en = m == "KO_EN"
        answer = w["en"] if use_en else w["ko"]
        wrong = list({(x["en"] if use_en else x["ko"]) for x in words} - {answer})
        choices = random.sample(wrong, min(3, len(wrong))) + [answer]
        random.shuffle(choices)
        qs.append({"w": w, "mode": m, "choices": choices, "answer": answer})
    return qs


def page_quiz(words):
    st.subheader("🎯 퀴즈 놀이")
    if len(words) < 4:
        st.info("퀴즈를 하려면 단어가 4개 이상 필요해요.")
        return

    ss = st.session_state
    if "quiz" not in ss:
        mode = st.radio(
            "어떤 퀴즈로 할까?",
            ["LISTEN", "EN_KO", "KO_EN", "MIX"],
            format_func=lambda m: {
                "LISTEN": "🎧 듣고 뜻 고르기",
                "EN_KO": "👀 영어 보고 뜻 고르기",
                "KO_EN": "🇰🇷 한글 보고 영어 고르기",
                "MIX": "🌈 섞어서!",
            }[m],
        )
        if st.button("시작! 🚀", type="primary", use_container_width=True):
            ss.quiz = {"qs": make_questions(words, mode), "i": 0, "score": 0,
                       "wrong": [], "picked": None}
            st.rerun()
        return

    q = ss.quiz
    if q["i"] >= len(q["qs"]):
        st.markdown(f"## {q['score']} / {len(q['qs'])}")
        st.markdown("완벽해요! 🏆" if q["score"] == len(q["qs"]) else "참 잘했어요! 🌟")
        for w in {x["en"]: x for x in q["wrong"]}.values():
            st.write(f"🔍 **{w['en']}** — {w['ko']}")
            play(w["en"])
        if st.button("한 번 더! 🔁", type="primary", use_container_width=True):
            del ss.quiz
            st.rerun()
        return

    item = q["qs"][q["i"]]
    w = item["w"]
    st.caption(f"{q['i'] + 1} / {len(q['qs'])}")

    if item["mode"] == "LISTEN":
        st.markdown("### 🔊 잘 듣고 뜻을 골라요")
        play(w["en"], autoplay=q["picked"] is None)
    elif item["mode"] == "EN_KO":
        st.markdown(f"### {w['en']}  <span style='font-size:16px;color:#8A8580'>무슨 뜻일까요?</span>", unsafe_allow_html=True)
        play(w["en"], autoplay=q["picked"] is None)
    else:
        st.markdown(f"### {w['ko']}  <span style='font-size:16px;color:#8A8580'>영어로 뭘까요?</span>", unsafe_allow_html=True)

    if q["picked"] is None:
        for c in item["choices"]:
            if st.button(c, use_container_width=True, key=f"c_{q['i']}_{c}"):
                q["picked"] = c
                if c == item["answer"]:
                    q["score"] += 1
                else:
                    q["wrong"].append(w)
                st.rerun()
    else:
        ok = q["picked"] == item["answer"]
        if ok:
            st.success(f"⭕ 정답! **{item['answer']}**")
            p = audio_path(random.choice(PRAISES))
            if p:
                st.audio(p, autoplay=True)
        else:
            st.error(f"❌ 정답은 **{item['answer']}** 이에요")
        if not ok:
            play(w["en"], autoplay=True)
        if st.button("다음 문제 ▶", type="primary", use_container_width=True):
            q["i"] += 1
            q["picked"] = None
            st.rerun()


# ---------- 관리 (보호자) ----------

def gh(path, method="GET", **kw):
    r = requests.request(
        method,
        f"https://api.github.com/repos/{st.secrets['GH_REPO']}/{path}",
        headers={
            "Authorization": f"Bearer {st.secrets['GH_TOKEN']}",
            "Accept": "application/vnd.github+json",
        },
        timeout=30,
        **kw,
    )
    r.raise_for_status()
    return r.json()


def commit_files(files: dict, message: str):
    """여러 파일(경로→bytes)을 GitHub에 '한 번의 커밋'으로 반영"""
    branch = st.secrets.get("GH_BRANCH", "main")
    head = gh(f"git/ref/heads/{branch}")["object"]["sha"]
    base_tree = gh(f"git/commits/{head}")["tree"]["sha"]
    tree = []
    for path, data in files.items():
        blob = gh("git/blobs", "POST",
                  json={"content": base64.b64encode(data).decode(), "encoding": "base64"})
        tree.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    new_tree = gh("git/trees", "POST", json={"base_tree": base_tree, "tree": tree})
    commit = gh("git/commits", "POST",
                json={"message": message, "tree": new_tree["sha"], "parents": [head]})
    gh(f"git/refs/heads/{branch}", "PATCH", json={"sha": commit["sha"]})


def gen_mp3(text: str, voice: str) -> bytes:
    import edge_tts

    async def _run(path):
        await edge_tts.Communicate(text, voice).save(path)

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        path = f.name
    try:
        asyncio.run(_run(path))
        with open(path, "rb") as f:
            return f.read()
    finally:
        os.unlink(path)


def check_admin() -> bool:
    if st.session_state.get("auth"):
        return True
    pw = st.text_input("비밀번호", type="password", key="admin_pw")
    if st.button("확인", key="admin_ok"):
        if pw == st.secrets.get("ADMIN_PASSWORD", ""):
            st.session_state.auth = True
            st.rerun()
        st.error("비밀번호가 달라요")
    return False


def kst(iso: str) -> str:
    """서버 UTC 시각을 한국 시간 문자열로"""
    try:
        from datetime import datetime, timedelta, timezone
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso[:16].replace("T", " ")


def page_report(words):
    st.subheader("📊 학습 리포트")
    if not check_admin():
        return

    try:
        r = requests.get(
            f"{SUPA_URL}/rest/v1/wf_stats?select=*&order=updated_at.desc",
            headers={"apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}"},
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json()
    except Exception as e:
        st.error(f"서버에서 기록을 불러오지 못했어요: {e}")
        return

    if not rows:
        st.info("아직 올라온 기록이 없어요. 아이 폰에서 학습하면 자동으로 올라옵니다.")
        return

    labels = {f"{x.get('child_name') or '기기'} ({x['device_id'][:6]}…)": x for x in rows}
    pick = st.selectbox("기기", list(labels.keys()))
    row = labels[pick]
    st.caption(f"마지막 기록: {kst(row.get('updated_at', ''))} (한국 시간)")

    stats = row.get("stats") or {}
    days = stats.get("days") or {}
    keys = sorted(days.keys(), reverse=True)[:14]

    # ---- 주간 요약: 최근 7일 vs 그 전 7일 ----
    from datetime import date, timedelta
    def day_val(d0, field):
        return (days.get(d0.isoformat()) or {}).get(field, 0)
    t = date.today()
    wk = [t - timedelta(days=i) for i in range(7)]
    prev = [t - timedelta(days=i) for i in range(7, 14)]
    def summary(ds):
        play = sum(day_val(d, "playSec") for d in ds)
        r = sum(day_val(d, "right") for d in ds)
        w = sum(day_val(d, "wrong") for d in ds)
        rate = round(r / (r + w) * 100) if (r + w) else 0
        return play // 60, rate, r + w
    p1, rate1, n1 = summary(wk)
    p0, rate0, n0 = summary(prev)

    c1, c2, c3 = st.columns(3)
    c1.metric("최근 7일 학습", f"{p1}분", delta=f"{p1 - p0:+d}분")
    c2.metric("최근 7일 정답률", f"{rate1}%" if n1 else "-",
              delta=(f"{rate1 - rate0:+d}%p" if n1 and n0 else None))
    c3.metric("최근 7일 문제 수", n1, delta=n1 - n0)

    # ---- 그래프 ----
    import pandas as pd
    ordered = sorted(days.keys())[-14:]
    if ordered:
        df = pd.DataFrame({
            "날짜": [k[5:] for k in ordered],
            "학습(분)": [round(days[k].get("playSec", 0) / 60, 1) for k in ordered],
        }).set_index("날짜")
        st.markdown("##### ⏱ 학습 시간 (최근 14일)")
        st.bar_chart(df, height=220)

        rated = [k for k in ordered
                 if days[k].get("right", 0) + days[k].get("wrong", 0) > 0]
        if rated:
            df2 = pd.DataFrame({
                "날짜": [k[5:] for k in rated],
                "정답률(%)": [
                    round(days[k]["right"] / (days[k]["right"] + days[k].get("wrong", 0)) * 100)
                    if (days[k].get("right", 0) + days[k].get("wrong", 0)) else 0
                    for k in rated
                ],
            }).set_index("날짜")
            st.markdown("##### 🎯 정답률 추이")
            st.line_chart(df2, height=220)

    # ---- 라이트너 상자 분포 ----
    wstats_all = stats.get("words") or {}
    tried = [s for s in wstats_all.values() if s.get("right", 0) + s.get("wrong", 0) > 0]
    if tried:
        dist = {f"상자{b}": sum(1 for s in tried if s.get("box", 0) == b) for b in range(5)}
        weak_n = dist["상자0"] + dist["상자1"]
        st.markdown(f"##### 📦 단어 상태 (약한 단어 {weak_n}개)")
        st.bar_chart(pd.DataFrame([dist]).T.rename(columns={0: "단어 수"}), height=200)
        st.caption("상자0~1 = 자주 나오게 되는 약한 단어 · 상자4 = 완전히 익힌 단어")

    st.markdown("##### 📅 일자별 기록")
    st.dataframe(
        [
            {
                "날짜": k,
                "접속(분)": round(days[k].get("appSec", 0) / 60, 1),
                "학습(분)": round(days[k].get("playSec", 0) / 60, 1),
                "⭕": days[k].get("right", 0),
                "❌": days[k].get("wrong", 0),
                "🎤": days[k].get("speak", 0),
                "⭐": days[k].get("stars", 0),
            }
            for k in keys
        ],
        use_container_width=True, hide_index=True,
    )

    wmap = {w["en"]: w for w in words}
    wstats = stats.get("words") or {}
    weak = sorted(
        ((en, s) for en, s in wstats.items() if s.get("wrong", 0) > 0),
        key=lambda x: -x[1].get("wrong", 0),
    )[:15]
    st.markdown("##### ❗ 많이 틀린 단어")
    if not weak:
        st.caption("틀린 단어가 아직 없어요 👍")
    else:
        st.dataframe(
            [
                {
                    "단어": en,
                    "뜻": wmap.get(en, {}).get("ko", ""),
                    "❌": s.get("wrong", 0),
                    "⭕": s.get("right", 0),
                    "상자(0=약함)": s.get("box", 0),
                    "최근": s.get("last", ""),
                }
                for en, s in weak
            ],
            use_container_width=True, hide_index=True,
        )


def page_admin(words):
    st.subheader("⚙️ 단어 관리 (보호자)")

    if not check_admin():
        return

    st.markdown("한 줄에 한 단어씩 · 형식: `영어,뜻,이모지,그룹` — 그룹은 아이 화면에 그대로 보이니 읽기 쉬운 이름으로 (예: 파닉스 1단계, 동물 단어)")
    cur_text = "\n".join(
        ",".join([w["en"], w["ko"], w["emoji"], w["group"]]).rstrip(",") for w in words)
    text = st.text_area("단어 목록 (이 내용 전체가 그대로 저장됩니다)", cur_text, height=320)
    voice = st.selectbox("발음 목소리", VOICES)
    regen = st.checkbox("모든 발음을 이 목소리로 다시 생성 (목소리를 바꿨을 때 체크)")

    if st.button("💾 저장 → 웹/앱에 적용", type="primary", use_container_width=True):
        new_words = []
        for line in text.splitlines():
            parts = [p.strip() for p in re.split(r"[,\t]", line.strip(), maxsplit=3)]
            if len(parts) >= 2 and parts[0] and parts[1] and parts[0] != "en":
                parts += ["", ""]
                new_words.append({"en": parts[0], "ko": parts[1],
                                  "emoji": parts[2], "group": parts[3]})
        if not new_words:
            st.error("저장할 단어가 없어요. 형식: 영어,뜻")
            return

        buf = io.StringIO()
        buf.write("en,ko,emoji,group\n")
        for w in new_words:
            buf.write(",".join([w["en"], w["ko"], w["emoji"], w["group"]]) + "\n")
        files = {"words.csv": buf.getvalue().encode("utf-8")}

        texts = [w["en"] for w in new_words] + PRAISES
        todo = [t for t in texts if regen or not audio_path(t)]
        prog = st.progress(0.0, text="원어민 발음 생성 중…")
        for i, t in enumerate(todo):
            try:
                files[f"audio/{slug(t)}.mp3"] = gen_mp3(t, voice)
            except Exception as e:
                st.warning(f"{t} 발음 생성 실패: {e}")
            prog.progress((i + 1) / max(len(todo), 1), text=f"발음 생성: {t}")
        prog.empty()

        try:
            commit_files(files, f"words: {len(new_words)}개 저장 (신규 발음 {len(todo)}개)")
        except Exception as e:
            st.error(f"GitHub 저장 실패: {e}")
            return

        st.success(
            f"저장 완료! 단어 {len(new_words)}개 · 발음 {len(todo)}개 생성. "
            "웹은 1~2분 안에 자동 재시작되며, 앱은 다음 실행(또는 단어 관리의 서버 동기화) 때 반영됩니다.")

    st.divider()
    st.markdown("#### 📲 앱 업데이트 배포")
    cur_v, cur_code = "없음", 0
    if os.path.exists("app/version.json"):
        try:
            import json as _json
            v = _json.load(open("app/version.json", encoding="utf-8"))
            cur_code = int(v.get("versionCode") or 0)
            cur_v = f"v{v.get('versionName')} (code {cur_code})"
        except Exception:
            pass
    st.caption(f"서버에 올라온 버전: {cur_v} · 올리면 앱의 관리자 화면 > 🔄 앱 업데이트에서 받을 수 있어요")

    c1, c2 = st.columns(2)
    vname = c1.text_input("versionName (예: 2.2)")
    vcode = c2.number_input(
        "versionCode — build.gradle의 versionCode와 같게, 이전보다 크게",
        min_value=1, step=1, value=max(cur_code + 1, 1),
    )
    if cur_code and vcode <= cur_code:
        st.warning(f"지금 서버 코드({cur_code})보다 커야 폰에서 업데이트 버튼이 켜져요")
    apk = st.file_uploader("서명된 APK 파일", type=["apk"])

    if st.button("📲 APK 업로드", use_container_width=True):
        if not apk or not vname.strip():
            st.error("APK 파일과 versionName 을 입력해 주세요")
        else:
            import json as _json
            data = apk.getvalue()
            meta = _json.dumps({"versionCode": int(vcode), "versionName": vname.strip(),
                                "size": len(data)}).encode("utf-8")
            try:
                with st.spinner(f"업로드 중… ({len(data)//1024} KB)"):
                    commit_files({"app/wordfriend.apk": data, "app/version.json": meta},
                                 f"app: v{vname.strip()} (code {int(vcode)})")
                st.success(f"업로드 완료! 앱에서 [관리자 → 🔄 앱 업데이트] 로 설치할 수 있어요")
            except Exception as e:
                st.error(f"GitHub 저장 실패: {e}")


# ---------- 메인 ----------

words = load_words()
st.markdown("## 🦓 단어친구")
tab = st.sidebar.radio("메뉴", ["📖 단어 배우기", "🎯 퀴즈 놀이", "📊 학습 리포트", "⚙️ 단어 관리"])
if tab.startswith("📖"):
    page_learn(words)
elif tab.startswith("🎯"):
    page_quiz(words)
elif tab.startswith("📊"):
    page_report(words)
else:
    page_admin(words)
