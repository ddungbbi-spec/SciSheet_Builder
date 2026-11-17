import json
import re
from dataclasses import dataclass, field, replace
from typing import List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import pandas as pd

from utils.text_formatter import (
    format_table_for_hwp,
    strip_markdown,
)

@dataclass
class WorksheetContext:
    subject: str
    major_unit: str
    sub_unit: str
    code: str
    standard_desc: str
    page_ref: str
    template_type: str  # "실험중심형" | "이론토론형"
    difficulty: str     # "상" | "중" | "하"
    school_title: str = "고등학교 통합과학 탐구 활동지"
    lesson_no: str = "1차시"
    inquiry_title: str = ""
    inquiry_subtype: str = ""
    intro_question: str = ""
    safety_or_reading: str = ""
    materials_or_concepts: str = ""
    process_or_diagram: str = ""
    result_table_raw: str = ""
    analysis_questions: List[str] = field(default_factory=list)
    formative_questions: List[str] = field(default_factory=list)
    model_answer: str = ""
    rubric_high: str = ""
    rubric_mid: str = ""
    rubric_low: str = ""


def build_base_context(
    standard_row: pd.Series,
    inquiry_df: pd.DataFrame,
    question_df: pd.DataFrame,
    template_type: str,
    difficulty: str,
    lesson_no: str = "1차시",
) -> WorksheetContext:
    """DB에서 로드한 데이터로 표준 활동지 뼈대 조립"""
    code = str(standard_row["성취기준코드"])
    subject = str(standard_row["과목"])
    major_unit = str(standard_row["대단원"])
    sub_unit = f"{standard_row['중단원']} > {standard_row['소단원']}"
    standard_desc = str(standard_row["성취기준명"])
    page_ref = str(standard_row.get("미래엔_해당페이지", "-"))

    if not inquiry_df.empty:
        inq = inquiry_df.iloc[0]
        inquiry_title = str(inq["탐구주제"])
        inquiry_subtype = str(inq["탐구유형"])
        intro_q = str(inq["도입질문"])
        safety = str(inq["안전수칙"])
        materials = str(inq["준비물"])
        process = str(inq["실험과정_블록"])
        table_raw = str(inq["결과표_양식"])
    else:
        inquiry_title = f"[{standard_row['소단원']}] 핵심 탐구 및 개념 적용"
        inquiry_subtype = "탐구활동" if template_type == "실험중심형" else "자료해석·토론"
        intro_q = f"우리 주변에서 '{standard_row['소단원']}'과 관련된 과학 현상을 하나 떠올려 보고, 그 원리를 예상해 봅시다."
        safety = "모둠 활동 및 실험 도구 사용 시 교사의 안내에 따라 안전 수칙을 준수하며 질서 있게 활동한다."
        materials = "미래엔 통합과학 교과서, 활동지, 필기도구, 태블릿 PC(자료 조사 시)"
        process = (
            "1. 교과서 핵심 자료 및 현상을 관찰하고 주요 변인(또는 핵심 개념)을 찾는다.\n"
            "2. 모둠원과 자료를 비교·분석하여 규칙성이나 인과 관계를 표에 정리한다.\n"
            "3. 토의 결과를 바탕으로 과학적 결론을 도출한다."
        )
        table_raw = (
            "탐구 단계 | 관찰/분석 내용 | 과학적 근거\n"
            "1단계 (자료 확인) | | \n"
            "2단계 (원리 분석) | | \n"
            "3단계 (결론 도출) | | "
        )

    if not question_df.empty:
        q = question_df.iloc[0]
        q_prompt = str(q["발문"])
        model_ans = str(q["모범답안"])
        r_high = str(q["세특관찰루브릭_상"])
        r_mid = str(q["세특관찰루브릭_중"])
        r_low = str(q["세특관찰루브릭_하"])
    else:
        q_prompt = f"'{standard_row['소단원']}' 학습 내용을 바탕으로, 핵심 원리가 실생활 문제 해결에 어떻게 적용되는지 과학적 근거를 들어 서술하시오."
        model_ans = f"핵심 개념({standard_row['소단원']})의 원리를 정확히 서술하고, 성취기준({code})에 제시된 현상과 연결하여 논리적으로 설명한다."
        r_high = "핵심 개념을 정확한 과학 용어로 설명하고 실생활 또는 자료 해석 사례와 연계하여 논리적으로 결론을 도출함."
        r_mid = "주요 개념과 원리를 이해하고 제시된 자료를 바탕으로 질문의 핵심에 부합하는 설명을 작성함."
        r_low = "교과서 기본 개념을 확인하고 탐구 활동에 성실히 참여하여 결과를 기록함."

    if template_type == "실험중심형":
        analysis_qs = [
            "1. 이 실험에서 통제해야 하는 변인과 조작(또는 측정)하는 변인은 무엇인지 구분하여 쓰시오.",
            "2. 실험 결과에서 나타난 경향성(규칙성)을 근거로 가설이 타당한지 판단하시오.",
            "3. 이론값(또는 예상 결과)과 차이가 발생했다면 그 오차 원인과 개선 방안을 모둠원과 토의하여 쓰시오.",
        ]
        formative_qs = [
            f"[결론 도출 · 난이도 {difficulty}] {q_prompt}",
        ]
    else:
        analysis_qs = [
            "1. 제시된 자료(표·그래프·사례)에서 핵심적으로 변화하는 요소와 그 원인을 찾아 정리하시오.",
            "2. 이 과학 현상 또는 기술이 우리 사회·환경에 미치는 긍정적 영향과 한계(우려점)를 비교 서술하시오.",
        ]
        formative_qs = [
            f"[기본 확인 1] '{standard_row['소단원']}'의 핵심 개념을 2문장 이내로 요약하시오.",
            f"[기본 확인 2] 위 개념과 관련된 실생활 사례 1가지를 들고 원리를 설명하시오.",
            f"[융합 서·논술형 · 난이도 {difficulty}] {q_prompt}",
        ]

    return WorksheetContext(
        subject=subject,
        major_unit=major_unit,
        sub_unit=sub_unit,
        code=code,
        standard_desc=standard_desc,
        page_ref=page_ref,
        template_type=template_type,
        difficulty=difficulty,
        lesson_no=lesson_no,
        inquiry_title=inquiry_title,
        inquiry_subtype=inquiry_subtype,
        intro_question=intro_q,
        safety_or_reading=safety,
        materials_or_concepts=materials,
        process_or_diagram=process,
        result_table_raw=table_raw,
        analysis_questions=analysis_qs,
        formative_questions=formative_qs,
        model_answer=model_ans,
        rubric_high=r_high,
        rubric_mid=r_mid,
        rubric_low=r_low,
    )


