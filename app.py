import itertools
import math
from copy import deepcopy

import pandas as pd
import streamlit as st

# =========================
# 기본 설정
# =========================
st.set_page_config(
    page_title="H조 순위 시뮬레이터",
    page_icon="🏆",
    layout="wide",
)

# =========================
# 스타일
# =========================
st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}
    .small-card {
        padding: 14px 16px;
        border-radius: 14px;
        border: 1px solid #2f2f2f;
        background: #111111;
        margin-bottom: 10px;
    }
    .highlight-card {
        padding: 16px 18px;
        border-radius: 16px;
        border: 1px solid #3b82f6;
        background: linear-gradient(180deg, #111827 0%, #0f172a 100%);
        margin-bottom: 12px;
    }
    .note-box {
        padding: 14px 16px;
        border-radius: 12px;
        border: 1px solid #2f2f2f;
        background: #0f0f0f;
        margin-bottom: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================
# 데이터
# =========================
INITIAL_STANDINGS = {
    "중앙대": {"승": 5, "패": 1, "득실차": 0},
    "강남대": {"승": 3, "패": 2, "득실차": 0},
    "시립대": {"승": 3, "패": 2, "득실차": 0},
    "인하대": {"승": 3, "패": 3, "득실차": 0},
    "명지대": {"승": 0, "패": 6, "득실차": 0},
}

REMAINING_GAMES = [
    ("G1", "강남대", "시립대"),
    ("G2", "강남대", "인하대"),
    ("G3", "강남대", "중앙대"),
    ("G4", "명지대", "시립대"),
    ("G5", "명지대", "중앙대"),
    ("G6", "시립대", "인하대"),
]

DEFAULT_NOTES = [
    "중앙대는 남은 경기 중 1승만 추가해도 1위 가능성이 매우 높음",
    "강남대와 시립대의 맞대결이 2위 경쟁의 핵심 분기점",
    "인하대는 자력보다 타 팀 결과까지 함께 봐야 하는 상황",
    "명지대는 하위권이지만 남은 경기 결과에 따라 상위권 구도에 영향 가능",
]

# =========================
# 유틸 함수
# =========================
def clone_state(state: dict) -> dict:
    return deepcopy(state)


def apply_result(state: dict, team1: str, team2: str, winner: str, margin: int = 1):
    """승패 + 득실차 반영"""
    if winner not in {team1, team2}:
        return

    loser = team2 if winner == team1 else team1
    state[winner]["승"] += 1
    state[loser]["패"] += 1

    margin = max(1, int(margin))
    state[winner]["득실차"] += margin
    state[loser]["득실차"] -= margin


def to_rank_df(state: dict) -> pd.DataFrame:
    rows = []
    for team, info in state.items():
        wins = info["승"]
        losses = info["패"]
        games = wins + losses
        win_rate = round(wins / games, 3) if games > 0 else 0
        rows.append(
            {
                "팀": team,
                "경기수": games,
                "승": wins,
                "패": losses,
                "승률": win_rate,
                "득실차(가정)": info["득실차"],
            }
        )

    df = pd.DataFrame(rows)
    df = df.sort_values(
        by=["승", "득실차(가정)", "승률", "팀"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)
    df.index = df.index + 1
    df.insert(0, "순위", df.index)
    return df


def get_rank_of_team(df: pd.DataFrame, team: str) -> int:
    row = df[df["팀"] == team]
    if row.empty:
        return -1
    return int(row.iloc[0]["순위"])


def scenario_label(result_map: dict) -> str:
    parts = []
    for game_id, winner in result_map.items():
        parts.append(f"{game_id}:{winner}")
    return " | ".join(parts)


def simulate_all_cases(base_state: dict, fixed_results: dict, unresolved_games: list):
    """
    fixed_results:
        {
          "G1": {"team1":"강남대","team2":"시립대","winner":"강남대","margin":3},
          ...
        }
    unresolved_games:
        [("G2","강남대","인하대"), ...]
    """
    # 먼저 고정 결과 반영
    fixed_state = clone_state(base_state)
    fixed_map_for_label = {}

    for gid, info in fixed_results.items():
        apply_result(
            fixed_state,
            info["team1"],
            info["team2"],
            info["winner"],
            info["margin"],
        )
        fixed_map_for_label[gid] = info["winner"]

    if not unresolved_games:
        df = to_rank_df(fixed_state)
        return [
            {
                "시나리오": scenario_label(fixed_map_for_label) if fixed_map_for_label else "현재 선택 완료",
                "state": fixed_state,
                "df": df,
            }
        ]

    all_results = []
    for bitmask in itertools.product([0, 1], repeat=len(unresolved_games)):
        sim_state = clone_state(fixed_state)
        sim_map = fixed_map_for_label.copy()

        for bit, game in zip(bitmask, unresolved_games):
            gid, team1, team2 = game
            winner = team1 if bit == 0 else team2
            apply_result(sim_state, team1, team2, winner, 1)
            sim_map[gid] = winner

        df = to_rank_df(sim_state)
        all_results.append(
            {
                "시나리오": scenario_label(sim_map),
                "state": sim_state,
                "df": df,
            }
        )

    return all_results


def summarize_team_outcomes(sim_results: list, focus_team: str):
    finish_counter = {}
    for r in sim_results:
        rank = get_rank_of_team(r["df"], focus_team)
        finish_counter[rank] = finish_counter.get(rank, 0) + 1

    total = len(sim_results)
    top2 = sum(v for k, v in finish_counter.items() if k <= 2)
    first = finish_counter.get(1, 0)
    second = finish_counter.get(2, 0)

    return {
        "total": total,
        "top2_count": top2,
        "first_count": first,
        "second_count": second,
        "top2_pct": round(top2 / total * 100, 1) if total else 0.0,
        "first_pct": round(first / total * 100, 1) if total else 0.0,
        "second_pct": round(second / total * 100, 1) if total else 0.0,
        "finish_counter": finish_counter,
    }


def build_full_scenario_df(sim_results: list, teams: list) -> pd.DataFrame:
    rows = []
    for r in sim_results:
        row = {"시나리오": r["시나리오"]}
        df = r["df"]
        for team in teams:
            row[f"{team}_순위"] = get_rank_of_team(df, team)
            team_row = df[df["팀"] == team].iloc[0]
            row[f"{team}_최종전적"] = f"{int(team_row['승'])}승 {int(team_row['패'])}패"
        rows.append(row)

    return pd.DataFrame(rows)


def short_status(rank: int) -> str:
    if rank == 1:
        return "현재 1위"
    if rank == 2:
        return "현재 2위"
    if rank > 2:
        return f"현재 {rank}위"
    return "순위 계산 불가"


# =========================
# 사이드바
# =========================
st.sidebar.title("⚙️ 설정")

focus_team = st.sidebar.selectbox(
    "집중해서 볼 팀",
    list(INITIAL_STANDINGS.keys()),
    index=1,  # 강남대 기본
)

st.sidebar.markdown("### 현재 기준 득실차(가정)")
st.sidebar.caption("동률 시 임시 판단용입니다. 모르면 0으로 두세요.")

base_state = clone_state(INITIAL_STANDINGS)
for team in base_state.keys():
    base_state[team]["득실차"] = st.sidebar.number_input(
        f"{team} 득실차",
        min_value=-100,
        max_value=100,
        value=base_state[team]["득실차"],
        step=1,
        key=f"diff_{team}",
    )

with st.sidebar.expander("참고", expanded=False):
    st.write(
        """
- 이 앱은 남은 경기 결과를 바탕으로 **최종 순위 시뮬레이션**을 합니다.
- 동률이 생기면 여기서는 우선 **승수 → 득실차(가정) → 팀명** 순으로 정렬합니다.
- 실제 대회 공식 규정(승자승, 득실차, 실점 등)이 다르면 최종 결과는 달라질 수 있습니다.
        """
    )

# =========================
# 헤더
# =========================
st.title("🏆 H조 순위 시뮬레이터")
st.markdown(
    f"""
현재 H조 상황을 기준으로 **잔여 경기 결과를 직접 선택**해보면서  
**{focus_team}의 최종 순위 / 2위 가능성 / 전체 시나리오**를 확인할 수 있게 만든 버전입니다.
"""
)

# =========================
# 탭 구성
# =========================
tab1, tab2, tab3 = st.tabs(["현재 상황", "결과 시뮬레이터", "전체 시나리오표"])

# =========================
# 탭 1 - 현재 상황
# =========================
with tab1:
    left, right = st.columns([1.2, 1])

    with left:
        st.subheader("📊 현재 순위")
        current_df = to_rank_df(base_state)
        st.dataframe(current_df, use_container_width=True, hide_index=True)

    with right:
        st.subheader("📌 핵심 포인트")
        for note in DEFAULT_NOTES:
            st.markdown(f"<div class='note-box'>• {note}</div>", unsafe_allow_html=True)

    st.subheader("📅 잔여 경기")
    cols = st.columns(2)
    for idx, (gid, t1, t2) in enumerate(REMAINING_GAMES):
        with cols[idx % 2]:
            st.markdown(
                f"""
                <div class='small-card'>
                    <b>{gid}</b><br>
                    {t1} vs {t2}
                </div>
                """,
                unsafe_allow_html=True,
            )

# =========================
# 탭 2 - 결과 시뮬레이터
# =========================
with tab2:
    st.subheader("🎮 남은 경기 결과 선택")

    selection_options = {}
    margin_inputs = {}
    fixed_results = {}
    unresolved_games = []

    for gid, team1, team2 in REMAINING_GAMES:
        st.markdown(
            f"""
            <div class='small-card'>
                <b>{gid}</b> — {team1} vs {team2}
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns([2, 1])

        with c1:
            selected = st.selectbox(
                f"{gid} 승리 팀",
                ["미정", team1, team2],
                key=f"winner_{gid}",
            )
            selection_options[gid] = selected

        with c2:
            margin = st.number_input(
                f"{gid} 점수차",
                min_value=1,
                max_value=30,
                value=1,
                step=1,
                key=f"margin_{gid}",
            )
            margin_inputs[gid] = margin

        if selected == "미정":
            unresolved_games.append((gid, team1, team2))
        else:
            fixed_results[gid] = {
                "team1": team1,
                "team2": team2,
                "winner": selected,
                "margin": margin,
            }

    # 선택된 결과 반영 후 현재 가상 순위
    projected_state = clone_state(base_state)
    for gid, info in fixed_results.items():
        apply_result(
            projected_state,
            info["team1"],
            info["team2"],
            info["winner"],
            info["margin"],
        )
    projected_df = to_rank_df(projected_state)

    st.markdown("---")
    st.subheader("📈 현재 선택 기준 예상 순위")
    st.dataframe(projected_df, use_container_width=True, hide_index=True)

    focus_rank = get_rank_of_team(projected_df, focus_team)
    status_text = short_status(focus_rank)
    if focus_rank <= 2:
        st.markdown(
            f"""
            <div class='highlight-card'>
                <b>{focus_team}</b> — {status_text}<br>
                현재 선택한 결과만 반영하면 일단 상위 2위 안에 들어갑니다.
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class='small-card'>
                <b>{focus_team}</b> — {status_text}<br>
                현재 선택한 결과만 반영하면 아직 2위 밖입니다.
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 전체 경우의 수 계산
    sim_results = simulate_all_cases(base_state, fixed_results, unresolved_games)
    summary = summarize_team_outcomes(sim_results, focus_team)

    st.subheader("🧮 경우의 수 요약")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("남은 경우의 수", summary["total"])
    m2.metric(f"{focus_team} 2위 이내", f"{summary['top2_count']}회", f"{summary['top2_pct']}%")
    m3.metric(f"{focus_team} 1위", f"{summary['first_count']}회", f"{summary['first_pct']}%")
    m4.metric(f"{focus_team} 2위", f"{summary['second_count']}회", f"{summary['second_pct']}%")

    # 유리한 시나리오 / 불리한 시나리오
    qualify_rows = []
    fail_rows = []

    for r in sim_results:
        rank = get_rank_of_team(r["df"], focus_team)
        team_row = r["df"][r["df"]["팀"] == focus_team].iloc[0]
        row = {
            "시나리오": r["시나리오"],
            "최종 순위": rank,
            "최종 전적": f"{int(team_row['승'])}승 {int(team_row['패'])}패",
            "득실차(가정)": int(team_row["득실차(가정)"]),
        }
        if rank <= 2:
            qualify_rows.append(row)
        else:
            fail_rows.append(row)

    qcol, fcol = st.columns(2)
    with qcol:
        st.subheader(f"✅ {focus_team} 상위 2위 시나리오")
        if qualify_rows:
            st.dataframe(pd.DataFrame(qualify_rows), use_container_width=True, hide_index=True)
        else:
            st.warning("현재 선택 기준으로는 상위 2위 시나리오가 없습니다.")

    with fcol:
        st.subheader(f"⚠️ {focus_team} 탈락 시나리오")
        if fail_rows:
            st.dataframe(pd.DataFrame(fail_rows), use_container_width=True, hide_index=True)
        else:
            st.success("현재 선택 기준으로는 탈락 시나리오가 없습니다.")

# =========================
# 탭 3 - 전체 시나리오표
# =========================
with tab3:
    st.subheader("📚 전체 시나리오 표")
    full_df = build_full_scenario_df(sim_results, list(base_state.keys()))
    st.dataframe(full_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("🌳 요약 흐름")
    st.code(
        f"""[현재 기준] {focus_team} 중심 시뮬레이션
|
+-- 선택 완료 경기: {len(fixed_results)}개
|
+-- 아직 미정 경기: {len(unresolved_games)}개
|
+-- 남은 경우의 수: {summary["total"]}개
|
+-- {focus_team} 2위 이내: {summary["top2_count"]}개 ({summary["top2_pct"]}%)
|
+-- {focus_team} 1위: {summary["first_count"]}개 ({summary["first_pct"]}%)
|
+-- {focus_team} 2위: {summary["second_count"]}개 ({summary["second_pct"]}%)
""",
        language="text",
    )