# 2026년 11월 23일 월요일 KBB 이전 가이드

학연운영팀 방문 중 Linux 워크스테이션에서 Mac Studio로 운영을 넘기고, 메뉴 게시 대상을 새 두레이 공지방으로 전환합니다. 시간은 모두 KST입니다.

**권장 전환은 월요일 12:05–16:30입니다.** 월요일 점심과 사진은 기존 방에서 마무리하고, 17:00 저녁부터 새 공지방에 게시합니다. 16:30까지 시험과 회원 확인을 마치지 못하면 Linux에서 월요일 저녁까지 운영합니다. 시험을 마쳤다면 마지막 사진 확인이 끝난 **18:40 이후**에 전환할 수 있습니다. 이 경우 새 방의 첫 정규 게시는 화요일 11:00 점심입니다. 문제가 남아 있으면 다음 전환 시간을 잡을 때까지 Linux에서 운영합니다.

| 담당 | 할 일 |
| --- | --- |
| 기존 운영자 | 소스 전달, 기존 Linux 상태 확인·중지, 기존 방 전환 안내 |
| 학연운영팀 관리자 | Mac 서비스 설치, 새 공지방과 구독 프로젝트 권한 확인, 전환 후 운영 |
| 동의한 시험 참여자 | 신규 신청 한 건 등록, 공지방 입장과 모바일 알림 확인 |

## 1. 방문 전에 소스 묶기

