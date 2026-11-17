import html
from typing import Literal, Optional, Tuple

from engines.template_assembler import WorksheetContext
from utils.text_formatter import parse_table_matrix, to_unicode_science

try:
    from weasyprint import HTML
    HAS_WEASYPRINT = True
except Exception:
    HAS_WEASYPRINT = False

LayoutMode = Literal["A4_1COL", "B4_2COL", "B4_2UP"]

LAYOUT_OPTIONS = {
    "A4 세로 (1단 표준)": "A4_1COL",
    "B4 가로 (2단 전개형)": "B4_2COL",
    "B4 가로 (B5 2부 절단용)": "B4_2UP",
}


def _esc(text: str) -> str:
    return html.escape(to_unicode_science(text or ""))


def _build_html_table(pipe_table: str) -> str:
    matrix = parse_table_matrix(pipe_table)
    if not matrix:
        return ""
    header_cells = "".join(f"<th>{_esc(c)}</th>" for c in matrix[0])
    body_rows = ""
    for row in matrix[1:]:
        padded = row + [""] * (len(matrix[0]) - len(row))
        tds = "".join(
            f"<td>{_esc(c) if c else '&nbsp;'}</td>" for c in padded[: len(matrix[0])]
        )
        body_rows += f"<tr>{tds}</tr>"
    return f"""
    <table class="data-table">
      <thead><tr>{header_cells}</tr></thead>
      <tbody>{body_rows}</tbody>
    </table>
    """


def _build_header_html(ctx: WorksheetContext, compact: bool = False) -> str:
    return f"""
    <header class="worksheet-header {'compact-header' if compact else ''}">
      <div class="header-top">
        <span>[{_esc(ctx.subject)}] {_esc(ctx.school_title)}</span>
        <span class="header-meta">{_esc(ctx.template_type)} · {_esc(ctx.lesson_no)}</span>
      </div>
      <table class="header-grid">
        <tr>
          <td class="label-cell">단원명</td>
          <td colspan="3">{_esc(ctx.major_unit)} &gt; {_esc(ctx.sub_unit)} (미래엔 p.{_esc(ctx.page_ref)})</td>
        </tr>
        <tr>
          <td class="label-cell">성취기준</td>
          <td colspan="3"><strong>{_esc(ctx.code)}</strong> {_esc(ctx.standard_desc)}</td>
        </tr>
        <tr>
          <td class="label-cell">소속</td>
          <td style="width:36%">[ &nbsp;&nbsp; ]분단 &nbsp; [ &nbsp;&nbsp; ]모둠</td>
          <td class="label-cell">학번/이름</td>
          <td>학번: ___________ &nbsp; 이름: ___________</td>
        </tr>
      </table>
    </header>
    """


