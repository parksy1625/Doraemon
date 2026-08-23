# DORA-001 — Take-copter

도라에몽의 `タケコプター`를 원작의 외형이 아니라 핵심 기능 기준으로 현실 공학 시스템으로 역설계한다.

## 목표

사람 1명이 착용하고 다음 기능을 수행할 수 있는 개인 비행 시스템의 축소형/무인 프로토타입을 단계적으로 개발한다.

- 수직 이륙
- 호버링
- 상승/하강
- 전후좌우 이동
- 자세 안정화
- 자동 착륙

## 개발 원칙

1. 1단계에서는 사람을 태우지 않는다.
2. 축소형 무인 플랫폼으로 추진/제어/전력 시스템을 검증한다.
3. 단일 머리 장착 프로펠러가 아니라 하중 분산 구조를 우선 검토한다.
4. 비행 소프트웨어는 수동 제어보다 안정화 제어를 먼저 검증한다.
5. 실제 탑승 단계는 별도의 안전 검토와 전문 항공 설계를 거친다.

## 단계

### DORA-001-A — Bench / Tethered Test

추진기, ESC, 전력계, IMU와 비행 컨트롤러를 고정 시험대에서 검증한다.

### DORA-001-B — Unmanned Prototype

4개 이상 추진기를 사용하는 소형 무인 플랫폼에서 호버링과 자세제어를 검증한다.

### DORA-001-C — Scaled Flight Platform

탑재 질량과 비행시간을 증가시키면서 추진/전력/제어/고장대응을 검증한다.

### DORA-001-D — Human-Carrying Feasibility Study

실제 사람 탑승 가능성을 별도 안전 프로젝트로 평가한다. 이 단계 이전에는 탑승 시험을 하지 않는다.

## 핵심 시스템

- Propulsion
- ESC / Motor Controller
- Flight Controller
- IMU / Barometer / GNSS
- Battery / Power Distribution
- Telemetry
- Emergency Stop
- Mechanical Frame / Harness

## 현재 상태

**Phase A — 요구사항 및 물리 모델 정의**
