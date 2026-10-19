# Laya vs SLM Demo

Built with Llama

Laya English 421M과 Llama 3.2 Instruct 1B·3B에 **동일한 질문, 사용자 지정 보기, 공통 지시문**을 전달하는 로컬 추론 데모입니다. 일반 질문과 로봇 제어 문제를 모두 같은 객관식 답변 선택 과제로 비교합니다. 왼쪽 입력창 하나와 오른쪽 모델별 결과창으로 구성하며, Laya → 1B → 3B 순서로 추론합니다.

**Jev API를 사용하거나 Jev 가중치를 재현한 프로그램은 아닙니다.** Laya는 별도의 공개 판단 모델입니다. 이 데모는 실제 로봇에 연결되지 않습니다.

## 에이전트에게 저장소 주소만 전달할 때

다음 요청을 복사해 사용하면 됩니다.

> https://github.com/ETTE154/laya-vs-slm-demo 를 설치하고 실행해 줘. README.md와 AGENTS.md를 먼저 읽고 Python 3.12 프로젝트 가상환경을 만들어 줘. setup_demo.py로 고정된 패키지와 모델을 설치하고, 설치 확인과 단위 테스트를 수행한 뒤 run_demo.py --open으로 화면을 열어 줘. 모델별 오답과 형식 오류를 보정하지 말고 실제 추론 결과를 확인해 줘.

에이전트용 세부 지침은 [AGENTS.md](AGENTS.md)에 있습니다. 이 저장소에는 모델 가중치와 `.venv`를 올리지 않습니다. 설치 스크립트가 **고정 revision의 공개 파일을 내려받고 모든 파일의 크기와 SHA-256을 검증**합니다. 다른 PC의 절대 경로나 사용자 홈 설정에 의존하지 않습니다.

이 백업본을 새 가상환경에서 설치하고 실제 추론까지 확인한 내역은 [검증 기록](docs/VALIDATION.md)에 있습니다.

## 1. 준비 사항

| 항목 | 조건 |
|---|---|
| Python | **3.12**, 64-bit |
| Git | 저장소 복제에 필요 |
| 운영체제 | Windows 11 / Python 3.12에서 실제 실행 확인. Linux·macOS 명령도 제공하나 동일 하드웨어 성능은 보장하지 않음 |
| RAM | **32GB 이상 권장**, 여유 있게 실행하려면 64GB. FP32 가중치만 약 19.5GB이며 추가 작업 메모리가 필요 |
| 디스크 | 새 설치 시 **20GB 이상 여유 권장**. 모델 다운로드 약 9.7GB와 가상환경·패키지 캐시 필요 |
| 네트워크 | 첫 설치에 PyPI, download.pytorch.org, huggingface.co 및 Hugging Face 파일 저장소 접근 필요 |
| GPU / API 키 | 필요 없음. 기본 실행은 CPU·FP32·8 threads·batch 1 |

