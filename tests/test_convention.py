"""
컨벤션 검증 노드 단위 테스트
"""

import pytest
from agents.nodes.convention import (
    _is_snake_case,
    _is_pascal_case,
    _to_snake_case,
    _ast_check,
    _extract_python_from_diff,
)


class TestNamingUtils:
    def test_snake_case_valid(self):
        assert _is_snake_case("get_user") is True
        assert _is_snake_case("calculate_discount_price") is True
        assert _is_snake_case("process") is True

    def test_snake_case_invalid(self):
        assert _is_snake_case("getData") is False
        assert _is_snake_case("GetUser") is False
        assert _is_snake_case("calculateDiscountPrice") is False

    def test_pascal_case_valid(self):
        assert _is_pascal_case("UserService") is True
        assert _is_pascal_case("PRData") is True
        assert _is_pascal_case("AgentState") is True

    def test_pascal_case_invalid(self):
        assert _is_pascal_case("user_service") is False
        assert _is_pascal_case("userService") is False

    def test_to_snake_case(self):
        assert _to_snake_case("getData") == "get_data"
        assert _to_snake_case("calculateDiscountPrice") == "calculate_discount_price"
        assert _to_snake_case("getUserByID") == "get_user_by_i_d"


class TestASTCheck:
    def test_snake_case_violation(self):
        diff = """--- a/test.py
+++ b/test.py
@@ -1,3 +1,5 @@
+def getData():
+    pass
"""
        violations = _ast_check(diff, ["test.py"])
        rule_names = [v.rule for v in violations]
        assert "naming_snake_case" in rule_names

    def test_bare_except_violation(self):
        diff = """--- a/test.py
+++ b/test.py
@@ -1,5 +1,7 @@
+try:
+    pass
+except:
+    pass
"""
        violations = _ast_check(diff, ["test.py"])
        rule_names = [v.rule for v in violations]
        assert "bare_except" in rule_names

    def test_no_violations_on_clean_code(self):
        diff = """--- a/test.py
+++ b/test.py
@@ -1,3 +1,5 @@
+def get_user(user_id: int) -> dict:
+    return {}
"""
        violations = _ast_check(diff, ["test.py"])
        # 타입 힌트나 기타 info 위반은 있을 수 있지만 error는 없어야 함
        errors = [v for v in violations if v.severity == "error"]
        assert len(errors) == 0

    def test_non_python_files_skipped(self):
        diff = """--- a/test.js
+++ b/test.js
@@ -1,2 +1,3 @@
+function getData() {}
"""
        violations = _ast_check(diff, ["test.js"])
        assert len(violations) == 0


class TestDiffExtraction:
    def test_extract_python_files(self):
        diff = """--- a/module.py
+++ b/module.py
@@ -1,3 +1,5 @@
+def hello():
+    return "world"
"""
        result = _extract_python_from_diff(diff)
        assert "module.py" in result
        assert any("def hello" in line for line in result["module.py"])

    def test_skip_removed_lines(self):
        diff = """--- a/module.py
+++ b/module.py
@@ -1,3 +1,3 @@
-def old_func():
+def new_func():
     pass
"""
        result = _extract_python_from_diff(diff)
        if "module.py" in result:
            # -로 시작하는 줄 (삭제된 줄)은 포함되지 않아야 함
            assert not any("old_func" in line for line in result["module.py"])
