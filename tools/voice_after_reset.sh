#!/bin/zsh
# 1回だけ動く：ElevenLabs の月の文字数が戻ったら（2026-10-22 13:08）、テストの向きの指示・説明の声を作って公開する（10/20 は残り0で作れず、端末の声で読んでいる）
# launchd: ~/Library/LaunchAgents/jp.legrandchariot.vorc-trainer.voice-1022.plist（10/22 14:20・10/23 8:20・10/24 8:20）。終わったら自分を外す
# DRY=1 で、声を作らずに流れだけ確かめる
set -u
source ~/.zshenv
cd /Users/miyazakihokuto/FNT-Apps/vorc-trainer || exit 1
L=jp.legrandchariot.vorc-trainer.voice-1022
echo "== $(date '+%F %T')"
left=$(curl -s -H "xi-api-key: $ELEVENLABS_API_KEY" https://api.elevenlabs.io/v1/user/subscription | /opt/homebrew/bin/python3 -c "import json,sys;d=json.load(sys.stdin);print(d['character_limit']-d['character_count'])")
echo "残り文字数: $left"
if [ -z "$left" ] || [ "$left" -lt 600 ]; then echo "まだ戻っていない。次の回に回す"; exit 0; fi
if [ "${DRY:-0}" = 1 ]; then /opt/homebrew/bin/python3 tools/voice_build.py --dry | tail -3; echo "DRY 終わり"; exit 0; fi
git pull -q
/opt/homebrew/bin/python3 tools/voice_build.py || { echo "作成に失敗"; exit 1; }
git add voice
if git diff --cached --quiet; then echo "足すファイルなし"; else
  sed -i '' -E "s/vorc-trainer-v([0-9]+)\.([0-9]+)\.([0-9]+)/vorc-trainer-v\1.\2.$(( $(grep -oE 'vorc-trainer-v[0-9.]+' sw.js | awk -F. '{print $3}') + 1 ))/" sw.js; git add sw.js
  git commit -q -m "テストの向きの指示（右へ3往復…）と説明の声を、いつもの声（リョウ）で足す

10/20 に ElevenLabs の月の文字数が0で作れず、端末の声で読んでいた分。月の文字数が戻った 10/22 に launchd で作った

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && git push -q && echo "push した"
fi
# 先に plist を退避してから外す（bootout は走っている自分ごと止めるので、後ろに置いた mv が走らず plist が残った 2026-10-22）
mkdir -p ~/Library/LaunchAgents/_retired; mv ~/Library/LaunchAgents/$L.plist ~/Library/LaunchAgents/_retired/ 2>/dev/null; echo "自分を外した"; launchctl bootout gui/$(id -u)/$L 2>/dev/null
