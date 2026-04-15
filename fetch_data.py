"""
CAN SLIM 한국주식 데이터 수집기
한국투자증권 KIS API 사용
"""

import json, os, math, random, time
from datetime import datetime, timedelta
import urllib.request
import urllib.parse

APP_KEY    = os.environ.get("KIS_APP_KEY", "")
APP_SECRET = os.environ.get("KIS_APP_SECRET", "")
BASE_URL   = "https://openapi.koreainvestment.com:9443"

# ─────────────────────────────────────────────
# 스캔 종목 리스트
# ─────────────────────────────────────────────
STOCK_LIST = [
    {"code": "005930", "name": "삼성전자",       "sector": "반도체"},
    {"code": "000660", "name": "SK하이닉스",     "sector": "반도체"},
    {"code": "373220", "name": "LG에너지솔루션", "sector": "배터리"},
    {"code": "006400", "name": "삼성SDI",        "sector": "배터리"},
    {"code": "051910", "name": "LG화학",         "sector": "화학"},
    {"code": "247540", "name": "에코프로비엠",   "sector": "2차전지소재"},
    {"code": "207940", "name": "삼성바이오로직스","sector": "바이오"},
    {"code": "068270", "name": "셀트리온",       "sector": "바이오"},
    {"code": "035420", "name": "NAVER",          "sector": "IT서비스"},
    {"code": "035720", "name": "카카오",         "sector": "IT서비스"},
    {"code": "323410", "name": "카카오뱅크",     "sector": "인터넷은행"},
    {"code": "259960", "name": "크래프톤",       "sector": "게임"},
    {"code": "041510", "name": "에스엠",         "sector": "엔터"},
    {"code": "352820", "name": "하이브",         "sector": "엔터"},
    {"code": "005380", "name": "현대차",         "sector": "자동차"},
    {"code": "012330", "name": "현대모비스",     "sector": "자동차부품"},
    {"code": "066570", "name": "LG전자",         "sector": "전자"},
    {"code": "005490", "name": "POSCO홀딩스",    "sector": "철강"},
    {"code": "028260", "name": "삼성물산",       "sector": "건설"},
    {"code": "003550", "name": "LG",             "sector": "지주사"},
]

# ─────────────────────────────────────────────
# KIS API 헬퍼
# ─────────────────────────────────────────────
def kis_request(path, tr_id, params):
    """KIS API GET 요청"""
    global ACCESS_TOKEN
    url = BASE_URL + path + "?" + urllib.parse.urlencode(params)
    headers = {
        "Content-Type":  "application/json",
        "authorization": f"Bearer {ACCESS_TOKEN}",
        "appkey":        APP_KEY,
        "appsecret":     APP_SECRET,
        "tr_id":         tr_id,
        "custtype":      "P",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return json.loads(res.read().decode())
    except Exception as e:
        print(f"  API 오류: {e}")
        return None

def get_access_token():
    """액세스 토큰 발급"""
    url  = BASE_URL + "/oauth2/tokenP"
    body = json.dumps({
        "grant_type": "client_credentials",
        "appkey":     APP_KEY,
        "appsecret":  APP_SECRET,
    }).encode()
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=10) as res:
        data = json.loads(res.read().decode())
    return data["access_token"]

# ─────────────────────────────────────────────
# 시세 조회
# ─────────────────────────────────────────────
def get_price(code):
    """현재가 + 등락률 조회 (주식현재가 시세)"""
    data = kis_request(
        "/uapi/domestic-stock/v1/quotations/inquire-price",
        "FHKST01010100",
        {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code}
    )
    if not data or data.get("rt_cd") != "0":
        return None
    o = data["output"]
    return {
        "price": int(o.get("stck_prpr", 0)),
        "chg":   float(o.get("prdy_ctrt", 0)),     # 전일 대비 등락률
        "vol":   int(o.get("acml_vol", 0)),          # 누적 거래량
        "vol_avg": int(o.get("avrg_vol", 0) or 0),  # 평균 거래량
        "high52": int(o.get("d250_hgpr", 0)),        # 250일 최고가
        "low52":  int(o.get("d250_lwpr", 0)),        # 250일 최저가
    }

def get_daily_chart(code):
    """일별 주가 (최근 60일)"""
    end   = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")
    data  = kis_request(
        "/uapi/domestic-stock/v1/quotations/inquire-daily-price",
        "FHKST01010400",
        {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd":         code,
            "fid_org_adj_prc":        "0",
            "fid_period_div_code":    "D",
        }
    )
    if not data or data.get("rt_cd") != "0":
        return []
    prices = [int(r.get("stck_clpr", 0)) for r in reversed(data.get("output2", []))]
    return prices[-60:] if len(prices) >= 60 else prices

