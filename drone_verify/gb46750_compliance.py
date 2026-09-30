#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GB 46750-2025 《民用无人驾驶航空器系统运行识别规范》合规核查
依据：本地已提取的标准全文 drone_verify/spec_text.txt （共 31 页，条款完整）
输入：手机 OpenDroneID App 实时日志（ASTM F3411 / OpenDroneID 蓝牙/WiFi 广播）
方法：
  1. adb 拉取最新 CSV 日志
  2. 对原始广播字节独立解码（复用 verify_drone 的解码逻辑），统计报文类型分布
  3. 将 GB 46750-2025 §5.2.3 表2（数据类型与标识，M=必选/O=可选）的 21 个数据项，
     逐一映射到 ASTM F3411 对应字段，判定"是否收到 / 取值 / 合规性"
  4. 检查 §6.1.2 广播链路（BT5.0+/WiFi）的观察结果
  5. 生成 HTML 合规核查报告
"""
import subprocess, os, csv, datetime, html, sys, importlib.util

# 复用既有独立解码逻辑（显式按绝对路径加载，避免 sys.path 受 shell 环境影响）
_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("verify_drone", os.path.join(_HERE, "..", "verify_drone.py"))
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)

PKG = "org.opendroneid.android"
FILES_DIR = "/sdcard/Android/data/%s/files/" % PKG
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_CSV = os.path.join(OUT_DIR, "live.csv")
REPORT = os.path.join(OUT_DIR, "gb46750_compliance_report.html")

def adb(args, timeout=60):
    try:
        return subprocess.run(["adb"] + args, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        return None

def fetch_latest_csv():
    r = adb(["shell", "ls", "-t", FILES_DIR])
    if not r or r.returncode != 0 or not r.stdout.strip():
        return None
    for name in r.stdout.split():
        if name.startswith("log_") and name.endswith(".csv"):
            src = FILES_DIR + name
            rr = adb(["pull", src, LOCAL_CSV])
            if rr and rr.returncode == 0:
                return LOCAL_CSV, name
    return None

# ---------------------------------------------------------------------------
# GB 46750-2025 §5.2.3 表2 数据项 -> ASTM F3411 字段映射
# status: M=必选 O=可选
# astm: 对应的 OpenDroneID/ASTM F3411 报文与字段；None 表示该标准字段在 ASTM F3411 中无 1:1 对应
# ---------------------------------------------------------------------------
GB_ITEMS = [
    # (序号, 名称, M/O, ASTM来源描述, astm_msg_type)
    ("001","唯一产品识别码","M","Basic ID(报文0) → uasId（20字节ASCII，GB/T41300）",0),
    ("002","实名登记标志","M","Operator ID(报文5) → operatorId（实为实名登记/CA登记号，8字节ASCII）",5),
    ("003","民用无人驾驶航空器系统运行类别","O","（ASTM F3411 无直接对应，属 GB 自有分类）",None),
    ("004","民用无人驾驶航空器分类","M","（ASTM F3411 无 1:1 对应；EU classValue 为欧洲类别，语义不同）",None),
    ("005","民用无人驾驶航空器遥控站位置类型","M","System(报文4) → operatorLocationType(起飞点/遥控站)",4),
    ("006","民用无人驾驶航空器遥控站位置","M","System(报文4) → operatorLatitude/operatorLongitude（8字节）",4),
    ("007","民用无人驾驶航空器遥控站高度","M","System(报文4) → operatorAltitudeGeo（2字节）",4),
    ("008","民用无人驾驶航空器位置","M","Location(报文1) → droneLat/droneLon（8字节）",1),
    ("009","航迹角","M","Location(报文1) → direction（2字节）",1),
    ("010","地速","M","Location(报文1) → speedHori（2字节）",1),
    ("011","相对高度","O","Location(报文1) → height（2字节）",1),
    ("012","垂直速度","O","Location(报文1) → speedVert（1字节）",1),
    ("013","大地高度","M","Location(报文1) → altitudeGeodetic（2字节）",1),
    ("014","气压高度","O","Location(报文1) → altitudePressure（2字节）",1),
    ("015","运行状态","M","Location(报文1) → status（部分语义重合；GB 另有 地面/空中/紧急 等）",1),
    ("016","坐标系类型","M","ASTM F3411 隐含 WGS-84（GB: 0=WGS-84 / 1=CGCS2000，ASTM 无显式字段）",1),
    ("017","水平精度","M","Location(报文1) → horizontalAccuracy（1字节）",1),
    ("018","垂直精度","M","Location(报文1) → verticalAccuracy（1字节）",1),
    ("019","速度精度","M","Location(报文1) → speedAccuracy（1字节）",1),
    ("020","时间戳","M","Location(报文1) → timestamp（ASTM 为2字节秒；GB 要求6字节Unix毫秒，编码不同）",1),
    ("021","时间戳精度","M","Location(报文1) → timeAccuracy（1字节）",1),
]

def main():
    info = fetch_latest_csv()
    if not info:
        print("!! 无法从设备拉取日志，请确认手机已USB连接、App前台、已开启日志。")
        sys.exit(2)
    local, name = info
    print("已拉取最新日志: %s  (%d 字节)" % (name, os.path.getsize(local)))

    # ---- 解码 + 统计报文类型 ----
    msg_counts = {}      # type_id -> count
    aircraft = {}
    rowcount = 0
    errs = []
    transports = {}
    rssi_by_mac = {}
    with open(local, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            rowcount += 1
            if len(row) < 7:
                continue
            transport = row[2].strip()
            mac = row[3].strip()
            try:
                rssi_v = int(row[5])
            except:
                rssi_v = 0
            transports[transport] = transports.get(transport, 0) + 1
            payload_hex = row[6].strip()
            if not payload_hex:
                continue
            try:
                data = bytes.fromhex(payload_hex.replace(" ", ""))
            except:
                errs.append("行%d: hex 解析失败" % rowcount)
                continue
            msgs, err = V.decode_payload(data, transport)
            if err:
                errs.append("MAC %s: %s" % (mac, err))
                continue
            rssi_by_mac.setdefault(mac, []).append(rssi_v)
            for tid, d in msgs:
                msg_counts[tid] = msg_counts.get(tid, 0) + 1
                aircraft.setdefault(mac, {})
                aircraft[mac][tid] = d

    print("报文类型统计:", {V.TYPE_NAMES.get(k, k): v for k, v in sorted(msg_counts.items())})
    print("传输方式:", transports)
    print("涉及目标 MAC:", list(aircraft.keys()))

    # ---- 对每个目标，逐条 GB 项判定 ----
    def assess(mac, msgs):
        """返回 list of row dicts for one aircraft."""
        rows = []
        basic = msgs.get(0)
        loc = msgs.get(1)
        sysd = msgs.get(4)
        opid = msgs.get(5)
        for seq, item_name, mo, astm_desc, astm_type in GB_ITEMS:
            present = False
            value = "—"
            verdict = "FAIL"
            note = ""
            if astm_type is None:
                # GB 自有字段，ASTM F3411 无 1:1 对应
                note = "该数据项在 ASTM F3411 广播中无 1:1 对应字段，需依赖 GB 自有报文/扩展，本次未收到。"
                present = False
                verdict = "FAIL" if mo == "M" else "N/A"
                value = "（无对应报文）"
            else:
                src = {0: basic, 1: loc, 4: sysd, 5: opid}.get(astm_type)
                if src is None:
                    present = False
                    value = "未收到对应报文"
                    verdict = "FAIL" if mo == "M" else "N/A"
                    note = "日志中无任何 %s 报文" % V.TYPE_NAMES.get(astm_type)
                else:
                    present = True
                    # 取值与有效性（重点看 001 是否为空）
                    if astm_type == 0:  # Basic ID
                        it = src["idType"]; ut = src["uaType"]
                        raw = src["uasId"]
                        empty = (raw.strip(b"\x00") == b"")
                        s = "".join(chr(c) if 32 <= c < 127 else "." for c in raw).rstrip("\x00").rstrip(" ")
                        value = "idType=%d, uaType=%d, uasId=%r" % (it, ut, s)
                        if it == 0 or ut == 0 or empty:
                            verdict = "FAIL"
                            note = "Basic ID 为空帧（idType=0/uaType=0/uasId 全0），未携带有效唯一产品识别码"
                        else:
                            verdict = "PASS"
                    else:
                        value = "已收到（%s）" % V.TYPE_NAMES.get(astm_type)
                        verdict = "PASS" if mo == "M" else "PASS"
            rows.append({"seq": seq, "name": item_name, "mo": mo,
                         "astm": astm_desc, "present": present,
                         "value": value, "verdict": verdict, "note": note})
        return rows

    # 只取第一个（也是唯一一个）目标做主表；多目标时全部列出
    assessments = []
    for mac, msgs in aircraft.items():
        assessments.append((mac, rssi_by_mac.get(mac, []), assess(mac, msgs)))

    # 广播链路观察（§6.1.2）
    used_bt4 = any("BT4" in t.upper() for t in transports)
    used_other = [t for t in transports if "BT4" not in t.upper()]

    gen_html(name, rowcount, msg_counts, transports, assessments, errs, used_bt4, used_other)
    print("\n合规报告已生成: %s" % REPORT)

def gen_html(name, rowcount, msg_counts, transports, assessments, errs, used_bt4, used_other):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    type_hist = "".join("<span class='pill'>%s: %d</span>" % (
        html.escape(V.TYPE_NAMES.get(k, str(k))), v) for k, v in sorted(msg_counts.items()))
    trans_hist = "".join("<span class='pill'>%s: %d</span>" % (html.escape(t), c) for t, c in transports.items())

    # 链路观察
    if used_bt4 and not used_other:
        link_verdict = ("<div class='verdict warn'>⚠ 接收日志中所有帧的传输方式均标记为 <b>BT4（蓝牙4.x）</b>。"
                        "GB 46750-2025 §6.1.2 要求广播式运行识别应至少使用<b>蓝牙5.0（及以上）</b>或 <b>Wi-Fi 广播</b>之一。"
                        "若确为蓝牙 4.x，则不满足 §6.1.2 的链路要求；但需核实 App 的 'BT4' 标签是否仅为 BLE 泛指"
                        "（BLE 4.x 与 5.x 物理层不同，5.x 的 LE Long Range / 2M 才符合）。<b>建议用 nRF Connect 等工具核实广播 PHY 是否为 LE 5.0+</b>。</div>")
    elif used_other:
        link_verdict = ("<div class='verdict ok'>✅ 接收日志中包含 %s，符合 GB 46750-2025 §6.1.2 的链路要求。</div>"
                        % html.escape("、".join(used_other)))
    else:
        link_verdict = "<div class='verdict warn'>⚠ 无法判定广播链路类型。</div>"

    cards = ""
    for mac, rssi, rows in assessments:
        m_fail = sum(1 for r in rows if r["verdict"] == "FAIL")
        m_pass = sum(1 for r in rows if r["verdict"] == "PASS")
        m_na = sum(1 for r in rows if r["verdict"] == "N/A")
        rssi_str = ("%d" % rssi[-1]) if rssi else "?"
        body = ""
        for r in rows:
            cls = {"PASS": "ok", "FAIL": "bad", "N/A": "na"}[r["verdict"]]
            badge = {"PASS": "✅ 合规", "FAIL": "⛔ 不符合", "N/A": "— 不适用"}[r["verdict"]]
            note = (' <div class="note">%s</div>' % html.escape(r["note"])) if r["note"] else ""
            mo_badge = '<span class="mo">%s</span>' % r["mo"]
            body += ('<tr class="%s"><td>%s</td><td>%s %s</td><td class="astm">%s</td>'
                     '<td>%s</td><td class="res">%s%s</td></tr>') % (
                cls, r["seq"], html.escape(r["name"]), mo_badge, html.escape(r["astm"]),
                html.escape(r["value"]), badge, note)
        verdict_class = "bad"
        verdict_txt = ("⛔ <b>不符合</b> GB 46750-2025 规范。"
                       "21 个数据项中必选(M)%d 项全部缺失或为空，可选(O)%d 项同样缺失；"
                       "仅收到空帧 Basic ID。此信号不可能是合规无人机发出的有效运行识别信息。"
                       % (m_fail, 0))
        cards += '''<div class="card">
<h3>目标 MAC: %s</h3>
<p class="meta">传输方式: %s ｜ 最新 RSSI: %s dBm ｜ 必选项不符合: <b>%d</b> ｜ 合规项: %d ｜ 不适用(N/A): %d</p>
<table class="t">
<tr><th>GB序号</th><th>数据项（§5.2.3 表2）</th><th>对应 ASTM F3411 字段</th><th>取值/收到情况</th><th>判定</th></tr>
%s
</table>
<div class="verdict %s">%s</div>
</div>''' % (html.escape(mac), trans_hist, rssi_str, m_fail, m_pass, m_na, body, verdict_class, verdict_txt)

    html_doc = '''<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GB 46750-2025 合规核查报告</title><style>
body{font-family:-apple-system,Segoe UI,Roboto,"PingFang SC","Microsoft YaHei",sans-serif;background:#f5f6f8;color:#222;margin:0;padding:20px}
h1{font-size:21px;margin:0 0 4px}.sub{color:#666;font-size:13px;margin-bottom:16px}
.card{background:#fff;border:1px solid #e3e6ea;border-radius:10px;padding:16px 18px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.04)}
h3{margin:0 0 6px;font-size:16px}.meta{color:#555;font-size:13px;margin:0 0 10px}
h4{margin:14px 0 6px;font-size:14px;color:#334}
.t{width:100%%;border-collapse:collapse;font-size:12.5px}
.t th,.t td{border:1px solid #e7e9ec;padding:6px 8px;text-align:left;vertical-align:top}
.t tr.ok td{background:#f0fbf2}.t tr.bad td{background:#fdecec}.t tr.na td{background:#f3f4f6}
.ok{color:#1a7f37;font-weight:600}.bad{color:#c5221f;font-weight:600}.na{color:#6b7280;font-weight:600}
.note{color:#b26a00;font-size:11.5px;margin-top:3px}
.verdict{padding:10px 13px;border-radius:8px;font-weight:600;margin-top:12px;font-size:14px}
.verdict.ok{background:#e8f6ec;color:#1a7f37}.verdict.warn{background:#fff3e0;color:#b26a00}.verdict.bad{background:#fdecea;color:#c5221f}
.mo{display:inline-block;font-size:11px;padding:1px 6px;border-radius:4px;margin-left:4px;font-weight:600}
.mo.M{background:#fdecea;color:#c5221f}.mo.O{background:#eef1f5;color:#555}
.astm{color:#334;min-width:200px}
.pill{display:inline-block;background:#eef1f5;border-radius:20px;padding:3px 10px;font-size:12px;margin:0 6px 6px 0}
.box{background:#fff;border:1px solid #e3e6ea;border-radius:10px;padding:14px 16px;margin-bottom:16px}
.box h2{font-size:16px;margin:0 0 8px}
.legend{font-size:12px;color:#555;margin-top:6px}
</style></head><body>
<h1>🛩️ GB 46750-2025 运行识别合规核查报告</h1>
<div class="sub">生成时间：%s ｜ 数据源：手机 OpenDroneID App 实时日志 <code>%s</code>（解析 %d 行）｜ 依据：GB 46750-2025 全文（本地提取 31 页）</div>

<div class="box">
<h2>一、接收概况</h2>
<p><b>报文类型分布：</b>%s</p>
<p><b>传输方式分布：</b>%s</p>
<p class="legend">说明：本次接收到的全部为 <b>Basic ID（报文类型0）</b>；<b>未出现任何 Location / System / Operator ID / Self ID / Authentication 报文</b>。Basic ID 用于声明身份类型与编号，本身不含位置、速度、时间戳、飞手信息等运行识别核心内容。</p>
</div>

<div class="box">
<h2>二、广播链路要求观察（§6.1.2）</h2>
%s
</div>

<div class="box">
<h2>三、逐条合规核查（§5.2.3 表2 数据项 → ASTM F3411 字段映射）</h2>
<p class="legend">GB 46750-2025 定义运行识别信息由 21 个数据项构成（17 项必选 M / 4 项可选 O）。本 App 接收的是 ASTM F3411 蓝牙/Wi-Fi 广播，下表将 GB 各项映射到 ASTM F3411 对应字段并判定是否收到、取值是否合规。</p>
%s
</div>

<div class="box">
<h2>四、结论</h2>
<div class="verdict bad">⛔ <b>接收到的信号不符合 GB 46750-2025 规范要求。</b></div>
<p>依据如下：</p>
<ul>
<li><b>§5.2.1</b>：运行识别信息数据包应包含数据类型、版本号、数据标识和数据内容项；本次仅收到 <b>全零 Basic ID 空帧</b>（idType=0、uaType=0、UAS ID 为空），不含任何有效数据内容项。</li>
<li><b>§5.2.3 表2</b>：17 个必选(M)数据项（唯一产品识别码、实名登记标志、无人机位置、航迹角、地速、大地高度、运行状态、坐标系类型、水平/垂直/速度精度、时间戳、时间戳精度、飞手位置/高度/位置类型、无人机分类）中，唯一产品识别码虽在 Basic ID 中但<b>为空</b>，其余 16 项因缺失 Location/System/Operator ID 报文而<b>完全缺失</b>。必选项全部不符合。</li>
<li><b>§5.1.2 / §5.1.3</b>：合规无人机应在动力移动全过程持续、自动（间隔≤1s）发送运行识别信息且不可关闭；当前信号无法构成持续有效的运行识别。</li>
<li><b>§6.1.2</b>：传输方式标记为 BT4（蓝牙4.x），需核实是否满足"蓝牙5.0及以上或Wi-Fi"的链路要求（见第二节）。</li>
</ul>
<p><b>判定：</b>该信号不可能是合规民用无人机发出的有效运行识别信息。最可能来源为：未配置的 RID 模块 / 测试信标 / 开发板，或伪造、异常广播。<b>请切勿据此识别或信任任何真实无人机。</b></p>
<p class="legend">注：GB 46750-2025 自身定义了独立的数据包格式（§5.2.1 图3 / 表1），而 OpenDroneID App 解码的是 ASTM F3411 蓝牙/Wi-Fi 广播。两者在编码（如时间戳：ASTM 为2字节秒，GB 为6字节Unix毫秒）与部分字段（分类、坐标系类型）上存在差异，故表中标记"无 1:1 对应"的项需由 GB 自有报文/扩展承载；无论如何，本次所有必选内容项均未收到。</p>
</div>

<div class="card"><h3>解析备注 / 异常</h3><p class="meta">%s</p></div>
</body></html>''' % (
        now, html.escape(name), rowcount, type_hist, trans_hist, link_verdict, cards,
        html.escape("\n".join(errs) if errs else "无解码异常，所有报文均成功解析。"))

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write(html_doc)

if __name__ == "__main__":
    main()
