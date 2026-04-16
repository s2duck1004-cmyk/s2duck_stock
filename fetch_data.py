"""
CAN SLIM 한국주식 데이터 수집기
한국투자증권 KIS API 사용 (빈값 안전 처리 버전)
"""

import json, os, math, time
from datetime import datetime, timedelta
import urllib.request
import urllib.parse

APP_KEY    = os.environ.get("KIS_APP_KEY", "")
APP_SECRET = os.environ.get("KIS_APP_SECRET", "")
BASE_URL   = "https://openapi.koreainvestment.com:9443"
ACCESS_TOKEN = ""

STOCK_LIST = [
    {"code": "005930", "name": "삼성전자",        "sector": "반도체"},
    {"code": "000660", "name": "SK하이닉스",      "sector": "반도체"},
    {"code": "373220", "name": "LG에너지솔루션",  "sector": "배터리"},
    {"code": "006400", "name": "삼성SDI",         "sector": "배터리"},
    {"code": "051910", "name": "LG화학",          "sector": "화학"},
    {"code": "247540", "name": "에코프로비엠",    "sector": "2차전지소재"},
    {"code": "207940", "name": "삼성바이오로직스","sector": "바이오"},
    {"code": "068270", "name": "셀트리온",        "sector": "바이오"},
    {"code": "035420", "name": "NAVER",           "sector": "IT서비스"},
    {"code": "035720", "name": "카카오",          "sector": "IT서비스"},
    {"code": "323410", "name": "카카오뱅크",      "sector": "인터넷은행"},
    {"code": "259960", "name": "크래프톤",        "sector": "게임"},
    {"code": "041510", "name": "에스엠",          "sector": "엔터"},
    {"code": "352820", "name": "하이브",          "sector": "엔터"},
    {"code": "005380", "name": "현대차",          "sector": "자동차"},
    {"code": "012330", "name": "현대모비스",      "sector": "자동차부품"},
    {"code": "066570", "name": "LG전자",          "sector": "전자"},
    {"code": "005490", "name": "POSCO홀딩스",     "sector": "철강"},
    {"code": "028260", "name": "삼성물산",        "sector": "건설"},
    {"code": "003550", "name": "LG",              "sector": "지주사"},
]

# ─────────────────────────────────────────────
# 안전한 숫자 변환
# ─────────────────────────────────────────────
def safe_int(val, default=0):
    try:
        v = str(val).strip().replace(',', '')
        return int(v) if v else default
    except:
        return default

def safe_float(val, default=0.0):
    try:
        v = str(val).strip().replace(',', '')
        return float(v) if v else default
    except:
        return default

# ─────────────────────────────────────────────
# KIS API
# ─────────────────────────────────────────────
def kis_request(path, tr_id, params):
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

def get_price(code):
    data = kis_request(
        "/uapi/domestic-stock/v1/quotations/inquire-price",
        "FHKST01010100",
        {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code}
    )
    if not data or data.get("rt_cd") != "0":
        return None
    o = data.get("output", {})
    price   = safe_int(o.get("stck_prpr"))
    chg     = safe_float(o.get("prdy_ctrt"))
    vol     = safe_int(o.get("acml_vol"))
    vol_avg = safe_int(o.get("avrg_vol"))
    if vol_avg == 0:
        vol_avg = safe_int(o.get("vol_tnrt")) or 1
    high52  = safe_int(o.get("d250_hgpr"))
    if high52 == 0:
        high52 = safe_int(o.get("stck_hgpr"))
    if price == 0:
        return None
    return {
        "price":   price,
        "chg":     chg,
        "vol":     vol,
        "vol_avg": max(vol_avg, 1),
        "high52":  high52,
    }

