#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenDroneID 接收数据独立校验工具
流程：adb 拉取手机上 App 实时写出的 CSV 日志 -> 取出每行原始广播字节(payload) ->
按照 ASTM F3411 / OpenDroneID 规范独立重新解码 -> 逐字段范围/枚举/合理性校验 ->
生成 HTML 报告 + 控制台摘要。

校验完全基于"原始字节"，不依赖 App 自身的解码结果，属于独立复核。
"""
import subprocess, os, re, csv, struct, datetime, html, json, sys

PKG = "org.opendroneid.android"
FILES_DIR = "/sdcard/Android/data/%s/files/" % PKG
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "drone_verify")
os.makedirs(OUT_DIR, exist_ok=True)
LOCAL_CSV = os.path.join(OUT_DIR, "live.csv")

# ---------------- adb helpers ----------------
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

# ---------------- OpenDroneID decode (independent) ----------------
LAT_MULT = 1e-7
SPD_VERT_MULT = 0.5

TYPE_NAMES = {0:"Basic ID",1:"Location",2:"Authentication",3:"Self ID",4:"System",5:"Operator ID",0xF:"Message Pack"}

ID_TYPE = {0:"None",1:"Serial Number",2:"CAA Registration ID",3:"UTM Assigned ID",4:"Session ID"}
UA_TYPE = {0:"None",1:"Aeroplane",2:"Helicopter",3:"Gyroplane",4:"Hybrid Lift",5:"Ornithopter",
           6:"Glider",7:"Kite",8:"Free Balloon",9:"Captive Balloon",10:"Airship",11:"Parachute",
           12:"Rocket",13:"Tethered Powered Aircraft",14:"Ground Obstacle",15:"Other"}
LOC_STATUS = {0:"No position data",1:"GPS",2:"GPS+Baro",3:"Network",4:"Network+Baro"}
OP_LOC_TYPE = {0:"Takeoff",1:"Live GNSS",2:"Fixed"}
CLASS_TYPE = {0:"Undeclared",1:"EU (Open)",2:"EU (Specific)",3:"EU (Certified)",4:"EU (Reserved)"}
CAT_EU = {0:"Undefined",1:"Entertainment",2:"Commercial",3:"Government",4:"Emergency"}
OP_ID_TYPE = {0:"None",1:"Serial Number",2:"CAA Registration ID",3:"UTM Assigned ID",4:"Session ID"}
AUTH_TYPE = {0:"None",1:"UAS ID",2:"Operator ID",3:"Custom"}

ACC_SCALE = {0:"Unknown",1:"10",2:"3",3:"1",4:"0.3",5:"0.1"}  # meters or m/s

def calc_speed(value, mult):
    return value*0.25 if mult==0 else (value*0.75 + 255*0.25)
def calc_dir(value, ew):
    return value if ew==0 else value+180
def calc_alt(raw):
    return raw/2.0 - 1000.0

def decode_message(b, off):
    """Decode one 25-byte OpenDroneID message at off. Returns (type_id, dict) or None."""
    if off + 25 > len(b):
        return None
    hdr = b[off]
    tid = (hdr & 0xF0) >> 4
    ver = hdr & 0x0F
    p = b[off+1:off+25]
    if tid == 0:  # Basic ID
        t = p[0]
        uas = bytes(p[1:21])
        return tid, {"idType":(t&0xF0)>>4, "uaType":t&0x0F, "uasId":uas}
    if tid == 1:  # Location
        st = p[0]
        status=(st&0xF0)>>4; htype=(st&0x04)>>2; ew=(st&0x02)>>1; smult=st&0x01
        direction=p[1]&0xFF; speedHori=p[2]&0xFF; speedVert=p[3]
        lat, lon = struct.unpack_from("<ii", p, 4)
        altP, altG, hgt = struct.unpack_from("<HHH", p, 12)
        hv = p[18]; horizAcc=hv&0x0F; vertAcc=(hv&0xF0)>>4
        sb = p[19]; baroAcc=(sb&0xF0)>>4; spdAcc=sb&0x0F
        ts, = struct.unpack_from("<H", p, 20)
        tacc = p[22]&0x0F
        return tid, {"status":status,"heightType":htype,"EWDirection":ew,"speedMult":smult,
                     "direction":direction,"speedHori":speedHori,"speedVert":speedVert,
                     "droneLat":lat,"droneLon":lon,"altitudePressure":altP,"altitudeGeodetic":altG,
                     "height":hgt,"horizontalAccuracy":horizAcc,"verticalAccuracy":vertAcc,
                     "baroAccuracy":baroAcc,"speedAccuracy":spdAcc,"timestamp":ts,"timeAccuracy":tacc}
    if tid == 2:  # Authentication
        t=p[0]; authType=(t&0xF0)>>4; page=t&0x0F
        d={"authType":authType,"authDataPage":page}
        if page==0:
            d["authLastPageIndex"]=p[1]&0xFF; d["authLength"]=p[2]&0xFF
            d["authTimestamp"]=struct.unpack_from("<I",p,3)[0]
            d["authData"]=bytes(p[7:24])
        else:
            off2 = 7 + (page-1)*23
            d["authData"]=bytes(p[off2:off2+23])
        return tid, d
    if tid == 3:  # Self ID
        return tid, {"descriptionType":p[0]&0xFF, "operationDescription":bytes(p[1:24])}
    if tid == 4:  # System
        st=p[0]; opLoc=st&0x03; cls=(st&0x1C)>>2
        opLat, opLon = struct.unpack_from("<ii", p, 1)
        areaCount, = struct.unpack_from("<H", p, 9)
        areaRadius=p[11]&0xFF
        areaCeil, areaFloor = struct.unpack_from("<HH", p, 12)
        c=p[16]; cat=(c&0xF0)>>4; clsVal=c&0x0F
        opAlt, = struct.unpack_from("<H", p, 17)
        sysTs, = struct.unpack_from("<I", p, 19)
        return tid, {"operatorLocationType":opLoc,"classificationType":cls,"operatorLatitude":opLat,
                     "operatorLongitude":opLon,"areaCount":areaCount,"areaRadius":areaRadius,
                     "areaCeiling":areaCeil,"areaFloor":areaFloor,"category":cat,"classValue":clsVal,
                     "operatorAltitudeGeo":opAlt,"systemTimestamp":sysTs}
    if tid == 5:  # Operator ID
        return tid, {"operatorIdType":p[0]&0xFF, "operatorId":bytes(p[1:21])}
    if tid == 0xF:  # Message Pack
        msz=p[1]&0xFF; cnt=p[2]&0xFF
        msgs=[]
        if msz==25 and 0<cnt<=9 and off+3+msz*cnt<=len(b):
            for k in range(cnt):
                sub=decode_message(b, off+3+k*msz)
                if sub: msgs.append(sub)
        return tid, {"messageSize":msz,"messagesInPack":cnt,"sub":msgs}
    return None

def decode_payload(data, transport):
    out=[]
    if "bt" in transport.lower() or "bluetooth" in transport.lower():
        i=-1
        for j in range(len(data)-2):
            if data[j]&0xFF==0xFA and data[j+1]&0xFF==0xFF and data[j+2]&0xFF==0x0D:
                i=j; break
        if i<0:
            return out, "BT: 未找到 RID 服务标记 FA FF 0D"
        off=i+4
    else:
        off=1
    m=decode_message(data, off)
    if not m:
        return out, "payload 长度不足或首报文无法解析"
    out.append(m)
    if m[0]==0xF:
        for sub in m[1]["sub"]:
            out.append(sub)
    return out, None

# ---------------- validation ----------------
def v_field(name, val, ok, note=""):
    return {"field":name,"value":val,"ok":ok,"note":note}

def validate_basicid(d):
    res=[]
    it=d["idType"]
    res.append(v_field("idType(识别类型)", "%d=%s"%(it,ID_TYPE.get(it,"Reserved")), it in (1,2,3,4), "0=None 表示未填写有效识别类型，真实无人机必须为 1-4" if it==0 else ("" if it in ID_TYPE else "保留/未定义值")))
    ut=d["uaType"]
    res.append(v_field("uaType(飞行器类型)", "%d=%s"%(ut,UA_TYPE.get(ut,"?")), ut!=0 and 0<=ut<=15, "0=None 表示未填写飞行器类型" if ut==0 else ("" if 0<=ut<=15 else "超出范围")))
    raw=d["uasId"]
    s="".join(chr(c) if 32<=c<127 else "." for c in raw).rstrip("\x00").rstrip(" ")
    printable = all(32<=c<127 for c in raw if c!=0)
    empty = (raw.strip(b"\x00")==b"" or raw.strip()==b"")
    res.append(v_field("uasId(无人机编号)", repr(s), (not empty) and printable, "空或含不可打印字符" if (empty or not printable) else ""))
    allzero = (it==0 and ut==0 and empty)
    return res, s, allzero

def validate_location(d):
    res=[]
    st=d["status"]; res.append(v_field("status(位置状态)", "%d=%s"%(st,LOC_STATUS.get(st,"Reserved")), st in LOC_STATUS, "" if st in LOC_STATUS else "保留值"))
    htype=d["heightType"]; res.append(v_field("heightType(高度基准)", "%d=%s"%(htype,"起飞点上方" if htype==0 else "地面上方"), htype in (0,1)))
    lat=d["droneLat"]*LAT_MULT; lon=d["droneLon"]*LAT_MULT
    res.append(v_field("Latitude(纬度)", "%.7f"%lat, -90<=lat<=90 and not(lat==0 and lon==0), "超出[-90,90]或坐标为(0,0)" if not(-90<=lat<=90) else ("坐标为(0,0)——未提供真实位置" if lat==0 and lon==0 else "")))
    res.append(v_field("Longitude(经度)", "%.7f"%lon, -180<=lon<=180 and not(lat==0 and lon==0), "超出[-180,180]" if not(-180<=lon<=180) else ""))
    if lat==0 and lon==0:
        if st in (1,2,3,4):
            res[-2]["ok"]=False; res[-2]["note"]="声称有定位(status=%s)但坐标为(0,0)"%LOC_STATUS.get(st)
            res[-1]["ok"]=False; res[-1]["note"]="声称有定位但坐标为(0,0)"
    ag=calc_alt(d["altitudeGeodetic"]); res.append(v_field("Altitude Geodetic(海拔)", "%.1f m"%ag, -1000<=ag<=5000, "异常高度" if not(-1000<=ag<=5000) else ""))
    h=d["height"]; hgt=calc_alt(h); res.append(v_field("Height(相对高度)", "%.1f m (基准:%s)"%(hgt,"起飞点" if htype==0 else "地面"), -1000<=hgt<=5000, "" if -1000<=hgt<=5000 else "异常"))
    spd=calc_speed(d["speedHori"], d["speedMult"]); res.append(v_field("Speed Horizontal(水平速度)", "%.2f m/s"%spd, 0<=spd<=200, "超出合理范围" if not(0<=spd<=200) else ""))
    sv=d["speedVert"]*SPD_VERT_MULT; res.append(v_field("Speed Vertical(垂直速度)", "%.2f m/s"%sv, -70<=sv<=70, "超出合理范围" if not(-70<=sv<=70) else ""))
    dr=calc_dir(d["direction"], d["EWDirection"]); res.append(v_field("Direction(航向)", "%.0f°"%dr, 0<=dr<360, "超出[0,360)" if not(0<=dr<360) else ("" if d["direction"]!=255 else "255=未提供")))
    for f,scale in [("horizontalAccuracy",ACC_SCALE),("verticalAccuracy",ACC_SCALE),("baroAccuracy",ACC_SCALE),("speedAccuracy",ACC_SCALE)]:
        v=d[f]; res.append(v_field(f, "%d=%s m"%(v,scale.get(v,"Reserved")), v in scale or v==0, "" if (v in scale) else "保留/未知精度值"))
    ts=d["timestamp"]; res.append(v_field("Timestamp(时间戳)", "%d"%ts, 0<=ts<=3599, "超出[0,3599]秒" if not(0<=ts<=3599) else ""))
    ta=d["timeAccuracy"]; ta_str=("%.1f s"%(ta*0.1)) if ta else "Unknown"
    res.append(v_field("TimeAccuracy", "%d=%s"%(ta, ta_str), ta in ACC_SCALE, "" if ta in ACC_SCALE else "保留值"))
    return res, {"lat":lat,"lon":lon,"alt":ag,"hgt":hgt,"spd":spd,"sv":sv,"dir":dr,"status":st}

def validate_system(d):
    res=[]
    olt=d["operatorLocationType"]; res.append(v_field("operatorLocationType(飞手位置类型)", "%d=%s"%(olt,OP_LOC_TYPE.get(olt,"?")), olt in OP_LOC_TYPE, "" if olt in OP_LOC_TYPE else "未知"))
    ct=d["classificationType"]; res.append(v_field("classificationType(分类)", "%d=%s"%(ct,CLASS_TYPE.get(ct,"?")), ct in CLASS_TYPE, "" if ct in CLASS_TYPE else "未知"))
    olat=d["operatorLatitude"]*LAT_MULT; olon=d["operatorLongitude"]*LAT_MULT
    res.append(v_field("Operator Latitude(飞手纬度)", "%.7f"%olat, -90<=olat<=90, "超出范围" if not(-90<=olat<=90) else ""))
    res.append(v_field("Operator Longitude(飞手经度)", "%.7f"%olon, -180<=olon<=180, "超出范围" if not(-180<=olon<=180) else ""))
    if olat==0 and olon==0:
        res[-2]["ok"]=False; res[-1]["ok"]=False; res[-2]["note"]="飞手坐标为(0,0)"; res[-1]["note"]="飞手坐标为(0,0)"
    ar=d["areaRadius"]*10; res.append(v_field("Area Radius(作业半径)", "%d m"%ar, 0<=ar<=9990, "" if 0<=ar<=9990 else "异常"))
    ac=d["areaCeiling"]; res.append(v_field("Area Ceiling(空域上限)", "%.1f m"%calc_alt(ac), -1000<=calc_alt(ac)<=5000, "" if -1000<=calc_alt(ac)<=5000 else "异常"))
    af=d["areaFloor"]; res.append(v_field("Area Floor(空域下限)", "%.1f m"%calc_alt(af), -1000<=calc_alt(af)<=5000, "" if -1000<=calc_alt(af)<=5000 else "异常"))
    cat=d["category"]; res.append(v_field("Category(EU)", "%d=%s"%(cat,CAT_EU.get(cat,"?")), cat in CAT_EU, "" if cat in CAT_EU else "未知"))
    cv=d["classValue"]; res.append(v_field("Class Value(EU)", "%d"%cv, 0<=cv<=15, "" if 0<=cv<=15 else "未知"))
    return res, {"olat":olat,"olon":olon,"ar":ar}

def validate_operatorid(d):
    res=[]
    ot=d["operatorIdType"]; res.append(v_field("operatorIdType(飞手ID类型)", "%d=%s"%(ot,OP_ID_TYPE.get(ot,"?")), ot in OP_ID_TYPE, "" if ot in OP_ID_TYPE else "未知"))
    raw=d["operatorId"]; s="".join(chr(c) if 32<=c<127 else "." for c in raw).rstrip("\x00").rstrip(" ")
    empty=(raw.strip(b"\x00")==b"" or raw.strip()==b"")
    res.append(v_field("operatorId(飞手编号)", repr(s), not empty, "空" if empty else ""))
    return res, s

# ---------------- main ----------------
def main():
    info = fetch_latest_csv()
    if not info:
        print("!! 无法从设备拉取日志。请确认：手机已USB连接、App在前台运行、且已开启日志。")
        sys.exit(2)
    local, name = info
    print("已拉取日志: %s  (%d 字节)" % (name, os.path.getsize(local)))

    # 解析 CSV
    aircraft = {}  # key=(mac) -> dict of msgtype->decoded + meta
    rowcount=0; errs=[]
    with open(local, "r", encoding="utf-8", errors="replace") as f:
        reader=csv.reader(f)
        header=next(reader, None)
        for row in reader:
            rowcount+=1
            if len(row) < 7:
                continue
            transport=row[2].strip(); mac=row[3].strip(); rssi=row[5].strip()
            try:
                ver=int(row[4]); rssi_v=int(row[5])
            except: 
                continue
            payload_hex=row[6].strip()
            if not payload_hex:
                continue
            try:
                data=bytes.fromhex(payload_hex.replace(" ",""))
            except:
                errs.append("行%d: payload 十六进制解析失败"%(rowcount)); continue
            msgs, err = decode_payload(data, transport)
            if err:
                errs.append("MAC %s: %s"%(mac, err)); continue
            for tid, d in msgs:
                if tid in (0,1,4,5):  # 我们只做这四类核心报文的字段校验
                    a=aircraft.setdefault(mac, {"transport":transport,"rssi":[],"msgs":{}})
                    a["msgs"][tid]=d
                    if rssi_v not in (0,) or transport.lower().startswith("bt"):
                        a["rssi"].append(rssi_v)

    if not aircraft:
        print("!! 日志中未解码出任何 Basic ID / Location / System / Operator ID 报文。")
        print("   错误样本:", errs[:5])
        sys.exit(3)

    # 校验 + 汇总
    results=[]
    for mac, a in aircraft.items():
        entry={"mac":mac,"transport":a["transport"],"rssi":a["rssi"],"checks":[],"uasId":"","operatorId":"","loc":None,"sys":None,"allzero":False}
        if 0 in a["msgs"]:
            cr, uas, allzero = validate_basicid(a["msgs"][0]); entry["checks"].append(("Basic ID",cr)); entry["uasId"]=uas; entry["allzero"]=allzero
        if 1 in a["msgs"]:
            cr, loc = validate_location(a["msgs"][1]); entry["checks"].append(("Location",cr)); entry["loc"]=loc
        if 4 in a["msgs"]:
            cr, sysd = validate_system(a["msgs"][4]); entry["checks"].append(("System",cr)); entry["sys"]=sysd
        if 5 in a["msgs"]:
            cr, op = validate_operatorid(a["msgs"][5]); entry["checks"].append(("Operator ID",cr)); entry["operatorId"]=op
        results.append(entry)

    # 生成 HTML
    gen_html(results, name, errs, rowcount)
    # 控制台摘要
    print("\n===== 校验摘要 =====")
    for e in results:
        fails=sum(1 for _,cr in e["checks"] for x in cr if not x["ok"])
        warns=sum(1 for _,cr in e["checks"] for x in cr if x["ok"] is None)
        print("无人机 MAC=%s  运输=%s  RSSI=%s" % (e["mac"], e["transport"], e["rssi"][-1] if e["rssi"] else "?"))
        print("  UAS ID = %s | 飞手ID = %s" % (e["uasId"] or "(缺失)", e["operatorId"] or "(缺失)"))
        if e["loc"]:
            print("  位置 lat=%.6f lon=%.6f 海拔=%.1fm 速度=%.1fm/s 航向=%.0f° 状态=%s" % (
                e["loc"]["lat"],e["loc"]["lon"],e["loc"]["alt"],e["loc"]["spd"],e["loc"]["dir"],LOC_STATUS.get(e["loc"]["status"],"?")))
        print("  字段校验: FAIL=%d  WARN=%d" % (fails,warns))
    print("\n报告已生成: %s" % os.path.join(OUT_DIR,"report.html"))

def gen_html(results, name, errs, rowcount):
    now=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    def badge(ok):
        if ok is True: return '<span class="ok">PASS</span>'
        if ok is False: return '<span class="bad">FAIL</span>'
        return '<span class="warn">WARN</span>'
    cards=""
    for e in results:
        allfail=0; allwarn=0; allpass=0
        checks_html=""
        for mname, cr in e["checks"]:
            rows=""
            for x in cr:
                cls = "ok" if x["ok"] is True else ("bad" if x["ok"] is False else "warn")
                if x["ok"] is True: allpass+=1
                elif x["ok"] is False: allfail+=1
                else: allwarn+=1
                note = (' <span class="note">⚠ %s</span>'%html.escape(x["note"])) if x["note"] else ""
                rows+='<tr class="%s"><td>%s</td><td>%s</td><td>%s%s</td></tr>'%(cls, html.escape(x["field"]), html.escape(str(x["value"])), badge(x["ok"]), note)
            checks_html+='<h4>%s</h4><table class="t"><tr><th>字段</th><th>取值</th><th>结果</th></tr>%s</table>'%(mname,rows)
        # 完整性 & 可信度判定
        have=set(m for m,_ in e["checks"])
        missing=[k for k in ["Basic ID","Location","System","Operator ID"] if k not in have]
        verdict=""
        if e["allzero"]:
            verdict='<div class="verdict bad">⛔ 收到的是<b>全零 Basic ID 空帧</b>（idType=0、uaType=0、UAS ID 为空），且整个日志中<b>没有任何 Location / System / Operator ID 报文</b>。这不可能是合规无人机发出的有效识别信息——很可能是未配置的 RID 模块、测试信标、开发板，或伪造/异常信号。<b>不能据此识别或信任任何无人机。</b></div>'
        elif allfail>0:
            verdict='<div class="verdict bad">⛔ 存在 %d 项字段校验失败，数据不可信，请排查信号/设备。</div>'%allfail
        elif missing:
            verdict='<div class="verdict warn">⚠ 数据基本可信，但缺少报文：%s（RID 发射端可能未播发，或本机未收到）。</div>'%("、".join(missing))
        elif allwarn>0:
            verdict='<div class="verdict warn">✅ 结构完整，但有 %d 项需注意（见上表 WARN）。</div>'%allwarn
        else:
            verdict='<div class="verdict ok">✅ 数据完整且全部字段通过规范校验，可信。</div>'
        missline = ('<p class="missing">缺失报文：%s</p>'%("、".join(missing))) if missing else ""
        loc=e["loc"]; sysd=e["sys"]
        locline=""
        if loc:
            locline=('<p>位置：纬度 %.6f，经度 %.6f，海拔 %.1f m，水平速度 %.1f m/s，航向 %.0f°，状态 %s</p>'%(
                loc["lat"],loc["lon"],loc["alt"],loc["spd"],loc["dir"],LOC_STATUS.get(loc["status"],"?")))
        banner = '<div class="verdict bad" style="margin-top:0">⚠ 全零 / 空帧 Basic ID —— 不属于合规无人机信号</div>' if e["allzero"] else ""
        cards+='''<div class="card">
<h3>无人机 MAC: %s</h3>
<p class="meta">传输方式: %s | RSSI: %s | UAS ID: <b>%s</b> | 飞手ID: <b>%s</b></p>
%s
%s
%s
%s
%s
</div>'''%(html.escape(e["mac"]), html.escape(e["transport"]),
        html.escape(str(e["rssi"][-1] if e["rssi"] else "?")), html.escape(e["uasId"] or "(缺失)"), html.escape(e["operatorId"] or "(缺失)"),
        banner, locline or "<p>（无 Location 报文）</p>", missline, checks_html, verdict)
    html_doc='''<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>无人机RID接收数据校验报告</title><style>
body{font-family:-apple-system,Segoe UI,Roboto,"PingFang SC","Microsoft YaHei",sans-serif;background:#f5f6f8;color:#222;margin:0;padding:20px}
h1{font-size:20px}.sub{color:#666;font-size:13px;margin-bottom:14px}
.card{background:#fff;border:1px solid #e3e6ea;border-radius:10px;padding:16px 18px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.04)}
h3{margin:0 0 6px;font-size:16px}.meta{color:#555;font-size:13px;margin:0 0 10px}
h4{margin:14px 0 6px;font-size:14px;color:#334}
.t{width:100%%;border-collapse:collapse;font-size:13px}
.t th,.t td{border:1px solid #e7e9ec;padding:5px 8px;text-align:left}
.t tr.ok td:first-child{background:#f0fbf2}.t tr.bad td:first-child{background:#fdecec}.t tr.warn td:first-child{background:#fff7e6}
.ok{color:#1a7f37;font-weight:600}.bad{color:#c5221f;font-weight:600}.warn{color:#b26a00;font-weight:600}
.note{color:#b26a00;font-size:12px}
.verdict{padding:9px 12px;border-radius:8px;font-weight:600;margin-top:12px;font-size:14px}
.verdict.ok{background:#e8f6ec;color:#1a7f37}.verdict.warn{background:#fff3e0;color:#b26a00}.verdict.bad{background:#fdecea;color:#c5221f}
.missing{color:#b26a00;font-size:13px}
.pill{display:inline-block;background:#eef1f5;border-radius:20px;padding:2px 10px;font-size:12px;margin-right:6px}
</style></head><body>
<h1>🛩️ 无人机远程识别(RID)接收数据校验报告</h1>
<div class="sub">生成时间：%s ｜ 数据源：手机 App 实时日志 <code>%s</code>（共解析 %d 行）｜ 校验方式：对原始广播字节独立解码并比对 ASTM F3411 / OpenDroneID 规范</div>
%s
<div class="card"><h3>解析备注 / 异常</h3><p class="meta">%s</p></div>
</body></html>'''%(now, html.escape(name), rowcount, cards, html.escape("\n".join(errs) if errs else "无解码异常，所有报文均成功解析。"))
    with open(os.path.join(OUT_DIR,"report.html"),"w",encoding="utf-8") as f:
        f.write(html_doc)

if __name__=="__main__":
    main()
