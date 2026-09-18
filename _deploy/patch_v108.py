#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
creem-hook：v1.0.7 → v1.0.8 就地补丁
====================================

修一个「交付邮件里装着一个从未生效的密码」的真 bug。

【主修复】重试路径发假密码
    _finish()（交付邮件重试分支）里原本写着：

        if password is None:
            password = self.make_password()
            try:
                self.api.update_user(int(row["user_id"]), password=password)
            except Exception as exc:
                self.log.error("重试时重置密码失败", error=str(exc))
        return self._send_delivery_mail(..., password)

    但 update_user() 的签名里**根本没有 password 参数** →
    这一行在 **Python 层直接抛 TypeError**（不是接口报错）→ 被 except 吞掉、
    只留一行日志 → **密码从未被设置**；而 return 在 try/except **之外** →
    **邮件照发**，客户拿着一个永远登不进去的密码，而且**没有任何告警**。
    命中场景正是「客户付了钱但没拿到 Key」的兜底路径 ——
    越需要它兜底的时候，它越会发一个假密码。

【修法（3 处）】
    1. update_user() 增加 password 参数并写进 payload。
       依据 New API controller/user.go 的 UpdateUser：
           updatePassword := updatedUser.Password != ""
           updatedUser.EditWithTx(tx, updatePassword)
       → password 是被**单独识别**的（quota/email/status 才是传了不生效）。
    2. 重置密码失败 → **不发信**，改发管理员告警，返回 "provisioned"。
       返回 "provisioned" 而不是 "failed"：账号本身是好的（额度、Key 都在），
       留在这个状态下次投递还能重试；而 "failed" 会被 v1.0.7 那条
       「已加过额度但交付未完成」的护栏永久拦住。
    3. 重置后再用新密码**真登一次**（api.login），登不上同样不发信。
       这个 bug 的本质就是「以为设好了」，所以不能只信接口返回 200 ——
       建号路径本来就会 login 一次，这里保持一致。

用法（在服务器上）：
    cd /root/creem-hook && python3 patch_v108.py

安全性：
    · 每个锚点都要求「恰好命中 1 次」，任何一个对不上就整份放弃、绝不改原文件
    · 原文件先备份为 creem_hook.py.v107.bak
    · 打完先做语法检查（py_compile），通过才覆盖
    · 重复执行安全（已是 1.0.8 直接跳过）

回归测试：python3 test_password_retry_v108.py
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

if 'VERSION = "1.0.8"' in src:
    print("[跳过] 这个文件已经是 v1.0.8，无需重复打补丁")
    raise SystemExit(0)

if 'VERSION = "1.0.7"' not in src:
    print("[失败] 目标文件不是 v1.0.7，不敢乱改。请先确认版本：%s" % TARGET)
    raise SystemExit(1)


def sub_once(old, new, label):
    """精确替换：锚点必须恰好命中一次。"""
    global src
    n = src.count(old)
    if n != 1:
        print("[失败] 锚点「%s」命中 %d 次（应为 1 次），未改动任何内容" % (label, n))
        raise SystemExit(1)
    src = src.replace(old, new)


def replace_block(anchor, new_code, label, end_anchor=None):
    """把 anchor 所在整行 → end_anchor 所在整行的内容替换成 new_code。

    两个锚点都必须在整份文件里唯一。这样就不必逐字比对中间那些
    容易出错的缩进（docstring 里的缩进本来就不规整）。
    """
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

sub_once('VERSION = "1.0.7"', 'VERSION = "1.0.8"', "版本号")


# ---------------------------------------------------------------------------
# 2) update_user 增加 password 参数（主修复第 1 处）
# ---------------------------------------------------------------------------

sub_once(
    "    def update_user(self, user_id, *, display_name=None, username=None, group=None):",
    "    def update_user(self, user_id, *, display_name=None, username=None, group=None,\n"
    "                    password=None):",
    "update_user 签名增加 password",
)


# ---------------------------------------------------------------------------
# 3) payload 写入 password
# ---------------------------------------------------------------------------

sub_once(
    '''        if group is not None:
            payload["group"] = group
        self.call("PUT", "/api/user/", payload, token=self.root)''',
    '''        if group is not None:
            payload["group"] = group
        # v1.0.8：password 必须支持。
        # 依据 controller/user.go 的 UpdateUser：
        #     updatePassword := updatedUser.Password != ""
        #     updatedUser.EditWithTx(tx, updatePassword)
        # → password 是被单独识别并透传给 EditWithTx 的。
        # 少了这个参数，调用方会在 **Python 层**直接 TypeError（v1.0.7 的真 bug）：
        # 交付邮件的重试路径自造了一个新密码、却从来没设置成功，然后把假密码发给客户。
        if password is not None:
            payload["password"] = password
        self.call("PUT", "/api/user/", payload, token=self.root)''',
    "payload 写入 password",
)


# ---------------------------------------------------------------------------
# 4) 更正 docstring 里「只写四个字段」的说法
# ---------------------------------------------------------------------------

replace_block(
    "依据 model/user.go 的 EditWithTx，这个接口**只**写四个字段：",
    '''        ⚠️ 依据 model/user.go 的 EditWithTx，这个接口能写这几个字段：
              username、display_name、group、remark，以及 password（v1.0.8 起）
           email、status、quota 传了也不会生效。
           额度必须走 add_quota()，邮箱用这个接口是改不了的。
''',
    "update_user docstring 字段说明",
    end_anchor="额度必须走 add_quota()，邮箱用这个接口是改不了的。",
)


# ---------------------------------------------------------------------------
# 5) 重试路径：重置失败就不发信（主修复第 2、3 处）
# ---------------------------------------------------------------------------

replace_block(
    "# 重试路径拿不到明文密码（不落库），改为重置密码再发",
    '''            # 重试路径拿不到明文密码（不落库），改为重置密码再发。
            #
            # v1.0.8 修一个真 bug：这里过去会发一封「假密码」邮件。
            #   update_user() 当时没有 password 参数 → 上面那行调用在 Python 层
            #   直接抛 TypeError，被下面的 except 吞掉只留一行日志 → 密码从未设置
            #   成功；而 return 在 try/except 之外 → 交付邮件照发，客户拿到的密码
            #   永远是错的，且没有任何告警。
            # 现在：重置 → 用新密码真登一次，任一失败都**不发信**，只告警人工跟进。
            password = self.make_password()
            try:
                self.api.update_user(int(row["user_id"]), password=password)
                # 接口回 200 不等于密码能用 —— 这个 bug 的本质就是「以为设好了」，
                # 所以照建号路径的做法，真登一次，登得上才算数。
                self.api.login(row["username"], password)
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
    "重试路径：失败不发信",
    end_anchor="return self._send_delivery_mail(event_key, email, tier, quota, row[\"username\"], row[\"token_key\"], password)",
)


# ---------------------------------------------------------------------------
# 写入（备份 + 语法检查 + 覆盖）
# ---------------------------------------------------------------------------

backup = TARGET + ".v107.bak"
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
print("        版本：1.0.7 → 1.0.8")
print("")
print("下一步（确认上面输出无误后再执行）：")
print("    python3 test_password_retry_v108.py          # 本地回归测试（不碰线上数据）")
print("    systemctl restart creem-hook")
print("    journalctl -u creem-hook -n 5 --no-pager     # 看到 version=\"1.0.8\" 即成功")