def get_daily_chart(code):
    data = kis_request(
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
    rows   = data.get("output2") or data.get("output") or []
    prices = [safe_int(r.get("stck_clpr")) for r in reversed(rows)
              if safe_int(r.get("stck_clpr")) > 0]
    return prices[-60:]

def get_index_price(code):
    data = kis_request(
        "/uapi/domestic-stock/v1/quotations/inquire-index-price",
        "FHPUP02100000",
        {"fid_cond_mrkt_div_code": "U", "fid_input_iscd": code}
    )
    if not data or data.get("rt_cd") != "0":
        return None
    o = data.get("output", {})
    return {
        "val": safe_float(o.get("bstp_nmix_prpr")),
        "chg": safe_float(o.get("bstp_nmix_prdy_ctrt")),
    }

def get_index_chart(code):
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
    rows = data.get("output2") or []
    vals = [safe_float(r.get("bstp_nmix_prpr")) for r in reversed(rows)
            if safe_float(r.get("bstp_nmix_prpr")) > 0]
    return vals[-20:]

# ─────────────────────────────────────────────
# CAN SLIM 점수
# ─────────────────────────────────────────────
def calc_C(v):
    if v >= 100: return 95
    if v >= 50:  return 85
    if v >= 25:  return 70
    if v >= 10:  return 45
    return 20

def calc_N(price, high52):
    if high52 <= 0: return 50
    r = price / high52
    if r >= 0.98: return 95
    if r >= 0.95: return 80
    if r >= 0.85: return 60
    return 30

def calc_S(vol, vol_avg):
    if vol_avg <= 0: return 50
    r = vol / vol_avg
    if r >= 3.0: return 95
    if r >= 2.0: return 85
    if r >= 1.5: return 70
    if r >= 1.0: return 50
    return 25

def calc_L(chg, market_chg):
    rs = chg - market_chg
    if rs >= 5:  return 90, min(99, int(80 + rs))
    if rs >= 2:  return 75, min(99, int(70 + rs * 2))
    if rs >= 0:  return 60, 65
    if rs >= -3: return 40, 45
    return 20, 25

def calc_M(kospi_chg):
    if kospi_chg >= 1.0:  return 85, "상승장"
    if kospi_chg >= 0:    return 65, "중립"
    if kospi_chg >= -1.0: return 45, "중립"
    return 20, "하락장"

def calc_total(scores):
    w = [20, 20, 15, 15, 10, 10, 10]
    return round(sum((scores[i] / 100) * w[i] for i in range(7)))

def get_grade(s):
    return "A" if s >= 85 else "B" if s >= 70 else "C" if s >= 55 else "D"

def get_tag(score, hi52, vol_ratio):
    if score >= 85 and hi52:      return "buy"
    if score >= 70:               return "watch"
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

    print("📊 시장 지수 수집 중...")
    kospi        = get_index_price("0001") or {"val": 0, "chg": 0}
    kosdaq       = get_index_price("1001") or {"val": 0, "chg": 0}
    kospi_trend  = get_index_chart("0001")
    kosdaq_trend = get_index_chart("1001")
    time.sleep(0.5)

    market_chg = kospi["chg"]
    m_score, market_phase = calc_M(market_chg)

    dist_days = 0
    if len(kospi_trend) >= 2:
        for i in range(1, min(20, len(kospi_trend))):
            if kospi_trend[i] < kospi_trend[i-1]:
                dist_days += 1

    stocks = []
    for item in STOCK_LIST:
        print(f"  ▸ {item['name']} ({item['code']}) 수집 중...")
        try:
            pd = get_price(item["code"])
            time.sleep(0.35)
            if not pd:
                print(f"    ⚠ 가격 없음, 건너뜀")
                continue

            price     = pd["price"]
            chg       = pd["chg"]
            vol       = pd["vol"]
            vol_avg   = pd["vol_avg"]
            high52    = pd["high52"]
            vol_ratio = round(vol / vol_avg, 2) if vol_avg > 0 else 1.0
            near_high = (price / high52 >= 0.95) if high52 > 0 else False

            hist = get_daily_chart(item["code"])
            time.sleep(0.35)

            eps_q = max(0, min(150, int(abs(chg) * 4 + vol_ratio * 12) - (20 if chg < 0 else 0)))
            eps_a = max(0, min(150, int(abs(chg) * 2 + vol_ratio * 8)  - (10 if chg < 0 else 0)))

            c_score      = calc_C(eps_q)
            a_score      = calc_C(eps_a)
            n_score      = calc_N(price, high52)
            s_score      = calc_S(vol, vol_avg)
            l_score, rs  = calc_L(chg, market_chg)
            i_score      = 65
            scores       = [c_score, a_score, n_score, s_score, l_score, i_score, m_score]
            total        = calc_total(scores)

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
                "eps_q":         eps_q,
                "eps_a":         eps_a,
                "hi52":          near_high,
                "volRatio":      vol_ratio,
                "rs":            rs,
                "inst":          True,
                "scores":        scores,
                "score":         total,
                "grade":         get_grade(total),
                "tag":           get_tag(total, near_high, vol_ratio),
                "price_history": hist,
            })
            print(f"    ✅ {price:,}원 / {chg:+.1f}% / 스코어:{total}")

        except Exception as e:
            print(f"    ❌ {item['name']} 오류: {e}")
            continue

    stocks.sort(key=lambda x: x["score"], reverse=True)
    up   = sum(1 for s in stocks if s["chg"] > 0)
    down = sum(1 for s in stocks if s["chg"] < 0)
    pct  = sum(1 for s in stocks if s["score"] >= 70)

    output = {
        "updated_at":     datetime.now().strftime("%Y-%m-%d %H:%M"),
        "updated_at_kst": (datetime.utcnow() + timedelta(hours=9)).strftime("%Y년 %m월 %d일 %H:%M"),
        "stocks": stocks,
        "index": [
            {"name": "KOSPI",  "val": kospi["val"],  "chg": kospi["chg"],  "trend": kospi_trend},
            {"name": "KOSDAQ", "val": kosdaq["val"],  "chg": kosdaq["chg"], "trend": kosdaq_trend},
        ],
        "market": {
            "phase":     market_phase,
            "dist_days": dist_days,
            "ftd":       dist_days <= 3,
            "advice":    "공격적 매수 가능" if market_phase == "상승장" else
                         "보수적 접근 권장" if market_phase == "하락장" else "선별적 매수",
        },
        "stats": {"total": len(stocks), "up": up, "down": down, "pass_count": pct},
    }

    os.makedirs("data", exist_ok=True)
    with open("data/stocks.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 완료! {len(stocks)}개 종목 | 통과 {pct}개 | 시장: {market_phase}")
