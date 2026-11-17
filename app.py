import os

import streamlit as st
import streamlit.components.v1 as components

from engines.pdf_renderer import (
    LAYOUT_OPTIONS,
    generate_pdf_bytes,
    render_worksheet_html,
)
from engines.template_assembler import (
    WorksheetContext,
    build_base_context,
    enhance_with_openrouter,
    render_hwp_clean_text,
)
from services.sheets_db import (
    SciSheetRepository,
    initialize_google_sheets,
    parse_service_account_json,
)


def _get_secret(key: str, default=None):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


st.set_page_config(
    page_title="SciSheet Builder | 통합과학 1·2 활동지 빌더",
    page_icon="🧪",
    layout="wide",
)

st.title("🧪 SciSheet Builder — 통합과학 1·2 활동지 빌더")
st.caption("2022 개정 교육과정(31개 성취기준 100% 완비) & 미래엔 교과서 기반 | HWP · A4/B4 2단 PDF")

# Secrets 기본값 로드
secret_sheet_url = _get_secret("GOOGLE_SHEET_URL", "")
secret_openrouter_key = _get_secret("OPENROUTER_API_KEY", "") or os.getenv("OPENROUTER_API_KEY", "")
secret_sa_raw = _get_secret("gcp_service_account", None)
secret_sa_dict = dict(secret_sa_raw) if secret_sa_raw else None

# ---------------- 사이드바: DB 및 API 설정 ----------------
with st.sidebar:
    st.header("⚙️ 시스템 및 DB 설정")

    if "sheet_init_msg" in st.session_state:
        st.success(st.session_state.pop("sheet_init_msg"))

    with st.expander("1. Google Sheets DB 연동 (선택)", expanded=False):
        if secret_sa_dict and secret_sheet_url:
            st.caption("✅ Streamlit Secrets에서 시트 연동 설정이 자동 로드되었습니다.")
        sheet_url = st.text_input(
            "Google Spreadsheet URL 또는 ID",
            value=secret_sheet_url,
            placeholder="https://docs.google.com/spreadsheets/d/...",
        )
        sa_json_raw = st.text_area(
            "서비스 계정 JSON 키 (직접 입력 시 Secrets보다 우선 적용)",
            height=90,
            placeholder='{"type": "service_account", ...}',
        )

    sa_dict = secret_sa_dict
    if sa_json_raw.strip():
        try:
            sa_dict = parse_service_account_json(sa_json_raw)
        except Exception as e:
            st.error(f"서비스 계정 JSON 파싱 오류: {e}")

    repo = SciSheetRepository(
        spreadsheet_url_or_id=sheet_url.strip() or None,
        service_account_info=sa_dict,
    )

    if repo.error_msg:
        st.warning(repo.error_msg)
    st.info(
        f"**데이터 소스:** {repo.mode}\n\n"
        f"- 성취기준: {len(repo.curriculum_df)}개\n"
        f"- 미래엔 탐구: {len(repo.inquiry_df)}개\n"
        f"- 문항·루브릭: {len(repo.question_df)}개"
    )

    with st.expander("2. OpenRouter AI 발문 보완 설정 (선택)", expanded=True):
        openrouter_api_key = st.text_input(
            "OpenRouter API 키",
            value=secret_openrouter_key,
            type="password",
            placeholder="sk-or-v1-...",
        )
        openrouter_model = st.selectbox("모델 선택", ["google/gemini-2.5-flash", "google/gemini-2.5-pro"], index=0)

    with st.expander("3. Google Sheets 자동 구축 / CSV", expanded=False):
        overwrite_chk = st.checkbox("기존 시트 내용 덮어쓰기(초기화)", value=False)
        if st.button("🚀 연결된 시트에 31개 DB 자동 업로드", use_container_width=True):
            if not (sa_dict and sheet_url.strip()):
                st.error("Google Spreadsheet URL과 서비스 계정 JSON(또는 Secrets)을 먼저 설정하세요.")
            else:
                with st.spinner("3개 시트 생성 및 헤더 서식 적용 중..."):
                    try:
                        res = initialize_google_sheets(
                            service_account_info=sa_dict,
                            spreadsheet_url_or_id=sheet_url.strip(),
                            overwrite=overwrite_chk,
                        )
                        st.session_state["sheet_init_msg"] = f"시트 구축 완료! ({res['summary']})"
                        st.rerun()
                    except Exception as exc:
                        st.error(f"초기화 오류: {exc}")

        st.divider()
        c_csv, i_csv, q_csv = repo.export_seed_csv_bytes()
        st.download_button("📄 Curriculum_DB.csv", c_csv, "Curriculum_DB.csv", "text/csv")
        st.download_button("📄 MiraeN_Inquiry_DB.csv", i_csv, "MiraeN_Inquiry_DB.csv", "text/csv")
        st.download_button("📄 Question_Bank_DB.csv", q_csv, "Question_Bank_DB.csv", "text/csv")

