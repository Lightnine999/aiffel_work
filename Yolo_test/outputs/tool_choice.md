# 문서/사진 분류·태깅 도구 선택 — 조사 기록

작성일: 2026-09-17 (조사는 2026-09-16에 수행, 2026-09-18 사용자 결정 반영)
이 문서는 대화에서 실제로 확인된 내용만 담는다. 확인하지 않은 정책·기준은 추정하지 않고 [사람이 결정]으로 남긴다.

### 사용자 확정 결정 (2026-09-18)
- **"노코드" 기준에 Docker는 포함하지 않는다** — 즉 Docker Compose 설치·실행, 설정 파일(YAML) 편집이 필요한 도구는 "노코드 설치형 앱" 조건을 충족하지 못한 것으로 최종 확정한다.
- 이 결정에 따라 **Immich, PhotoPrism, Paperless-ngx(+Paperless-AI 등)는 노코드 조건 미충족으로 최종 탈락**한다. (참고: Docker 자체의 비용 문제는 아니다 — Docker Personal은 무료이며, 이번 결정은 순수하게 "코딩 없이 쓰는 도구"라는 요구사항에 Docker 설정 작업이 부합하지 않는다는 판단이다. 출처: [Docker Pricing FAQ](https://www.docker.com/pricing/faq/), 2026-09-18 확인)
- **로컬/클라우드 절충 허용 범위: Private Cloud Compute(Apple 서버 경유)까지는 허용한다.** 단, 이 결정은 Apple의 Private Cloud Compute에 한정한 것이며, OpenAI 등 제3자 일반 클라우드 API까지 허용한다는 뜻인지는 아직 확인되지 않았다.
- 이 결정에 따라 macOS Shortcuts + Apple Intelligence 조합에서, 온디바이스 모델이 이미지를 지원하지 않더라도(2025-06 시점 확인된 제약) Private Cloud Compute로 사진 분류를 처리하는 것이 조건 위반이 아니게 된다 — 즉 이 후보의 "사진 처리" 제약이 사실상 해소됨.
- **문서용 도구와 사진용 도구를 따로 써도 된다.** 이에 따라 "사진 전용" 또는 "문서 전용"이라는 이유만으로는 더 이상 후보를 탈락시키지 않는다. 단, 이 결정이 기존 탈락 판정을 뒤집지는 않는다: digiKam은 여전히 "임의 커스텀 카테고리 zero-shot 미지원"으로 탈락 상태이고, Paperless-ngx는 여전히 "노코드 미충족"으로 탈락 상태다 — 두 도구 모두 "전용 도구라서"가 아니라 **다른 사유로** 탈락한 것이므로 이번 결정과 무관하게 탈락이 유지된다.

---

## 1. 조사한 업무와 자료

### 업무
문서(계약서·영수증 등)와 일반 사진(인물/사물/풍경)을 **분류·태깅**하는 AI 도구를 고른다.

### 대화에서 확정된 요구사항
| 항목 | 확정 내용 |
|---|---|
| 처리 대상 | 일반 사진 + 혼합(문서+사진) |
| 처리 빈도 | 일회성이 아니라 매일·매주 소량씩 지속 발생 |
| 사용 방식 | 코딩 없이 쓰는 설치형 앱/프로그램(No-code) |
| 예산 | 무료/오픈소스만 |
| 설치 환경 | macOS, Apple Silicon M5 Pro |
| 결과 반영 | 파일 위치는 그대로 두고 태그/라벨만 추가 |
| 카테고리 방식 | 사용자가 직접 정한 고정 카테고리 — **계약서 / 영수증 / 가족사진** 3개로 확정(2026-09-18) |
| 학습 데이터 | 카테고리 이름만 주면 예시 없이 AI가 판단(zero-shot) — 단, 재검토 단계에서 "카테고리당 소수 예시가 필요한 few-shot도 부담이 크지 않을 수 있다"는 가능성이 다시 제기됨 |
| 언어 | 문서/사진 내용은 한국어 위주. 도구가 보여주는 카테고리 표현은 영어여도 무방 |
| 파일 저장 위치 | 현재: 로컬 폴더 + Google Drive(클라우드). 추후: 외장하드·다른 클라우드도 고려 |
| 오프라인 여부 | 완전 오프라인 필수 아님. 가끔 인터넷 연결 가능한 환경 |
| 태그 확인 방식 | Finder 태그 검색도 가능하지만, 별도 앱 UI로 시각적으로 확인·검토하고 싶음 |

### 조사 방법과 한계
WebSearch + 내장 브라우저로 공식 문서·저장소·가격 페이지를 직접 열람했다. 다음은 직접 열람 성공: `docs.immich.app`, `photoprism.app`/`docs.photoprism.app`, `support.apple.com`(2026-09-14 게시), `1dot.ai`(FilesMagicAI 공식 페이지). 다음은 직접 열람 실패, 검색 스니펫으로만 확인: `macstories.net`(Cloudflare 봇 차단), `digikam.org/about/license/`(404). 해당 항목은 아래 표에 "스니펫만 확인"으로 표시했다.

---

## 2. 공식 근거를 확인한 후보

| 후보 | 확인 방식 | 근거 URL |
|---|---|---|
| Immich (immich-app/immich, AGPL-3.0) — **탈락 확정(노코드 미충족)** | 공식 문서 직접 열람 | [External Libraries](https://docs.immich.app/features/libraries/), [GitHub 저장소](https://github.com/immich-app/immich), [라이선싱 발표](https://github.com/immich-app/immich/discussions/11186) |
| immich-ml-tag (Immich 부가 플러그인) — **탈락 확정(Immich 종속)** | 검색 스니펫만 확인 | [DeepWiki 요약](https://deepwiki.com/openpaul/Immich-ML-Tag) |
| PhotoPrism (photoprism/photoprism, AGPL Community판) — **탈락 확정(노코드 미충족)** | 공식 문서 직접 열람 | [가격/에디션](https://www.photoprism.app/editions/), [라벨 생성 문서](https://docs.photoprism.app/developer-guide/vision/label-generation/) |
| digiKam (GPL-2.0-or-later) | 공식 라이선스 페이지 열람 실패(404), 검색 스니펫으로만 확인 | Wikipedia "DigiKam" 항목, alternativeto.net 8.3/8.4/8.6/8.7 릴리스 뉴스 (스니펫) |
| Paperless-ngx (+ Paperless-AI/Paperless-AIssist/paperless-local-ai) — **탈락 확정(노코드 미충족)** | GitHub 공식 디스커션 확인 | [소비 폴더 동작 관련 디스커션 #3548](https://github.com/paperless-ngx/paperless-ngx/discussions/3548), [#111](https://github.com/paperless-ngx/paperless-ngx/discussions/111) |
| Docker (Personal 플랜, 비용 근거) | 공식 가격 FAQ 직접 열람 | [Docker Pricing FAQ](https://www.docker.com/pricing/faq/) — Personal 플랜 무료이나 "노코드 아님"으로 사용자가 최종 판단(2026-09-18) |
| Hazel | 검색 스니펫으로 가격 확인 | mactools.pro, fast.io 2026 비교 글 (스니펫) — ⚠️ 검색 중 `Hazel-download/-Hazel-download`라는 GitHub 저장소가 노출되었는데, 실제 Hazel은 Noodlesoft의 유료 상용 앱으로 GitHub에 공식 배포되지 않는다. 해당 저장소는 공식이 아닐 가능성이 높아 **다운로드 출처로 쓰지 말 것을 권고**한다 |
| FilesMagicAI v2 | 공식 사이트 직접 열람 | [1dot.ai 공식 페이지](https://1dot.ai/files-magic-ai) |
| NameQuick / FilesDesk | 검색 스니펫으로 가격 확인 | namequick.app, filesdesk.app 가격 페이지 (스니펫) |
| macOS Shortcuts + Apple Intelligence "모델 사용" 액션 | Apple 공식 문서 직접 열람 | [How to get Apple Intelligence (2026-09-14 게시)](https://support.apple.com/en-us/121115), [Mac 단축어의 Apple Intelligence 사용](https://support.apple.com/en-ie/guide/mac-help/mchl91750563/26/mac/26) |
| Actions 앱 (Sindre Sorhus, 파일 태그 액션 제공) | App Store 페이지 + 검색 스니펫 | [App Store](https://apps.apple.com/us/app/actions/id1586435171) |
| Shortcuts On-Device/Private Cloud Compute 실사용 사례 | 3자 실사용 후기(공식 문서 아님) | [Six Colors, 2025-06-25](https://sixcolors.com/post/2025/06/experimenting-with-apples-ai-models-inside-shortcuts/) |

---

## 3. 확인된 사실 / 추론 / 미확인

### 확인된 사실
- Immich은 AGPL-3.0 오픈소스이며, 라이선스 구매는 선택적 후원일 뿐 핵심 기능은 계속 무료다(공식 디스커션 확인).
- Immich 외부 라이브러리 기능에서, 파일에 추가한 메타데이터(태그·앨범 등)는 **원본 파일에 기록되지 않고 Immich 내부에만 저장된다**(공식 문서 문구로 확인).
- PhotoPrism Community 에디션은 무료·AGPL이며, Ollama 연동으로 로컬 LLM 기반 커스텀 프롬프트 라벨 생성이 가능하다(공식 문서 확인). 단, `vision.yml` 파일을 직접 설정해야 한다.
- digiKam의 Auto-Tags 기능은 EfficientNet(사물 1000종) 또는 YOLOv11(COCO 80종) 같은 **사전학습된 고정 카테고리 인식기**를 쓴다(검색 스니펫 확인).
- Paperless-ngx는 기본 동작상 "소비(consume) 폴더"에 넣은 원본 파일을 자체 관리 저장소로 옮기고 원래 위치에서 제거한다(공식 GitHub 디스커션 확인).
- Apple Intelligence는 M1 이상 Apple Silicon Mac에서 무료로 제공되며, 한국어를 베타로 지원한다(Apple 공식 문서, 2026-09-14 게시).
- 2025년 6월 시점 실사용 보고에 따르면, 당시 Apple의 온디바이스 모델은 이미지 업로드를 지원하지 않아 이미지 작업에는 Private Cloud Compute(Apple 서버 경유)를 써야 했다(Six Colors, 2025-06-25).
- Actions 앱(무료, App Store)은 Shortcuts에 파일 태그 관련 액션을 추가로 제공한다.

### 추론 (자료에서 유추했으나 직접 확인은 아님)
- 2026년 6월 WWDC에서 발표된 Foundation Models 프레임워크가 이미지 입력을 지원하는 대형 모델(AFM 3 Core Advanced)을 추가했다는 보도로 미루어, Shortcuts 앱의 "온디바이스" 옵션도 이미지 입력을 지원하도록 갱신되었을 가능성이 있다. 그러나 이는 개발자용 Swift 프레임워크 기준 설명이며, Shortcuts 앱 UI에 동일하게 반영됐는지는 별도 확인이 필요하다.
- 카테고리가 3~5개 규모라면, immich-ml-tag처럼 카테고리당 소수 예시가 필요한 few-shot 방식의 부담이 실제로는 크지 않을 수 있다.

### 미확인
- Shortcuts "온디바이스" 옵션이 2026년 9월 현재 이미지를 직접 입력받는지 여부.
- Google Drive 동기화 폴더가 Immich/PhotoPrism의 파일시스템 감시(watch) 기능과 안정적으로 작동하는지(Drive가 파일을 완전히 로컬 다운로드해두는지, 스트리밍 방식인지에 따라 달라짐).
- immich-ml-tag의 실제 정확도·유지보수 활성도(README 이상의 실사용 검증 자료를 찾지 못함).
- PhotoPrism이 "문서(Documents)" 항목에도 커스텀 zero-shot 라벨을 적용할 수 있는지(검색된 문서는 사진 라벨링만 다룸).
- Ollama 로컬 비전 모델들의 한국어 문서(계약서·영수증) OCR·이해 품질.
- digiKam이 로컬 Ollama와 연동되는지(검색 범위 내에서 근거를 찾지 못함 — OpenAI/Claude 클라우드 API 연동만 확인됨).

---

## 4. AI가 판단할 수 없어 사람이 결정할 사항

- ~~**[사람이 결정]** "노코드"의 정확한 기준~~ → **2026-09-18 결정 완료**: Docker는 노코드로 보지 않는다. (Immich·PhotoPrism·Paperless-ngx 탈락 확정에 반영됨)
- ~~**[사람이 결정]** 로컬/클라우드 절충 허용 범위~~ → **2026-09-18 결정 완료**: Private Cloud Compute(Apple 서버 경유)까지는 허용. (OpenAI 등 제3자 일반 클라우드 API까지 허용하는지는 별도 미확인 — 필요 시 추가 확인)
- ~~**[사람이 결정]** 문서와 사진을 반드시 하나의 도구로 처리해야 하는지, 두 개 도구(문서용/사진용 분리)를 운용해도 되는지.~~ → **2026-09-18 결정 완료**: 문서용·사진용 도구를 따로 써도 된다.
- ~~**[사람이 결정]** 실제로 쓸 카테고리 이름과 정확한 개수~~ → **2026-09-18 결정 완료**: **계약서 / 영수증 / 가족사진** 3개로 확정. (문서 2종 + 사진 1종 — 문서용/사진용 도구를 분리해 쓰기로 한 결정과도 자연스럽게 맞물림)
- **[사람이 결정]** Google Drive 폴더가 완전히 로컬 다운로드되어 있는지, 스트리밍 방식인지 — 이는 사용자의 Google Drive 설정에 달려 있어 AI가 추정할 수 없음.
- **[사람이 결정]** "무료/오픈소스만" 기준을 계속 유지할지, 아니면 소액 유료 도구까지 허용 범위를 넓힐지.

---

## 5. 실제 업무와 닮은 비교 자료와 평가 방법

아직 실제 성능 비교 데이터는 없다(도구 설치·실행 없이는 얻을 수 없음). 실제 업무와 닮은 방식으로 검증하려면 다음 절차가 필요하며, 이는 사람이 자신의 환경에서 직접 실행해야 하는 영역이다.

1. **테스트셋 구성**: 확정된 3개 카테고리(계약서/영수증/가족사진) 각각에 대해, 실제 보유한 로컬/Google Drive 파일 중 대표 파일을 5~10개씩 골라 테스트셋을 만든다. 계약서·영수증은 문서용 도구, 가족사진은 사진용 도구 테스트셋으로 분리해 구성한다(문서·사진 도구 분리 결정 반영).
2. **후보별 동일 조건 실행**: 위에서 확인된 후보(Immich+immich-ml-tag, PhotoPrism+Ollama, Shortcuts+Apple Intelligence 등) 중 실제로 설치 가능한 것들에 같은 테스트셋을 넣는다.
3. **평가축**:
   - 카테고리 정답률 (사람이 직접 눈으로 대조)
   - 파일 1건당 처리 소요 시간
   - 설치·설정에 걸린 체감 난이도(“노코드”로 느꼈는지)
   - 태그를 실제로 찾아보는 경험(Finder 태그 검색 vs 별도 앱 갤러리 UI)
4. **한계**: 이 비교는 AI가 대신 수행할 수 없다 — 실제 로컬 파일 접근과 도구 설치·실행이 필요하므로 **[사람이 결정 및 실행]** 영역이다.

---

## 6. 선택을 다시 조사해야 할 변화나 실패

다음 사실이 확인되면 위 후보 평가가 뒤집히거나 재조사가 필요하다.

- ~~Shortcuts "온디바이스" 옵션이 실제로 이미지를 입력받지 못한다는 게 확인되면 → 사진 분류는 결국 Private Cloud Compute(클라우드 경유)가 필요해져, "로컬" 장점이 문서 처리에만 국한됨~~ → **2026-09-18 결정으로 더 이상 차단 요인 아님**: Private Cloud Compute 사용이 허용되었으므로, 온디바이스가 이미지를 지원하지 않아도 조건 위반이 아니다. (다만 "완전 로컬"이라는 장점 자체는 사진 처리에서는 약해진다는 사실 관계는 유효)
- ~~"노코드" 기준에 Docker/설정파일 편집이 포함되지 않는다고 확인되면 → Immich, PhotoPrism이 다시 유력 후보로 복귀~~ → **2026-09-18 확정으로 종결**: Docker는 노코드가 아니라고 결정했으므로 이 후보들은 탈락 유지. (단, 이 결정 자체를 나중에 뒤집으면 재조사 필요)
- Google Drive 폴더가 스트리밍(placeholder) 방식으로 확인되면 → 자동 감시(watch) 대신 주기적 수동 스캔으로 운영 방식을 바꿔야 함.
- 카테고리 수·이름이 확정되고 few-shot 예시 준비가 실제로 부담스럽다고 판단되면 → immich-ml-tag 같은 few-shot 방식은 다시 제외 대상이 됨.
- PhotoPrism의 문서(Documents) 라벨링 지원 여부가 "미지원"으로 확인되면 → 문서용 도구를 별도로 찾아야 함.
- Apple이 향후 macOS 업데이트에서 Shortcuts 온디바이스 모델의 이미지 지원을 공식 발표하면 → 재조사 필요.
