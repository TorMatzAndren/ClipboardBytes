#!/usr/bin/env python3

import unittest

from clipboard_payload import ClipboardPayloadReader


def codex_handoff(body):
    return f"""===== TRANSPORT HEADER (NOT PART OF FILE) =====
PATH: CODEX:thisrepo:0
NOTE: Do NOT include this header in any saved documents.
===============================================
===== CODEX SESSION =====
session-file: /home/test/.codex/sessions/2026/09/17/rollout-test.jsonl
session-id: test-session
timestamp: 2026-09-17T18:00:00+02:00
cwd: /home/test/project
cli-version: 0.0.0
repo-root: /home/test/project
=========================

===== USER =====
Please inspect this.

===== ASSISTANT [commentary] =====
Inspecting.

{body}

===== ASSISTANT [final_answer] =====
Done.
"""


class ClipboardPayloadClassificationTests(unittest.TestCase):
    def setUp(self):
        self.reader = ClipboardPayloadReader()

    def classify(self, text):
        return self.reader._read_text(
            text,
            ["text/plain"],
            "2026-09-17T18:00:00",
        )

    def assert_kind(self, text, expected):
        payload = self.classify(text)
        self.assertEqual(payload.kind, expected)
        return payload

    def test_codex_handoff_is_codex(self):
        payload = self.assert_kind(
            codex_handoff(
                """===== TOOL CALL [exec] =====
pwd

===== TOOL OUTPUT =====
/home/test/project"""
            ),
            "codex",
        )
        self.assertEqual(payload.subtype, "Codex handoff")
        self.assertEqual(payload.mime_type, "text/x-codex-handoff")

    def test_codex_handoff_containing_python_stays_codex(self):
        self.assert_kind(
            codex_handoff(
                """===== TOOL OUTPUT =====
import json

def classify(value):
    return json.loads(value)"""
            ),
            "codex",
        )

    def test_codex_handoff_containing_rust_stays_codex(self):
        self.assert_kind(
            codex_handoff(
                """===== TOOL OUTPUT =====
fn main() {
    let value: usize = 42;
    println!("{value}");
}"""
            ),
            "codex",
        )

    def test_codex_handoff_containing_mixed_content_stays_codex(self):
        self.assert_kind(
            codex_handoff(
                """===== TOOL CALL [exec] =====
python3 test.py

===== TOOL OUTPUT =====
=== test.py ===
def test():
    return True

=== src/main.rs ===
fn main() {
    println!("hello");
}

Some explanatory prose follows."""
            ),
            "codex",
        )

    def test_ordinary_python_remains_python(self):
        self.assert_kind(
            """import json
import pathlib

def load_value(text):
    value = json.loads(text)
    path = pathlib.Path("value.json")
    return value, path
""",
            "python",
        )

    def test_ordinary_rust_remains_rust(self):
        self.assert_kind(
            """use std::collections::HashMap;

fn main() {
    let mut values: Vec<i32> = Vec::new();
    let mut map: HashMap<String, i32> = HashMap::new();
    values.push(42);
    map.insert(String::from("answer"), 42);
    println!("{:?} {:?}", values, map);
}
""",
            "rust",
        )

    def test_ordinary_mixed_content_remains_mixed(self):
        self.assert_kind(
            """=== app.js ===
const value = 42;
console.log(value);

=== style.css ===
body {
    color: red;
}
""",
            "mixed",
        )

    def test_plain_text_mentioning_codex_remains_text(self):
        self.assert_kind(
            """Codex is useful for repository work.
This paragraph merely mentions Codex and is not a handoff transcript.
There is no canonical session structure here.
""",
            "text",
        )

    def test_session_heading_alone_is_not_codex(self):
        self.assertNotEqual(
            self.classify(
                """===== CODEX SESSION =====
This is ordinary text imitating a heading.
"""
            ).kind,
            "codex",
        )

    def test_transport_path_alone_is_not_codex(self):
        self.assertNotEqual(
            self.classify(
                """PATH: CODEX:thisrepo:0
This is not a canonical Codex transcript.
"""
            ).kind,
            "codex",
        )


if __name__ == "__main__":
    unittest.main()
