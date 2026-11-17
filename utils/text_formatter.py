import re
from typing import List

SUBSCRIPT_MAP = str.maketrans("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎")
SUPERSCRIPT_MAP = str.maketrans("0123456789+-=()", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾")

CHEMICAL_REPLACEMENTS = {
    "H2O2": "H₂O₂",
    "H2O": "H₂O",
    "CO2": "CO₂",
    "O2": "O₂",
    "H2": "H₂",
    "N2": "N₂",
    "Cl2": "Cl₂",
    "Br2": "Br₂",
    "I2": "I₂",
    "CH4": "CH₄",
    "NH3": "NH₃",
    "NH4NO3": "NH₄NO₃",
    "NH4Cl": "NH₄Cl",
    "NH4+": "NH₄⁺",
    "NH4": "NH₄",
    "H2SO4": "H₂SO₄",
    "CaCO3": "CaCO₃",
    "CaCl2": "CaCl₂",
    "Ca(OH)2": "Ca(OH)₂",
    "Ba(OH)2": "Ba(OH)₂",
    "Na2CO3": "Na₂CO₃",
    "C12H22O11": "C₁₂H₂₂O₁₁",
    "SiO2": "SiO₂",
    "SiO4": "SiO₄",
    "Fe2O3": "Fe₂O₃",
    "Na+": "Na⁺",
    "Cl-": "Cl⁻",
    "H+": "H⁺",
    "OH-": "OH⁻",
    "Ca2+": "Ca²⁺",
    "Mg2+": "Mg²⁺",
    "Cu2+": "Cu²⁺",
    "SO42-": "SO₄²⁻",
    "CO32-": "CO₃²⁻",
    "NO3-": "NO₃⁻",
    "SO4": "SO₄",
    "CO3": "CO₃",
    "NO3": "NO₃",
}


def to_unicode_science(text: str) -> str:
    """화학식, 이온 전하, 물리량 단위(^, _)를 HWP 호환 유니코드 첨자로 변환"""
    if not text:
        return ""

    result = text

    # 1) 명시적 지수 표기 (예: m/s^2, 10^-15, Ca^2+, OH^-)
    result = re.sub(
        r"\^([0-9+\-=()]+)",
        lambda m: m.group(1).translate(SUPERSCRIPT_MAP),
        result,
    )

    # 2) 명시적 아래첨자 표기 (예: H_2O, CO_2)
    result = re.sub(
        r"_([0-9+\-=()]+)",
        lambda m: m.group(1).translate(SUBSCRIPT_MAP),
        result,
    )

    # 3) 일반 단위 지수 보정 (m/s2, cm2, cm3, m2, m3)
    result = re.sub(
        r"(?<![A-Za-z])(m/s|cm|mm|km|m)([23])\b",
        lambda m: m.group(1) + m.group(2).translate(SUPERSCRIPT_MAP),
        result,
    )

    # 4) 화학식 사전 치환 (긴 토큰 우선)
    for raw, uni in sorted(CHEMICAL_REPLACEMENTS.items(), key=lambda x: -len(x[0])):
        result = result.replace(raw, uni)

    return result


def strip_markdown(text: str) -> str:
    """HWP 붙여넣기 시 깨지는 마크다운 문법 제거 (활동지 빈칸 밑줄 _____ 보존)"""
    if not text:
        return ""

    cleaned = text
    cleaned = re.sub(r"```[\s\S]*?```", lambda m: m.group(0).replace("```", ""), cleaned)
    cleaned = cleaned.replace("`", "")
    cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"(?<!\S)\*(.+?)\*(?!\S)", r"\1", cleaned)
    # 연속 밑줄 빈칸(______)은 보존하고 마크다운 __강조__만 제거
    cleaned = re.sub(r"__(?!_)([^_\n]+?)(?<!_)__", r"\1", cleaned)
    cleaned = re.sub(r"^\s{0,3}#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*>\s?", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*[-*]\s+", "• ", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.replace("$", "")

    return to_unicode_science(cleaned).strip()


def format_table_for_hwp(pipe_table_text: str) -> str:
    """파이프(|) 구분 표 문자열을 HWP [문자열을 표로] 호환 탭(\t) 구분 텍스트로 변환"""
    if not pipe_table_text or not pipe_table_text.strip():
        return ""

    lines = [ln.strip() for ln in pipe_table_text.strip().splitlines() if ln.strip()]
    tab_rows: List[str] = []
    for ln in lines:
        if re.match(r"^\|?[\s:\-|]+\|?$", ln):
            continue
        cells = [strip_markdown(c.strip()) for c in ln.strip("|").split("|")]
        tab_rows.append("\t".join(cells))

    return "\n".join(tab_rows)


def parse_table_matrix(pipe_table_text: str) -> List[List[str]]:
    """HTML/PDF 렌더링용 2차원 행렬 파싱"""
    if not pipe_table_text or not pipe_table_text.strip():
        return []
    lines = [ln.strip() for ln in pipe_table_text.strip().splitlines() if ln.strip()]
    matrix: List[List[str]] = []
    for ln in lines:
        if re.match(r"^\|?[\s:\-|]+\|?$", ln):
            continue
        cells = [to_unicode_science(c.strip()) for c in ln.strip("|").split("|")]
        matrix.append(cells)
    return matrix
