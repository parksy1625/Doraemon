# DORA-001 Requirements

## Functional requirements

| ID | Requirement | Target |
|---|---|---|
| FR-01 | 수직 이륙/착륙 | 가능 |
| FR-02 | 안정적 호버링 | 자동 자세제어 |
| FR-03 | 상승/하강 | 추력 제어 |
| FR-04 | 전후좌우 이동 | 자세/추력 벡터 제어 |
| FR-05 | 자동 자세 복원 | IMU 기반 |
| FR-06 | 비상 정지 | 독립 하드웨어 경로 |
| FR-07 | 원격 텔레메트리 | 시험 단계에서 필수 |

## Engineering constraints

- 초기 시험은 무인 상태로 제한한다.
- 추진계는 추력 여유를 확보하도록 선정한다.
- 배터리는 최대전류와 열 조건을 포함해 검토한다.
- 프로펠러/팬 파손에 대한 물리적 방호를 고려한다.
- 단일 센서 고장에 의존하지 않는 안전 구조를 목표로 한다.

## Initial mass model

초기 설계변수:

- `m_frame`: 프레임 질량
- `m_motor`: 모터/추진계 질량
- `m_battery`: 배터리 질량
- `m_electronics`: 전자장치 질량
- `m_payload`: 시험 탑재 질량

총 질량:

`m_total = m_frame + m_motor + m_battery + m_electronics + m_payload`

정지 호버링에 필요한 최소 총추력:

`T_hover >= m_total * g`

여기서 `g = 9.80665 m/s²`.

실제 추진계는 최소 호버링 값보다 높은 최대추력과 제어 여유를 가져야 한다. 구체적인 추력/전력 수치는 실측 데이터와 선정한 추진계에 따라 결정한다.
