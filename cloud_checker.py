#!/usr/bin/env python3
"""
클라우드 망분리 준수 검토기 (Cloud Network Separation Compliance Checker)
전자금융감독규정 제15조 및 금융부문 망분리 가이드라인 기준

사용법:
  python cloud_checker.py [파일경로]          # 파일 입력
  python cloud_checker.py                     # 대화형 입력
  python cloud_checker.py -o result.json      # 결과 저장
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

try:
    from openai import OpenAI
except ImportError:
    print("[오류] openai 패키지를 설치하세요: pip install openai")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────
# 시스템 프롬프트 — 망분리 규정 기준 정의
# ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """당신은 금융회사 클라우드 네트워크 망분리 전문가입니다.
제공된 클라우드 네트워크 구성(AWS VPC / Azure VNet / GCP VPC 등)을 분석하여
전자금융감독규정 제15조 및 금융부문 망분리 가이드라인 준수 여부를 검토합니다.

검토 항목:
  NET-01 내부업무망↔인터넷망 분리  — 내부 서브넷에서 IGW 직접 라우팅 금지
  NET-02 서버/DB 구간 Private 격리 — DB·앱서버가 Private Subnet에 위치
  NET-03 Public/Private 서브넷 분리 — 퍼블릭과 프라이빗 서브넷 명확히 구분
  NET-04 DMZ 구성               — ALB·WAF·NAT GW가 DMZ(또는 Public) 서브넷에만 위치
  NET-05 보안그룹/NACL 최소 허용  — 0.0.0.0/0 인바운드 불필요한 개방 여부
  NET-06 DB 인터넷 노출 금지     — RDS·DB 인스턴스가 퍼블릭 IP 없이 Private에만 존재
  NET-07 망간 자료전송 통제      — 인터넷↔내부망 자료이동 경로(PrivateLink·Transit GW 등)
  SEC-01 경계 침입차단(방화벽)    — Security Group·NACL·WAF 설정 적정성
  SEC-02 암호화 통신             — HTTPS/TLS 적용, 평문 포트(80·21·23 등) 인바운드 차단
  SEC-03 관리 접근 통제          — SSH(22)·RDP(3389) 등 관리 포트 전체 개방 여부

