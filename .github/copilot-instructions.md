## 요약

이 저장소는 Windows용 PyQt6 기반 데스크탑 툴(트래커 + 에디터)을 포함합니다. 주요 기능은 화면을 캡처해 Tesseract OCR로 잠재력(아이템) 이름을 읽고, 로컬에 저장한 덱(user_decks.json)과 대조하여 UI에 하이라이트하는 것입니다.

간단히 말해, 빠르게 생산적인 편집/디버깅을 하려면 다음 파일들을 먼저 읽으세요:
- `Mao-chan_Helper.py` — 앱 진입점(메인 윈도우, 트래커와 에디터 탭 연결, 전역 단축키 설정)
- `tracker.py` — OCR 파이프라인, 화면 캡처, 레이블 업데이트, 주요 비즈니스 로직
- `editor.py` — 데이터 편집 UI (에디터에서 저장 시 트래커가 데이터 리로드됨)
- `common_utils.py` — 데이터 경로 해석기(get_datafile_path), `DataParser` (데이터 파일 파싱 로직)
- `config.json`, `gamedata.json`, `user_decks.json` — 런타임에 사용하는 설정/데이터

## 아키텍처(큰 그림)

- 두 모듈(Tracker / Editor)이 하나의 탭 기반 앱(`Mao-chan_Helper.py`)으로 결합되어 있으며, 에디터가 저장하면 트래커가 `data_saved` 시그널을 통해 `reload_all_data_and_decks`를 호출합니다.
- OCR 파이프라인(핵심 흐름)은 `tracker.py`의 `run_ocr_check` → `get_processed_images` → `pytesseract.image_to_string` → Levenshtein 유사도 비교 순입니다. 잘 동작하지 않으면 먼저 `config.json`의 캡처 좌표를 확인하세요.
- 데이터 파일(`HitDamage.json`, `EffectValue.json`, 등)은 `common_utils.DataParser`에서 로드되며, `parse_param`을 통해 문자열 파라미터를 구조화합니다. 데이터 파일은 리포지토리 루트에서 찾습니다.
- 번들/배포 시 `sys._MEIPASS`/`sys.executable` 기반 경로 처리를 사용하므로 리소스 접근은 반드시 `get_datafile_path()` 또는 `get_bundled_path()`를 사용하세요.

## 개발자 워크플로(로컬에서 빠르게 실행/디버그하기)

1. 의존 설치(권장, Windows PowerShell):

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install PyQt6 pytesseract opencv-python pillow python-Levenshtein keyboard numpy
```

2. 로컬에서 실행(콘솔 로그로 문제 원인 확인):

```powershell
python Mao-chan_Helper.py
```

3. 빌드(릴리스 exe 생성): 이 프로젝트는 PyInstaller 스펙 파일(`tracker.spec`, `editor.spec`)을 포함합니다. 배포 빌드를 만들려면:

```powershell
pyinstaller --noconfirm tracker.spec
pyinstaller --noconfirm editor.spec
```

빌드 생성물은 기존 `build/` 디렉터리 구조를 참고하세요. Tesseract 실행파일 및 `tessdata`는 `tesseract_bundle/` 안에 있으므로 배포에 포함되어야 합니다.

중요: exe로 빌드했을 때 리소스 경로는 `get_datafile_path()`가 `sys.executable` 위치를 기준으로 해석합니다.

## 프로젝트 규약 / 패턴 (이 저장소에만 해당)

- 데이터 파일은 루트에 JSON 형식(`gamedata.json`, `user_decks.json`, 그리고 `HitDamage.json` 등)을 둡니다. `DataParser.load_data_files()`에서 파일명 목록을 하드코딩해서 로드합니다.
- 덱 항목 표기: 대개 "[캐릭터] [스타일] 항목명" 형태입니다. 트래커는 `extract_potential_name(...)`으로 `'] '` 이후 부분을 표준 이름으로 사용합니다.
- OCR 비교: Korean 문자만 추출해 비교합니다 (`clean_text_for_comparison`), Levenshtein 비율 임계치는 코드 내에서 `0.6` 수준으로 설정되어 있습니다.
- 좌표 저장: 캡처 영역은 `config.json`의 `coordinates.box1/2/3`으로 저장되며, UI에서 재설정 가능합니다. 창 위치가 바뀌면 좌표를 다시 설정해야 합니다.

## 통합 포인트 / 외부 의존성

- Tesseract OCR: 로컬 `tesseract_bundle/tesseract.exe` 을 사용하도록 코드가 기본 설정되어 있습니다. `pytesseract.pytesseract.tesseract_cmd`를 확인하세요.
- 전역 단축키: `keyboard` 모듈을 사용합니다. 관리자 권한이 필요하거나 실패할 수 있으니, 단축키 관련 이슈는 권한 문제를 의심하세요.
- 이미지 처리: OpenCV (`get_processed_images`)로 여러 전처리(스케일, 이진화, 엣지 등)를 만들어 Tesseract 후보들을 다수 비교합니다.

## 코드 변경시 체크포인트 (즉각 확인할 것)

- OCR 관련 변경: `tracker.py::get_processed_images`, `run_ocr_check`, `update_result_label`을 먼저 살펴보고 단위 동작(스크린샷 → 전처리 → pytesseract 결과)을 로그로 출력해 확인하세요.
- 데이터 파싱 변경: `common_utils.DataParser`의 `load_data_files`와 `parse_param`을 수정하면 `tracker._parse_potential_effects`의 합산 결과가 바뀝니다. 샘플 JSON 파일로 수동 확인을 권장합니다.
- 배포 경로/리소스 문제: `get_datafile_path()` 동작(스크립트 모드 vs exe 모드)을 고려하지 않으면 파일을 못 찾습니다.

## 빠른 예시(문제 진단 시)
- OCR이 아예 동작하지 않음: `python Mao-chan_Helper.py`로 실행 → 콘솔에서 "Tesseract 초기화 완료" 로그 확인 → `run_ocr_check`에서 예외 로그 출력 확인
- 잘못 매칭되는 항목: `tracker.update_result_label`에서 `Levenshtein.ratio` 계산부와 `clean_text_for_comparison` 정규식(`r'[가-힣]+'`)을 검토

## 마무리(요청사항)

이 파일을 기반으로 더 다루었으면 하는 항목(예: 빌드 스크립트, CI 설정, 더 자세한 데이터 포맷 설명 등)을 알려주세요. 불명확한 부분이나 누락된 파일 레퍼런스가 있으면 알려주시면 바로 보완하겠습니다.

---
Files referenced: `Mao-chan_Helper.py`, `tracker.py`, `editor.py`, `common_utils.py`, `config.json`, `gamedata.json`, `user_decks.json`, `tesseract_bundle/`.
