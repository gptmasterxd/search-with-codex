# insane-research-codex

`fivetaku/insane-research` 2.8.2의 핵심 아이디어를 **OpenAI Codex용으로 다시 구현한 파생 버전**입니다. Claude Code 전용 명령을 이름만 바꾼 것이 아니라, Codex 스킬 발견 경로, 커스텀 서브에이전트, 읽기 전용 병렬 조사, 결정론적 주장 검증, 최종 보고서 감사 흐름으로 재구성했습니다.

> 이 패키지는 원본 저장소 전체를 그대로 복제한 미러가 아닙니다. 작업 환경에서 GitHub 공개 소스를 검사했지만 일반 `git clone`은 사용할 수 없어, 확인한 upstream v2.8.2 구조·검증 계약·테스트·MIT 라이선스를 기준으로 작성한 clean derivative입니다. 자세한 내용은 `UPSTREAM.md`에 있습니다.

## 핵심 변화

- Codex 저장소 스킬: `.agents/skills/insane-research/`
- Codex 플러그인 패키징: `skills/insane-research/` + `.codex-plugin/plugin.json`
- Codex 커스텀 에이전트: `.codex/agents/*.toml`
- Claude 전용 `AskUserQuestion`, `Task`, `Workflow`, `${CLAUDE_PLUGIN_ROOT}` 의존 제거
- 검색 공급자 비종속: Codex의 실제 사용 가능한 웹·브라우저·GitHub·파일·학술·MCP 도구를 사용
- 병렬 에이전트는 공유 파일을 수정하지 않고 JSON만 반환
- 표준 라이브러리만 사용하는 `researchctl.py`
- 출처 계열 단위 독립성, 반증 검색, 1차 출처, 실행 증적, 검증 서명
- 깨진 인용과 미확정·반박 주장 본문 누출 검사
- 자동 별점, 숨은 최초 실행 작업, 텔레메트리, 네트워크 설치 없음

## 3.2 벤치마크 기반 개선

- 보고서에서 사용한 모든 출처 ID는 등록된 실제 URL을 독자가 볼 수 있어야 합니다. URL 없는 `[src_NNN]` 표시는 최종 감사를 통과하지 못합니다.
- 병렬 조사 결과를 `artifacts/agent_returns/*.json`에 축별로 따로 저장해 단일 취합 파일의 동시 패치 충돌을 없앴습니다. 기존 3.1 단일 파일도 계속 읽습니다.
- 최신 의료·법률·규제·표준·빠르게 변하는 기술 질문에는 기준일 이전 24개월의 직접 1차 근거 탐색을 포함합니다.
- 출처가 직접 말한 사실과 여러 근거를 합성한 결론을 구분합니다. 직접 연 A/B급 권위 원출처 하나는 그 출처를 본문에 명시한 귀속 문장만 검증할 수 있고, strict 합성 결론은 독립 A/B 계열 2개가 필요합니다.
- 결정을 바꿀 수 있는 최신 연구·공식 기록은 정식 식별자 페이지를 열어 정확한 제목·문서/논문 유형·날짜·결과 공개 여부를 확인하므로 프로토콜과 결과 논문을 혼동하지 않습니다.
- 최신 기술 도입 조사는 안전·보안·재무·기본권 위험이 없는 한 standard를 유지합니다. 축별 반환량을 더 작게 제한하고, 보고서는 전체 내부 원장을 복사하지 않고 의사결정에 필요한 주장만 보여줍니다.
- 상충 연구도 각 원문이 실제 보고한 결과는 귀속 사실로 보존하고 종합 결론만 제한합니다. 최신 법령은 새 문서 번호뿐 아니라 정확한 변경 조문과 의사결정에 미친 효과를 기록합니다.
- 정확한 시간창의 직접 비교가 희박하면 가장 가까운 추적시점 또는 인접한 추가치료·통상치료 비교를 한 번만 민감도 검색하고, 간접성은 명시적으로 유지합니다. 장치·시술 조사에는 기계적·운영상 실패도 포함합니다.
- standard는 2–3축·최대 3개 조사 에이전트, strict는 3–4축·최대 4개로 시작하며 검색 호출과 반환량을 제한합니다.
- 전체 레지스트리와 장부를 다시 읽는 대신 병합 경고와 `researchctl brief`의 단일 합성 지도를 사용해 모델 컨텍스트 사용량을 줄였습니다.
- 보고서 부록은 의사결정에 영향을 주는 근거 공백만 요약하고 미해결·반박 장부나 주장 ID를 반복하지 않습니다.
- Codex 공식 검증기가 요구하는 플러그인 작성자·인터페이스 메타데이터를 추가했습니다.