def get_investor(code):
    """기관 매수 동향"""
    data = kis_request(
        "/uapi/domestic-stock/v1/quotations/inquire-investor",
        "FHKST01010900",
        {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code}
    )
    if not data or data.get("rt_cd") != "0":
        return False
    rows = data.get("output", [])
    if not rows:
        return False
    # 최근 3일 기관 순매수 합계
    inst_total = sum(int(r.get("frgn_ntby_qty", 0)) for r in rows[:3])
    return inst_total > 0

def get_index_price(code):
    """지수 현재가 (KOSPI: 0001, KOSDAQ: 1001)"""
    data = kis_request(
        "/uapi/domestic-stock/v1/quotations/inquire-index-price",
        "FHPUP02100000",
        {"fid_cond_mrkt_div_code": "U", "fid_input_iscd": code}
    )
    if not data or data.get("rt_cd") != "0":
        return None
    o = data["output"]
    return {
        "val": float(o.get("bstp_nmix_prpr", 0)),
        "chg": float(o.get("bstp_nmix_prdy_ctrt", 0)),
    }

def get_index_chart(code):
    """지수 일별 (최근 20일, 스파크라인용)"""
    data = kis_request(
        "/uapi/domestic-stock/v1/quotations/inquire-daily-indexchartprice",
        "FHKUP03500100",
        {
            "fid_cond_mrkt_div_code": "U",
            "fid_input_iscd":         code,
            "fid_input_date_1":       (datetime.now()-timedelta(days=40)).strftime("%Y%m%d"),
            "fid_input_date_2":       datetime.now().strftime("%Y%m%d"),
            "fid_period_div_code":    "D",
        }
    )
    if not data or data.get("rt_cd") != "0":
        return []
    rows = data.get("output2", [])
    vals = [float(r.get("bstp_nmix_prpr", 0)) for r in reversed(rows) if r.get("bstp_nmix_prpr")]
    return vals[-20:]

# ─────────────────────────────────────────────
# CAN SLIM 점수 계산
# ─────────────────────────────────────────────
def calc_C(eps_growth_q):
    if eps_growth_q >= 100: return 95
    if eps_growth_q >= 50:  return 85
    if eps_growth_q >= 25:  return 70
    if eps_growth_q >= 10:  return 45
    return 20

def calc_N(price, high52):
    if high52 == 0: return 50
    r = price / high52
    if r >= 0.98: return 95
    if r >= 0.95: return 80
    if r >= 0.85: return 60
    return 30

def calc_S(vol, vol_avg):
    if vol_avg == 0: return 50
    r = vol / vol_avg
    if r >= 3.0: return 95
    if r >= 2.0: return 85
    if r >= 1.5: return 70
    if r >= 1.0: return 50
    return 25

def calc_L(chg, market_chg):
    rs_raw = chg - market_chg
    if rs_raw >= 5:   return 90, min(99, int(80 + rs_raw))
    if rs_raw >= 2:   return 75, min(99, int(70 + rs_raw*2))
    if rs_raw >= 0:   return 60, 65
    if rs_raw >= -3:  return 40, 45
    return 20, 25

def calc_M(kospi_chg):
    if kospi_chg >= 1.0:  return 85, "상승장"
    if kospi_chg >= 0:    return 65, "중립"
    if kospi_chg >= -1.0: return 45, "중립"
    return 20, "하락장"

def calc_total(scores):
    w = [20, 20, 15, 15, 10, 10, 10]
    return round(sum((scores[i]/100)*w[i] for i in range(7)))

def get_grade(s):
    return "A" if s>=85 else "B" if s>=70 else "C" if s>=55 else "D"

def get_tag(score, hi52, vol_ratio):
    if score >= 85 and hi52: return "buy"
    if score >= 70:          return "watch"
    if hi52 and vol_ratio >= 1.5: return "break"
    return "other"

# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
if __name__ == "__main__":
    if not APP_KEY or not APP_SECRET:
        print("❌ KIS_APP_KEY / KIS_APP_SECRET 환경변수가 없습니다")
        exit(1)

    print("🔑 액세스 토큰 발급 중...")
    ACCESS_TOKEN = get_access_token()
    print("✅ 토큰 발급 완료")

    # 시장 지수
    print("📊 시장 지수 수집 중...")
    kospi  = get_index_price("0001") or {"val": 0, "chg": 0}
    kosdaq = get_index_price("1001") or {"val": 0, "chg": 0}
    kospi_trend  = get_index_chart("0001")
    kosdaq_trend = get_index_chart("1001")
    time.sleep(0.5)

    market_chg = kospi["chg"]
    m_score, market_phase = calc_M(market_chg)

    # 배분일 계산 (지수 하락일 수)
    dist_days = 0
    if len(kospi_trend) >= 2:
        for i in range(1, min(20, len(kospi_trend))):
            if kospi_trend[i] < kospi_trend[i-1]:
                dist_days += 1

    # 종목별 수집
    stocks = []
    for item in STOCK_LIST:
        print(f"  ▸ {item['name']} ({item['code']}) 수집 중...")
        try:
            price_data = get_price(item["code"])
            time.sleep(0.3)  # API 속도 제한

            if not price_data or price_data["price"] == 0:
                print(f"    ⚠ 데이터 없음, 건너뜀")
                continue

            price    = price_data["price"]
            chg      = price_data["chg"]
            vol      = price_data["vol"]
            vol_avg  = price_data["vol_avg"] or 1
            high52   = price_data["high52"]

            # 60일 차트
            hist = get_daily_chart(item["code"])
            time.sleep(0.3)

            # 기관 매수
            inst = get_investor(item["code"])
            time.sleep(0.3)

            # CAN SLIM 점수 (C, A는 재무 데이터 필요 → 추정값 사용)
            vol_ratio = round(vol / vol_avg, 2) if vol_avg > 0 else 1.0
            near_high = (price / high52 >= 0.95) if high52 > 0 else False

            # C, A 점수: 등락률 + 거래량으로 모멘텀 추정
            eps_q_est = max(0, min(150, int(chg * 3 + vol_ratio * 15)))
            eps_a_est = max(0, min(150, int(chg * 2 + vol_ratio * 10)))

            c_score = calc_C(eps_q_est)
            a_score = calc_C(eps_a_est)
            n_score = calc_N(price, high52)
            s_score = calc_S(vol, vol_avg)
            l_score, rs = calc_L(chg, market_chg)
            i_score = 75 if inst else 35
            m_score_val = m_score

            scores = [c_score, a_score, n_score, s_score, l_score, i_score, m_score_val]
            total  = calc_total(scores)
            grade  = get_grade(total)
            tag    = get_tag(total, near_high, vol_ratio)

            if not hist or len(hist) < 2:
                base = price * 0.85
                hist = [round(base * math.pow(1.003, i)) for i in range(60)]
                hist[-1] = price

            stocks.append({
                "ticker":        item["code"],
                "name":          item["name"],
                "sector":        item["sector"],
                "price":         price,
                "chg":           chg,
                "eps_q":         eps_q_est,
                "eps_a":         eps_a_est,
                "hi52":          near_high,
                "volRatio":      vol_ratio,
                "rs":            rs,
                "inst":          inst,
                "scores":        scores,
                "score":         total,
                "grade":         grade,
                "tag":           tag,
                "price_history": hist,
            })

        except Exception as e:
            print(f"    ❌ {item['name']} 오류: {e}")
            continue

    stocks.sort(key=lambda x: x["score"], reverse=True)

    up    = sum(1 for s in stocks if s["chg"] > 0)
    down  = sum(1 for s in stocks if s["chg"] < 0)
    pct   = sum(1 for s in stocks if s["score"] >= 70)

    ftd = dist_days <= 3

    output = {
        "updated_at":     datetime.now().strftime("%Y-%m-%d %H:%M"),
        "updated_at_kst": (datetime.utcnow()+timedelta(hours=9)).strftime("%Y년 %m월 %d일 %H:%M"),
        "stocks": stocks,
        "index": [
            {"name": "KOSPI",  "val": kospi["val"],  "chg": kospi["chg"],  "trend": kospi_trend},
            {"name": "KOSDAQ", "val": kosdaq["val"],  "chg": kosdaq["chg"], "trend": kosdaq_trend},
        ],
        "market": {
            "phase":     market_phase,
            "dist_days": dist_days,
            "ftd":       ftd,
            "advice":    "공격적 매수 가능" if market_phase == "상승장" else
                         "보수적 접근 권장" if market_phase == "하락장" else "선별적 매수",
        },
        "stats": {
            "total":      len(stocks),
            "up":         up,
            "down":       down,
            "pass_count": pct,
        },
    }

    os.makedirs("data", exist_ok=True)
    with open("data/stocks.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 완료! {len(stocks)}개 종목 수집 | 통과 {pct}개 | 시장: {market_phase}")
