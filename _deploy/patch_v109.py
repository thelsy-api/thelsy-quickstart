#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
creem-hook：v1.0.8 → v1.0.9 就地补丁
====================================

补 v1.0.8 自己留下的一个坑：改密码时会顺手把客户资料清空。

【问题】
    v1.0.8 把重试路径修好了（密码真的会被设置），但它是这么调的：

        self.api.update_user(int(row["user_id"]), password=password)
                                                    ↑ 只带了密码

    而这个接口（New API 的 EditWithTx）是**无条件写入**语义：请求 JSON 里没带的
    字段会被写成**空串**，不是「保持原样」。所以这次调用会把
        username / display_name / group
    一起清空 → 客户下一次调用立刻报 `No available channel for model ...`。
    （《客户重置密码-SOP.md》第六节把「不传 group 就保存」列为「绝对不要做」之一。）

    为什么以前没炸：v1.0.7 那句调用因为签名缺 password 而永远抛 TypeError，
    根本没执行到接口。v1.0.8 把它修通了，坑才真正露出来。

【修法】
    先把该账号的现有资料读出来，**原样带回去**，只额外带上新密码：

        info = self.api.get_user(int(row["user_id"])) or {}
        keep_name    = info.get("username") or row["username"]
        keep_display = info.get("display_name") or keep_name
        keep_group   = info.get("group") or self.cfg["NEW_USER_GROUP"]
        self.api.update_user(..., display_name=keep_display, username=keep_name,
                             group=keep_group, password=password)

    读不到时退回事件行里存的账号名 / 配置里的默认分组，避免因为一次 GET 抖动就写空。
    验证登录也改用 keep_name。

用法（在服务器上）：
    cd /root/creem-hook && python3 patch_v109.py

安全性：
    · 锚点必须恰好命中 1 次，任何一个对不上就整份放弃、绝不改原文件
    · 原文件先备份为 creem_hook.py.v108.bak
    · 打完先做语法检查（py_compile），通过才覆盖
    · 重复执行安全（已是 1.0.9 直接跳过）

