"""LightShield v0.0.03 — validator.py smoke test (Gate E)

执行 Claude Code 下发的 4 组测试用例，验证 TargetValidator 的校验逻辑。
"""

import sys
import os

# 将项目根目录加入搜索路径，使 lightshield 包可被导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lightshield.utils.validator import TargetValidator

passed = 0
failed = 0
failures = []  # 记录失败用例的详情


def check(case_id: str, actual_ok: bool, expected_ok: bool,
          actual_msg: str, target_repr: str):
    global passed, failed
    if actual_ok == expected_ok:
        passed += 1
        tag = "通过" if expected_ok else "正确拒绝"
        print(f"  PASS  {case_id}: {target_repr} -> {tag} ({actual_msg})")
    else:
        failed += 1
        failures.append({
            "id": case_id,
            "target": target_repr,
            "expected": expected_ok,
            "actual": actual_ok,
            "message": actual_msg,
        })
        tag = "预期通过，实际拒绝" if expected_ok else "预期拒绝，实际通过"
        print(f"  FAIL  {case_id}: {target_repr} -> {tag} ({actual_msg})")


# ============================================================
# 测试 1：合法输入（必须全部返回 True）
# ============================================================
print("=" * 60)
print("测试 1：合法输入（必须全部返回 True）")
print("=" * 60)

valid_targets = [
    ("192.168.1.1",    "合法 IPv4"),
    ("10.0.0.1",       "内网 IPv4"),
    ("example.com",    "合法域名"),
    ("sub.example.cn", "多级域名"),
    ("localhost",      "localhost"),
    ("::1",            "IPv6 回环"),
    ("fe80::1",        "IPv6 链路本地"),
]

for i, (target, desc) in enumerate(valid_targets, 1):
    ok, msg = TargetValidator.validate(target)
    check(f"T1-{i}", ok, True, msg, f"{target} ({desc})")

print()

# ============================================================
# 测试 2：非法输入（必须全部返回 False）
# ============================================================
print("=" * 60)
print("测试 2：非法输入（必须全部返回 False）")
print("=" * 60)

invalid_targets = [
    ("",                            "空字符串"),
    ("192.168.1.0/24",             "CIDR 网段"),
    ("10.0.0.1/8",                 "CIDR /8"),
    ("192.168.1.1-192.168.1.10",   "IP 范围"),
    ("192.168.1.1-10",             "IP 缩写范围"),
    ("*.example.com",              "通配符域名"),
    ("http://example.com",         "HTTP URL"),
    ("https://example.com/path",   "HTTPS URL"),
    ("example.com:443",            "带端口域名"),
]

for i, (target, desc) in enumerate(invalid_targets, 1):
    ok, msg = TargetValidator.validate(target)
    check(f"T2-{i}", ok, False, msg, repr(target) + f" ({desc})")

print()

# ============================================================
# 测试 3：扫描参数校验（R6 合规）
# ============================================================
print("=" * 60)
print("测试 3：扫描参数校验（R6 合规）")
print("=" * 60)

scan_params = [
    (20, 5.0, True,  "并发 20 / 间隔 5.0s -> 应通过"),
    (21, 5.0, False, "并发 21 / 间隔 5.0s -> 应拒绝（超过上限）"),
    (10, 2.0, False, "并发 10 / 间隔 2.0s -> 应拒绝（间隔不足）"),
]

for i, (concurrency, interval, expected, desc) in enumerate(scan_params, 1):
    ok, msg = TargetValidator.validate_scan_params(concurrency, interval)
    check(f"T3-{i}", ok, expected, msg, desc)

print()

# ============================================================
# 测试 4：所有权确认提示（R4 合规）
# ============================================================
print("=" * 60)
print("测试 4：所有权确认提示（R4 合规）")
print("=" * 60)

ownership_text = TargetValidator.confirm_ownership("192.168.1.1")
has_keyword = "所有权" in ownership_text

if has_keyword:
    passed += 1
    print(f"  PASS  T4-1: confirm_ownership 返回文本包含 '所有权'")
    print(f"          内容: {ownership_text}")
else:
    failed += 1
    failures.append({
        "id": "T4-1",
        "target": "confirm_ownership('192.168.1.1')",
        "expected": "包含 '所有权'",
        "actual": ownership_text,
        "message": "未包含所有权关键词",
    })
    print(f"  FAIL  T4-1: confirm_ownership 返回文本不包含'所有权'")
    print(f"          内容: {ownership_text}")

print()

# ============================================================
# 汇总
# ============================================================
total = passed + failed
print("=" * 60)
print(f"v0.0.03 Gate E 测试汇总: {passed}/{total} 通过, {failed}/{total} 失败")
print("=" * 60)

if failures:
    print("\n失败用例详情:")
    for f in failures:
        print(f"  [{f['id']}] 目标: {f['target']}")
        print(f"          预期: {f['expected']}")
        print(f"          实际: {f['actual']}")
        print(f"          信息: {f['message']}")
    print("\n结论: FAIL")
    sys.exit(1)
else:
    print("\n结论: PASS")
    sys.exit(0)
