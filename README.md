# 록맨 에그제 레거시 컬렉션 Vol.1 한글패치

Mega Man Battle Network Legacy Collection Vol. 1 (Nintendo Switch, 010038E016264000) 한글패치입니다.
게임의 **번체 중국어(繁體中文)** 언어 칸을 한국어로 바꿉니다. 일본어·영어 칸은 그대로입니다.

> 게임 파일(롬·NSP·추출물)은 이 저장소에 없습니다. 패치 파일은 [Releases](../../releases) 에서 받으세요.

## 대상

| 항목 | 값 |
|---|---|
| 본편 | 010038E016264000 (v0) |
| 업데이트 | 010038E016264800 **v196608 (1.0.3)** — 필수. 런처 메뉴 패치가 이 판의 실행 파일에 맞춰져 있습니다 |
| DLC | 010038E016265001 — 있어도 없어도 됩니다 |

## 한글화 범위

- **록맨 에그제 1 / 2 / 3 (화이트·블랙)**: 대사·메뉴·칩 이름·설명 전부, 폰트(본문·메뉴·칩 이름용), 그림 글자(메뉴·폴더·결과·타이틀·상점 등)
- **컬렉션 런처**: 메인 메뉴·설정·통신 화면·PC 조작 안내, 갤러리(미스터리 데이터·뮤직 플레이어·트로피),
  배포 칩·개조 카드 설명, 안내 그림, 타이틀 로고 「콜렉션 1」
- 각 게임 대사는 기존 한글패치의 번역을 컬렉션 형식으로 옮긴 것입니다.
  - EXE1: EXE1 [K] 패치
  - EXE2: [rockman-exe2-kr-patch](https://github.com/Einbroch/rockman-exe2-kr-patch) v0.9.31
  - EXE3: [rockman-exe3-kr-patch](https://github.com/Einbroch/rockman-exe3-kr-patch) v0.9.3

## 설치

### 스위치 (Atmosphere)

1. `MMBNLC1_KR_v0.9.2_atmosphere.zip` 을 SD 카드 루트에 풉니다.
   - `atmosphere/contents/010038E016264000/romfs/...`
   - `atmosphere/exefs_patches/MMBNLC1_KoreanPatch/B6272978CA72D798209CD94C5AD2B14327024791.ips`
2. 본체 **시스템 언어를 「繁體中文」** 으로 둡니다(컬렉션은 시스템 언어로 표시 언어를 정합니다).

### 에뮬레이터 (Eden / yuzu 계열, Ryujinx)

1. `MMBNLC1_KR_v0.9.2_emulator.zip` 을 풀면 `KoreanPatch/` 폴더가 나옵니다.
2. 게임 우클릭 → 모드 폴더 열기(Open Mod Data Location)에 `KoreanPatch` 폴더째 넣습니다.
   - Eden/yuzu: `load/010038E016264000/KoreanPatch/{romfs,exefs}`
   - Ryujinx: `mods/contents/010038E016264000/KoreanPatch/{romfs,exefs}`
3. 에뮬레이터의 시스템 언어를 **번체 중국어(Traditional Chinese)** 로 둡니다.

## 알려진 점

- 한국어로 보려면 언어가 번체 중국어여야 합니다.
- 언어 선택 목록의 「日本語」·「简体中文」은 언어 이름이라 그대로 두었습니다.
- 타이틀 로고(ROCKMAN EXE)는 번체판과 같은 영어 로고 그대로입니다.
- 런처 실행 파일은 Vol.1·Vol.2 공용입니다. Vol.1 에 나오지 않는 Vol.2 전용 데이터(EXE4~6 칩 목록, Vol.2 아트·트로피 등)는 번체 그대로입니다.
  배포 칩·개조 카드 설명(EXE4~6 포함 700개)은 번역했습니다.
- 컬렉션은 모든 글자를 같은 폭(띄어쓰기도 한 칸)으로 찍어서, GBA 한글판 문장이 칩 설명 같은 좁은 상자에서는 넘칩니다.
  상자 폭을 원본 언어판에서 재서 넘치는 줄만 다시 나눴습니다(필요한 곳만 띄어쓰기 생략).
- 아직 모든 화면을 실제 플레이로 확인하지는 못했습니다(그래서 0.9 판입니다). 깨지거나 일본어·중국어가 남은 화면을 이슈로 알려 주세요.

## 도구 (`tools/`)

직접 빌드하려면 본편+업데이트 RomFS·exefs 를 추출하고 각 한글 롬을 준비해야 합니다(경로는 `tools/game_cfg.py`).

| 파일 | 하는 일 |
|---|---|
| `build_game.py exe1\|exe2\|exe3` | 한글 롬 대사 → 번체 칸 `message_cht.mpak/.map` + 폰트(EXE3 은 화이트·블랙 한 번에) |
| `gate_game.py <판> [--negative]` | 빌드한 mpak 을 다른 경로로 되읽어 한글 롬 원문과 대조(음성 대조 포함) |
| `krsrc.py` | 한글 롬 해석, 좁은 상자 재조판(`narrow_caps`·`rewrap`), 빌드·게이트 공통 후처리 |
| `game_cfg.py` | 게임별 설정(문자표, 폰트 페이지, 번체 고정 기호 칸, 부분 치환 등) |
| `ui_ko_exe1/2/3.py` | 게임 그림 글자(`*_ct`·`*_cht`·`*_tc`·`*_zt`) |
| `launcher_xaml.py` | 런처 실행 파일(NSO) 속 NoesisGUI XAML → exefs IPS32 패치(문서 구간 길이 유지) |
| `launcher_card_ko.py`, `launcher_gallery_text.py`, `lc_pairs.py` | 카드·갤러리·칩 목록 번역 생성 |
| `launcher_png.py`, `launcher_logo.py`, `launcher_gallery.py` | 런처 안내 그림·로고·갤러리 머리글·타이틀 글자 |
| `make_dist.py` | 배포 zip 두 벌 + SHA256SUMS |

폰트는 [에스코어 드림](https://www.s-core.co.kr/company/font/)(S-Core Dream)을 썼습니다.