새 관리자에게 **기존 방 ID, 새 운영 공지방 ID, 구독 프로젝트 ID, 새 공지방의 전체 Incoming Hook URL, 새 관리자 개인 API 토큰**이 준비되어 있는지 확인합니다. 동일한 두레이 계정이 **기존 방의 참여자, 새 방의 관리자, 신청 프로젝트의 업무를 읽고 완료할 수 있는 멤버**여야 합니다. 테스트 공지방의 훅 URL도 별도로 준비합니다. ID와 비밀 값은 현장에서 각자 확인하고, 훅 URL과 토큰은 학연운영팀이 관리하는 비공개 경로로 전달합니다. [두레이 서비스 API](https://helpdesk.dooray.com/share/pages/9wWo-xwiR66BO5LGshgVTg/2939987647631384419)

Linux 운영 체크아웃의 소스를 묶습니다. 묶음에는 자동 초대와 회원 이전 스크립트, 두 LaunchDaemon 템플릿, 휴무 캘린더를 같이 넣습니다.

```bash
cd "$HOME/workbench/KIST-Bob-Bot"
git status --short
git diff --check

kit=$(mktemp -d)
tar -czf "$kit/kbb-source.tgz" \
  README.md MAC-STUDIO-HANDOFF.md LICENSE \
  kbb_agent.sh kbb_common.sh kist_bob_bot.sh kist_menu_scraper.py \
  post_slot_images.sh notify_dooray.sh skip_dates.txt dooray.conf.example \
  kist-bob-bot.service kbb_invite.py kbb_migrate_members.py \
  assets/KBB-avatar.png deploy/macos/local.kist-bob-bot.plist \
  deploy/macos/local.kbb-invite.plist
git rev-parse HEAD > "$kit/kbb-source-base.txt"
(cd "$kit" && sha256sum kbb-source.tgz > kbb-source.sha256)
tar -tzf "$kit/kbb-source.tgz"
printf '전달할 파일 폴더 %s\n' "$kit"
```

`kbb-source.tgz`, `kbb-source.sha256`, `kbb-source-base.txt`를 Mac에 전달합니다. 기준 커밋과 함께 **아카이브 해시**를 기록하면 현장에서 사용한 작업 트리의 버전을 식별할 수 있습니다.

## 2. Mac에 소스와 설정 놓기

**Mac 관리자**가 KIST 내부망 연결, 서비스 계정 `kbb`, 관리자 권한을 확인합니다. 자동 실행에 쓸 Mac의 절전·재시동 정책과 FileVault 잠금 해제 담당자도 확인합니다. 아래 템플릿은 `/Users/kbb/kist-bob-bot`과 `/Users/kbb/kbb-ops`를 기준으로 합니다. 실제 경로가 다르면 두 plist와 이 가이드의 경로를 맞춥니다. [Apple LaunchDaemon 가이드](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html)

**Mac 관리자**가 전달받은 파일이 있는 폴더에서 실행합니다. `ls -A`에 기존 설치 파일이 보이면 그 설치를 먼저 확인하고, 신규 설치 경로에 압축을 풉니다.

```bash
shasum -a 256 -c kbb-source.sha256
sudo -u kbb mkdir -p /Users/kbb/kist-bob-bot
sudo -u kbb ls -A /Users/kbb/kist-bob-bot
# 체크섬 통과와 비어 있는 설치 경로를 확인한 다음 실행
sudo -u kbb tar -xzf - -C /Users/kbb/kist-bob-bot < kbb-source.tgz
sudo -H -u kbb /bin/bash -l
```

이제 **`kbb`의 Bash 세션**에서 실행합니다. 이후 시험과 일괄 초대 명령도 이 세션에서 실행합니다.

```bash
cd /Users/kbb/kist-bob-bot
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
python3 -c 'import ssl, kist_menu_scraper, kbb_invite, kbb_migrate_members'
curl --version
ops=/Users/kbb/kbb-ops
umask 077
mkdir -p "$ops"/{state,invite-state,manual-state,rehearsal-state}
chmod 700 "$ops"
for conf in sandbox production; do
  if [ ! -e "$ops/$conf.conf" ]; then
    install -m 0600 dooray.conf.example "$ops/$conf.conf"
  fi
done
```

편집기로 `$ops/sandbox.conf`에는 테스트 공지방의 전체 훅 URL을, `$ops/production.conf`에는 새 운영 공지방의 전체 훅 URL을 `DOORAY_HOOK_URL` 값으로 넣습니다. 기존 파일이 있으면 그 값을 확인합니다. 신규 토큰을 아래처럼 저장합니다.

```bash
chmod 600 "$ops/sandbox.conf" "$ops/production.conf"
read -rsp '새 관리자의 두레이 개인 API 토큰: ' kbb_dooray_token
printf '\n'
printf '%s\n' "$kbb_dooray_token" > "$ops/invite.token"
chmod 600 "$ops/invite.token"
unset kbb_dooray_token
```

## 3. 테스트 방에서 메뉴와 사진 확인

`kbb` 세션에서 메뉴와 사진이 실제로 있는 날짜를 지정합니다. 아래 예시는 11월 18일입니다. 과거 사진을 원본에서 읽을 수 없으면 메뉴·사진이 확인된 최근 날짜를 사용합니다.

```bash
meal_day=20261118
(
  export KBB_LOCAL_CONF="$ops/sandbox.conf" KBB_STATE_DIR="$ops/manual-state"
  export KBB_DRY_RUN=1
  ./kist_bob_bot.sh lunch --date "$meal_day" &&
    ./post_slot_images.sh lunch --date "$meal_day"
)
```

`.dryrun/`에서 메뉴와 사진 페이로드가 둘 다 만들어졌는지 확인하고, 테스트 공지방에 실제 게시합니다.

```bash
(
  export KBB_LOCAL_CONF="$ops/sandbox.conf" KBB_STATE_DIR="$ops/manual-state"
  export KBB_DRY_RUN=0
  ./kist_bob_bot.sh lunch --date "$meal_day" &&
    ./post_slot_images.sh lunch --date "$meal_day"
)
```

테스트 공지방에서 메뉴 내용, 사진 렌더링, 봇 이름을 확인합니다. 사진 명령은 사진이 없어도 조용히 종료할 수 있으므로 채널에서 실제 사진을 확인합니다. 휴무 처리를 확인하려면 첫 번째 미리보기 블록에서 `meal_day=20261009`로 바꿔 실행하고 메뉴 명령이 종료 코드 4를 반환하는지 확인합니다.

**Mac 관리자**는 별도 터미널에서 게시용 LaunchDaemon을 먼저 테스트 설정으로 올립니다. 이미 같은 이름의 작업이 등록돼 있으면 `launchctl print`로 확인하고, 시험 대상임을 확인한 후 중지한 상태에서 설치합니다.

```bash
publisher=system/local.kist-bob-bot
publisher_plist=/Library/LaunchDaemons/local.kist-bob-bot.plist
sudo install -o root -g wheel -m 0644 \
  /Users/kbb/kist-bob-bot/deploy/macos/local.kist-bob-bot.plist "$publisher_plist"
sudo plutil -lint "$publisher_plist"
sudo launchctl enable "$publisher"
sudo launchctl bootstrap system "$publisher_plist"
sudo launchctl print "$publisher"
```

`state = running`, PID, 테스트 설정 경로를 확인합니다. `/Users/kbb/kbb-ops/agent.log`에 시작 기록이 있어야 합니다. GUI 로그아웃 후에도 작업이 살아 있는지 확인하고, 재시동 시험은 Mac 사용 일정에 맞춰 운영 전환 전에 진행합니다. 네트워크가 사용자 로그인에 의존하면 그 조건을 먼저 해결하고 Linux에서 계속 게시합니다.

## 4. 새 운영 공지방에서 한 건 시험

`kbb` 세션에서 방 ID와 프로젝트 ID를 읽습니다. 각 ID가 운영 공지방과 신청 프로젝트를 가리키는지 확인합니다. 비멤버 계정으로 **새 업무**의 프로젝트 선택에서 신청 프로젝트를 고를 수 있는지, 다른 신청자의 업무 링크에는 접근할 수 없는지 확인합니다. 열람 확인에 쓴 업무는 닫습니다. [프로젝트 권한과 신청 방법](README.md#구독-신청-및-공지방-자동-초대)

```bash
read -rp '기존 KBB 방 ID: ' old_room_id
read -rp '새 운영 공지방 ID: ' new_room_id
read -rp '구독 프로젝트 ID: ' project_id
invite_args=(
  --project-id "$project_id"
  --channel-id "$new_room_id"
  --token-file "$ops/invite.token"
  --state-dir "$ops/invite-state"
)
migration_args=(
  --source-room-id "$old_room_id"
  --destination-room-id "$new_room_id"
  --token-file "$ops/invite.token"
)
```

1. 새 방에 아직 없는 **동의한 시험 계정 한 명**이 구독 프로젝트에 업무를 등록합니다. 제목은 자유입니다. 아래 미리보기에서 새 방 제목과 예정한 신청자 한 명을 확인합니다. `--apply`는 실행 시점의 열린 신청을 읽으므로, 첫 시험을 마칠 때까지 신청 안내 배포를 보류합니다. 미리보기에 다른 신청도 보이면 처리 범위를 확인합니다.

   ```bash
   python3 kbb_invite.py "${invite_args[@]}"
   ```

2. 대상이 맞으면 실행합니다. `Invited: 1`과 `Tasks marked Done: 1`이 표시되고, 시험 계정의 메신저에 새 방이 생기며 신청 업무가 **완료**가 되는지 확인합니다.

   ```bash
   python3 kbb_invite.py "${invite_args[@]}" --apply
   ```

3. 새 공지방의 훅으로 점검 메시지 한 건을 보냅니다. 시험 계정에서 메시지와 설정된 모바일 알림을 확인합니다.

   ```bash
   KBB_LOCAL_CONF="$ops/production.conf" KBB_DRY_RUN=0 \
     ./notify_dooray.sh 'KBB 이전 점검' '학연운영팀 서버에서 운영 공지방 연결을 확인 중입니다.'
   ```

## 5. 기존 방 회원을 새 방으로 초대

**기존 운영자와 새 관리자**가 미리보기의 기존 방·새 방 제목을 확인하고, `Source members` 수를 기존 방 멤버 목록의 인원과 대조합니다. `to invite`는 새 방에 아직 없는 인원입니다.

```bash
python3 kbb_migrate_members.py "${migration_args[@]}"
```

대상과 인원이 맞고 운영 공지방 검증을 마쳤으면 `--apply`를 실행합니다. 스크립트는 20명씩 추가하고 새 방의 참여자 목록을 다시 조회합니다.

```bash
python3 kbb_migrate_members.py "${migration_args[@]}" --apply
```

`Verified all … source members` 또는 `All source members are already in the destination room`을 확인합니다. 중간에 실패하면 미리보기를 다시 실행해 남은 인원을 확인한 뒤 그 결과를 기준으로 재실행합니다. 원본 방 인원과 API 조회 인원이 다르면 원인을 확인하고 전환을 보류합니다. 일괄 초대가 끝난 뒤 기존 방에도 전환 시점을 안내하고, 기존 방 기록은 참조할 수 있게 둡니다.

## 6. 게시 서버 전환

**Mac 관리자**는 시험 게시 작업을 내립니다. `launchctl print`에서 작업이 보이면 `bootout`으로 내리고, 그 뒤 서비스가 조회되지 않는지 확인합니다.

```bash
publisher=system/local.kist-bob-bot
publisher_plist=/Library/LaunchDaemons/local.kist-bob-bot.plist
sudo launchctl disable "$publisher"
sudo launchctl bootout "$publisher"
sudo launchctl print "$publisher"
```

**Linux 운영자**는 점심 사진 창이 끝난 뒤, 또는 저녁까지 기존 방에서 운영했다면 18:40 이후에, 기존 게시 작업을 멈춥니다. `is-active`와 `is-enabled`의 출력은 각각 `inactive`와 `disabled`여야 합니다. 별도 cron이나 수동 실행 프로세스도 확인합니다.

```bash
cd "$HOME/workbench/KIST-Bob-Bot"
systemctl --user disable --now kist-bob-bot.service
systemctl --user is-active kist-bob-bot.service
systemctl --user is-enabled kist-bob-bot.service
```

기존 방 게시 이력과 유효한 Linux 상태 경로를 대조합니다. 월요일 오후 전환이면 `20261123-lunch-menu` 또는 `20261123-lunch-menu-missed`로 끝난 점심을 확인합니다. `20261123-lunch`는 사진 게시가 있었을 때만 생깁니다. 18:40 이후 전환이면 저녁도 같은 방식으로 확인합니다. 이력에서 메뉴나 사진 게시 또는 미게시 처리를 확인했는데 파일만 빠졌다면, 중지된 장비에서 해당 마커를 복구하고 운영자끼리 확인합니다. 아직 남아 있는 게시 슬롯에 이미 마커가 있으면 그 사유를 확인한 뒤 전환합니다. 지난 슬롯의 상태를 넘기면 새 방에 이미 끝난 식사의 경고가 나가는 일을 막을 수 있습니다.

**Linux 운영자**가 정지 직후 운영 상태를 묶습니다. 서비스에서 `KBB_STATE_DIR`을 지정했다면 `state_dir`을 해당 경로로 바꿉니다.

```bash
state_dir=.state
snap=$(mktemp -d)
tar -C "$state_dir" -czf "$snap/kbb-state.tgz" .
(cd "$snap" && sha256sum kbb-state.tgz > kbb-state.sha256)
printf '상태 전달 폴더 %s\n' "$snap"
```

**Mac 관리자**는 두 상태 파일을 넘겨받아 체크섬과 대상 폴더를 확인합니다. 운영 폴더에 마커가 이미 있으면 채널 이력과 대조한 뒤 진행합니다.

```bash
shasum -a 256 -c kbb-state.sha256
sudo -u kbb ls -A /Users/kbb/kbb-ops/state
# 체크섬 통과와 비어 있는 운영 상태 폴더를 확인한 다음 실행
sudo -u kbb tar -xzf - -C /Users/kbb/kbb-ops/state < kbb-state.tgz
```

**Mac 관리자**는 정지된 게시 작업에 운영 훅과 운영 상태를 지정합니다. 경로와 검사 결과를 확인하고, 기존 Linux 게시 작업이 멈춘 상태에서 기동합니다.

```bash
sudo /usr/libexec/PlistBuddy -c \
  'Set :EnvironmentVariables:KBB_LOCAL_CONF /Users/kbb/kbb-ops/production.conf' "$publisher_plist"
sudo /usr/libexec/PlistBuddy -c \
  'Set :EnvironmentVariables:KBB_STATE_DIR /Users/kbb/kbb-ops/state' "$publisher_plist"
sudo plutil -lint "$publisher_plist"
sudo plutil -p "$publisher_plist"
sudo -u kbb test -r /Users/kbb/kbb-ops/production.conf
sudo -u kbb test -w /Users/kbb/kbb-ops/state
sudo launchctl enable "$publisher"
sudo launchctl bootstrap system "$publisher_plist"
sudo launchctl print "$publisher"
```

운영 설정 경로와 실행 PID를 확인합니다. 첫 정규 게시는 예약 시각에 기다려 확인합니다. 수동 메뉴 명령은 예약 시간 이외에도 게시할 수 있으므로, 전환 시험에는 위의 짧은 점검 메시지를 사용합니다.

## 7. 자동 초대도 정기 실행

**Mac 관리자**는 관리자 터미널에서 `/bin/bash`를 열어 실행합니다. 이미 등록된 시험용 초대 작업이 있으면 중지한 상태에서 plist를 설치합니다. `project_id`, `new_room_id`에는 4단계에서 확인한 숫자 ID를 넣습니다. 게시용과 초대용 작업은 각각 중지하고 재기동할 수 있습니다.

```bash
read -rp '구독 프로젝트 ID: ' project_id
read -rp '새 운영 공지방 ID: ' new_room_id
inviter=system/local.kbb-invite
inviter_plist=/Library/LaunchDaemons/local.kbb-invite.plist

sudo install -o root -g wheel -m 0644 \
  /Users/kbb/kist-bob-bot/deploy/macos/local.kbb-invite.plist "$inviter_plist"
sudo /usr/libexec/PlistBuddy -c "Set :ProgramArguments:4 $project_id" "$inviter_plist"
sudo /usr/libexec/PlistBuddy -c "Set :ProgramArguments:6 $new_room_id" "$inviter_plist"
sudo plutil -lint "$inviter_plist"
sudo plutil -p "$inviter_plist"
sudo -u kbb test -r /Users/kbb/kbb-ops/invite.token
sudo -u kbb test -w /Users/kbb/kbb-ops/invite-state
```

두 ID와 토큰·상태 경로를 대조하고 신청 미리보기 결과를 확인한 후 기동합니다. 기존 장비에서 **같은 운영 프로젝트·공지방**을 처리 중이었다면 그 작업을 먼저 멈추고 기존 초대 상태를 운영 경로로 승계합니다.

```bash
sudo launchctl enable "$inviter"
sudo launchctl bootstrap system "$inviter_plist"
sudo launchctl print "$inviter"
sudo tail -n 25 /Users/kbb/kbb-ops/invite.log /Users/kbb/kbb-ops/invite.err
```

설치 직후와 이후 3분마다 실행됩니다. 한 번 실행하고 끝나는 작업이므로 실행 사이에 PID가 없어도 정상입니다. 로그에서 최근 실행과 성공 여부를 확인합니다. 가능한 경우 두 번째 동의한 비멤버 계정으로 신청을 한 건 등록해, 다음 주기에 방에 초대되고 업무가 완료되는지 확인합니다.

## 8. 확인, 복구, 인계 완료

- **전환 당일과 다음 운영일**에 운영 공지방의 메뉴와 사진, `agent.log`, `agent.err`, 운영 상태를 대조합니다. 메뉴는 11:00·17:00부터 시도하고, 사진이 올라오면 11:55·18:25까지 확인합니다. 카페테리아 휴무 또는 미등록은 이전 실패와 구분해 기록합니다.
- **초대 작업에만 문제가 있으면** Mac에서 `sudo launchctl disable system/local.kbb-invite` 후, 작업이 올라와 있으면 `sudo launchctl bootout system/local.kbb-invite`를 실행합니다. 초대 대상과 토큰 권한을 고친 뒤 신청 미리보기부터 다시 확인합니다.
- **Mac 게시를 복구할 수 없으면** 먼저 Mac의 게시·초대 작업을 각각 `disable`하고, 올라와 있는 작업을 `bootout`한 뒤 `launchctl print`에서 둘 다 조회되지 않는지 확인합니다. Mac에 접속할 수 없으면 담당자가 게시 작업의 중지 또는 격리를 확인합니다. Linux에서는 **기존 방 훅과 기존 방의 운영 상태**를 사용하고, 그 방의 게시 이력을 기준으로 현재 슬롯을 대조합니다. `systemctl --user enable --now kist-bob-bot.service`로 복구하고 `journalctl --user -u kist-bob-bot.service -n 30`과 다음 게시를 확인합니다. 구독자에게 기존 방으로 임시 복귀한 사실을 안내합니다.
- **인계 기록**에 운영자와 백업 담당, 배포 아카이브 해시, 방과 프로젝트 ID, 비밀 값의 보관 위치, 운영 로그·상태 경로, 첫 정상 게시와 자동 초대 결과를 남깁니다. 두레이 이용자에게 안내할 구독 신청 경로도 확인합니다. 다음 운영일 검증과 인수 확인 후 기존 Linux 훅 및 남은 비밀 값의 정리 시점을 학연운영팀과 합의합니다.
