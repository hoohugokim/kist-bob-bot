![KIST-Bob-Bot avatar](https://raw.githubusercontent.com/hoohugokim/kist-bob-bot/refs/heads/main/assets/KBB-avatar.png)

# KIST-Bob-Bot (키밥봇)

KIST(한국과학기술연구원) 식당 메뉴를 Dooray 채널에 자동으로 알려주는 알림봇입니다.


- **중식 11:00**, **석식 17:00** (월–금) — 코너별 메뉴 + kcal, 탄수화물/단백질/지방 비율, 나트륨, 재료별 kcal 등 영양 정보를 보여줍니다.
- **사진 카드** — 식당 직원이 식사 사진을 올리면 자동으로 사진 카드를 게시합니다.
- **🟢 온라인 / 🔴 오프라인** 안내 — 스케줄러 데몬 시작/중단 시 알림을 전송합니다.

**현황 (2026년 9월): 운영 중.** 알림채널 참여를 원하실 경우 두레이 메신저에서 '김후 (물자원순환연구단)' 에게 메시지를 주시면 초대해 드립니다.

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

## 데이터 출처 안내

메뉴는 `puls2.pulmuone.com`(풀무원 "원더풀 플러스")에 공개된 데이터에서 가져옵니다. 본 프로젝트는 해당 웹앱의 내부 AJAX 엔드포인트(`/src/sql/intro/intro_sql.php`, `/src/sql/menu/today_sql.php`, `/src/sql/menu/nutrient_sql.php`)를 일반 HTTP POST로 재구현했습니다. 따라서 풀무원이 엔드포인트를 바꾸게 된다면 스크레이퍼는 작동하지 않습니다(에이전트가 포기 시점에 메뉴 서비스를 마지막까지 한 번 조회하고, ⚠️ 안내에 실제 사유 — 미등록 / 봇 오프라인 / 서비스 접속 불가 — 를 적어 게시). 풀무원 서버에 부담이 가지 않도록 부하 제한이 설정되어 있습니다: 한 실행당 5회 안쪽의 요청(요청 사이 1초 간격)이며, 게시는 슬롯당 하루 1회로 제한됩니다(메뉴 미등록 시에만 30초~1분 간격으로 재시도, 11:55/17:55 포기).

## 라이선스

[MIT](LICENSE)
