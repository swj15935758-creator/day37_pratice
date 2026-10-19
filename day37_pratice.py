# day37_practice.py
# 주제: 캠퍼스 시설 안내 음성 도우미
# Streamlit 웹 화면 구성, WAV 입력/결과/출력 표시

import streamlit as st

def main():

    st.set_page_config(
        page_title = ' 캠퍼스 시설 안내 음성 도우미',
        page_icon = '🏫',
        layout = 'centered'
    )

    st.title(' 캠퍼스 시설 안내 음성 도우미')
    st.caption('WAV파일 > faster-whisper STT > 규칙 기반 응답 > edge-tts 음성 합성')

    source = st.radio('음성 입력 방식', ['WAV파일 업로드', '마이크 녹음'])

    if source == 'WAV파일 업로드':
        uploaded = st.file_uploader('실제 WAV파일을 선택하세요', type=['wav'])
    else:
        uploaded = st.audio_input('마이크로 한국어 음성을 녹음하세요')

    with st.form('voice_form'):

        model_size = st.selectbox(
            'STT 모델',
            ['tiny', 'base', 'small', 'medium'],
            index=1
        )

        voice_id = st.selectbox(
            'TTS 목소리',
            ['ko-KR-SunHiNeural', 'ko-KR-InJoonNeural']
        )

        submitted = st.form_submit_button('음성 파이프라인 실행')

    if not submitted:
        return # 실행하지 않았다면 화면 구성만 수행

    if uploaded is None:
        st.error('먼저 WAV파일을 선택하거나 음성을 녹음해 주세요.')
        return

    audio = uploaded.getvalue() # 업로드된 WAV파일의 bytes 읽기

    if not audio or len(audio) > MAX_BYTES:
        st.error(f'WAV 파일은 0바이트보다 크고 {MAX_BYTES}바이트 이하여야 합니다.')
        return

    try:
        audio_info = validate_wav(audio)
    except ValueError as e:
        st.error(str(e))
        return

    st.subheader('입력 WAV 파일')

    st.audio(audio, format='audio/wav')

    st.json(audio_info)

    with st.spinner('실제 음성 인식 및 음성 합성 처리 중...'):
        result, marks, meta, error = run_pipeline(audio, model_size, voice_id)

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

        st.download_button('TTS MP3 저장', output, 'reply.mp3', mime=mime)

    st.metric('총 처리시간', f"{meta['total_ms']:.0f} ms")

    st.bar_chart(marks)

    st.json(meta)

if __name__ == '__main__':
    main()
