각 항목별 JSON 응답 형식(반드시 이 스키마만 반환):
{
  "summary": {
    "overall": "PASS|FAIL|WARN",
    "total": <int>,
    "pass": <int>,
    "fail": <int>,
    "warn": <int>,
    "na": <int>
  },
  "verdict": "<종합 의견 2~3문장 — 한국어>",
  "rules": [
    {
      "id": "NET-01",
      "name": "<규칙 이름>",
      "status": "PASS|FAIL|WARN|NA",
      "finding": "<발견 내용 — 한국어>",
      "recommendation": "<개선 권고 — 한국어, PASS이면 빈 문자열>"
    }
  ]
}
마크다운 코드블록 없이 순수 JSON만 반환하십시오."""


# ─────────────────────────────────────────────────────────────
# API Key 로드 (환경변수 → .env 파일 → 직접 입력)
# ─────────────────────────────────────────────────────────────
def load_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if key:
        return key

    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("OPENAI_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("\"'")
                if key:
                    return key

    print("\n[안내] OpenAI API Key가 설정되지 않았습니다.")
    print("  방법 1: 환경변수  set OPENAI_API_KEY=sk-...")
    print("  방법 2: .env 파일  OPENAI_API_KEY=sk-...")
    print("  방법 3: 지금 직접 입력\n")
    key = input("OpenAI API Key 입력 (sk-...): ").strip()
    if not key:
        print("[오류] API Key가 없으면 분석할 수 없습니다.")
        sys.exit(1)
    return key


# ─────────────────────────────────────────────────────────────
# OpenAI 분석 호출
# ─────────────────────────────────────────────────────────────
def analyze(config_text: str, api_key: str, model: str) -> dict:
    client = OpenAI(api_key=api_key)
    user_msg = (
        "다음 클라우드 네트워크 구성을 망분리 준수 관점에서 검토해주세요:\n\n"
        + config_text
    )
    response = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )
    raw = response.choices[0].message.content
    return json.loads(raw)


# ─────────────────────────────────────────────────────────────
# 결과 출력
# ─────────────────────────────────────────────────────────────
STATUS_ICON = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️ ", "NA": "⬜"}
STATUS_KR   = {"PASS": "적합", "FAIL": "위반", "WARN": "주의", "NA": "해당없음"}

def print_report(result: dict, source_label: str = ""):
    s = result.get("summary", {})
    overall = s.get("overall", "WARN")
    icon = STATUS_ICON.get(overall, "❓")

    print("\n" + "=" * 64)
    print("  망분리 준수 검토 결과")
    if source_label:
        print(f"  대상: {source_label}")
    print(f"  일시: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 64)

    print(f"\n  종합 판정: {icon} {STATUS_KR.get(overall, overall)}")
    print(
        f"  검토 항목: 총 {s.get('total', 0)}건 "
        f"(적합 {s.get('pass', 0)} / 위반 {s.get('fail', 0)} / "
        f"주의 {s.get('warn', 0)} / 해당없음 {s.get('na', 0)})"
    )
    verdict = result.get("verdict", "")
    if verdict:
        print(f"\n  {verdict}")

    print("\n" + "-" * 64)
    print("  항목별 결과")
    print("-" * 64)

    for rule in result.get("rules", []):
        st = rule.get("status", "NA")
        print(
            f"\n  {STATUS_ICON.get(st, '?')} [{rule.get('id', '')}] {rule.get('name', '')}"
            f"  — {STATUS_KR.get(st, st)}"
        )
        finding = rule.get("finding", "")
        if finding:
            print(f"     발견: {finding}")
        rec = rule.get("recommendation", "")
        if rec:
            print(f"     권고: {rec}")

    print("\n" + "=" * 64)


# ─────────────────────────────────────────────────────────────
# 진입점
# ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="클라우드 망분리 준수 검토기 — 전자금융감독규정 제15조 기준",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python cloud_checker.py examples/aws_vpc.json
  python cloud_checker.py examples/aws_vpc.json -o result.json
  python cloud_checker.py --model gpt-4.1
  python cloud_checker.py              # 대화형: 설정 붙여넣기 후 Ctrl+Z(Windows)/Ctrl+D(Mac)
        """,
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="클라우드 네트워크 설정 파일 경로 (JSON/YAML/텍스트). 생략 시 대화형 입력.",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o",
        help="OpenAI 모델 ID (기본값: gpt-4o)",
    )
    parser.add_argument(
        "--output", "-o",
        help="분석 결과를 저장할 JSON 파일 경로",
    )
    args = parser.parse_args()

    # 입력 수집
    if args.input:
        p = Path(args.input)
        if not p.exists():
            print(f"[오류] 파일을 찾을 수 없습니다: {args.input}")
            sys.exit(1)
        config_text = p.read_text(encoding="utf-8")
        source_label = p.name
    else:
        print("클라우드 네트워크 구성을 붙여넣으세요.")
        print("완료 후 Windows: Ctrl+Z → Enter  /  Mac·Linux: Ctrl+D\n")
        try:
            config_text = sys.stdin.read().strip()
        except KeyboardInterrupt:
            print("\n취소되었습니다.")
            sys.exit(0)
        if not config_text:
            print("[오류] 입력 내용이 없습니다.")
            sys.exit(1)
        source_label = "직접 입력"

    api_key = load_api_key()

    print(f"\n[분석 중] 모델: {args.model} …")
    try:
        result = analyze(config_text, api_key, args.model)
    except Exception as e:
        print(f"[오류] OpenAI API 호출 실패: {e}")
        sys.exit(1)

    print_report(result, source_label)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n결과 저장 완료: {out_path}")


if __name__ == "__main__":
    main()
