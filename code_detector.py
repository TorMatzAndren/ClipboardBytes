import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CodeDetection:
    language: str
    subtype: str
    confidence: int
    tier: str


class CodeDetector:
    MIN_CLASSIFY_CONFIDENCE = 70

    def detect(self, text: str):
        lines = self._clean_lines(text)
        if len(lines) < 2:
            return None

        if self._looks_like_file_generation_heredoc(lines):
            return None

        candidates = []
        for language, subtype, checker in (
            ("sql", "query", self._hint_sql),
            ("markdown", "document", self._hint_markdown),
            ("python", "block", self._hint_python),
            ("go", "package/func", self._hint_go),
            ("java", "class/main", self._hint_java),
            ("csharp", "using/class", self._hint_csharp),
            ("rust", "fn/main", self._hint_rust),
            ("javascript", "function/const/let", self._hint_javascript),
            ("bash", "shell", self._hint_bash),
        ):
            score = checker(lines)
            if score > 0:
                candidates.append((language, subtype, score))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[2], reverse=True)
        top_language, top_subtype, top_score = candidates[0]

        if top_score < self.MIN_CLASSIFY_CONFIDENCE:
            return None

        if len(candidates) > 1:
            second_score = candidates[1][2]
            if top_score - second_score < 10:
                return None

        return self._make(top_language, top_subtype, top_score)

    def scan_hints(self, text: str):
        lines = self._clean_lines(text)
        if not lines:
            return []

        hints = []

        for name, checker in (
            ("python", self._hint_python_loose),
            ("markdown", self._hint_markdown),
            ("bash", self._hint_bash),
            ("sql", self._hint_sql),
            ("javascript", self._hint_javascript),
            ("csharp", self._hint_csharp),
            ("java", self._hint_java),
            ("go", self._hint_go),
            ("rust", self._hint_rust),
        ):
            score = checker(lines)
            if score >= 40:
                hints.append((name, score))

        hints.sort(key=lambda item: item[1], reverse=True)
        return hints[:3]

    def _clean_lines(self, text):
        return [line.rstrip() for line in text.splitlines() if line.strip()]

    def _tier(self, confidence):
        if confidence >= 90:
            return "strong"
        if confidence >= 75:
            return "moderate"
        if confidence >= 60:
            return "weak"
        return "low"

    def _make(self, language, subtype, confidence):
        confidence = max(0, min(100, int(confidence)))
        return CodeDetection(language, subtype, confidence, self._tier(confidence))

    def _looks_like_file_generation_heredoc(self, lines):
        if not lines:
            return False

        joined = "\n".join(lines)
        return bool(
            not lines[0].strip().startswith("#!")
            and re.search(r"<<['\"]?\w+['\"]?", joined)
            and re.search(r"^\s*(cat|tee)\s+.*>\s*\S+.*<<", joined, re.MULTILINE)
        )

    def _has_prose(self, lines):
        prose = 0

        for line in lines:
            stripped = line.strip()

            if stripped.startswith(("#", "//", "--", "*", "-", ">", "```")):
                continue

            if len(stripped) >= 18 and re.search(
                r"\b(this|that|the|and|because|should|would|could|following|example|clipboard|document|snippet|explains|works|note|several)\b",
                stripped,
                re.IGNORECASE,
            ):
                prose += 1

        return prose >= 2

    def _hint_sql(self, lines):
        if not lines or self._has_prose(lines):
            return 0

        joined = "\n".join(lines).lower()
        score = 0

        if re.search(r"\bselect\b.+\bfrom\b", joined, re.DOTALL):
            score += 65
        if re.search(r"\b(insert\s+into|create\s+table|update\b.+\bset|delete\s+from)\b", joined, re.DOTALL):
            score += 65
        if re.search(r"\b(where|group\s+by|order\s+by|join|with|limit)\b", joined):
            score += 20

        return min(94, score)

    def _hint_markdown(self, lines):
        if not lines:
            return 0

        fences = sum(1 for line in lines if line.strip().startswith("```"))
        headings = sum(1 for line in lines if re.match(r"^#{1,6}\s+\w+", line.strip()))
        lists = sum(1 for line in lines if re.match(r"^([-*+]|\d+\.)\s+\w+", line.strip()))
        links = sum(1 for line in lines if re.search(r"\[[^\]]+\]\([^)]+\)", line.strip()))

        if fences >= 2:
            return 95

        score = 0
        if headings:
            score += min(35, headings * 25)
        if lists:
            score += min(35, lists * 12)
        if links:
            score += min(20, links * 15)
        if headings and lists:
            score += 30
        if headings and links:
            score += 20

        return min(90, score)

    def _hint_python(self, lines):
        if not lines or self._has_prose(lines):
            return 0

        joined = "\n".join(lines)

        if re.search(
            r"\b(using\s+System|Console\.WriteLine|public\s+class|static\s+void|namespace|package\s+main|func\s+\w+|fmt\.Print|fn\s+main|println!)\b",
            joined,
        ):
            return 0

        if any(line.strip().endswith(";") for line in lines):
            return 0

        for line in lines:
            stripped = line.strip()
            if re.match(r"^(def|class|if|elif|else|for|while|try|except|finally|with)\b", stripped):
                if not stripped.endswith(":"):
                    return 0

        has_entry = bool(
            re.search(r"^\s*(def|class)\s+\w+.*:\s*$", joined, re.MULTILINE)
            or re.search(r"^\s*(from|import)\s+\w+", joined, re.MULTILINE)
        )

        if not has_entry:
            return 0

        score = 50
        if any(line.strip().endswith(":") for line in lines):
            score += 10
        if any(line.startswith((" ", "\t")) for line in lines):
            score += 10
        if re.search(r"\b(self|None|True|False|Path|json|print)\b", joined):
            score += 15

        return min(96, score)

    def _hint_python_loose(self, lines):
        if not lines:
            return 0

        joined = "\n".join(lines)

        if re.search(r"^\s*(def|class|from|import|if|elif|return)\b", joined, re.MULTILINE):
            return min(70, self._hint_python(lines) or 54)

        return 0

    def _hint_go(self, lines):
        if not lines or self._has_prose(lines):
            return 0

        joined = "\n".join(lines)
        score = 0

        if re.search(r"\bpackage\s+main\b", joined):
            score += 40
        if re.search(r"\bfunc\s+main\s*\(", joined):
            score += 35
        if "fmt." in joined:
            score += 15
        if ":=" in joined:
            score += 10

        return min(92, score)

    def _hint_java(self, lines):
        if not lines or self._has_prose(lines):
            return 0

        joined = "\n".join(lines)
        score = 0

        if re.search(r"\bpublic\s+class\b", joined):
            score += 40
        if re.search(r"\bpublic\s+static\s+void\s+main\b", joined):
            score += 35
        if "System.out.println" in joined:
            score += 25
        if re.search(r"\bimport\s+java\.", joined):
            score += 10

        return min(95, score)

    def _hint_csharp(self, lines):
        if not lines or self._has_prose(lines):
            return 0

        joined = "\n".join(lines)
        score = 0

        if "using System" in joined:
            score += 35
        if "Console.WriteLine" in joined:
            score += 35
        if re.search(r"\bnamespace\b|\bpublic\s+class\b|\bstatic\s+void\s+Main\b", joined):
            score += 20

        return min(94, score)

    def _hint_rust(self, lines):
        if not lines or self._has_prose(lines):
            return 0

        joined = "\n".join(lines)
        score = 0

        if re.search(r"\bfn\s+main\s*\(", joined):
            score += 40
        if "println!" in joined:
            score += 35
        if re.search(r"\blet\s+(mut\s+)?\w+", joined):
            score += 15
        if re.search(r"\buse\s+std::", joined):
            score += 10

        return min(94, score)

    def _hint_javascript(self, lines):
        if not lines or self._has_prose(lines):
            return 0

        joined = "\n".join(lines)
        score = 0

        if "console.log" in joined:
            score += 35

        if re.search(r"\b(function\s+\w+|const\s+\w+|let\s+\w+|var\s+\w+)\b", joined):
            score += 40

        if "=>" in joined:
            score += 20

        if re.search(r"\bmodule\.exports\b|\bexport\s+default\b", joined):
            score += 15

        if re.search(r"\brequire\s*\(", joined):
            score += 10

        if "JSON.stringify" in joined:
            score += 15

        if re.search(r"^\s*[A-Za-z_][A-Za-z0-9_]*\s*:\s*", joined, re.MULTILINE):
            score += 10

        if re.search(r"\bimport\s+React\b|\bfrom\s+['\"]react['\"]|return\s+<", joined):
            score += 20

        return min(92, score)

    def _hint_bash(self, lines):
        if not lines or self._has_prose(lines):
            return 0

        joined = "\n".join(lines)
        score = 0

        if lines[0].strip().startswith("#!"):
            score += 45
        if re.search(r"\b(echo|grep|cd|ls|rm|mkdir|chmod|sudo|export|source|printf|cat)\b", joined):
            score += 25
        if re.search(r"\$[A-Za-z_]", joined):
            score += 15
        if re.search(r"\b(if|then|fi|else)\b", joined):
            score += 20
        if re.search(r"<<['\"]?\w+['\"]?", joined) and lines[0].strip().startswith("#!"):
            score += 10

        return min(92, score)
