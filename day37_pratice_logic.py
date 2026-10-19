# day37_logic.py
# WAV 파일을 이용한 STT > 응답 생성 > TTS 파이프라인

import asyncio # 비동기 TTS 함수를 실행
import hashlib # 원본 음성의 SHA-256 해시값 계산
import tempfile # STT 입력을 위한 임시 WAV 파일 생성
import time # 처리 단계별 실행 시간 측정
import uuid # 요청별 고유 ID 생성
import wave # WAV 파일 헤더와 PCM 형식 검사
from datetime import datetime, timezone # UTC 시각 생성
from pathlib import Path # 파일 경로 처리
import streamlit as st # 웹 기반 사용자 인터페이스

from day37_db import store_meta


# 입력 파일 최대 크기를 10Mbytes로 제한
MAX_BYTES = 10 * 1024 * 1024

# 사용할 Whisper모델 크기
MODEL_SIZE = 'base'

# Edge TTS에서 사용하는 한국어 여성 음성 모델 ID
VOICE_ID = 'ko-KR-SunHiNeural'

FACILITIES = {
    "도서관": "도서관은 본관 옆 건물이며 평일 9시부터 18시까지 운영합니다.",
    "학생식당": "학생식당은 학생회관 1층에 있으며 11시부터 14시까지 운영합니다.",
    "취업지원센터": "취업지원센터는 학생회관 2층이며 취업 상담을 제공합니다.",
    "행정실": "행정실은 본관 1층이며 각종 증명서 발급을 안내합니다.",
}

# WAV 파일 확인 후 음성 파일 정보 추출 함수
def validate_wav(audio):
    import io # WAV 데이터를 메모리 파일 처럼 읽기위함

    try:
        with wave.open(io.BytesIO(audio), 'rb') as wav:
            channels = wav.getnchannels()
            sample_rate = wav.getframerate()
            sample_width = wav.getsampwidth()
            frames = wav.getnframes()
            compression = wav.getcomptype()

    except (wave.Error, EOFError, OSError) as e:
        raise ValueError('유효한 비압축 PCM WAV 파일을 입력해 주세요.') from e

    if compression != 'NONE' or channels not in (1, 2) or sample_rate <= 0 or frames <= 0:
        raise ValueError('모노/스테레오 비압축 PCM WAV 파일이 필요합니다.')

    return {
        'channels': channels,
        'sample_rate': sample_rate,
        'bit_depth': sample_width * 8,
        'duration': round(frames / sample_rate, 2)
    }


# faster-whisper 음성인식 모델을 CPU에 로딩하는 함수
@st.cache_resource(show_spinner='whisper 모델을 로딩중 입니다...')
def load_stt_model(model_size):
    from faster_whisper import WhisperModel
    return WhisperModel(model_size, device='cpu', compute_type='int8')


# WAV 데이터를 임시 파일로 저장후 실제 한국어로 인식하는 함수 load_model > 전사
def transcribe_wav(audio, model_size):
    model = load_stt_model(model_size)

    # 임시 파일 생성
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        f.write(audio) # 바이너리 기록
        wav_path = Path(f.name) # 생성된 임시 파일 경로

    try:
        segments, info = model.transcribe(
            str(wav_path),
            language='ko',
            vad_filter=True,
        )

        transcript = ''.join(segment.text.strip() for segment in segments).strip()

        return transcript

    finally: # 파일 제거
        wav_path.unlink(missing_ok=True)


# 인식한 문장 정리후 응답 문장 생성 함수
def build_reply(transcript):
    clean = ''.join(transcript.split())
    if not clean:
        return '음성 인식 불가 다시 시도하세요.'
    return f'방금 내용은 "{clean}" 입니다!'


# tts mp3로 만들어 저장하는 함수
async def generate_tts_mp3(text, voice):
    import edge_tts

    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
        mp3_path = Path(f.name)

    try: # 저장부분
        await edge_tts.Communicate(text=text, voice=voice).save(str(mp3_path))
        return mp3_path.read_bytes()

    finally: # 임시 파일 지우기
        mp3_path.unlink(missing_ok=True)


# 함수를 동기 코드에서 실행하는 코드
def synthesize_speech(text, voice_id):
    mp3_bytes = asyncio.run(generate_tts_mp3(text, voice_id))
    return mp3_bytes, 'audio/mp3'


# WAV 검증 > STT > 응답 생성 > TTS > 로그 저장 과정을 연결해서 실행하는 파이프라인 함수
def run_pipeline(audio, model_size, voice_id):

    # 요청을 구분할 고유 요청 ID
    request_id = str(uuid.uuid4())

    # 음성 원문을 기록하지 않고 해시값만 보관
    digest = hashlib.sha256(audio).hexdigest() # SHA256 16진수 해시값 생성

    # 단계별 실행시간 초기화 (ms)
    marks = {'stt_ms': 0.0, 'reply_ms': 0.0, 'tts_ms': 0.0}

    # 전체 처리 시작 시각
    started = time.perf_counter()

    result = None # 성공한 경우 처리 결과 저장
    error = None # 실패한 경우 예외 저장

    try:

        # STT 단계 실행 후 소요시간 측정
        t0 = time.perf_counter()
        transcript = transcribe_wav(audio, model_size)
        marks['stt_ms'] = (time.perf_counter() - t0) * 1000

        # 규칙 기반 응답 생성 단계 실행 후 소요시간 측정
        t0 = time.perf_counter()
        reply = build_reply(transcript)
        marks['reply_ms'] = (time.perf_counter() - t0) * 1000

        # 실제 TTS 음성 합성 단계 실행 후 소요시간 측정
        t0 = time.perf_counter()
        output, mime = synthesize_speech(reply, voice_id)
        marks['tts_ms'] = (time.perf_counter() - t0) * 1000

        # UI에서 사용할 성공 결과를 튜플로 저장
        result = (transcript, reply, output, mime)

    except Exception as e:
        error = e

    # 전체 처리시간에는 최초 모델 로딩 시간도 포함
    elapsed = (time.perf_counter() - started) * 1000

    meta = {
        'request_id': request_id,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'status': 'error' if error else 'success',
        **{key: round(value, 2) for key, value in marks.items()},
        'total_ms': round(elapsed, 2),
        'model_version': f'whisper-{model_size}/edge-tts/{voice_id}',
        'audio_sha256': digest
    }

    store_meta(meta)

    return result, marks, meta, error