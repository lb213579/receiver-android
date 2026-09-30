#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下载资料库中的 GB 46750-2025 PDF 并抽取正文文本。"""
import subprocess, sys, os, json, urllib.request, io

BASE = r'D:/Programs/WorkBuddy/resources/app.asar.unpacked/resources/plugins/workbuddy-builtin/skills/library'
PY = r'C:/Users/69116/.workbuddy/binaries/python/versions/3.13.12/python.exe'
VENV = r'C:/Users/69116/.workbuddy/binaries/python/envs/default'
VENV_PY = os.path.join(VENV, 'Scripts', 'python.exe')
NODE = '9mNRpbDUKcLmMPCmJYr4vj'
TOKEN = 'op_tptcjamx9ah58rawnb763rndtr'
OUT_DIR = r'D:/tian/receiver-android-master/drone_verify'
PDF_PATH = os.path.join(OUT_DIR, 'GB46750-2025.pdf')
TXT_PATH = os.path.join(OUT_DIR, 'spec_text.txt')

def run(cmd, stdin=None):
    return subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=180)

# 1) 确保 venv + pypdf
if not os.path.exists(VENV_PY):
    print('创建 venv ...')
    run([PY, '-m', 'venv', VENV])
try:
    run([VENV_PY, '-c', 'import pypdf'])
    print('pypdf 已就绪')
except Exception:
    print('安装 pypdf ...')
    r = run([VENV_PY, '-m', 'pip', 'install', '--quiet', 'pypdf'])
    if r.returncode != 0:
        print('pip install 失败:', r.stderr[:500]); sys.exit(1)

# 2) 取下载链接
print('获取 PDF 下载链接 ...')
dl = run([VENV_PY, os.path.join(BASE, 'drive', 'get_download_link.py'), '--node-id', NODE, '--token-stdin'], stdin=TOKEN)
line = dl.stdout.strip().splitlines()[0] if dl.stdout.strip() else ''
print('  stdout 首行:', line[:120])
if not line.startswith('KS_DRIVE_DOWNLOAD'):
    print('  未取到下载链接，stderr=', dl.stderr[:300]); sys.exit(2)
info = json.loads(line.split(' ', 1)[1])
url = info['download_url']
fname = info.get('file_name', 'GB46750-2025.pdf')
print('  文件名:', fname, ' ext:', info.get('ext'))

# 3) 下载 PDF
print('下载 PDF ...')
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
data = urllib.request.urlopen(req, timeout=120).read()
open(PDF_PATH, 'wb').write(data)
print('  已保存:', PDF_PATH, '字节数:', len(data))

# 4) 抽取文本
print('抽取文本 ...')
from pypdf import PdfReader
reader = PdfReader(io.BytesIO(data))
texts = []
for i, page in enumerate(reader.pages):
    try:
        t = page.extract_text() or ''
    except Exception as e:
        t = ''
    texts.append(t)
full = '\n'.join(texts)
open(TXT_PATH, 'w', encoding='utf-8').write(full)
print('  页数:', len(reader.pages), ' 抽取字符数:', len(full))
# 采样
print('--- 前 1500 字符 ---')
print(full[:1500])
print('--- 字符长度分布 (非空页) ---')
nonempty = sum(1 for t in texts if t.strip())
print('非空页:', nonempty, '/', len(reader.pages))