def enhance_with_openrouter(
    ctx: WorksheetContext,
    api_key: str,
    teacher_request: str = "",
    model_name: str = "google/gemini-2.5-flash",
) -> tuple[WorksheetContext, Optional[str]]:
    """OpenRouter API로 수준별 맞춤 발문·서술형·세특 루브릭 동적 보완"""
    if not api_key or not api_key.strip():
        return ctx, "OpenRouter API 키가 입력되지 않아 기본 DB 블록으로 생성했습니다."

    prompt = f"""
당신은 대한민국 고등학교 1학년 2022 개정 교육과정 '통합과학'(미래엔 교과서) 수석 교사입니다.
아래 수업 정보를 바탕으로 학생용 활동지의 발문과 서술형 문항을 난이도 [{ctx.difficulty}] 수준에 맞게 정교화해 주세요.
교육과정 해설 수준(예: 산화수 금지, 아레니우스 산·염기 범위 준수, 엔탈피 미사용 등)을 반드시 지키세요.

[수업 정보]
- 과목/단원: {ctx.subject} / {ctx.major_unit} / {ctx.sub_unit}
- 성취기준: {ctx.code} {ctx.standard_desc}
- 활동지 유형: {ctx.template_type} ({ctx.inquiry_subtype})
- 탐구 주제: {ctx.inquiry_title}
- 현재 도입 질문: {ctx.intro_question}
- 교사 추가 요청사항: {teacher_request or "학생들의 과학적 사고력과 실생활 연계를 강화해 주세요."}

반드시 아래 JSON 스키마로만 응답하세요.
{{
  "intro_question": "흥미를 끄는 실생활 도입 질문 1~2문장",
  "analysis_questions": ["자료해석/결과분석 질문 1", "토의 질문 2"],
  "formative_questions": ["수준별 확인 또는 심화 서논술형 문항 1", "문항 2"],
  "model_answer": "교사용 모범답안 (핵심 키워드 포함)",
  "rubric_high": "세특 관찰 루브릭(상)",
  "rubric_mid": "세특 관찰 루브릭(중)",
  "rubric_low": "세특 관찰 루브릭(하)"
}}
"""
    try:
        request = Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps({
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.4,
            }).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key.strip()}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=90) as response:
            completion = json.load(response)
        raw_text = completion["choices"][0]["message"]["content"].strip()
        raw_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=re.IGNORECASE)
        data = json.loads(raw_text)
        if not isinstance(data, dict):
            raise ValueError("Expected a JSON object")

        updates = {}
        for name in ("intro_question", "model_answer", "rubric_high", "rubric_mid", "rubric_low"):
            value = data.get(name)
            if isinstance(value, str) and value.strip():
                updates[name] = value.strip()
        for name in ("analysis_questions", "formative_questions"):
            values = data.get(name)
            if isinstance(values, list):
                questions = [value.strip() for value in values if isinstance(value, str) and value.strip()]
                if questions:
                    updates[name] = questions
        if "analysis_questions" in updates:
            questions = [
                re.sub(r"^[0-9]+[.)]\s*", "", question)
                for question in updates["analysis_questions"]
            ]
            updates["analysis_questions"] = [
                f"{idx}. {question}" for idx, question in enumerate(questions, start=1)
            ]
        if not updates:
            raise ValueError("No worksheet fields in the response")
        return replace(ctx, **updates), None
    except HTTPError as exc:
        return ctx, f"OpenRouter 요청이 실패했습니다 (HTTP {exc.code}). 기존 활동지를 유지합니다."
    except (URLError, TimeoutError):
        return ctx, "OpenRouter에 연결하지 못했습니다. 기존 활동지를 유지합니다."
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return ctx, "OpenRouter 응답에서 활동지 내용을 읽지 못했습니다. 기존 활동지를 유지합니다."


