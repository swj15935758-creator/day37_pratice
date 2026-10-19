# day37_practice.py
# 주제: 캠퍼스 시설 안내 음성 도우미
# Streamlit 웹 화면 구성, WAV 입력/결과/출력 표시

import pandas as pd
import streamlit as st

from day37_db import load_recent_runs
from day37_pratice_logic import MAX_BYTES, MODEL_SIZE, VOICE_ID, validate_wav, run_pipeline


def main():

    st.set_page_config(
        page_title='캠퍼스 시설 안내 음성 도우미',
        page_icon='🏫',
        layout='centered'
    )

    st.title('캠퍼스 시설 안내 음성 도우미')
    st.caption('마이크/WAV > STT > 시설 안내 응답 > TTS > 음성 재생')

    source = st.radio('음성 입력 방식', ['마이크 녹음', 'WAV파일 업로드'])

    if source == 'WAV파일 업로드':
        uploaded = st.file_uploader('실제 WAV파일을 선택하세요', type=['wav'])
    else:
        uploaded = st.audio_input('마이크로 한국어 음성을 녹음하세요')

    stt_mode = st.radio('STT 처리 방식', ['데모 STT', '실제 faster-whisper'])
    tts_mode = st.radio('TTS 처리 방식', ['비프음 데모', '실제 edge-tts'])

    with st.form('voice_form'):
        demo_text = ''
        if stt_mode == '데모 STT':
            demo_text = st.text_input('데모 STT 예시 질문', value='도서관 운영시간 알려줘')

        model_size = st.selectbox(
            'STT 모델',
            ['tiny', 'base', 'small', 'medium'],
            index=['tiny', 'base', 'small', 'medium'].index(MODEL_SIZE)
        )

        voice_id = st.selectbox(
            'TTS 목소리',
            ['ko-KR-SunHiNeural', 'ko-KR-InJoonNeural'],
            index=['ko-KR-SunHiNeural', 'ko-KR-InJoonNeural'].index(VOICE_ID)
        )

        submitted = st.form_submit_button('음성 파이프라인 실행')

    if stt_mode == '데모 STT':
        st.caption('데모 STT는 녹음 음성을 분석하지 않고 입력한 예시 질문을 인식 결과로 사용합니다.')
    if tts_mode == '비프음 데모':
        st.caption('비프음 데모는 응답 문장을 읽지 않고 짧은 비프음을 재생합니다.')

    if submitted:
        if uploaded is None:
            st.error('먼저 WAV파일을 선택하거나 음성을 녹음해 주세요.')
        else:
            audio = uploaded.getvalue() # 업로드된 WAV파일의 bytes 읽기

            if not audio or len(audio) > MAX_BYTES:
                st.error(f'WAV 파일은 0바이트보다 크고 {MAX_BYTES}바이트 이하여야 합니다.')
            else:
                try:
                    audio_info = validate_wav(audio)
                except ValueError as e:
                    st.error(str(e))
                else:
                    st.subheader('입력 WAV 파일')
                    st.audio(audio, format='audio/wav')
                    st.json(audio_info)

                    with st.spinner('음성 인식 및 음성 합성 처리 중...'):
                        result, marks, meta, error = run_pipeline(
                            audio, model_size, voice_id, stt_mode, tts_mode, demo_text
                        )

                    if error:
                        st.error(f'처리 오류: {type(error).__name__}: {error}')
                    else:
                        transcript, reply, output, mime = result

                        st.subheader('STT 인식 결과')
                        st.write(transcript or '(인식된 음성이 없습니다)')

                        st.subheader('응답 문장')
                        st.write(reply)

                        st.subheader('TTS 합성 음성')
                        st.audio(output, format=mime)

                        filename = 'reply.mp3' if mime == 'audio/mpeg' else 'beep.wav'
                        st.download_button('TTS 음성 저장', output, filename, mime=mime)

                    if meta.get('db_warning'):
                        st.warning(meta['db_warning'])

                    st.metric('총 처리시간', f"{meta['total_ms']:.0f} ms")
                    st.bar_chart(pd.DataFrame({
                        '단계': ['STT', '응답 생성', 'TTS'],
                        '시간(ms)': [marks['stt_ms'], marks['reply_ms'], marks['tts_ms']]
                    }), x='단계', y='시간(ms)')
                    st.json(meta)

    st.subheader('최근 처리 이력')
    try:
        recent_runs = load_recent_runs(10)
        if recent_runs:
            columns = ['created_at', 'request_id', 'status', 'model_version',
                       'stt_ms', 'reply_ms', 'tts_ms', 'total_ms']
            st.dataframe(pd.DataFrame(recent_runs).reindex(columns=columns), hide_index=True)
        else:
            st.info('아직 저장된 실행 이력이 없습니다.')
    except OSError as e:
        st.warning(f'최근 이력 읽기 실패: {type(e).__name__}: {e}')


if __name__ == '__main__':
    main()