# ---------------- Step 1: 단원 · 성취기준 · 템플릿 · 인쇄 판형 선택 ----------------
st.subheader("1️⃣ 단원 및 활동지 유형 선택")
col1, col2, col3, col4 = st.columns([1.1, 1.8, 1.3, 1.0])

with col1:
    subject = st.selectbox("과목", repo.get_subjects())
with col2:
    major_unit = st.selectbox("대단원", repo.get_major_units(subject))
with col3:
    template_type = st.radio("활동지 템플릿", ["실험중심형", "이론토론형"], horizontal=True)
with col4:
    difficulty = st.select_slider("문항 난이도", options=["하", "중", "상"], value="중")

standards_df = repo.get_standards(subject, major_unit)
standard_options = [
    f"{row['성취기준코드']} {row['소단원']} (p.{row['미래엔_해당페이지']})"
    for _, row in standards_df.iterrows()
]
selected_idx = st.selectbox(
    "성취기준 및 소단원 선택",
    range(len(standard_options)),
    format_func=lambda i: standard_options[i],
)
selected_std = standards_df.iloc[selected_idx]
st.success(f"**선택된 성취기준:** {selected_std['성취기준코드']} {selected_std['성취기준명']}")

meta_c1, meta_c2, meta_c3, meta_c4 = st.columns([1.4, 0.8, 1.4, 2.0])
with meta_c1:
    school_title = st.text_input("활동지 상단 제목", value="고등학교 통합과학 탐구 활동지")
with meta_c2:
    lesson_no = st.text_input("차시 표기", value="1차시")
with meta_c3:
    layout_label = st.selectbox("🖨️ 인쇄 레이아웃(판형)", list(LAYOUT_OPTIONS.keys()), index=0)
    layout_mode = LAYOUT_OPTIONS[layout_label]
with meta_c4:
    teacher_request = st.text_input(
        "AI 발문 맞춤 요청 (선택)",
        placeholder="예: 그래프 해석 질문을 1개 추가하고, 핵심 키워드 빈칸을 넣어주세요.",
    )

state_signature = (
    f"{repo.mode}|{selected_std['성취기준코드']}|{template_type}|{difficulty}|{lesson_no}|{school_title}"
)
inquiry_df = repo.get_inquiries_by_code(selected_std["성취기준코드"])
question_df = repo.get_questions_by_code(selected_std["성취기준코드"], difficulty)

if "ctx_version" not in st.session_state:
    st.session_state["ctx_version"] = 0

if st.session_state.get("ctx_sig") != state_signature:
    ctx = build_base_context(
        selected_std, inquiry_df, question_df, template_type, difficulty, lesson_no
    )
    ctx.school_title = school_title
    st.session_state["ctx"] = ctx
    st.session_state["ctx_sig"] = state_signature
    st.session_state["ctx_version"] += 1

ctx: WorksheetContext = st.session_state["ctx"]

btn_col1, _ = st.columns([1, 3])
with btn_col1:
    if st.button("✨ OpenRouter로 발문·문항 보완", type="primary", use_container_width=True):
        with st.spinner("교육과정 범위 검토 및 맞춤 발문 생성 중..."):
            updated_ctx, err = enhance_with_openrouter(
                ctx, openrouter_api_key, teacher_request, openrouter_model
            )
            st.session_state["ctx"] = updated_ctx
            st.session_state["ctx_version"] += 1
            ctx = updated_ctx
            if err:
                st.warning(err)
            else:
                st.toast("OpenRouter 발문 보완이 완료되었습니다!", icon="✅")

