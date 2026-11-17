"""
Google Sheets 통합과학 1·2 DB 자동 초기화 CLI 스크립트
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    tomllib = None

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.sheets_db import initialize_google_sheets  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="SciSheet Builder Google Sheets 자동 초기화 도구")
    parser.add_argument("--sa-json", help="Google 서비스 계정 JSON 파일 경로")
    parser.add_argument("--sheet", help="대상 Google Spreadsheet URL 또는 ID")
    parser.add_argument("--create", help="새로 생성할 Google Spreadsheet 제목")
    parser.add_argument("--share-email", help="--create 사용 시 편집 권한을 부여할 교사 구글 이메일")
    parser.add_argument(
        "--from-secrets",
        action="store_true",
        help=".streamlit/secrets.toml에서 gcp_service_account와 GOOGLE_SHEET_URL을 자동 로드",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="이미 데이터가 있는 탭도 덮어써서 초기 시드로 재설정",
    )
    args = parser.parse_args()

    sa_info = None
    sheet_target = args.sheet

    if args.from_secrets:
        if tomllib is None:
            sys.exit("[오류] --from-secrets 옵션은 Python 3.11 이상이 필요합니다.")
        secrets_path = ROOT_DIR / ".streamlit" / "secrets.toml"
        if not secrets_path.exists():
            sys.exit(f"[오류] {secrets_path} 파일을 찾을 수 없습니다.")
        with open(secrets_path, "rb") as f:
            secrets = tomllib.load(f)
        sa_info = dict(secrets.get("gcp_service_account", {}))
        if not sheet_target:
            sheet_target = secrets.get("GOOGLE_SHEET_URL")
    elif args.sa_json:
        sa_path = Path(args.sa_json)
        if not sa_path.exists():
            sys.exit(f"[오류] 서비스 계정 파일을 찾을 수 없습니다: {sa_path}")
        sa_info = json.loads(sa_path.read_text(encoding="utf-8"))
    else:
        sys.exit("[오류] --sa-json 또는 --from-secrets 옵션을 지정해 주세요.")

    if not sa_info:
        sys.exit("[오류] 서비스 계정 인증 정보가 비어 있습니다.")

    print("🚀 Google Sheets 초기화 시작...")
    res = initialize_google_sheets(
        service_account_info=sa_info,
        spreadsheet_url_or_id=sheet_target,
        create_title=args.create,
        share_email=args.share_email,
        overwrite=args.force,
    )
    print(f"✅ 완료! 시트 제목: {res['title']}")
    print(f"🔗 URL: {res['spreadsheet_url']}")
    print(f"📊 결과: {res['summary']}")


if __name__ == "__main__":
    main()
