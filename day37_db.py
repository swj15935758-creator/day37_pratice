# day37_db.py
import json # 실행 기록을 JSONL 형식으로 저장
import os # DATABASE_URL 환경변수 조회
from pathlib import Path # 파일 경로 처리
import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

# local 실행을 위해 .env 로딩
load_dotenv()

# sql 파일 경로
SQL_DIR = Path(__file__).resolve().parent / "sql"

# 실행이력을 저장할 jsonl파일 경로
LOG_PATH = Path(__file__).with_name('voice_runs.jsonl')

# 실행하는 함수
def execute(name, params=()):
    # 환경변수에서 데이터 베이스URL 획득
    url = os.getenv("DATABASE_URL", '').strip()
    if not url:
        raise ValueError("DATABASE_URL .env 환경변수를 설정하세요.")

    # sql 파일의 문자열 획득
    sql = (SQL_DIR / name).read_text(encoding="utf-8")

    with psycopg.connect(
        url, # 접속 URL
        connect_timeout=15, # 접속까지 15초는 대기
        row_factory=dict_row # 행을 딕셔너리로
    ) as conn:

        # sql 실행
        cursor = conn.execute(sql, params)

        # 조회 결과가 있는 경우 리스트로 반환
        if cursor.description is not None:
            return cursor.fetchall()

        return []


# 실행정보 JSONL 파일에 추가하고 선택적으로 PostgreSQL에 저장
def store_meta(meta):

    # JSONL은 JSON객체를 한 줄에 하나씩 기록하는 텍스트 파일
    with LOG_PATH.open('a', encoding='utf-8') as f:
        # json.dumps(딕셔너리) : 딕셔너리를 JSON객체 문자열로 변환
        # ensure_ascii=False : 한글로 저장 = ASCII로 변환해서 저장하지 않음
        f.write(json.dumps(meta, ensure_ascii=False) + '\n')

    # 환경변수의 DATABASE_URL 변수의 값
    database_url = os.getenv('DATABASE_URL', '').strip()
    if not database_url:
        return None

    try:

        # 테이블 생성
        execute('create_table.sql')

        # 실행 이력 INSERT
        execute(
            'insert_meta.sql',
            (
                meta['request_id'],
                meta['created_at'],
                meta['status'],
                meta['stt_ms'],
                meta['reply_ms'],
                meta['tts_ms'],
                meta['total_ms'],
                meta['model_version'],
                meta['audio_sha256']
            )
        )

    except Exception as e:
        return f'DB 실행 이력 저장 실패: {type(e).__name__}: {e}'

    return None