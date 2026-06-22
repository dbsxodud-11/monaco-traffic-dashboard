# 🚦 Monaco 교통 네트워크 대시보드

SUMO 교통 시뮬레이션 결과를 추상화해 보여 주는 인터랙티브 대시보드입니다.
모나코 도로망에서 일부 도로를 제거/추가한 여러 네트워크의 **혼잡도**와
**교통 흐름 변화**를 한눈에 비교할 수 있습니다.

| 탭 | 내용 |
|----|------|
| 🗺️ **네트워크 탐색** | 네트워크를 선택하면 왼쪽에 혼잡도 지도(🟢 원활 → 🔴 정체)가 표시되고 ▶ 재생 버튼으로 시간에 따른 혼잡 변화를 애니메이션으로 볼 수 있습니다. 오른쪽에는 대기/주행/지연 시간 등 지표가 정리됩니다. |
| 🔀 **네트워크 비교** | 기존(`default`) 대비 🔴 제거된 도로 / 🔵 추가된 도로를 보여 주고, 도로 변화로 인한 교통 흐름 개선(🟢)을 시각화합니다. |

---

## 빠른 실행 (사전 생성된 데이터 사용 — SUMO 불필요)

저장소에 시뮬레이션 결과(`results/Monaco/dashboard/dashboard_data.pkl`)가
포함되어 있어, 별도 시뮬레이션 없이 바로 실행할 수 있습니다.

```bash
# 1) (권장) 가상환경 생성
python -m venv .venv && source .venv/bin/activate
#    또는: conda create -n monaco-dashboard python=3.10 && conda activate monaco-dashboard

# 2) 의존성 설치
pip install -r requirements.txt

# 3) 대시보드 실행
streamlit run dashboard.py
```

브라우저에서 자동으로 열리지 않으면 터미널에 표시되는 `http://localhost:8501`
주소로 접속하세요. 원격 서버에서 실행 중이라면 SSH 포트포워딩을 사용합니다:

```bash
ssh -L 8501:localhost:8501 <서버주소>
```

---

## 데이터 재생성 (선택 — SUMO 필요)

시뮬레이션부터 다시 돌려 데이터를 새로 만들려면 [Eclipse SUMO](https://eclipse.dev/sumo/)
(`sumo`, `netconvert` 바이너리)와 추가 패키지가 필요합니다.

```bash
# SUMO 설치 (예: Ubuntu)
sudo apt-get install sumo sumo-tools
export SUMO_HOME=/usr/share/sumo

# 추가 파이썬 패키지
pip install networkx sumolib traci matplotlib tqdm

# 데이터 생성 (base + 5개 네트워크, 1800초, 60초 단위)
python collect_dashboard_data.py --num_networks 5 --simulation_time 1800 --period 60
```

생성된 `results/Monaco/dashboard/dashboard_data.pkl` 을 대시보드가 읽습니다.

주요 옵션:
- `--num_networks` : 생성할 변형 네트워크 수
- `--simulation_time` : 시뮬레이션 길이(초)
- `--period` : 혼잡도 집계 간격(초). 작을수록 애니메이션 프레임이 촘촘해짐
- `--seed` : 난수 시드

---

## 구조

```
monaco-dashboard/
├── dashboard.py                 # Streamlit 대시보드 (메인 산출물)
├── collect_dashboard_data.py    # SUMO 시뮬레이션 → 대시보드용 데이터 생성
├── data_collection_monaco.py    # 네트워크 생성 유틸 (collect 스크립트가 사용)
├── requirements.txt
├── .streamlit/config.toml       # 다크 테마 설정
├── sumo/Monaco/                 # SUMO 입력 (도로망 + 교통 수요)
│   ├── default.net.xml          # 기존(원본) 네트워크
│   ├── default_dense.net.xml    # 변형 네트워크 생성용 조밀 네트워크
│   ├── default_dense.rou.xml    # 교통 수요(라우트)
│   └── eternal_edges.pkl        # 제거 불가 도로 캐시
└── results/Monaco/dashboard/
    └── dashboard_data.pkl       # 사전 생성된 시뮬레이션 결과
```

## 동작 원리 (요약)

- 각 도로(edge)의 **혼잡도 = 평균 주행속도 ÷ 제한속도** (1에 가까울수록 원활).
- SUMO의 `edgeData` 출력을 시간대별로 집계해 색으로 표현합니다.
- 비교 탭의 흐름 변화는 동일한 교통 수요(`default_dense.rou.xml`)로
  기존 네트워크와 변형 네트워크를 각각 시뮬레이션해 도로별 혼잡도 차이를 계산합니다.
