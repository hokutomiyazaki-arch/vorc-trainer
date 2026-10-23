#!/usr/bin/env python3
"""VORC トレーニングが読み上げる文の音声を voice/ に置く（2026-10-18）。元：~/FNT-Apps/hanasaki-awase/tools/voice_build.py

  python3 tools/voice_build.py          # 足りない分をそろえる（元の fnt-camera-check/voice にあればコピー、無ければ ElevenLabs で作る）
  python3 tools/voice_build.py --dry    # 一覧と、新しく作る字数だけ

- 読み上げる文は index.html から拾う（cue・fail の文字列と INTRO_*）＋ 組み合わせで変わる文は下の EXTRA に並べる
- 文 → 鍵（空白と「。」を抜いたもの）→ ファイル名 は voice/index.json。index.html の vkey() と同じ規則
- ファイル名は「音にする文」の md5 の頭12文字なので、元のアプリと同じ文なら同じファイル名になる（そのままコピーできる）
- 無い文は、アプリが端末の声で読む（止まらない）。コンソールに「[voice] 音声ファイルなし」が出たら、その文を EXTRA に足して走らせ直す
- 声と型は元と同じ：eleven_v3・リョウ。鍵は ~/.zshenv の ELEVENLABS_API_KEY（値は出さない）
"""
import hashlib, json, os, re, shutil, subprocess, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'voice'
SRC = Path.home() / 'FNT-Apps' / 'hanasaki-awase' / 'voice'   # 元のアプリの音声（同じ文はここからコピー）
API = 'https://api.elevenlabs.io'
MODEL = 'eleven_v3'
VOICE = '1cOJcfrlMmUCGpeJbXg9'   # リョウ

def to_speech(h):   # index.html の toSpeech() と同じ変換
    t = re.sub(r'<br\s*/?>', '。', h).replace('<small>', '。')
    t = re.sub(r'<button.*?</button>', '', t, flags=re.S)
    t = re.sub(r'<[^>]+>', '', t)
    t = t.replace('「∞」', '8の字').replace('∞', '8の字')
    t = re.sub(r'(\d+)(周目|往復目)／\d+', r'\1\2', t).replace('／', '、')
    t = re.sub(r'\s+', ' ', t); t = re.sub(r'。+', '。', t); t = re.sub(r'^。|。$', '', t)
    return t.strip()

def vkey(t): return re.sub(r'[\s。]', '', t)

def to_speech_js(h):   # index.html の toSpeech() と同じ変換（.arw・canvas を抜く）
    h = re.sub(r'<span class="arw">.*?</span>', '', h); h = re.sub(r'<canvas.*?</canvas>', '', h, flags=re.S)
    return to_speech(h)

def texts():
    s = (ROOT / 'index.html').read_text(encoding='utf-8')
    H = set()
    for m in re.finditer(r"\b(?:cue|fail)\((?:[a-zA-Z]+,\s*)?(['`])((?:(?!\1).)*)\1", s, re.S):
        if '${' not in m.group(2): H.add(m.group(2))
    for m in re.finditer(r"const INTRO_\w+ = '([^']*)'", s): H.add(m.group(1))
    S = {to_speech_js(h) for h in H}
    E = set()
    E |= {'右', '左', '上', '下', '右上', '左上', '右下', '左下'}   # セットの向き（cue の voice＝DJ[k]）
    E.add('顔が外れました。次へ進みます')
    E |= {f'{d}へ3往復' for d in ['右', '左', '上', '下', '右上', '左上', '右下', '左下']}   # テストの向き（runSet の cue。2026-10-20）
    E.add('右へ3往復。スマホといっしょに、音に合わせて動かします。高い音で出て、低い音で戻ります')   # テストの最初の向き
    E.add('右へ3往復。自分のペースで、スマホといっしょに動かします。3往復すると、次の向きに進みます')   # テストの最初の向き（自分のペース・ジャイロで数える。2026-10-20）
    E.add('スマホを、顔の正面、目の高さに持ってください')   # 構えの確かめ（runSet の cue の声。2026-10-23）
    E |= {'1', '2', '3', '4', '5'}   # トレーニングの数える声（count()。2026-10-18）   # runSession の三項の中の cue（拾えない）
    for w in ['顔が見つかりませんでした', '顔が見えている時間が短すぎました']:
        E.add(f'{w}。顔を画面に入れて、もう一度どうぞ')
    E |= {'OK。下の「次へ」を押してください', '顔の位置を合わせます。顔が見つかりません。カメラに顔を向けてください'}
    for a in ['', 'もう少し近づいて', 'もう少し離れて']:
        for b in ['', '顔をまっすぐ正面に', '首のかしげをまっすぐに']:
            for c in ['', '暗いです。明るい所へ']:
                x = '。'.join(v for v in (a, b, c) if v)
                if x: E.add('顔の位置を合わせます。' + x)
    return sorted(t for t in (S | E) if t)