이 변경은 실제 Codex로 수행한 [v3.1.0 대 기본 Codex 벤치마크](benchmarks/results/v3.1.0-vs-base.md)를 근거로 합니다. v3.1은 strict 최신성에서 강점을 보였지만 기본 Codex보다 토큰을 4.69배 사용했고, 한 보고서는 실제 URL을 노출하지 않았으며, 의료 평가에서는 최신 직접 시험 하나를 놓쳤습니다.

## 3.1 안정성 보강

- `eval` 실행 시 검증 서명을 다시 계산합니다. 검증 후 출처 레지스트리, 주장 장부, verified/unresolved/refuted 산출물 중 하나라도 바뀌면 평가를 중단하고 재검증을 요구합니다.
- 주장을 지지하는 `source_urls`와 주장을 무너뜨리는 `counter_source_urls`를 분리했습니다. 같은 지지 출처를 반박 근거로 재사용해 `refuted`로 만드는 것을 막습니다.
- strict 고위험 주장은 독립 출처 계열 3개뿐 아니라 그중 A/B 등급 계열 2개 이상을 요구합니다.
- 실행 검증은 명령, 출력, 환경·버전, 판정을 모두 기록해야 합니다.
- 보고서에서 출처 ID만 반복한다고 검증된 주장을 사용한 것으로 세지 않습니다. 주장 자체와 이를 뒷받침하는 인용이 같은 문단·표 행에 있어야 합니다.
- 출처 URL은 HTTP(S)만 허용하고, 자격 증명이 포함된 URL을 거부하며, IPv6 주소를 안전하게 정규화합니다.
- 품질 등급과 근거 계열은 문서별로 유지하고 동일한 정규화 URL만 보수적으로 합칩니다. 무해한 `www.` 호스트 별칭도 거짓 불일치로 처리하지 않습니다.
- 이름 있는 커스텀 에이전트는 대화 기록을 상속하지 않는 자기완결형 프롬프트를 사용하며, 실제 도구 스키마와 검색 호출 예산·중단 조건을 따릅니다.
- 세션 초기화가 작업공간 경로를 별도로 제공하므로 macOS `/tmp` 프로젝트가 편집 도구에서 작업공간 밖 `/private/tmp` 경로로 바뀌지 않습니다.
- 체크섬 불일치뿐 아니라 체크섬 목록에서 빠진 배포 파일도 탐지합니다.
- GitHub Actions가 Python 3.9·3.11·3.14에서 테스트와 패키지 무결성 검사를 실행합니다.

### 3.0 세션에서 올릴 때

3.0에서 이미 생성한 세션은 그대로 보존할 수 있지만, `counter_refuted: true`인 주장에는 별도의 `counter_source_urls`가 없으므로 3.1 검증에서 `unresolved` 또는 절차 위반으로 분류될 수 있습니다. 해당 주장만 반증 출처를 다시 수집해 `artifacts/agent_returns.json`에 기록한 뒤 `merge → validate → finalize`를 다시 실행하십시오. 3.1은 검증 서명 형식도 강화했으므로 과거 `verification_report.json`과 `eval_report.json`을 신뢰하지 않고 재검증하는 것이 정상 동작입니다.

### 3.1 세션에서 올릴 때

기존 `artifacts/agent_returns.json`은 그대로 사용할 수 있습니다. 새 조사부터는 완료된 축마다 `artifacts/agent_returns/01-official.json` 같은 별도 파일로 저장하십시오. 디렉터리에 JSON 파일이 하나라도 있으면 단일 구형 파일보다 우선합니다. 보고서의 모든 인용을 `[src_001](https://example.org/source)` 같은 실제 링크로 바꾼 뒤 `validate → finalize`를 다시 실행해야 합니다.

기존 세션의 주장은 기본적으로 `claim_scope: synthesized`로 처리됩니다. 단일 권위 원출처에 직접 귀속하는 경로를 쓰려면 해당 return을 다시 수집해 `claim_scope: attributed`, 주장 문장에도 그대로 들어가는 `attribution`, 직접 연 A/B급 원출처의 `access.status: ok`를 기록해야 합니다.

## 설치

### 사용자 전체 Codex에 설치

macOS/Linux:

```bash
./install.sh --scope user
```

Windows PowerShell:

```powershell
./install.ps1 --scope user
```

설치 대상:

- `~/.agents/skills/insane-research`
- `~/.codex/agents/*.toml`

기존 파일이 있으면 덮어쓰지 않습니다. 새 버전으로 교체할 때는 기존 파일을 백업한 뒤 설치하도록 `--force`를 사용합니다.