def _build_sections_parts(ctx: WorksheetContext) -> Tuple[str, str]:
    data_table_html = _build_html_table(ctx.result_table_raw)

    analysis_html = "".join(
        f"""
        <div class="question-block">
          <p class="q-text">{_esc(q)}</p>
          <div class="answer-box"></div>
        </div>
        """
        for q in ctx.analysis_questions
    )

    formative_html = "".join(
        f"""
        <div class="question-block">
          <p class="q-text">{_esc(q)}</p>
          <div class="answer-box tall"></div>
        </div>
        """
        for q in ctx.formative_questions
    )

    process_lines = "<br>".join(
        _esc(line) for line in ctx.process_or_diagram.splitlines() if line.strip()
    )

    if ctx.template_type == "실험중심형":
        left_part = f"""
        <div class="topic-banner">■ 탐구 주제: {_esc(ctx.inquiry_title)} <span class="badge">{_esc(ctx.inquiry_subtype)}</span></div>

        <section class="card">
          <h2>1. [도입] 생각 열기 및 실험 안전 확인</h2>
          <p><strong>• 생각 열기:</strong> {_esc(ctx.intro_question)}</p>
          <div class="line-write">나의 예상: </div>
          <div class="safety-box">
            <strong>⚠ 실험 안전 수칙:</strong> {_esc(ctx.safety_or_reading)}
            <span class="check-right">☐ 숙지함</span>
          </div>
        </section>

        <section class="card">
          <h2>2. [탐구 설계] 가설 설정 및 준비물</h2>
          <p><strong>• 조별 가설:</strong> 만약 ________________________ 하면, ________________________ 할 것이다.</p>
          <p><strong>• 준비물 확인:</strong> {_esc(ctx.materials_or_concepts)}</p>
        </section>

        <section class="card">
          <h2>3. [실험 수행 및 관찰] 과정 &amp; 데이터 기록</h2>
          <div class="process-box">{process_lines}</div>
          {data_table_html}
        </section>
        """

        right_part = f"""
        <section class="card">
          <h2>4. [결과 분석 및 토의]</h2>
          {analysis_html}
        </section>

        <section class="card">
          <h2>5. [정리 및 세특 피드백]</h2>
          {formative_html}
          <table class="data-table rubric-table">
            <thead>
              <tr><th>자기 평가 항목</th><th style="width:11%">상</th><th style="width:11%">중</th><th style="width:11%">하</th></tr>
            </thead>
            <tbody>
              <tr><td style="text-align:left">실험 안전 수칙을 준수하고 모둠원과 협력하여 탐구를 수행하였다.</td><td></td><td></td><td></td></tr>
              <tr><td style="text-align:left">관찰·측정 결과를 근거로 과학적 결론을 논리적으로 설명할 수 있다.</td><td></td><td></td><td></td></tr>
            </tbody>
          </table>
        </section>
        """
    else:
        left_part = f"""
        <div class="topic-banner">■ 학습 주제: {_esc(ctx.inquiry_title)} <span class="badge">{_esc(ctx.inquiry_subtype)}</span></div>

        <section class="card">
          <h2>1. [도입] 생각 열기 (실생활 현상 탐색)</h2>
          <p><strong>• 탐구 발문:</strong> {_esc(ctx.intro_question)}</p>
          <div class="answer-box"></div>
        </section>

        <section class="card">
          <h2>2. [개념 다지기] 핵심 원리 구조화</h2>
          <p><strong>• 핵심 자료/키워드:</strong> {_esc(ctx.materials_or_concepts)}</p>
          <div class="process-box">{process_lines}</div>
          <div class="answer-box tall mindmap-box">
            [ 핵심 원리 마인드맵 또는 단계별 흐름도 작성란 ]
          </div>
        </section>
        """

        right_part = f"""
        <section class="card">
          <h2>3. [자료 해석 / 토론 과제]</h2>
          <p class="note">※ 활동 안내: {_esc(ctx.safety_or_reading)}</p>
          {data_table_html}
          {analysis_html}
        </section>

        <section class="card">
          <h2>4. [형성평가] 단계별 문제 해결</h2>
          {formative_html}
        </section>

        <section class="card">
          <h2>5. [성찰] 자기 평가 및 교사 관찰 연계</h2>
          <div class="line-write">오늘 활동을 통해 가장 인상 깊었던 과학 원리나 더 탐구할 점: </div>
          <table class="data-table rubric-table">
            <thead>
              <tr><th>자기 평가 항목</th><th style="width:11%">상</th><th style="width:11%">중</th><th style="width:11%">하</th></tr>
            </thead>
            <tbody>
              <tr><td style="text-align:left">과학적 자료를 근거로 자신의 주장과 원리를 논리적으로 서술하였다.</td><td></td><td></td><td></td></tr>
              <tr><td style="text-align:left">모둠 토의에서 상대방의 의견을 경청하고 대안을 협력적으로 모색하였다.</td><td></td><td></td><td></td></tr>
            </tbody>
          </table>
        </section>
        """

    return left_part, right_part


