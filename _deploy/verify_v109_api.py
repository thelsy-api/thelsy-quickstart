#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生产端真机验证：v1.0.9 依赖的那条「改密码」路，在真实网关上到底通不通
====================================================================
为什么必须在生产上跑：代码怎么改都只是"我以为"。SOP 第四节说
`PUT /api/user/` 带 password 可以改密码（依据 controller/user.go 源码），
但**从来没有在真实网关上验证过**。这个脚本就是来验它的。

测什么：
  1 建号时的原密码能登录            （先确认基线成立）
  2 带资料 + 新密码调用后，新密码能登录   ← 修复真的生效的证据
  3 旧密码已失效
  4 分组没被写空                    ← v1.0.9 补的那个坑
  5 账号名没被写空
  6 显示名没被写空

安全性：
  · 只读本机 config.env 取网关地址与 root token，**绝不打印任何密钥**
  · 用一次性测试账号，跑完在 finally 里删除（删不掉会明确提示手动删）

跑法：
    cd /root/creem-hook && python3 verify_v109_api.py
"""

import os
import secrets
import string
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)
import creem_hook as H          # noqa: E402

CFG_PATH = "config.env"
TEST_NAME = "zzverify109"

results = []


def check(name, got, want):
    ok = got == want
    results.append(ok)
    print("   %s %s   实际=%r 期望=%r" % ("[通过]" if ok else "[失败]", name, got, want))


def pw(n=18):
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(n))


def main():
    print("被测版本：", H.VERSION)
    cfg = H.Config(CFG_PATH)
    log = H.Log(cfg["LOG_PATH"])
    api = H.NewAPI(cfg["NEWAPI_BASE"], cfg["NEWAPI_ROOT_TOKEN"],
                   int(cfg["NEWAPI_TIMEOUT"]), log)
    group = cfg["NEW_USER_GROUP"]
    print("网关地址：%s（root token 不打印）" % cfg["NEWAPI_BASE"])
    print("")

    # 清掉可能残留的同名账号
    old = api.find_user_by_username(TEST_NAME)
    if old:
        print("发现同名残留账号 id=%s，先删除" % old["id"])
        api.call("DELETE", "/api/user/%s" % old["id"], token=api.root)

    uid = None
    try:
        pw_a, pw_b = pw(), pw()
        u = api.create_user(TEST_NAME, pw_a, TEST_NAME)
        uid = int(u["id"])
        print("已建测试账号 %s（id=%s）" % (TEST_NAME, uid))

        # 把它整成「正常客户」的样子（分组设好）
        api.update_user(uid, display_name=TEST_NAME, username=TEST_NAME, group=group)

        try:
            api.login(TEST_NAME, pw_a)
            ok_a = True
        except Exception as exc:
            ok_a = False
            print("     原密码登录报错：%s" % exc)
        check("1 建号时的原密码能登录", ok_a, True)

        # 关键一步：完全照 v1.0.9 重试路径的调用形状来 —— 带资料 + 新密码
        info = api.get_user(uid) or {}
        api.update_user(uid,
                        display_name=info.get("display_name") or TEST_NAME,
                        username=info.get("username") or TEST_NAME,
                        group=info.get("group") or group,
                        password=pw_b)

        try:
            api.login(TEST_NAME, pw_b)
            ok_b = True
        except Exception as exc:
            ok_b = False
            print("     新密码登录报错：%s" % exc)
        try:
            api.login(TEST_NAME, pw_a)
            old_ok = True
        except Exception:
            old_ok = False

        check("2 新密码能登录（修复真的生效）", ok_b, True)
        check("3 旧密码已失效", old_ok, False)

        after = api.get_user(uid) or {}
        check("4 分组没被写空", after.get("group"), group)
        check("5 账号名没被写空", after.get("username"), TEST_NAME)
        check("6 显示名没被写空", after.get("display_name"), TEST_NAME)
    finally:
        if uid:
            try:
                api.call("DELETE", "/api/user/%s" % uid, token=api.root)
                gone = api.find_user_by_username(TEST_NAME)
                print("")
                print("收尾：测试账号已删除" if not gone
                      else "收尾：删除后仍能查到 —— 请到后台「用户」页手动删除 %s" % TEST_NAME)
            except Exception as exc:
                print("")
                print("收尾：删除失败（%s）—— 请到后台「用户」页手动删除 %s" % (exc, TEST_NAME))

    print("")
    ok = all(results)
    print("PASS（%d/%d）" % (sum(results), len(results)) if ok
          else "FAIL（%d/%d）" % (sum(results), len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