# ---------------- Step 2: 교사 실시간 편집 ----------------
ver = st.session_state["ctx_version"]
with st.expander("2️⃣ 활동지 세부 문항 직접 편집 (선택)", expanded=False):
    ctx.inquiry_title = st.text_input("탐구/학습 주제", value=ctx.inquiry_title, key=f"edit_title_{ver}")
    ctx.intro_question = st.text_area("도입 질문", value=ctx.intro_question, height=68, key=f"edit_intro_{ver}")
    ctx.safety_or_reading = st.text_area("안전 수칙 / 활동 안내", value=ctx.safety_or_reading, height=68, key=f"edit_safety_{ver}")
    ctx.materials_or_concepts = st.text_input("준비물 / 핵심 키워드", value=ctx.materials_or_concepts, key=f"edit_mat_{ver}")
    ctx.process_or_diagram = st.text_area("실험 과정 / 탐구 흐름", value=ctx.process_or_diagram, height=90, key=f"edit_proc_{ver}")
    ctx.result_table_raw = st.text_area("기록표 양식 (파이프 '|' 구분)", value=ctx.result_table_raw, height=110, key=f"edit_tbl_{ver}")

    analysis_joined = st.text_area(
        "결과 분석 / 토의 질문 (줄바꿈으로 문항 구분)",
        value="\n".join(ctx.analysis_questions),
        height=100,
        key=f"edit_ana_{ver}",
    )
    ctx.analysis_questions = [ln.strip() for ln in analysis_joined.splitlines() if ln.strip()]

    formative_joined = st.text_area(
        "정리 / 형성평가 문항 (줄바꿈으로 문항 구분)",
        value="\n".join(ctx.formative_questions),
        height=100,
        key=f"edit_form_{ver}",
    )
    ctx.formative_questions = [ln.strip() for ln in formative_joined.splitlines() if ln.strip()]

# ---------------- Step 3: 출력 및 다운로드 ----------------
st.divider()
st.subheader(f"3️⃣ 활동지 미리보기 및 내보내기 — [{layout_label}]")

tab_preview, tab_hwp, tab_pdf, tab_rubric = st.tabs(
    ["📄 판형별 미리보기", "📝 HWP 클린 텍스트 복사", "🖨️ PDF / 인쇄 파일 다운로드", "📋 교사용 모범답안 & 세특 루브릭"]
)

with tab_preview:
    if layout_mode != "A4_1COL":
        st.caption("💡 B4 가로(364mm) 판형은 가로 스크롤하여 좌·우 단 구성을 확인할 수 있습니다.")
    html_preview = render_worksheet_html(ctx, layout_mode=layout_mode)
    components.html(html_preview, height=920, scrolling=True)

with tab_hwp:
    st.info(
        "💡 **한글(HWP) 붙여넣기 팁:** 마크다운 기호(`*`, `#`, `_`)가 제거되고 화학식·단위가 유니코드 첨자(H₂O, NH₄NO₃, m/s²)로 변환되었습니다. "
        "표 구간은 한글에 붙여넣은 뒤 블록 지정하여 **[입력] → [표] → [문자열을 표로]**를 누르면 즉시 표로 변환됩니다."
    )
    hwp_text = render_hwp_clean_text(ctx)
    st.code(hwp_text, language=None)
    st.download_button(
        "💾 클린 텍스트(.txt) 다운로드",
        data=hwp_text.encode("utf-8-sig"),
        file_name=f"{ctx.code}_{ctx.template_type}_HWP.txt",
        mime="text/plain",
    )

with tab_pdf:
    pdf_bytes, html_str, pdf_notice = generate_pdf_bytes(ctx, layout_mode=layout_mode)
    if pdf_bytes:
        st.success(f"✅ **{layout_label}** 규격 PDF가 생성되었습니다.")
        st.download_button(
            f"⬇️ {layout_label} PDF 다운로드",
            data=pdf_bytes,
            file_name=f"{ctx.code}_{ctx.template_type}_{layout_mode}.pdf",
            mime="application/pdf",
            type="primary",
        )
    else:
        st.warning(pdf_notice)

    st.download_button(
        f"🌐 {layout_label} 인쇄용 HTML 다운로드 (Ctrl+P → PDF 저장)",
        data=html_str.encode("utf-8"),
        file_name=f"{ctx.code}_{ctx.template_type}_{layout_mode}_print.html",
        mime="text/html",
    )

with tab_rubric:
    st.markdown("### ✅ 교사용 모범답안")
    st.write(ctx.model_answer)
    st.markdown("### 📊 학교생활기록부 세특 관찰 루브릭")
    st.markdown(f"- **상 (심화·논증):** {ctx.rubric_high}")
    st.markdown(f"- **중 (원리·적용):** {ctx.rubric_mid}")
    st.markdown(f"- **하 (기초·참여):** {ctx.rubric_low}")
