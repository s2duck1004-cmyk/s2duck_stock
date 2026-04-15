# 📈 CAN SLIM KR — 한국주식 스크리너

윌리엄 오닐의 CAN SLIM 기법을 기반으로 한 한국주식 일일 스크리닝 대시보드입니다.

---

## 🚀 GitHub Pages 배포 방법 (처음 1회만)

### 1단계 — GitHub 계정 만들기
1. [github.com](https://github.com) 접속
2. **Sign up** 클릭 → 이메일, 비밀번호, 사용자명 입력
3. 이메일 인증 완료

### 2단계 — 새 저장소(Repository) 만들기
1. 로그인 후 오른쪽 위 **+** 버튼 → **New repository**
2. Repository name: `canslim-kr` (또는 원하는 이름)
3. **Public** 선택 (꼭 Public이어야 GitHub Pages 무료 사용 가능)
4. **Create repository** 클릭

### 3단계 — 파일 업로드
1. 새 저장소 페이지에서 **uploading an existing file** 클릭
2. 이 폴더의 파일들을 모두 드래그앤드롭:
   - `index.html`
   - `fetch_data.py`
   - `data/stocks.json` ← **data 폴더째로** 업로드
   - `.github/workflows/update.yml` ← **.github 폴더째로** 업로드
3. **Commit changes** 클릭

> 💡 **팁**: 폴더 구조 유지가 중요합니다. `.github/workflows/update.yml` 경로가 그대로여야 Actions가 작동합니다.

### 4단계 — GitHub Pages 활성화
1. 저장소 페이지 → **Settings** 탭
2. 왼쪽 메뉴 **Pages** 클릭
3. Source: **Deploy from a branch**
4. Branch: **main** / **/ (root)** 선택
5. **Save** 클릭
6. 잠시 후 `https://[내 아이디].github.io/canslim-kr/` 주소 생성!

### 5단계 — 업데이트 버튼 주소 연결
`index.html` 파일에서 아래 부분을 본인 정보로 수정:

```html
<!-- 현재 -->
<a class="update-btn" id="actionBtn" href="#" target="_blank">

<!-- 수정 후 (본인 아이디와 저장소명으로 교체) -->
<a class="update-btn" id="actionBtn" href="https://github.com/[내아이디]/canslim-kr/actions/workflows/update.yml" target="_blank">
```

---

## 🔄 데이터 업데이트 방법

1. `https://github.com/[내아이디]/canslim-kr/actions` 접속
2. 왼쪽에서 **📈 CAN SLIM 데이터 업데이트** 클릭
3. 오른쪽 **Run workflow** 버튼 클릭
4. 초록색 **Run workflow** 버튼 클릭
5. 약 1~2분 후 데이터 자동 업데이트 완료!

또는 대시보드 상단의 **▶ 데이터 업데이트** 버튼 클릭 (위 5단계 완료 후)

---

## 📊 로컬에서 데이터 직접 수집하기

```bash
# 패키지 설치
pip install yfinance numpy

# 실행
python fetch_data.py
```

---

## 🏗 파일 구조

```
canslim-kr/
├── index.html                    # 대시보드 메인 페이지
├── fetch_data.py                 # Yahoo Finance 데이터 수집기
├── data/
│   └── stocks.json               # 수집된 데이터 (자동 업데이트)
└── .github/
    └── workflows/
        └── update.yml            # GitHub Actions 워크플로우
```

---

## ⚠ 주의사항

- 본 시스템은 정보 제공 목적으로만 사용됩니다
- 투자 권유가 아니며 실제 투자 손실에 대한 책임을 지지 않습니다
- Yahoo Finance 무료 API 특성상 일부 재무 데이터는 추정값일 수 있습니다
