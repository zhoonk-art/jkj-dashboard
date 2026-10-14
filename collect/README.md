# 시장 데이터 자동 수집

`invest.html` 의 **삼성전자 PER/PBR 비교**와 **실거래가 vs 호가** 차트에 쓰이는 데이터를
GitHub Actions(`.github/workflows/collect.yml`)가 평일 16:30(KST)에 모아서 `data/*.json` 으로 커밋합니다.

## 1. 관심 종목·단지 정하기 — `config/watch.json`
- `stocks`: `{ "code": "005930", "name": "삼성전자" }`
- `apartments` 예시:
  ```json
  { "id": "mapo-raemian", "name": "마포래미안푸르지오 84㎡", "lawdCd": "11440",
    "dong": "아현동", "aptNm": "마포래미안푸르지오", "area": 84, "areaTol": 1.5 }
  ```
  - `lawdCd`: 시군구 법정동코드 앞 5자리 (예: 마포구 11440). 행정표준코드관리시스템에서 확인
  - `aptNm`: 실거래 신고상 단지명. 부분 일치, 공백 무시
  - `area`: 전용면적(㎡), `areaTol`: 허용 오차
- ⚠️ 이 저장소는 GitHub Pages 로 공개되므로 관심 단지가 노출됩니다.

## 2. 실거래가 API 키 (한 번만)
1. data.go.kr 가입 → **국토교통부_아파트 매매 실거래가 상세 자료** 활용 신청 (자동 승인)
2. 저장소 **Settings → Secrets and variables → Actions → New repository secret**
   이름 `DATA_GO_KR_KEY`, 값은 발급받은 **일반 인증키**

## 3. 실행
**Actions → Collect market data → Run workflow**. 처음엔 `months` 를 24 로 두면 2년치 실거래가를 채웁니다.
이후엔 매 평일 자동 실행됩니다.

## 알아둘 점
- **PER/PBR 과거 이력은 받아오지 않습니다.** 선행 값은 과거 컨센서스를 무료로 받을 수 없어서,
  첫 실행한 날부터 하루 한 점씩 쌓입니다. 과거치가 필요하면 `data/market.json` 의 `rows` 에 직접 채워 넣을 수 있어요.
- 선행 PER = 네이버 금융 추정PER, 선행 PBR = 현재가 ÷ 컨센서스 BPS(추정 첫 해, 직접 계산).
- 호가는 공식 API 가 없어서 차트 카드의 **호가 입력**으로 직접 기록합니다.
- 응답 형식이 바뀌면 Actions 가 실패하며 로그에 읽지 못한 항목이 나옵니다.
- 로컬 테스트: `python -m unittest discover -s collect`