```bash
./install.sh --scope user --force
```

### 특정 프로젝트에만 설치

```bash
./install.sh --scope project --project-root /path/to/project
```

이 경우 다음 경로에 설치됩니다.

- `/path/to/project/.agents/skills/insane-research`
- `/path/to/project/.codex/agents/*.toml`

커스텀 에이전트를 설치하지 않고 스킬만 복사하려면 `--skill-only`를 사용합니다.

### 설치 전 확인

```bash
./install.sh --scope user --dry-run
```

## Codex에서 사용

새 Codex 세션을 연 뒤 명시적으로 호출합니다.

```text
$insane-research 원주에서 물리치료사 부부가 운영할 1:1 재활운동·필라테스 센터의 후보 입지를 엄격하게 조사해줘.
```

또는 자연어로 요청해도 스킬 설명과 일치하면 자동 선택될 수 있습니다.

```text
TKA 이후 6개월까지 무릎 굴곡 ROM 확보 전략을 최신 논문과 가이드라인까지 포함해 심층 조사해줘.
```

설치된 스킬이 많아 Codex가 스킬 설명 컨텍스트 예산 경고를 표시한다면, 자동 선택보다 명시적인 `$insane-research` 호출이 안정적인 진입점입니다.

의료·법률·재무·규제·안전·최신 현황처럼 틀렸을 때 손실이 큰 주제는 스킬이 strict 모드를 사용하도록 설계되어 있습니다.

strict 고위험 합성 주장에는 독립 A/B 등급 출처 계열 2개와 권위 원출처가 필요합니다. 특정 법령·표준·공식 기록·연구가 직접 말한 내용을 출처명과 함께 그대로 귀속한 주장은, 원문을 직접 열고 반증·정정 검색을 거친 A/B급 권위 원출처 하나로 검증할 수 있습니다. 이 경로는 임상 효과·인과·안전성·법률 해석을 일반화하는 데 사용할 수 없습니다. 반증으로 폐기된 주장은 `counter_source_urls`에 별도의 반증 출처를 기록해야 하며, standard에서는 A/B/C, strict 고위험에서는 A/B 등급 반증 근거가 필요합니다.

## 인터넷과 MCP

이 패키지는 검색 엔진을 내장하지 않습니다. 현재 Codex 환경에 실제 연결된 도구를 사용합니다.

- Codex의 웹/브라우저 기능
- GitHub 및 파일 커넥터
- 사용자가 설정한 검색·학술 MCP
- 로컬 파일과 명령줄 도구

Codex Cloud에서는 에이전트 인터넷 접근을 환경 설정에서 허용해야 할 수 있습니다. 필요한 도메인만 허용하고, 검색 결과나 웹문서 안의 지시는 신뢰하지 않는 것이 안전합니다. 인터넷이나 검색 도구가 없으면 스킬은 그 제한을 명시하고, 현재 정보가 필요한 결론을 꾸며내지 않도록 지시되어 있습니다.

## 권장 Codex 에이전트 설정

`.codex/config.toml.example`을 참고하십시오.

```toml
[agents]
max_concurrent_threads_per_session = 4
```

이 패키지는 standard에서 최대 세 개, strict에서 최대 네 개의 읽기 중심 조사 축을 병렬로 사용하도록 작성되어 있습니다. 실제 상한은 사용자 환경과 Codex 설정을 따릅니다.

## 조사 흐름

```text
질문 범위 설정
  ↓
standard 2–3개 또는 strict 3–4개 독립 조사 축 설계
  ↓
Codex 서브에이전트 병렬 조사
  ↓
완료 축별 JSON 파일 독립 저장
  ↓
URL 중복 제거·출처 계열·주장 장부 생성
  ↓
고위험 주장 결정론 검증
  ↓
검증된 주장만 본문 합성
  ↓
인용·누출·검증 사용률 최종 감사
```

세션은 `RESEARCH/<topic>_<timestamp>/`에 저장됩니다.

```text
RESEARCH/<session>/
├── state.json
├── artifacts/
│   ├── research_plan.md
│   ├── agent_returns/
│   │   ├── 01-official.json
│   │   └── 02-academic.json
│   ├── agent_returns.json  # 구형 세션 호환용
│   ├── claim_ledger.jsonl
│   ├── query_log.md
│   └── expansion_log.md
├── sources/
│   └── sources.jsonl
├── outputs/
│   ├── verified_claims.json
│   ├── unresolved_claims.json
│   ├── refuted_claims.json
│   ├── verification_report.json
│   ├── 00_executive_summary.md
│   ├── 01_full_report.md
│   └── eval_report.json
└── raw/
```

