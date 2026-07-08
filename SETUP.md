# 단어친구 파이프라인 세팅 (GitHub → Streamlit → 웹 & 앱)

구조: **GitHub 저장소 하나**가 단어(words.csv)와 원어민 발음(audio/*.mp3)의 원본.
웹(Streamlit)과 안드로이드 앱 둘 다 여기서 읽어감.
단어 추가는 웹 관리 페이지에서 → 발음 MP3 자동 생성 → GitHub에 커밋 → 웹/앱 자동 반영.

## 1. GitHub 저장소 만들기 (1회)

1. github.com 에서 **Public** 저장소 생성. 이름 예: `wordfriend`
   (앱이 raw.githubusercontent.com 으로 읽으므로 Public 필요)
2. 이 폴더(wordfriend-web)의 파일 전부 업로드:
   `streamlit_app.py, requirements.txt, words.csv, audio/, tools/`
   - git 몰라도 됨: 저장소 페이지 > Add file > Upload files 로 드래그

## 2. GitHub 토큰 만들기 (1회) — 관리 페이지가 커밋할 때 사용

1. GitHub > Settings > Developer settings > **Fine-grained tokens** > Generate new token
2. Repository access: **Only select repositories** → wordfriend 선택
3. Permissions > Repository permissions > **Contents: Read and write**
4. 생성된 `github_pat_...` 복사해 두기

## 3. Streamlit Cloud 배포 (1회)

1. share.streamlit.io > New app > 저장소 `wordfriend`, 파일 `streamlit_app.py`
2. App settings > **Secrets** 에 아래 입력:

```toml
GH_REPO = "본인아이디/wordfriend"
GH_BRANCH = "main"
GH_TOKEN = "github_pat_여기에토큰"
ADMIN_PASSWORD = "원하는비밀번호"
```

## 4. 첫 발음 생성 (1회)

배포된 웹 > ⚙️ 단어 관리 > 비밀번호 입력 > 내용 그대로 두고 **저장** 버튼.
→ 30개 단어의 원어민 MP3가 생성되어 GitHub에 커밋됨 (1~2분).

## 5. 안드로이드 앱 연결 (1회)

WordFriend 프로젝트의 `Remote.kt` 맨 위 한 줄만 수정 후 빌드:

```kotlin
const val REPO = "본인아이디/wordfriend"
```

## 이후 단어 추가 (평소 운영)

PC(또는 폰) 브라우저에서 웹 관리 페이지 열기 → 목록에 줄 추가
(`영어,뜻,이모지,그룹`) → 저장. 끝.
- 웹: 1~2분 내 자동 재시작되며 반영
- 앱: 실행 시 자동 동기화(6시간 간격) 또는 단어 관리의 "☁ 서버에서 받기" 즉시 반영
- 발음: 새 단어만 자동 생성. 목소리를 바꾸려면 목소리 선택 후 "다시 생성" 체크

## 참고

- 발음 엔진: edge-tts (무료, Microsoft 신경망 음성). 기본 en-US-Jenny,
  어린이 목소리 en-US-Ana 선택 가능.
- 앱은 단어/MP3를 폰에 캐시하므로 오프라인에서도 동작 (발음 파일이 아직
  안 받아진 단어만 기기 TTS로 대체).
- 삭제한 단어의 MP3는 저장소에 남지만 무해함 (앱/웹은 words.csv 기준).
