#!/usr/bin/env python3
"""
klsonsaeng.py — 클선생 콘텐츠 검열봇
=====================================
Gate 1: Python 린터 (결정론적, 비용 0)
Gate 2: LLM Judge (Claude, 맥락 판단)

Usage:
    python3 scripts/klsonsaeng.py lint [파일|디렉토리]     # Gate 1만
    python3 scripts/klsonsaeng.py judge [파일]             # Gate 1 + Gate 2
    python3 scripts/klsonsaeng.py sweep                     # 전체 84페이지 Gate 1
    python3 scripts/klsonsaeng.py sweep --full              # 전체 Gate 1 + Gate 2
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import yaml

# ── Paths ─────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = ROOT / ".vcms-policy.yml"
SPEC_PATH = ROOT / "_data" / "doctrine" / "llms-full.txt"
KO_DIR = ROOT / "ko"

# ── Load Policy ───────────────────────────────────────────────────
def load_policy() -> dict:
    if not POLICY_PATH.exists():
        print(f"ERROR: {POLICY_PATH} not found", file=sys.stderr)
        sys.exit(1)
    with open(POLICY_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_spec() -> str:
    if not SPEC_PATH.exists():
        print(f"WARN: {SPEC_PATH} not found, fetching from docs.vcms.io...", file=sys.stderr)
        SPEC_PATH.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["curl", "-s", "https://docs.vcms.io/llms-full.txt", "-o", str(SPEC_PATH)],
            check=True,
        )
    return SPEC_PATH.read_text(encoding="utf-8")


# ── MDX Tag Stripper ──────────────────────────────────────────────
def strip_mdx_tags(content: str) -> str:
    """Remove MDX/JSX tags and frontmatter, keep inner text."""
    # Remove frontmatter
    content = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL)
    # Remove import statements
    content = re.sub(r"^import\s+.*$", "", content, flags=re.MULTILINE)
    # Remove JSX component tags but keep inner text
    content = re.sub(r"<[^>]+>", "", content)
    return content


def get_line_number(original: str, match_start: int) -> int:
    """Get line number from character position in original file."""
    return original[:match_start].count("\n") + 1


# ══════════════════════════════════════════════════════════════════
# GATE 1: Python Linter (deterministic, $0)
# ══════════════════════════════════════════════════════════════════

class LintResult:
    def __init__(self, file: str, line: int, level: str, rule: str, message: str, suggestion: str = ""):
        self.file = file
        self.line = line
        self.level = level  # ERROR | WARN
        self.rule = rule
        self.message = message
        self.suggestion = suggestion

    def __str__(self):
        icon = "❌" if self.level == "ERROR" else "⚠️"
        s = f"  {icon} [{self.level}] L{self.line}: {self.message} ({self.rule})"
        if self.suggestion:
            s += f"\n     → {self.suggestion}"
        return s


def gate1_lint(file_path: Path, policy: dict) -> list[LintResult]:
    """Run Gate 1 deterministic checks on a single MDX file."""
    results = []
    raw = file_path.read_text(encoding="utf-8")
    text = strip_mdx_tags(raw)
    lines = raw.split("\n")

    # ── Terminology checks ────────────────────────────────────
    for rule in policy.get("terminology", {}).get("rules", []):
        pattern = rule.get("pattern", rule["banned"])
        exceptions = policy.get("terminology", {}).get("exceptions", [])

        for i, line in enumerate(lines, 1):
            # Skip frontmatter, imports, component tags
            stripped = re.sub(r"<[^>]+>", "", line)
            if stripped.startswith("import ") or stripped.startswith("---"):
                continue

            for m in re.finditer(pattern, stripped):
                matched = m.group()
                # Check exceptions
                is_exception = False
                for exc in exceptions:
                    if exc["term"] in matched and exc["context"] in line:
                        is_exception = True
                        break
                if not is_exception:
                    results.append(LintResult(
                        file=str(file_path.relative_to(ROOT)),
                        line=i,
                        level="ERROR",
                        rule="terminology",
                        message=f"'{matched}' → '{rule['preferred']}' (용어집 위반)",
                        suggestion=f"'{matched}'를 '{rule['preferred']}'로 변경하세요",
                    ))

    # ── Forbidden expressions ─────────────────────────────────
    for expr in policy.get("tone", {}).get("forbidden", []):
        for i, line in enumerate(lines, 1):
            if expr in line:
                results.append(LintResult(
                    file=str(file_path.relative_to(ROOT)),
                    line=i,
                    level="ERROR",
                    rule="forbidden_expression",
                    message=f"금지 표현 '{expr}' 사용됨",
                    suggestion=f"'{expr}'를 중립적 표현으로 교체하세요",
                ))

    # ── SLA claims ────────────────────────────────────────────
    sla_pattern = r"\d+초\s*이내|\d+분\s*이내|\d+초\s*만에|\d+분\s*만에"
    for i, line in enumerate(lines, 1):
        for m in re.finditer(sla_pattern, line):
            results.append(LintResult(
                file=str(file_path.relative_to(ROOT)),
                line=i,
                level="WARN",
                rule="sla_claim",
                message=f"SLA 수치 주장 '{m.group()}' — docs.vcms.io에서 확인 필요",
                suggestion="근거 없는 성능 수치는 제거하거나 완화하세요",
            ))

    # ── PII patterns ──────────────────────────────────────────
    phone_pattern = r"01[016789]\d{7,8}"
    for i, line in enumerate(lines, 1):
        for m in re.finditer(phone_pattern, line):
            results.append(LintResult(
                file=str(file_path.relative_to(ROOT)),
                line=i,
                level="ERROR",
                rule="pii_phone",
                message=f"전화번호 패턴 감지: {m.group()[:3]}****",
                suggestion="전화번호를 제거하세요",
            ))

    return results


# ══════════════════════════════════════════════════════════════════
# GATE 2: LLM Judge (Claude, contextual)
# ══════════════════════════════════════════════════════════════════

class JudgeResult:
    def __init__(self, file: str, verdict: str, findings: list[dict]):
        self.file = file
        self.verdict = verdict  # PASS | WARN | FAIL
        self.findings = findings  # [{type, line_hint, claim, spec_ref, suggestion}]

    def __str__(self):
        icons = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}
        s = f"\n{icons.get(self.verdict, '?')} [{self.verdict}] {self.file}"
        for f in self.findings:
            level_icon = "❌" if f.get("type") == "FAIL" else "⚠️"
            s += f"\n  {level_icon} {f.get('claim', '')}"
            if f.get("spec_ref"):
                s += f"\n     📖 docs.vcms.io: {f['spec_ref']}"
            if f.get("suggestion"):
                s += f"\n     → {f['suggestion']}"
        return s


def gate2_judge(file_path: Path, policy: dict, spec: str) -> JudgeResult | None:
    """Run Gate 2 LLM Judge on a single MDX file."""
    try:
        import anthropic
    except ImportError:
        print("WARN: anthropic 패키지 없음, Gate 2 스킵", file=sys.stderr)
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("WARN: ANTHROPIC_API_KEY 없음, Gate 2 스킵", file=sys.stderr)
        return None

    content = file_path.read_text(encoding="utf-8")
    file_rel = str(file_path.relative_to(ROOT))

    # Build promotion patterns few-shot
    patterns_text = ""
    for p in policy.get("promotion_patterns", []):
        patterns_text += f"\n패턴: {p['name']} — {p['description']}\n"
        patterns_text += f"  BAD: {p['bad']}\n  GOOD: {p['good']}\n"

    # Build channel lists
    active_channels = ", ".join(policy.get("channels", {}).get("active", []))
    pending_channels = ", ".join(policy.get("channels", {}).get("pending", []))
    product_is = ", ".join(policy.get("product_scope", {}).get("is", []))
    product_not = ", ".join(policy.get("product_scope", {}).get("not", []))

    system_prompt = dedent(f"""\
    당신은 VCMS 콘텐츠 검열봇 "클선생"입니다.
    아래 공식 제품 문서(docs.vcms.io)를 Source of Truth로 사용하여 콘텐츠를 팩트체크합니다.

    ## 판정 기준
    - FAIL: 공식 문서와 명백히 모순되는 주장
    - WARN: 공식 문서에 언급되지 않은 주장 (UNANCHORED)
    - PASS: 공식 문서에서 확인된 주장, 또는 스펙 주장이 아닌 운영 팁/맥락

    ## 승격 패턴 (VOC 소망이 스펙으로 잘못 작성된 경우)
    {patterns_text}

    ## 채널 상태
    - 연동 채널: {active_channels}
    - 준비 중 (비연동): {pending_channels}
    → 비연동 채널을 연동 채널처럼 사용하면 FAIL

    ## 제품 범위
    - VCMS 기능: {product_is}
    - VCMS 기능 아님: {product_not}
    → VCMS 기능이 아닌 것을 VCMS 기능처럼 설명하면 FAIL

    ## 출력 형식
    JSON으로 출력하세요:
    {{
      "verdict": "PASS" | "WARN" | "FAIL",
      "findings": [
        {{
          "type": "FAIL" | "WARN",
          "claim": "문제가 된 문장",
          "spec_ref": "관련 docs.vcms.io 섹션 (있으면)",
          "suggestion": "수정 제안"
        }}
      ]
    }}

    findings가 비어있으면 verdict는 PASS입니다.
    FAIL이 1개라도 있으면 verdict는 FAIL입니다.
    WARN만 있으면 verdict는 WARN입니다.
    """)

    user_prompt = dedent(f"""\
    ## 검열 대상 파일: {file_rel}

    ```mdx
    {content}
    ```

    ## 공식 제품 문서 (docs.vcms.io 전체)

    {spec}
    """)

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw_text = response.content[0].text

        # Extract JSON from response
        json_match = re.search(r"\{[\s\S]*\}", raw_text)
        if json_match:
            result = json.loads(json_match.group())
            return JudgeResult(
                file=file_rel,
                verdict=result.get("verdict", "PASS"),
                findings=result.get("findings", []),
            )
    except Exception as e:
        print(f"WARN: Gate 2 실패 ({file_rel}): {e}", file=sys.stderr)

    return None


# ══════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════

def collect_mdx_files(target: str | None) -> list[Path]:
    """Collect MDX files from target path."""
    if target and Path(target).is_file():
        return [Path(target).resolve()]

    base = Path(target).resolve() if target else KO_DIR
    files = []
    for subdir in ["vcms-usage", "channels", "magazine"]:
        d = base / subdir if base == KO_DIR else base
        if d.exists():
            files.extend(sorted(d.glob("**/*.mdx")))
        elif base != KO_DIR:
            files.extend(sorted(base.glob("**/*.mdx")))
            break

    # Exclude stories (VOC raw data, not curated content)
    files = [f for f in files if "/stories/" not in str(f)]
    # Exclude index files
    files = [f for f in files if f.name != "index.mdx"]
    return files


def cmd_lint(args):
    """Gate 1 only."""
    policy = load_policy()
    files = collect_mdx_files(args.target)
    if not files:
        print("No MDX files found.")
        return 0

    total_errors = 0
    total_warns = 0

    for f in files:
        results = gate1_lint(f, policy)
        if results:
            rel = str(f.relative_to(ROOT))
            print(f"\n📄 {rel}")
            for r in results:
                print(r)
                if r.level == "ERROR":
                    total_errors += 1
                else:
                    total_warns += 1

    print(f"\n{'═' * 50}")
    print(f"Gate 1 완료: {len(files)}파일 검사, {total_errors} ERROR, {total_warns} WARN")

    return 1 if total_errors > 0 else 0


def cmd_judge(args):
    """Gate 1 + Gate 2."""
    policy = load_policy()
    spec = load_spec()
    files = collect_mdx_files(args.target)
    if not files:
        print("No MDX files found.")
        return 0

    total_errors = 0
    total_warns = 0

    # Gate 1 first
    print("━━ Gate 1: 린터 ━━━━━━━━━━━━━━━━━━━━━━━━━")
    for f in files:
        results = gate1_lint(f, policy)
        if results:
            rel = str(f.relative_to(ROOT))
            print(f"\n📄 {rel}")
            for r in results:
                print(r)
                if r.level == "ERROR":
                    total_errors += 1
                else:
                    total_warns += 1

    # Gate 2
    print("\n━━ Gate 2: 클선생 LLM Judge ━━━━━━━━━━━━━")
    gate2_fails = 0
    gate2_warns = 0

    for f in files:
        rel = str(f.relative_to(ROOT))
        print(f"\n🔍 검열 중: {rel}...", end="", flush=True)
        result = gate2_judge(f, policy, spec)
        if result:
            print(result)
            for finding in result.findings:
                if finding.get("type") == "FAIL":
                    gate2_fails += 1
                else:
                    gate2_warns += 1
        else:
            print(" (스킵)")

    print(f"\n{'═' * 50}")
    print(f"Gate 1: {total_errors} ERROR, {total_warns} WARN")
    print(f"Gate 2: {gate2_fails} FAIL, {gate2_warns} WARN")

    return 1 if (total_errors > 0 or gate2_fails > 0) else 0


def cmd_sweep(args):
    """Full sweep of all curated pages."""
    if args.full:
        args.target = None
        return cmd_judge(args)
    else:
        args.target = None
        return cmd_lint(args)


def main():
    parser = argparse.ArgumentParser(description="클선생 — VCMS 콘텐츠 검열봇")
    sub = parser.add_subparsers(dest="cmd")

    p_lint = sub.add_parser("lint", help="Gate 1 린터만 실행")
    p_lint.add_argument("target", nargs="?", help="파일 또는 디렉토리")

    p_judge = sub.add_parser("judge", help="Gate 1 + Gate 2 실행")
    p_judge.add_argument("target", nargs="?", help="파일 또는 디렉토리")

    p_sweep = sub.add_parser("sweep", help="전체 페이지 검열")
    p_sweep.add_argument("--full", action="store_true", help="Gate 2 포함 (LLM 비용 발생)")

    args = parser.parse_args()
    if args.cmd == "lint":
        sys.exit(cmd_lint(args))
    elif args.cmd == "judge":
        sys.exit(cmd_judge(args))
    elif args.cmd == "sweep":
        sys.exit(cmd_sweep(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