Python 설치 여부는 Windows에서 `py -3.12 --version`, Linux/macOS에서 `python3.12 --version`으로 확인합니다. Python이 없다면 [공식 Python 배포](https://www.python.org/downloads/) 또는 운영체제의 패키지 관리자로 **3.12와 venv 지원**을 설치하세요. 다른 버전으로 임의 대체하지 마세요.

## 2. 설치

### Windows PowerShell

```powershell
git clone https://github.com/ETTE154/laya-vs-slm-demo.git
cd laya-vs-slm-demo
py -3.12 setup_demo.py
```

### Linux / macOS

```bash
git clone https://github.com/ETTE154/laya-vs-slm-demo.git
cd laya-vs-slm-demo
python3.12 setup_demo.py
```

`setup_demo.py`는 다음 순서로 동작합니다.

1. 저장소 안에 `.venv`를 생성합니다. 전역 Python 패키지는 변경하지 않습니다.
2. Windows/Linux에서는 PyTorch 공식 CPU 인덱스의 고정 버전을 설치합니다. macOS에서는 PyPI 배포본을 사용하되 추론 장치는 CPU입니다.
3. `requirements.txt`의 고정된 직접 의존성을 설치하고 import·버전·`pip check`를 확인합니다.
4. `models.lock.json`에 고정된 Laya와 Llama 1B·3B 파일을 `models/`에 다운로드합니다.
5. 가중치뿐 아니라 tokenizer와 config까지 모든 파일의 크기·SHA-256을 확인합니다.

첫 설치에는 큰 파일을 내려받는 시간이 필요합니다. 파일별 진행률이 출력됩니다. 네트워크 오류가 나면 같은 명령을 다시 실행하세요. 검증된 파일은 재사용하고 `.part` 파일은 서버가 Range 요청을 지원할 때 이어받습니다. SSL 검증을 끄거나 임의의 다른 모델로 바꾸지 않습니다.

패키지만 먼저 설치하고 싶다면:

```powershell
py -3.12 setup_demo.py --skip-models
```

그 뒤 모델 설치:

```powershell
.\.venv\Scripts\python.exe download_models.py
```

Linux/macOS에서는 위 Python 경로를 `.venv/bin/python`으로 바꿉니다.

## 3. 설치 확인과 테스트

### Windows

```powershell
py -3.12 setup_demo.py --check
.\.venv\Scripts\python.exe -m unittest discover -s demo -p "test_*.py" -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

### Linux / macOS

```bash
python3.12 setup_demo.py --check
.venv/bin/python -m unittest discover -s demo -p 'test_*.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

`--check`는 다운로드나 설치 없이 패키지 상태와 로컬 모델 해시를 확인합니다. 모델 파일 전체를 읽으므로 시간이 걸릴 수 있습니다. `--check --skip-models`는 패키지만 확인합니다. 단위 테스트는 실제 모델을 로딩하지 않으며, 스트리밍 테스트가 localhost 임시 포트를 사용합니다.

실제 추론 검증은 다음 실행 단계에서 수행합니다. 단위 테스트 통과와 모델 정답률은 별개의 결과입니다.

## 4. 실행

Windows:

```powershell
py -3.12 run_demo.py --open
```

Linux / macOS:

```bash
python3.12 run_demo.py --open
```

또는 Windows의 `START_DEMO.cmd`를 더블클릭합니다. 가상환경 활성화 명령은 필요하지 않습니다. 런처가 저장소의 `.venv`를 사용합니다.

- 실행 화면: **http://127.0.0.1:8776/**
- 상태: **http://127.0.0.1:8776/api/meta**
- 종료: 실행한 터미널에서 **Ctrl+C**
- 모델은 **첫 번째 실행 버튼을 누를 때** 순서대로 로딩됩니다. 그 뒤 같은 서버 프로세스에서 재사용됩니다.
- `--open`이 없는 경우 브라우저를 자동으로 열지 않습니다. 원격/헤드리스 에이전트는 `python run_demo.py`로 실행하고 상태·실제 API 요청으로 확인하면 됩니다.
- 포트 충돌 시 기존 프로세스를 임의로 종료하지 말고 `python run_demo.py --port 8777 --open`처럼 다른 포트를 지정하세요.

설치 후 오프라인 상태 확인은 `python setup_demo.py --offline`으로 할 수 있습니다. 실제 모델 로딩은 로컬 파일만 사용하며 cloud inference를 호출하지 않습니다.

## 5. 입력과 결과 확인

입력창 하나에 질문과 보기를 함께 작성합니다.

```text
2+3?
A. 4
B. 5
C. 6
D. 7
```

로봇 제어도 같은 형식입니다. 분야 감지나 고정된 행동 후보는 없습니다.

```text
An open gripper is touching a cube but is not holding it. What should the robot do next to pick it up?
A. Close the gripper around the cube.
B. Transport the cube to the destination.
C. Open the gripper.
D. Wait without moving.
```

복사할 입력 파일은 [examples/](examples/)에 있습니다. 보기는 대문자 A부터 연속으로 2–10개를 한 줄에 하나씩 적습니다. `A.`, `A)`, `A:` 형식을 지원합니다. 질문·추가 설명은 첫 번째 보기 앞에 작성하세요.

- 전체 입력 2,000자, 질문 1,600자, 보기 하나 300자 이내입니다.
- Laya의 보기당 48토큰 제한도 검사합니다. 일부 모델에만 잘린 보기가 전달되지 않도록 긴 입력은 중단하고 안내합니다.
- 보기 없이 `2+3?`만 입력하면 추론을 시작하지 않고 형식을 안내합니다. Laya가 자유 응답을 생성할 수 없어 공통 과제를 객관식 선택으로 맞췄습니다.
- Laya는 보기별 점수로 선택합니다. SLM은 선택한 보기의 **문자 하나만** 생성하도록 요청합니다.
- 결과는 `B · 5`처럼 표시하며, SLM의 생성 원문도 보존합니다. 설명이나 `B.` 등을 생성하면 엄격한 출력 계약상 **보기 형식 오류**입니다. 원문에서 답을 추측해 교정하지 않습니다.
- 정답 라벨을 입력받지 않으므로 화면의 `완료`는 추론 완료를 의미하며 **정답 판정이 아닙니다**.

첫 실험은 산술·일반 지식·로봇 제어 세 입력으로 확인하세요. SLM 텍스트가 완료 전에 도착하는지, Laya 생성 토큰이 0인지, 세 모델의 공통 과제 SHA-256이 일치하는지 확인합니다. 기록용 확인 도구도 제공합니다.

```powershell
.\.venv\Scripts\python.exe verify_live.py --url http://127.0.0.1:8776 --out test-results/live.json
```

이 검사는 전송·형식·실행 순서를 검증하고 **오답과 형식 오류도 기록**합니다. 실패한 모델 응답을 성공한 응답으로 덮어쓰거나 프롬프트를 문항별로 조정하지 마세요.

## 6. API와 원문

```http
POST /api/stream
Content-Type: application/json

{"input":"2+3?\nA. 4\nB. 5\nC. 6\nD. 7"}
```

응답은 JSON 배열이 아니라 **한 줄당 JSON 객체인 NDJSON 스트림**입니다. `run_start` → 모델별 `model_start` / `status` / `token` / `model_result` → `run_end` 순서로 전송합니다. 모델별 오류와 전체 오류도 별도 이벤트로 표시합니다. `run_start.task`에 실제 공통 질문·보기·지시문·해시가 들어 있으며 각 결과에도 같은 해시가 포함됩니다. 모델은 동시 실행하지 않으며 두 번째 요청은 409로 거절합니다.

Laya SDK의 실제 [입력 원문](examples/laya_sdk_input_raw.json), [출력 원문](examples/laya_sdk_output_raw.json)도 보존했습니다. 이 SDK 입력은 HTTP 요청 본문과 구분해야 합니다. SDK는 `predict(state, questions, max_len=..., head_max_len=...)`를 받습니다.

## 7. 속도와 해석상의 한계

- 추론 시간: 입력 처리·토큰화·모델 계산·결과 변환 포함, 모델 로딩과 앞 모델 대기 제외.
- TTFT: 입력 처리와 prefill을 포함해 첫 생성 토큰까지 걸린 시간. 첫 화면 글자가 보이는 시각과 다를 수 있습니다.
- 생성 속도: `(생성 토큰 수 − 1) / (마지막 토큰 시각 − 첫 토큰 시각)`. EOS도 토큰 수에 포함합니다.
- Laya는 비자기회귀 판단 모델이므로 생성 토큰 0, tok/s·TTFT는 해당 없음입니다.
- SLM은 greedy decoding, 최대 16토큰입니다. 짧은 문자와 EOS만 생성하므로 tok/s의 표본이 작아 편차가 큽니다.
- 영어 기본 체크포인트를 사용합니다. 모델이 산술·상식·로봇 상태를 정확히 판단한다고 보장하지 않으며, 이번 실제 테스트에도 **오답과 출력 형식 오류가 있었습니다**.
- 후보 점수는 이 문제나 로봇 도메인에서 검증된 안전 확률이 아닙니다. 실제 로봇 작동이나 안전 제어에 사용하지 마세요.
- `reference_results/`는 개발 PC에서 얻은 과거 기록이며 재실행 결과나 정확도 보장을 의미하지 않습니다. 첫 JSON 포장 실험도 별도 이름으로 보존했고, 현재 버전은 SLM에 일반 텍스트 형식으로 공통 질문·보기를 전달합니다.

## 8. 모델 버전과 라이선스

| 키 | 다운로드 저장소 | 고정 revision |
|---|---|---|
| laya | convaiinnovations/laya | `7b928d828b7b0e022f929d9bd2e44165aa270148` |
| llama1b | unsloth/Llama-3.2-1B-Instruct | `5a8abab4a5d6f164389b1079fb721cfab8d7126c` |
| llama3b | unsloth/Llama-3.2-3B-Instruct | `006f5dcd1393c3add266de40994ba96225e9689d` |

Laya는 Apache 2.0, Llama 모델은 Llama 3.2 Community License 적용 대상입니다. 공개 Unsloth 배포본을 로컬에 내려받으며 Unsloth 전용 커널이나 `trust_remote_code`를 사용하지 않습니다. [Llama 라이선스](LICENSES/LICENSE_LLAMA_3_2.txt)와 [고지](LICENSES/NOTICE_Llama.txt)를 읽고 사용하세요. 원본 모델과 라이브러리의 권리는 각 권리자에게 있습니다.

핵심 패키지는 `requirements.txt`에 고정했습니다. 개발 PC의 전체 패키지 기록은 `requirements-lock.windows-py312.txt`로 보존하지만, 운영체제가 다를 수 있어 설치기는 직접 의존성 핀과 해당 플랫폼의 의존성 해결을 사용합니다.

## 9. 문제 해결

| 증상 | 확인·조치 |
|---|---|
| Python 버전 오류 | `py -3.12` 또는 `python3.12`로 실행. 다른 전역 Python의 pip를 사용하지 않음 |
| torch CPU wheel을 찾지 못함 | Python 3.12/64-bit와 공식 CPU 인덱스 접근을 확인. 버전을 조용히 바꾸지 말고 오류를 보고 |
| pip 의존성 충돌 | 이 저장소 `.venv`에서 설치했는지, `pip check` 오류 확인. 전역 패키지 삭제 금지 |
| 다운로드 403/404/인증 요구 | 공개 고정 URL과 네트워크·프록시 상태 확인. 저장소 접근 조건이 바뀌었으면 중단하고 원인을 보고. 인증/접근 제한 우회 금지 |
| SHA-256 불일치 | 잘못된 해당 파일만 별도 위치로 옮긴 뒤 다시 다운로드. `models.lock.json`의 기대 해시를 바꾸지 않음 |
| 메모리 부족 / 매우 느림 | 메모리 여유와 CPU 사용 확인. 기본 FP32 CPU 설정 유지. 양자화/GPU 전환은 원래 측정과 다른 조건으로 기록 |
| 실행 직후 모델 대기 | 정상. 첫 실행 버튼을 누를 때 로딩하며 그 동안 단계별 상태 표시 |
| localhost 접속 불가 | 서버 터미널 오류와 `/api/meta` 확인. 동일 PC의 브라우저 사용, 포트 충돌이면 다른 포트 선택 |
| 보기 형식 오류 | 사용자 입력 형식과 모델 생성 원문을 확인. 모델의 지시 불이행도 결과로 기록 |

이 백업은 주간 미팅 작업 폴더에서 현재 실행 데모만 추출한 것입니다. 개인 발표자료, 가상환경, 모델 가중치, 캐시 및 인증 정보는 포함하지 않습니다. 경로 정리 내역은 [백업 출처](docs/backup_provenance.json)에 기록했습니다.