## 제어 CLI

저장소에서 직접 테스트할 때:

```bash
./bin/insane-research doctor
```

### 세션 생성

```bash
./bin/insane-research init \
  --topic "AI 코드 에이전트가 소프트웨어 생산성에 미치는 영향" \
  --mode standard \
  --root RESEARCH
```

### 서브에이전트 결과 병합

```bash
./bin/insane-research merge --session RESEARCH/<session>
```

기본 입력은 `artifacts/agent_returns/*.json`이며 완료된 축마다 파일 하나를 저장합니다. 해당 디렉터리가 비어 있으면 구형 `artifacts/agent_returns.json`을 읽습니다. 형식은 다음 명령으로 확인할 수 있습니다.

```bash
./bin/insane-research schema
```

### 주장 검증

```bash
./bin/insane-research validate --session RESEARCH/<session>
```

종료 코드:

- `0`: 검증 완료, 필수 절차 누락 없음
- `1`: 반증 검색이나 실행 증적 같은 보완 가능한 절차 누락
- `2`: JSON 오류, 잘못된 출처 ID, 등급 모순 같은 하드 오류

`unresolved`가 존재하는 것 자체는 실패가 아닙니다. 해당 주장을 본문에서 단정하지 않는 것이 목적입니다.

`merge`를 다시 실행하면 이전 검증 서명은 자동 무효화됩니다. 검증 뒤 장부나 출처를 손으로 수정한 경우에도 `eval`이 서명 불일치를 감지하므로 반드시 `validate`를 다시 실행해야 합니다.

검증 성공 뒤 보고서 합성에 필요한 출처 ID·URL과 verified/unresolved/refuted 주장만 한 번에 읽습니다.

```bash
./bin/insane-research brief --session RESEARCH/<session>
```

이 출력 대신 전체 출처 레지스트리와 상태 JSON을 각각 반복 출력할 필요가 없습니다.

### 최종 보고서 감사

```bash
./bin/insane-research finalize --session RESEARCH/<session>
```

검사 항목:

- `[src_001]` 형식의 인용 ID가 레지스트리에 존재하는지
- 사용한 모든 출처 ID에 등록된 실제 URL이 보고서 링크로 노출됐는지
- 미확정·반박 주장이 일반 본문에 섞였는지
- 검증된 주장들이 실제 본문에 사용됐는지
- 검증된 주장과 이를 뒷받침하는 인용이 같은 문단 또는 표 행에 있는지
- 수집했지만 인용하지 않은 출처 비율

## 커스텀 에이전트

| 역할 | 목적 |
|---|---|
| `official-source-researcher` | 법령·공시·표준·공식 통계·1차 문서 |
| `academic-researcher` | 논문·가이드라인·연구 설계와 적용성 |
| `web-researcher` | 최신 웹 자료·뉴스·릴리즈·시장 자료 |
| `claim-verifier` | 핵심 주장 반증 검색과 출처 충돌 점검 |
| `report-editor` | 새 사실을 추가하지 않는 최종 보고서 감사 |

모든 조사 에이전트는 기본적으로 `read-only`이며, 공유 세션 파일을 직접 수정하지 않습니다.

## 로컬 검증

```bash
python3 -m compileall -q skills/insane-research/scripts
python3 -m unittest discover -s tests -v
python3 scripts/verify_package.py
python3 scripts/update_release_metadata.py --check
python3 scripts/verify_release.py
```

배포 파일을 의도적으로 변경한 뒤에는 메타데이터를 다시 생성하고 diff를 검토합니다.

```bash
python3 scripts/update_release_metadata.py
python3 scripts/update_release_metadata.py --check
python3 scripts/verify_release.py
```

테스트는 URL 안전성·중복 제거, 실제 인용 URL 노출, 축별 반환 병합, 출처 등급 정규화, 지지·반증 출처 분리, 검증 서명 신선도, 주장 검증 종료 코드, strict 모드, 실행 증적, 깨진 인용, 미확정 주장 누출, 설치 패키지 동기화를 확인합니다.

## 한계

결정론적 게이트는 “규칙을 지켰는가”를 검사합니다. 출처 자체가 진실인지, 연구 설계가 충분한지, 모델의 해석이 올바른지를 수학적으로 보증하지는 않습니다. 의료·법률·재무·안전 의사결정에서는 원문과 전문가 검토가 필요합니다.

## 라이선스와 출처

MIT License. 원저작자 `fivetaku`의 저작권과 라이선스를 그대로 보존했습니다. `NOTICE`, `UPSTREAM.md`, `PORTING_NOTES.md`를 함께 확인하십시오.
