![KIST-Bob-Bot avatar](https://raw.githubusercontent.com/hoohugokim/kist-bob-bot/refs/heads/main/assets/KBB-avatar.png)

# KIST-Bob-Bot (키밥봇)

KIST(한국과학기술연구원) 식당 메뉴를 Dooray 채널에 자동으로 알려주는 알림봇입니다.


- **중식 11:00**, **석식 17:00** (월–금) — 코너별 메뉴 + kcal, 탄수화물/단백질/지방 비율, 나트륨, 재료별 kcal 등 영양 정보를 보여줍니다.
- **사진 카드** — 식당 직원이 식사 사진을 올리면 자동으로 사진 카드를 게시합니다.
- **🟢 온라인 / 🔴 오프라인** 안내 — 스케줄러 데몬 시작/중단 시 알림을 전송합니다.

**현황 (2026년 12월): 원 제작자의 이직으로 행정팀 서버에 공지대화방으로 확장 이전하여 운영 중.** 알림채널 참여를 원하실 경우 두레이 업무 좌측 하단의 '전체 프로젝트'에서 `키밥봇-구독-신청` 프로젝트를 검색하셔서 안내대로 신청 업무를 등록하시면 키밥봇 서버에서 자동으로 초대해 드립니다.

해당 봇은 클라우드 모델 없이 로컬 Qwen3.8-27B (FP8 W8A16, vLLM) 모델을 추론 강도 xhigh로 OpenCode 하네스에 구동하여 제작되었습니다.

Mac Studio로 서비스를 인계하는 담당자는 [버전 비교, 설치 리허설, 전환 및 복구 절차](MAC-STUDIO-HANDOFF.md)를 참고하세요.

## 게시 예시

```
🏫 KIST Cafeteria Lunch — 2026-08-24 (월)

K1 소고기쌀국수
478 kcal · sodium 1,143 mg
탄 ■■■■■■□□□□ 60 %  73 g
단 ■□□□□□□□□□ 11 %  13 g
지 ■■■□□□□□□□ 29 %  16 g
파인애플볶음밥 247 · 춘권 146 · 소고기쌀국수 43 · 깍두기 23 · 양파초절임 19

K2 고추장찌개
695 kcal · sodium 2,488 mg
탄 ■■■■■■□□□□ 63 %  114 g
단 ■■□□□□□□□□ 16 %  29 g
지 ■■□□□□□□□□ 21 %  17 g
잡곡밥 342 · 미니돈까스＆토마토케첩 181 · …

샐러드 블랙페퍼닭다리살샐러드
452 kcal
```

(탄/단/지 = 탄수화물/단백질/지방; 바 = 에너지 비중, 10칸 = 100 %)

## 동작 방식

```
kbb_agent.sh (systemd user 서비스, 30초 tick, 월–금)
 ├── kist_bob_bot.sh            # 메뉴 게시: 스크랩 → 포맷 → 전송
 │    └── kist_menu_scraper.py  #   puls2.pulmuone.com:
 │                              #     storeList → pageStore(단축 코드)
 │                              #     → today_sql(메뉴 행)
 │                              #     → nutrient_sql(코너별 영양 상세)
 ├── post_slot_images.sh        # 사진 후속 (1일 1회/슬롯,
 │                              #   imageUrl 첨부 카드)
 └── notify_dooray.sh           # incoming hook POST
                                #   (훅 URL = 자격 증명, dooray.conf에만)
```

스크레이퍼는 웹 앱의 AJAX 호출을 그대로 재구현한 것입니다(엔드포인트·파라미터 동일, JS/브라우저/로그인 없음). 공개 스토어 목록에서 KIST 행을 자동으로 찾아 (`KIST_TARGET_NAME`, 기본값 `KIST`) 작동하므로 별도의 스토어 코드 하드코딩이 없습니다.

## 디렉터리 구조

```
kbb_agent.sh            # Scheduler daemon (systemd unit; 🟢/🔴, retry)
kist_menu_scraper.py    # Scraper + message formatter (python3 표준 라이브러리)
kist_bob_bot.sh         # Orchestrator: Scarpe → format → notify
post_slot_images.sh     # Follow-up images (사진 업로드 시 게시)
notify_dooray.sh        # Dooray 전송 (incoming hook only)
kbb_common.sh           # 공통 헬퍼 (스킵일 판정 등)
skip_dates.txt          # 수동 스킵일 (게시 중단 날짜) 목록
kist-bob-bot.service    # systemd user unit
dooray.conf.example     # 설정 템플릿 (dooray.conf로 복사, chmod 600)
```

## 요구 사항

- Python 3 (표준 라이브러리, pip 설치 불필요)
- bash, curl
- Dooray 채널 + incoming hook (채널 → 설정 → Incoming Hook)
- systemd (선택 — 스케줄러용; cron으로도 동작)
- 시간대 — 스크립트가 `TZ=Asia/Seoul`을 강제하므로 머신 시간대와 무관 (KIST 일정, KST 기준)

KIST 내부망에 연결되어 GOV Dooray API를 통한 두레이 메신저 채널의 Incoming webhook 접근이 가능한 머신에서 작동하도록 설계되었습니다.

Linux systemd 및 Python 표준 라이브러리만 사용하여 의존성을 최소화하였습니다.

## 설치

1. **클론 및 설정**

   ```bash
   git clone <이 repo> && cd kist-bob-bot
   cp dooray.conf.example dooray.conf
   chmod 600 dooray.conf
   ```

   `dooray.conf` 항목:
   - `DOORAY_HOOK_URL` — **필수**. 채널 설정에서 받는 incoming hook URL. **훅 URL은 자격 증명과 동일** — URL을 가진 누구나 채널에 게시할 수 있으므로, 절대 repo에 올리지 마세요 (gitignore된 로컬 `dooray.conf`에만 기입)!
   - `DOORAY_BOT_NAME` — 게시글에 표시될 봇 이름.
    - `DOORAY_BOT_ICON_URL` — 선택. 모든 게시에 쓰이는 봇 아바타용 공개 이미지 URL.

2. **Dry-run** (전송될 정확한 페이로드를 표시하고 `.dryrun/`에 저장)

별도의 Dev 채널 대신 dry-run으로 봇 전송 결과 테스트가 가능합니다.

   ```bash
   KBB_DRY_RUN=1 ./kist_bob_bot.sh lunch
   ```

3. **직접 게시**

   ```bash
   ./kist_bob_bot.sh lunch              # 중식
   ./kist_bob_bot.sh dinner             # 석식
   ./kist_bob_bot.sh all                # 게시 대상 슬롯 전부
   ./post_slot_images.sh lunch --date 20260825   # 특정 날짜 사진
   ```

4. **스케줄러 설치** (systemd user 서비스)

   ```bash
   # ExecStart를 repo clone 경로로 고친 뒤:
   cp kist-bob-bot.service ~/.config/systemd/user/
   systemctl --user daemon-reload
   systemctl --user enable --now kist-bob-bot
   loginctl enable-linger $USER    # 로그인 세션 없이 부팅 시에도 실행
   ```

   systemd 없이 cron 두 줄로도 메뉴 게시는 가능합니다 (사진 후속과 🟢/🔴는 에이전트 담당):

   ```cron
    0-55 11 * * 1-5  cd /path/to/kist-bob-bot && ./kist_bob_bot.sh lunch >/dev/null 2>&1
    0-55 17 * * 1-5  cd /path/to/kist-bob-bot && ./kist_bob_bot.sh dinner >/dev/null 2>&1
    ```

(`.state/`에 해당 날짜+슬롯의 게시 기록을 남겨 같은 날 재실행은 조용히 종료됩니다. 에이전트도 같은 파일로 중복을 막습니다.)

## 일정 및 동작

| 시각 (KST, 월–금) | 동작 |
|---|---|
| 11:00–11:55 | 중식 게시 — 식당 등록 전까지 30초 간격 재시도; 11:55에도 미게시이면 ⚠️ yellow 안내 (사유 판별: 미등록 / 봇 오프라인 / 서비스 접속 불가) |
| 17:00–17:55 | 석식 동일 |
| 11:05–11:55 / 17:05–18:25 | 사진 watcher (5분 간격) — 사진은 메뉴 게시 몇 분 후에 업로드됨 (해당 슬롯의 메뉴가 실제로 게시된 날만 동작) |
| 데몬 시작 / 종료 시 | 🟢 online / 🔴 offline 안내 (`KBB_LIFECYCLE_NOTICE=0`로 비활성 가능) |

- 동작 시간대 중 봇이 꺼져 있던 경우는 **미게시** (사후 게시 없음).
- 조식·주말·휴무일(식당 휴무)은 안내하지 않습니다.
- 코너에 영양 상세가 등록되지 않으면 일반 메뉴 목록(이름 + kcal + 단백질)으로 fallback 합니다.

### 수동 스킵일 (`skip_dates.txt`)

자동 휴무일 판정(식당의 `closeGb` 휴무 플래그)이 불안정할 때, 게시를 완전히 중단할 날짜를 직접 지정합니다.

2027년 말까지 평일에 해당하는 전국 공휴일과 대체공휴일을 반영했습니다. 임시공휴일이 지정되거나 KIST 식당이 별도 휴무를 공지하면 담당자가 해당 날짜를 추가합니다. [우주항공청 2027년 월력요항](https://www.kasa.go.kr/bbs/BBSMSTR_000000000018/view.do?nttId=B000000003234Li6nD2)

```
# skip_dates.txt — 한 줄에 날짜 하나 (YYYYMMDD 또는 YYYY-MM-DD), # 주석 가능
20270915    # 추석
2027-10-04  # 개천절 대체공휴일
```

- 지정된 날짜는 **주말과 동일하게 완전 침묵** — 메뉴·사진 게시 없음, ⚠️ 미게시 안내도 없음.
- 추가한 날짜는 에이전트가 다음 주기(약 30초)에 확인합니다. 당일 휴무가 취소되면 메뉴 게시를 재개하기 전에 채널과 해당 슬롯의 `-menu-missed` 기록을 함께 확인하세요.
- 날짜는 지난 뒤에도 그대로 두거나 삭제해도 무방합니다.

## 설정 참고

`dooray.conf` (`notify_dooray.sh`가 읽음; `chmod 600`):

| key | 필수 | 역할 |
|---|---|---|
| `DOORAY_HOOK_URL` | 예 | incoming hook URL — 게시 대상 |
| `DOORAY_BOT_NAME` | 아니오 | 게시 봇 이름 (기본 `KIST-Bob-Bot`) |
| `DOORAY_BOT_ICON_URL` | 아니오 | 봇 아바타용 공개 이미지 URL |

환경 변수 override:

| env | 기본값 | 역할 |
|---|---|---|
| `PULM_BASE` | `https://puls2.pulmuone.com` | 식당 웹 베이스 URL |
| `KIST_TARGET_NAME` | `KIST` | 스크레이퍼가 매칭할 스토어 이름 부분 문자열 |
| `KBB_DRY_RUN` | off | `1` = 페이로드 구성+저장만, 게시/상태 기록 없음 |
| `KBB_LOCAL_CONF` | `dooray.conf` | 대체 설정 파일 (예: 개인 테스트 채널) |
| `KBB_STATE_DIR` | `.state/` | 대체 상태 디렉터리 (테스트 격리) |
| `KBB_SKIP_DATES_FILE` | `skip_dates.txt` | 대체 스킵일 목록 파일 (테스트) |
| `KBB_LIFECYCLE_NOTICE` | on (1) | `0` = 🟢/🔴 온라인/오프라인 안내를 게시하지 않음 (systemd unit의 `Environment=`로 설정; 재부팅이 잦을 때) |

## 변경사항 테스트 (개발 워크플로우)

```bash
# DRY RUN — 전체 파이프라인 실행, 게시 없음 (페이로드는 표시 + .dryrun/ 저장)
KBB_DRY_RUN=1 ./kist_bob_bot.sh lunch

# 샌드박스 — 1인 개인 테스트 채널로 실제 게시.
# 1인 Dooray 채널을 만들고 incoming hook URL을 샌드박스 conf에 넣으면:
KBB_LOCAL_CONF=dooray.sandbox.conf KBB_STATE_DIR=.state-test ./kist_bob_bot.sh lunch

# 프로덕션 — 변경이 만족스러우면:
systemctl --user restart kist-bob-bot   # 🔴 → 🟢 게시
```

## 구독 신청 및 공지방 자동 초대

### 두레이 프로젝트 설정

1. 두레이 웹 **프로젝트 → 즐겨찾는 프로젝트 옆 + → 프로젝트**에서 `키밥봇-구독-신청`을 만듭니다. **프로젝트 설정 → 일반 → 멤버**에는 학연운영팀 담당자와 자동화에 쓸 운영 계정만 추가합니다. 자동화 계정은 구독 프로젝트의 멤버이면서 대상 공지방의 관리자여야 합니다.
2. **프로젝트 설정 → 업무 → 권한**에서 아래 값을 지정합니다. 등록 대상 조직을 고를 수 있으면 KIST를 선택합니다. [두레이 프로젝트 만들기](https://helpdesk.dooray.com/share/pages/9wWo-xwiR66BO5LGshgVTg/2896315749455837575) · [두레이 프로젝트 권한](https://helpdesk.dooray.com/share/pages/9wWo-xwiR66BO5LGshgVTg/2896316138135651348)

   | 권한 | 선택값 |
   | --- | --- |
   | 읽기 | 멤버와 업무 등록자/담당자/참조자 읽기 가능 |
   | 등록 | 모두 등록 가능 |
   | 편집 | 멤버는 모든 업무 편집 가능 |
   | 이동/삭제/공유하기 | 본인이 등록한 업무만 이동/삭제/공유 가능 |

   이 옵션으로 신청자는 잘못 등록한 업무를 삭제하고 다시 신청할 수 있습니다. 두레이는 본인 업무의 이동과 공유 권한도 함께 부여합니다. 이미 공지방에 가입한 뒤 구독을 취소하려면 메신저에서 직접 방을 나갑니다.

3. 신청자는 두레이에 로그인해 **프로젝트 → 새 업무 → 프로젝트 선택**에서 `키밥봇-구독-신청`을 고르고 업무를 등록합니다. 제목은 자유롭게 입력하고 본문, 담당자, 참조자는 비워도 됩니다. 공개 전에 프로젝트 비멤버 A와 B로 `권한 확인 A`, `권한 확인 B` 업무를 각각 만듭니다. 각자 본인 업무를 열고 삭제한 뒤 다시 등록할 수 있는지, 상대의 업무는 열 수 없는지, 운영팀은 두 업무를 모두 볼 수 있는지 확인합니다. 권한 확인 업무는 자동 초대를 실행하기 전에 닫거나 삭제하세요. 읽기를 제한한 프로젝트는 **전체 프로젝트** 목록에 표시되지 않을 수 있으므로 비멤버의 **새 업무** 프로젝트 선택 화면에서 등록 경로도 확인하세요. [업무 등록](https://helpdesk.dooray.com/share/pages/9wWo-xwiR66BO5LGshgVTg/2896331778671698861) · [전체 프로젝트 표시 조건](https://helpdesk.dooray.com/share/pages/9wWo-xwiR66BO5LGshgVTg/2909485018131061027)

### 테스트 공지방에 한 번 초대

테스트에 동의한 계정 한 명이 신청 프로젝트에 업무를 등록합니다. Mac의 `kbb` 서비스 계정에서 아래 명령을 실행하고, 프로젝트 멤버이자 테스트방 관리자인 두레이 계정의 개인 인증 토큰을 입력합니다. `PROJECT_ID`에는 신청 프로젝트의 숫자 ID, `CHANNEL_ID`에는 테스트 공지방의 숫자 ID를 사용합니다. 프로젝트 ID는 업무 주소가 `/task/<project-id>/<post-id>` 형식이면 첫 번째 숫자이며, `GET /project/v1/projects?member=me`로도 확인할 수 있습니다. [두레이 서비스 API](https://helpdesk.dooray.com/share/pages/9wWo-xwiR66BO5LGshgVTg/2939987647631384419)

```bash
cd /Users/kbb/kist-bob-bot
ops=/Users/kbb/kbb-ops
mkdir -p "$ops"
read -rsp '두레이 개인 API 토큰: ' DOORAY_TOKEN
printf '\n'
(umask 077; printf '%s\n' "$DOORAY_TOKEN" > "$ops/invite.token")
chmod 600 "$ops/invite.token"
unset DOORAY_TOKEN

invite_args=(
  --project-id PROJECT_ID
  --channel-id CHANNEL_ID
  --token-file "$ops/invite.token"
  --state-dir "$ops/invite-state"
)
python3 kbb_invite.py "${invite_args[@]}"
```

미리보기에서 테스트 공지방 제목과 초대 대상이 맞으면 `python3 kbb_invite.py "${invite_args[@]}" --apply`를 실행합니다. 참가자 목록과 신청자 메신저에서 가입을 확인하고, 두레이 업무가 **완료**로 표시되는지도 확인합니다. 스크립트는 신청 프로젝트의 열린 업무를 제목과 본문에 관계없이 처리합니다. 초대 성공이나 기존 가입을 확인하면 상태 디렉터리에 먼저 기록하고, 이어서 해당 신청을 완료 처리합니다. 이미 초대 기록이 있고 업무가 열려 있으면 완료 처리만 실행합니다. 가입 또는 완료 처리에 실패한 업무는 다음 조회에서 재시도합니다.

### Mac Studio에서 3분 간격으로 실행

수동 시험이 통과하면 [자동 초대용 LaunchDaemon 템플릿](deploy/macos/local.kbb-invite.plist)의 두 ID와 서버 경로를 시험에 쓴 값으로 바꿉니다. `plutil -lint`로 확인한 복사본을 관리자가 `/Library/LaunchDaemons/local.kbb-invite.plist`로 설치하고 `sudo launchctl bootstrap system /Library/LaunchDaemons/local.kbb-invite.plist`를 실행합니다. 설치 직후와 이후 3분마다 신청을 처리합니다. `invite.log`, `invite.err`에서 결과를 확인합니다. 운영 공지방으로 전환할 때는 해당 방을 관리하는 계정의 토큰과 운영 프로젝트·공지방 ID를 지정합니다. 같은 프로젝트를 재사용하면 다른 방에서 처리한 열린 신청도 새 방의 초대 대상이 되므로 테스트 신청을 먼저 닫습니다.

## 데이터 출처 안내

메뉴는 `puls2.pulmuone.com`(풀무원 "원더풀 플러스")에 공개된 데이터에서 가져옵니다. 본 프로젝트는 해당 웹앱의 내부 AJAX 엔드포인트(`/src/sql/intro/intro_sql.php`, `/src/sql/menu/today_sql.php`, `/src/sql/menu/nutrient_sql.php`)를 일반 HTTP POST로 재구현했습니다. 따라서 풀무원이 엔드포인트를 바꾸게 된다면 스크레이퍼는 작동하지 않습니다(에이전트가 포기 시점에 메뉴 서비스를 마지막까지 한 번 조회하고, ⚠️ 안내에 실제 사유 — 미등록 / 봇 오프라인 / 서비스 접속 불가 — 를 적어 게시). 풀무원 서버에 부담이 가지 않도록 부하 제한이 설정되어 있습니다: 한 실행당 5회 안쪽의 요청(요청 사이 1초 간격)이며, 게시는 슬롯당 하루 1회로 제한됩니다(메뉴 미등록 시에만 30초~1분 간격으로 재시도, 11:55/17:55 포기).

## 라이선스

[MIT](LICENSE)
