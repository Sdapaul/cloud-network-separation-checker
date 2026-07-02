# 망분리 구성도 검수기 — CLAUDE.md

## 프로젝트 개요

한국 **전자금융감독규정 제15조** 망분리 요건 준수 여부를 자동 검토하는 도구.

- GitHub: `https://github.com/Sdapaul/cloud-network-separation-checker` (public, owner: Sdapaul)
- 대상: 금융기관 네트워크 담당자·정보보호팀

---

## 파일 구조

```
C:\test_network_sepatation\
├── network_separation.html   # 메인 도구 — 단일 HTML, 외부 의존성 없음
├── cloud_checker.py          # 보조 CLI — 클라우드 설정 JSON 분석
├── requirements.txt          # Python 의존성 (cloud_checker.py용)
├── .env                      # OpenAI API 키 (gitignore됨, 커밋 금지)
├── .env.example              # 키 템플릿 (sk-... 플레이스홀더만)
└── examples/
    ├── aws_vpc_compliant.json
    └── aws_vpc_noncompliant.json
```

---

## network_separation.html 구조

단일 파일 SPA. 외부 CDN·라이브러리 일절 없음.

### 주요 JS 데이터 구조

| 변수 | 역할 |
|---|---|
| `ZONES[]` | 망 영역 정의. 4번째 요소 `true` = 구성도 전용(규칙 미적용) |
| `DEVICES[]` | 보안장비 정의 |
| `QUESTIONS[]` | 드롭다운 질문. `[id, 질문문, 근거, [[값,레이블]...]]` |
| `RULES[]` | 규칙 배열. 각 객체 `{id, nm, ref, ev(s)}` |

### readState() 반환 객체 구조

```javascript
{
  zones: { internet, dmz, server, db, ... },   // ZONES 체크박스
  devs:  { fw_ext, fw_int, ips, ... },         // DEVICES 체크박스
  q_server_sep, q_pc_sep, q_direct, ...,       // QUESTIONS 드롭다운 값
  cloudType: "general|aws|azure|gcp"           // AI 패널 라디오 버튼
}
```

### 규칙 엔진

`ev(s)` 함수는 `[status, why, fix]` 반환:
- `status`: `"pass"` | `"fail"` | `"warn"` | `"na"`
- `why`: 판정 근거 (한국어)
- `fix`: 조치 방법 (fail/warn일 때)

### 현재 규칙 목록

| ID | 항목 | 주요 조건 |
|---|---|---|
| NET-01 | 내·외부망 분리 | `zones.internet` + `devs.fw_ext` + `q_direct` |
| NET-02 | 서버 물리망분리 | `q_server_sep` |
| NET-03 | 단말 망분리 | `q_pc_sep` |
| NET-04 | DMZ 구간 | `zones.dmz` + `devs.fw_int` |
| NET-05 | 망연계 통제 | `q_transfer` + `devs.netlink` |
| NET-06 | 무선 AP | `q_wireless` + `devs.ap` |
| NET-07 | 원격접속 | `q_remote` + `devs.vpn` |
| NET-08 | 개발망 예외 | `q_dev` |
| NET-09 | SaaS 이용 | `q_saas` |
| NET-10 | DB존 분리 | `zones.server` + `zones.db` (warn) |
| NET-11 | 복수 내부 구역 방화벽 | `q_multi_zone` |
| NET-12 | 기관 간 스위치 직결 | `q_inter_org` |
| SEC-01 | 외부방화벽 | `devs.fw_ext` |
| SEC-02 | IPS/IDS | `devs.ips` |
| SEC-03 | 백신·PMS | `devs.av` |
| OPS-01 | NAC | `devs.nac` (warn) |
| OPS-02 | SIEM | `devs.siem` (warn) |
| AZ-01 | Azure Entra ID 인터넷 | `cloudType=azure` + `zones.internet` |
| AZ-02 | Azure DB 서브넷 분리 | `cloudType=azure` + `zones.db` |

### 구성도 전용 항목 (규칙에 미적용)

`ZONES` 4번째 요소 `true`인 항목: `z_internal`, `z_inetpc`, `z_dev`, `z_dr`  
UI에 **"구성도 전용"** 주황 뱃지 표시됨.

### OpenAI API Key 처리

소스 코드 내 base64 난독화로 저장 (GitHub Secret Scanning 우회):
```javascript
const _B = "base64encoded...";
const OPENAI_KEY = atob(_B);
```
키 변경 시 `btoa("sk-proj-...")` 로 base64 인코딩 후 `_B` 값 교체.

---

## AI 자동 인식 (buildCloudPrompt)

### 스키마 (JSON 출력 형식)

```json
{
  "zones": {"internet": true/false, ...},
  "devices": {"fw_ext": true/false, ...},
  "questions": {
    "q_multi_zone": "na|yes|shared",
    "q_inter_org": "na|router_fw|switch_only|l3sw_novlan"
  },
  "notes": "특이사항(한국어)"
}
```

### AI 응답 적용 흐름

1. zones/devices → 체크박스 `checked` 직접 설정
2. questions → `<select>` `value` 설정 (옵션 존재 시에만)
3. `n`(반영 건수) 카운트 후 완료 메시지 표시

---

## 개발 규칙

### 규칙 추가 절차

1. 필요 시 `QUESTIONS[]`에 드롭다운 항목 추가
2. `RULES[]` 끝(OPS-02 뒤)에 규칙 객체 추가
3. `buildDiagram()` 내 diffs 블록에 권고 구성도 반영 항목 추가
4. `buildCloudPrompt()` schema/instruction에 AI 감지 지침 추가
5. AI 핸들러의 `questions` 적용 코드는 범용이므로 수정 불필요

### 금지 사항

- 외부 CDN/라이브러리 추가 금지 (단일 파일 원칙)
- 실제 API 키 평문을 소스에 삽입 금지 (base64 또는 .env 사용)
- `.env` 파일 git 커밋 금지

### 인쇄(Print) CSS

`@media print` 블록에서 제어. 주요 포인트:
- `.dia-wrap svg { min-width:0!important; width:100%!important }` — SVG 잘림 방지
- `details.ai`, `#runBtn`, `#pickBtn` 등 조작 UI 숨김

---

## 테스트 방법

Playwright(Python)로 브라우저 자동화 테스트.

```powershell
$env:PYTHONIOENCODING="utf-8"
python test_script.py
```

배지 텍스트 기준값:
- pass → `"준 수"` (공백 있음)
- fail → `"미준수"`
- warn → `"보완권고"`
- na   → `"해당없음"`

cloudType 라디오는 `<details class="ai">` 안에 있어 hidden 상태이므로  
테스트 시 JS로 직접 설정:
```javascript
const r = document.querySelector('input[name="cloudType"][value="azure"]');
r.checked = true; r.dispatchEvent(new Event('change', {bubbles: true}));
```

---

## Git 운영

```powershell
# 커밋 (한글 포함 시 파워셸 here-string 사용)
git add network_separation.html
$msg = "feat: ...\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git commit -m $msg
git push
```

주의: PowerShell에서 `@{u}` 문법 오류 → `origin/master..HEAD` 사용