回归测试：python3 test_password_retry_v108.py   （里面「严格假 API」那几条就是冲这个坑来的）
"""

import io
import os
import py_compile
import shutil
import sys

TARGET = sys.argv[1] if len(sys.argv) > 1 else "/root/creem-hook/creem_hook.py"

if not os.path.exists(TARGET):
    print("[失败] 找不到文件：%s" % TARGET)
    raise SystemExit(1)

src = io.open(TARGET, encoding="utf-8").read()

if 'VERSION = "1.0.9"' in src:
    print("[跳过] 这个文件已经是 v1.0.9，无需重复打补丁")
    raise SystemExit(0)

if 'VERSION = "1.0.8"' not in src:
    print("[失败] 目标文件不是 v1.0.8，不敢乱改。请先确认版本：%s" % TARGET)
    raise SystemExit(1)


def sub_once(old, new, label):
    global src
    n = src.count(old)
    if n != 1:
        print("[失败] 锚点「%s」命中 %d 次（应为 1 次），未改动任何内容" % (label, n))
        raise SystemExit(1)
    src = src.replace(old, new, 1)


def replace_block(anchor, new_code, label, end_anchor=None):
    """把 anchor 所在整行 → end_anchor 所在整行的内容替换成 new_code。"""
    global src
    if src.count(anchor) != 1:
        print("[失败] 起始锚点不唯一（%d 次）：%s" % (src.count(anchor), label))
        raise SystemExit(1)
    if end_anchor is None:
        end_anchor = anchor
    if src.count(end_anchor) != 1:
        print("[失败] 结束锚点不唯一（%d 次）：%s" % (src.count(end_anchor), label))
        raise SystemExit(1)
    i = src.find(anchor)
    j = src.find(end_anchor, i)
    if j < 0 or (j - i) > 3000:
        print("[失败] 结束锚点定位异常：%s" % label)
        raise SystemExit(1)
    i = src.rfind("\n", 0, i) + 1
    j = src.find("\n", j) + 1
    src = src[:i] + new_code + src[j:]


# ---------------------------------------------------------------------------
# 1) 版本号
# ---------------------------------------------------------------------------

sub_once('VERSION = "1.0.8"', 'VERSION = "1.0.9"', "版本号")


# ---------------------------------------------------------------------------
# 2) 重试路径：改密码时把现有资料一起带回去（本补丁的核心）
# ---------------------------------------------------------------------------

replace_block(
    "# 重试路径拿不到明文密码（不落库），改为重置密码再发。",
    '''            # 重试路径拿不到明文密码（不落库），改为重置密码再发。
            #
            # v1.0.8 修的是「发假密码」：update_user() 当时没有 password 参数 →
            #   Python 层直接 TypeError → 被 except 吞掉 → 密码从未设置成功；而发信
            #   那行在 try/except 之外 → 邮件照发，装着一个永远登不进去的密码。
            #
            # v1.0.9 补一个 v1.0.8 自己留下的坑：**改密码必须把现有资料一起带回去**。
            #   这个接口（EditWithTx）是无条件写入 —— 请求里没带的字段会被写成空串，
            #   不是「保持原样」。所以只传 password 会把 username / display_name /
            #   group 一起清空，客户立刻报 No available channel for model ...
            #   （《客户重置密码-SOP.md》第六节把这条列为「绝对不要做」之一。）
            #   做法：先读出现有资料原样带回去，只额外加新密码；读不到就退回事件行
            #   里存的账号名 / 配置里的默认分组，别因为一次 GET 抖动就把账号写空。
            password = self.make_password()
            try:
                info = self.api.get_user(int(row["user_id"])) or {}
                keep_name = info.get("username") or row["username"]
                keep_display = info.get("display_name") or keep_name
                keep_group = info.get("group") or self.cfg["NEW_USER_GROUP"]
                self.api.update_user(int(row["user_id"]),
                                     display_name=keep_display, username=keep_name,
                                     group=keep_group, password=password)
                # 接口回 200 不等于密码能用 —— 这个 bug 的本质就是「以为设好了」，
                # 所以照建号路径的做法，真登一次，登得上才算数。
                self.api.login(keep_name, password)
            except Exception as exc:
                self.log.error("重试时重置密码失败，已阻止发出无效密码邮件",
                               user_id=row["user_id"], username=row["username"],
                               error=str(exc))
                self.alert_admin(
                    "[Thelsy] 重置密码失败，已阻止发出一封假密码邮件",
                    "事件：%s；客户邮箱：%s；账号：%s（id=%s）；档位：%s。"
                    "情况：这条重试路径本要给客户补发交付邮件，但「重置密码」或"
                    "「用新密码验证登录」没成功，所以邮件没有发出去 —— 这是故意的："
                    "发一封密码是错的邮件，比不发更糟。"
                    "请人工跟进：到网关后台「用户」页确认该账号，按《客户重置密码-SOP.md》"
                    "手动重置密码后通知客户。报错：%s"
                    % (event_key, email, row["username"], row["user_id"], tier, exc),
                )
                return "provisioned"
        return self._send_delivery_mail(event_key, email, tier, quota, row["username"], row["token_key"], password)
''',
    "重试路径：带上现有资料再改密码",
    end_anchor="return self._send_delivery_mail(event_key, email, tier, quota, row[\"username\"], row[\"token_key\"], password)",
)


# ---------------------------------------------------------------------------
# 写入（备份 + 语法检查 + 覆盖）
# ---------------------------------------------------------------------------

backup = TARGET + ".v108.bak"
if not os.path.exists(backup):
    shutil.copy2(TARGET, backup)

tmp = TARGET + ".new"
io.open(tmp, "w", encoding="utf-8", newline="\n").write(src)
try:
    py_compile.compile(tmp, cfile=tmp + "c", doraise=True)
except py_compile.PyCompileError as exc:
    os.remove(tmp)
    print("[失败] 补丁后的文件语法检查不通过，原文件未改动：\n%s" % exc)
    raise SystemExit(1)
if os.path.exists(tmp + "c"):
    os.remove(tmp + "c")
os.replace(tmp, TARGET)

print("[完成] 已写入：%s" % TARGET)
print("        备份：%s" % backup)
print("        版本：1.0.8 → 1.0.9")
print("")
print("下一步（确认上面输出无误后再执行）：")
print("    python3 test_password_retry_v108.py          # 回归测试（不碰线上数据）")
print("    systemctl restart creem-hook")
print("    journalctl -u creem-hook -n 5 --no-pager     # 看到 version 1.0.9 即成功")