YOMI = {'1': 'いち', '2': 'にー', '3': 'さん', '4': 'よん', '5': 'ごー', '右': 'みぎ', '左': 'ひだり', '上': 'うえ', '下': 'した', '右上': 'みぎうえ', '左上': 'ひだりうえ', '右下': 'みぎした', '左下': 'ひだりした', '真ん中': 'まんなか'}   # 1語だけだと読み違えるので、かなで読ませる（元と同じ）

def say_text(t):   # 音にする文。記号は読ませない（元と同じ）
    if t in YOMI: return YOMI[t]
    t = re.sub(r'[①②③④]\s*', '', t).replace('3・2・1', '3、2、1').replace(' → ', '、').replace('→', '、')
    return t.replace('✓', '').replace('↔', 'と').replace('〜', 'から').replace('cm', 'センチ').replace('OK', 'オーケー').strip('。 ')

def tts(text, path):
    k = os.environ.get('ELEVENLABS_API_KEY') or sys.exit('ELEVENLABS_API_KEY が無い（~/.zshenv）')
    body = json.dumps({'text': text, 'model_id': MODEL, 'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75}}).encode()
    req = urllib.request.Request(f'{API}/v1/text-to-speech/{VOICE}?output_format=mp3_22050_32', data=body,
                                 headers={'xi-api-key': k, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as r: path.write_bytes(r.read())

def main():
    T = texts(); OUT.mkdir(exist_ok=True)
    idx, copy, make = {}, [], []
    for t in T:
        f = hashlib.md5(say_text(t).encode()).hexdigest()[:12] + '.mp3'
        idx[vkey(t)] = f
        if (OUT / f).exists(): continue
        (copy if (SRC / f).exists() else make).append((t, f))
    n = sum(len(say_text(t)) for t, _ in make)
    print(f'文 {len(T)}・元からコピー {len(copy)}・新しく作る {len(make)}（{n}字・eleven_v3 は約 {n // 2} クレジット）')
    if '--dry' in sys.argv:
        for t, _ in make: print('  作る:', t)
        return
    for t, f in copy: shutil.copy2(SRC / f, OUT / f)
    for i, (t, f) in enumerate(make, 1):
        tts(say_text(t), OUT / f); print(f'  {i}/{len(make)} {t[:40]}')
    if not (OUT / 'unlock.mp3').exists():
        if (SRC / 'unlock.mp3').exists(): shutil.copy2(SRC / 'unlock.mp3', OUT / 'unlock.mp3')
        else: subprocess.run(['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=22050:cl=mono', '-t', '0.2', '-b:a', '32k', str(OUT / 'unlock.mp3')], check=True)
    keep = set(idx.values()) | {'unlock.mp3', 'index.json'}
    for p in OUT.iterdir():   # 使わなくなった音声は消す（index.json に無いもの）
        if p.name not in keep: p.unlink(); print('  消した:', p.name)
    (OUT / 'index.json').write_text(json.dumps(dict(sorted(idx.items())), ensure_ascii=False, indent=0))
    print('voice/index.json', len(idx))

main()