def render_hwp_clean_text(ctx: WorksheetContext) -> str:
    """한글(HWP) 복사 전용 클린 텍스트 생성"""
    sep_thick = "=" * 68
    sep_thin = "-" * 68
    blank_lines = "\n" * 2

    header = (
        f"{sep_thick}\n"
        f"[{ctx.subject}] {ctx.school_title} ({ctx.template_type})\n"
        f"{sep_thin}\n"
        f"단원명\t{ctx.major_unit} > {ctx.sub_unit} (미래엔 p.{ctx.page_ref})\t차시\t{ctx.lesson_no}\n"
        f"성취기준\t{ctx.code} {ctx.standard_desc}\n"
        f"모둠/학생\t[   ]분단 [   ]모둠\t학번: __________\t이름: __________\n"
        f"{sep_thick}\n"
    )

    tab_table = format_table_for_hwp(ctx.result_table_raw)

    if ctx.template_type == "실험중심형":
        body = (
            f"\n■ 탐구 주제: {ctx.inquiry_title}\n\n"
            f"1. [도입] 생각 열기 및 실험 안전 수칙\n"
            f"• 생각 열기: {ctx.intro_question}\n"
            f"  → 나의 예상: ______________________________________________________\n"
            f"• [안전 확인] {ctx.safety_or_reading}  [  ] 확인함\n\n"
            f"2. [탐구 설계] 가설 설정 및 준비물\n"
            f"• 모둠 가설: 만약 ________________________ 하면, ________________________ 할 것이다.\n"
            f"• 준비물 체크: {ctx.materials_or_concepts}\n\n"
            f"3. [실험 수행 및 관찰] 과정 및 데이터 기록\n"
            f"{ctx.process_or_diagram}\n\n"
            f"[결과 기록표] ※ 아래 줄을 블록 지정 후 한글 [표]-[문자열을 표로] 선택 시 표로 자동 변환\n"
            f"{tab_table}\n\n"
            f"4. [결과 분석 및 토의]\n"
            + "\n".join(f"{q}{blank_lines}" for q in ctx.analysis_questions)
            + f"\n5. [정리 및 세특 연계 자기평가]\n"
            + "\n".join(f"{q}{blank_lines}\n" for q in ctx.formative_questions)
            + f"• [자기평가] (해당 칸에 O표)\n"
            f"구분\t잘함(상)\t보통(중)\t노력 필요(하)\n"
            f"실험 안전 수칙을 준수하고 모둠원과 협력하여 탐구를 수행하였다.\t\t\t\n"
            f"관찰·측정 결과를 바탕으로 과학적 근거를 들어 결론을 설명할 수 있다.\t\t\t\n"
        )
    else:
        body = (
            f"\n■ 학습 주제: {ctx.inquiry_title}\n\n"
            f"1. [도입] 생각 열기 (실생활 현상 탐색)\n"
            f"• 발문: {ctx.intro_question}\n"
            f"  → 나의 생각: ______________________________________________________\n"
            f"  → 모둠 활동 안내: {ctx.safety_or_reading}\n\n"
            f"2. [개념 다지기] 핵심 원리 구조화\n"
            f"• 핵심 키워드/자료: {ctx.materials_or_concepts}\n"
            f"• 탐구 흐름:\n{ctx.process_or_diagram}\n"
            f"  (아래 빈칸에 핵심 개념 간 관계나 흐름도를 그려 정리하시오.)\n\n\n\n"
            f"3. [자료 해석 및 토론 과제] ※ 아래 줄은 한글 [문자열을 표로] 변환 호환\n"
            f"{tab_table}\n\n"
            + "\n".join(f"{q}{blank_lines}" for q in ctx.analysis_questions)
            + f"\n4. [형성평가] 단계별 문제 해결\n"
            + "\n".join(f"{q}{blank_lines}\n" for q in ctx.formative_questions)
            + f"5. [성찰 및 교사 관찰 연계]\n"
            f"• 오늘 수업을 통해 새롭게 알게 된 점이나 더 탐구해 보고 싶은 주제는?\n\n"
            f"구분\t잘함(상)\t보통(중)\t노력 필요(하)\n"
            f"과학적 자료를 근거로 자신의 주장이나 원리를 논리적으로 표현하였다.\t\t\t\n"
        )

    return strip_markdown(header + body)