def render_worksheet_html(
    ctx: WorksheetContext, layout_mode: LayoutMode = "A4_1COL"
) -> str:
    """A4 1단 / B4 2단 전개형 / B4 B5 2부 절단용 HTML 생성"""
    header_html = _build_header_html(ctx, compact=(layout_mode == "B4_2UP"))
    left_part, right_part = _build_sections_parts(ctx)

    if layout_mode == "A4_1COL":
        page_css = "@page { size: A4 portrait; margin: 15mm; }"
        screen_width = "210mm"
        body_inner = f"""
        <div class="sheet-page a4-page">
          {header_html}
          {left_part}
          {right_part}
        </div>
        """
    elif layout_mode == "B4_2COL":
        page_css = "@page { size: 364mm 257mm; margin: 10mm 12mm; }"
        screen_width = "364mm"
        body_inner = f"""
        <div class="sheet-page b4-page">
          <div class="b4-columns">
            <div class="b4-col b4-col-left">
              {header_html}
              {left_part}
            </div>
            <div class="b4-divider fold-line" title="접지선"></div>
            <div class="b4-col b4-col-right">
              <div class="mini-continuation">
                <span><strong>{_esc(ctx.code)}</strong> {_esc(ctx.inquiry_title)}</span>
                <span>학번: ________ 이름: ________</span>
              </div>
              {right_part}
              <div class="memo-box">
                <div class="memo-title">📝 모둠 토의 메모 / 그래프·추가 계산 여백</div>
              </div>
            </div>
          </div>
        </div>
        """
    else:  # B4_2UP
        page_css = "@page { size: 364mm 257mm; margin: 7mm 9mm; }"
        screen_width = "364mm"
        single_half = f"""
        {header_html}
        {left_part}
        {right_part}
        """
        body_inner = f"""
        <div class="sheet-page b4-page b4-2up-mode">
          <div class="b4-columns">
            <div class="b4-col b4-half">{single_half}</div>
            <div class="b4-divider cut-line"><span class="scissor">✂</span></div>
            <div class="b4-col b4-half">{single_half}</div>
          </div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<title>{_esc(ctx.subject)} - {_esc(ctx.inquiry_title)}</title>
<style>
  {page_css}
  * {{
    box-sizing: border-box;
  }}
  body {{
    font-family: "Malgun Gothic", "Apple SD Gothic Neo", "NanumGothic", "Noto Sans CJK KR", "Noto Sans KR", sans-serif;
    font-size: 10pt;
    line-height: 1.58;
    color: #1a1a1a;
    margin: 0;
    padding: 0;
  }}

  @media screen {{
    body {{
      background: #e2e8f0;
      padding: 14px;
    }}
    .sheet-page {{
      background: #ffffff;
      width: {screen_width};
      margin: 0 auto;
      padding: 12mm;
      box-shadow: 0 4px 18px rgba(15, 23, 42, 0.14);
      border-radius: 3px;
    }}
  }}

  @media print {{
    body {{
      background: none;
      padding: 0;
    }}
    .sheet-page {{
      background: none;
      width: auto;
      margin: 0;
      padding: 0;
      box-shadow: none;
    }}
  }}

  .b4-columns {{
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    align-items: stretch;
    width: 100%;
  }}
  .b4-col {{
    width: 48.2%;
  }}
  .b4-divider {{
    width: 0;
    position: relative;
  }}
  .fold-line {{
    border-left: 1px dashed #cbd5e1;
  }}
  .cut-line {{
    border-left: 1.2px dashed #64748b;
  }}
  .scissor {{
    position: absolute;
    top: -4px;
    left: -7px;
    background: #fff;
    font-size: 10pt;
    color: #475569;
  }}

  .b4-page {{
    font-size: 9.2pt;
    line-height: 1.48;
  }}
  .mini-continuation {{
    display: flex;
    justify-content: space-between;
    font-size: 8.4pt;
    color: #334155;
    border-bottom: 1.5px solid #1f3a5f;
    padding-bottom: 3px;
    margin-bottom: 6px;
  }}
  .memo-box {{
    border: 1px dashed #94a3b8;
    border-radius: 4px;
    min-height: 44px;
    margin-top: 6px;
    padding: 4px 8px;
    background: #fafafa;
  }}
  .memo-title {{
    font-size: 8pt;
    color: #64748b;
  }}

  /* B4 2부 절단용 초압축 B5 규격 */
  .b4-2up-mode {{
    font-size: 7.9pt;
    line-height: 1.35;
  }}
  .b4-2up-mode .header-top {{
    padding: 3px 7px;
    font-size: 8.8pt;
  }}
  .b4-2up-mode .header-grid {{
    font-size: 7.4pt;
  }}
  .b4-2up-mode .header-grid td {{
    padding: 2px 4px;
  }}
  .b4-2up-mode .topic-banner {{
    padding: 3px 6px;
    font-size: 8.4pt;
    margin-bottom: 4px;
  }}
  .b4-2up-mode h2 {{
    font-size: 8.6pt;
    margin: 4px 0 2px 0;
  }}
  .b4-2up-mode .card {{
    margin-bottom: 4px;
  }}
  .b4-2up-mode .process-box {{
    padding: 3px 6px;
    font-size: 7.7pt;
    margin-bottom: 3px;
  }}
  .b4-2up-mode .data-table {{
    font-size: 7.5pt;
    margin: 3px 0 4px 0;
  }}
  .b4-2up-mode .data-table th,
  .b4-2up-mode .data-table td {{
    padding: 2px 3px;
    height: 15px;
  }}
  .b4-2up-mode .answer-box {{
    height: 24px;
  }}
  .b4-2up-mode .answer-box.tall {{
    height: 34px;
  }}
  .b4-2up-mode .mindmap-box {{
    padding-top: 10px !important;
    font-size: 7.3pt !important;
  }}

  .worksheet-header {{
    border: 1.5px solid #1f3a5f;
    border-radius: 4px;
    margin-bottom: 8px;
    overflow: hidden;
  }}
  .header-top {{
    background-color: #1f3a5f;
    color: #ffffff;
    padding: 5px 10px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: bold;
    font-size: 10.5pt;
  }}
  .header-meta {{
    font-size: 8.5pt;
    font-weight: normal;
  }}
  .header-grid {{
    width: 100%;
    border-collapse: collapse;
    font-size: 8.8pt;
  }}
  .header-grid td {{
    border-top: 1px solid #cbd5e1;
    border-right: 1px solid #cbd5e1;
    padding: 3px 7px;
  }}
  .header-grid td:last-child {{
    border-right: none;
  }}
  .label-cell {{
    background-color: #f1f5f9;
    font-weight: bold;
    width: 14%;
    text-align: center;
  }}
  .topic-banner {{
    background-color: #eef4fb;
    border-left: 4px solid #1f3a5f;
    padding: 5px 9px;
    font-weight: bold;
    font-size: 10pt;
    margin-bottom: 8px;
  }}
  .badge {{
    display: inline-block;
    background: #1f3a5f;
    color: #fff;
    font-size: 7.5pt;
    padding: 1px 6px;
    border-radius: 10px;
    margin-left: 5px;
    vertical-align: middle;
  }}
  .card {{
    margin-bottom: 8px;
    page-break-inside: avoid;
    break-inside: avoid;
  }}
  h2 {{
    font-size: 10pt;
    color: #1f3a5f;
    border-bottom: 1.5px solid #cbd5e1;
    padding-bottom: 2px;
    margin: 6px 0 5px 0;
  }}
  p {{
    margin: 2px 0;
  }}
  .note {{
    font-size: 8.6pt;
    color: #475569;
  }}
  .safety-box {{
    background: #fff7ed;
    border: 1px solid #fdba74;
    padding: 4px 7px;
    border-radius: 3px;
    font-size: 8.6pt;
    margin-top: 4px;
  }}
  .check-right {{
    float: right;
    font-weight: bold;
  }}
  .process-box {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    padding: 5px 8px;
    border-radius: 3px;
    margin-bottom: 5px;
    font-size: 9pt;
  }}
  .data-table {{
    width: 100%;
    border-collapse: collapse;
    margin: 5px 0 7px 0;
    font-size: 8.8pt;
  }}
  .data-table th, .data-table td {{
    border: 1px solid #64748b;
    padding: 4px 5px;
    text-align: center;
    height: 22px;
  }}
  .data-table th {{
    background-color: #f1f5f9;
    font-weight: bold;
  }}
  .question-block {{
    margin-bottom: 6px;
  }}
  .q-text {{
    font-weight: 500;
  }}
  .answer-box {{
    border: 1px solid #94a3b8;
    border-radius: 3px;
    height: 42px;
    margin-top: 2px;
    background: #ffffff;
  }}
  .answer-box.tall {{
    height: 62px;
  }}
  .mindmap-box {{
    text-align: center;
    color: #888;
    font-size: 8.5pt;
    padding-top: 22px;
  }}
  .line-write {{
    border-bottom: 1px dashed #64748b;
    padding: 3px 0 8px 0;
    margin-bottom: 4px;
    font-size: 9pt;
  }}
</style>
</head>
<body>
  {body_inner}
</body>
</html>
"""


def generate_pdf_bytes(
    ctx: WorksheetContext, layout_mode: LayoutMode = "A4_1COL"
) -> Tuple[Optional[bytes], str, Optional[str]]:
    """선택된 레이아웃(A4 / B4 2단 / B4 2부 절단용)으로 PDF 바이트 생성"""
    html_str = render_worksheet_html(ctx, layout_mode=layout_mode)
    if not HAS_WEASYPRINT:
        return (
            None,
            html_str,
            "WeasyPrint가 설치되지 않아 인쇄용 HTML 파일로 제공합니다. (브라우저에서 열기 → Ctrl+P → 용지 A4/B4 선택 → PDF 저장)",
        )

    try:
        pdf_bytes = HTML(string=html_str).write_pdf()
        return pdf_bytes, html_str, None
    except Exception as exc:
        return (
            None,
            html_str,
            f"PDF 엔진(GTK/Pango) 환경 제약으로 인쇄용 HTML을 제공합니다: {exc}",
        )
