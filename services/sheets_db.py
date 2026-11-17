import json
from typing import Dict, List, Optional, Tuple
import pandas as pd

from data.seed_data import CURRICULUM_SEED, INQUIRY_SEED, QUESTION_BANK_SEED

try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _col_letter(n: int) -> str:
    """1-based 열 번호를 엑셀 열 문자(A, B, ..., AA)로 변환"""
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


class SciSheetRepository:
    """Google Sheets 연동 + 로컬 시드 Fallback 저장소"""

    def __init__(
        self,
        spreadsheet_url_or_id: Optional[str] = None,
        service_account_info: Optional[Dict] = None,
    ):
        self.spreadsheet_url_or_id = spreadsheet_url_or_id
        self.service_account_info = service_account_info
        self.mode = "로컬 내장 DB (시드 모드)"
        self.error_msg: Optional[str] = None

        self.curriculum_df = pd.DataFrame(CURRICULUM_SEED).fillna("")
        self.inquiry_df = pd.DataFrame(INQUIRY_SEED).fillna("")
        self.question_df = pd.DataFrame(QUESTION_BANK_SEED).fillna("")

        if spreadsheet_url_or_id and service_account_info:
            self._load_from_google_sheets()

    def _load_from_google_sheets(self) -> None:
        if not HAS_GSPREAD:
            self.error_msg = "gspread 또는 google-auth 패키지가 설치되지 않았습니다."
            return

        try:
            creds = Credentials.from_service_account_info(
                self.service_account_info, scopes=SCOPES
            )
            client = gspread.authorize(creds)

            if self.spreadsheet_url_or_id.startswith("http"):
                sh = client.open_by_url(self.spreadsheet_url_or_id)
            else:
                sh = client.open_by_key(self.spreadsheet_url_or_id)

            c_rows = sh.worksheet("Curriculum_DB").get_all_records()
            i_rows = sh.worksheet("MiraeN_Inquiry_DB").get_all_records()
            q_rows = sh.worksheet("Question_Bank_DB").get_all_records()

            if c_rows:
                self.curriculum_df = pd.DataFrame(c_rows).fillna("")
            if i_rows:
                self.inquiry_df = pd.DataFrame(i_rows).fillna("")
            if q_rows:
                self.question_df = pd.DataFrame(q_rows).fillna("")

            self.mode = f"Google Sheets 실시간 연동 ({sh.title})"
        except Exception as exc:
            self.error_msg = f"Google Sheets 연동 실패 (로컬 시드로 대체됨): {exc}"

    def get_subjects(self) -> List[str]:
        return self.curriculum_df["과목"].replace("", pd.NA).dropna().unique().tolist()

    def get_major_units(self, subject: str) -> List[str]:
        sub_df = self.curriculum_df[self.curriculum_df["과목"] == subject]
        return sub_df["대단원"].replace("", pd.NA).dropna().unique().tolist()

    def get_standards(self, subject: str, major_unit: str) -> pd.DataFrame:
        return self.curriculum_df[
            (self.curriculum_df["과목"] == subject)
            & (self.curriculum_df["대단원"] == major_unit)
        ].reset_index(drop=True)

    def get_inquiries_by_code(self, code: str) -> pd.DataFrame:
        matched = self.inquiry_df[self.inquiry_df["성취기준코드"] == code]
        return matched.reset_index(drop=True)

    def get_questions_by_code(
        self, code: str, difficulty: Optional[str] = None
    ) -> pd.DataFrame:
        matched = self.question_df[self.question_df["성취기준코드"] == code]
        if difficulty and not matched.empty:
            diff_matched = matched[matched["난이도"] == difficulty]
            if not diff_matched.empty:
                return diff_matched.reset_index(drop=True)
        return matched.reset_index(drop=True)

    def export_seed_csv_bytes(self) -> Tuple[bytes, bytes, bytes]:
        return (
            self.curriculum_df.to_csv(index=False).encode("utf-8-sig"),
            self.inquiry_df.to_csv(index=False).encode("utf-8-sig"),
            self.question_df.to_csv(index=False).encode("utf-8-sig"),
        )


def parse_service_account_json(raw_json: str) -> Optional[Dict]:
    if not raw_json or not raw_json.strip():
        return None
    return json.loads(raw_json)


def initialize_google_sheets(
    service_account_info: Dict,
    spreadsheet_url_or_id: Optional[str] = None,
    create_title: Optional[str] = None,
    share_email: Optional[str] = None,
    overwrite: bool = False,
) -> Dict[str, str]:
    """
    기존 Google Spreadsheet에 3개 DB 탭을 자동 구축하거나,
    새 스프레드시트를 생성해 시드 데이터를 업로드하고 헤더 서식을 지정합니다.
    """
    if not HAS_GSPREAD:
        raise RuntimeError("gspread 및 google-auth 패키지가 필요합니다.")

    creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
    client = gspread.authorize(creds)

    if spreadsheet_url_or_id:
        sh = (
            client.open_by_url(spreadsheet_url_or_id)
            if spreadsheet_url_or_id.startswith("http")
            else client.open_by_key(spreadsheet_url_or_id)
        )
    elif create_title:
        sh = client.create(create_title)
        if share_email:
            sh.share(share_email.strip(), perm_type="user", role="writer")
    else:
        raise ValueError("spreadsheet_url_or_id 또는 create_title 중 하나를 지정해야 합니다.")

    datasets = [
        ("Curriculum_DB", CURRICULUM_SEED),
        ("MiraeN_Inquiry_DB", INQUIRY_SEED),
        ("Question_Bank_DB", QUESTION_BANK_SEED),
    ]

    existing_titles = {ws.title: ws for ws in sh.worksheets()}
    results = []

    for sheet_name, rows in datasets:
        df = pd.DataFrame(rows).fillna("")
        values = [df.columns.tolist()] + df.astype(str).values.tolist()
        num_rows = len(values)
        num_cols = len(df.columns)

        if sheet_name in existing_titles:
            ws = existing_titles[sheet_name]
            current_vals = ws.get_all_values()
            if len(current_vals) > 1 and not overwrite:
                results.append(f"{sheet_name}: 기존 데이터 보존(건너뜀)")
                continue
            ws.clear()
            ws.resize(rows=max(num_rows + 20, 100), cols=max(num_cols + 2, 12))
        else:
            ws = sh.add_worksheet(
                title=sheet_name,
                rows=max(num_rows + 20, 100),
                cols=max(num_cols + 2, 12),
            )

        ws.update(values=values, range_name="A1")

        header_range = f"A1:{_col_letter(num_cols)}1"
        ws.format(
            header_range,
            {
                "backgroundColor": {"red": 0.12, "green": 0.23, "blue": 0.37},
                "textFormat": {
                    "bold": True,
                    "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                },
                "horizontalAlignment": "CENTER",
            },
        )
        ws.freeze(rows=1)
        results.append(f"{sheet_name}: {len(df)}행 초기화 완료")

    for default_name in ("Sheet1", "시트1"):
        if default_name in existing_titles and len(sh.worksheets()) > 1:
            try:
                default_ws = existing_titles[default_name]
                if not default_ws.get_all_values():
                    sh.del_worksheet(default_ws)
            except Exception:
                pass

    return {
        "title": sh.title,
        "spreadsheet_id": sh.id,
        "spreadsheet_url": sh.url,
        "summary": " | ".join(results),
    }
