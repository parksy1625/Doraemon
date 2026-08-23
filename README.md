# Doraemon Engineering Project

도라에몽의 비밀도구를 수집하고, 각 도구를 현대 과학·공학 관점에서 분석해 현실 구현 가능성을 연구하는 프로젝트입니다.

## 현재 단계

- Phase 0: 도구 Master Database 구축
- 원작/애니/극장판/게임 출처를 구분
- 별칭과 중복 도구 정규화
- 설명문은 외부 자료를 그대로 복제하지 않고 프로젝트용 요약으로 작성
- 공개 원천 데이터 정적 수집 배치 A~F 구축 완료
- 깨진 일본어명 필드(`General InformationFunctionsDetails` 등) 자동 제외 규칙 적용
- 중복/별칭 후보를 별도 검토 목록으로 관리

## 데이터 구조

- `data/gadgets.seed.json` : 초기 대표 도구 목록
- `data/schema.json` : Master Gadget Database 스키마
- `data/upstream/` : 외부 공개 자료에서 수집한 이름 중심 정적 배치
- `data/duplicate-candidates.json` : 수동 검토 중복/별칭 후보
- `scripts/build_catalog.py` : 네트워크 기반 카탈로그 빌더
- `scripts/build_static_catalog.py` : 저장소 내부 정적 배치 기반 오프라인 빌더
- `docs/sources.md` : 수집 출처와 규칙

## 수집 진행 상태

현재 Yobubble 공개 데이터셋의 앞·중간·후반 구간을 나눠 A~F 배치로 수집하고 있습니다. `Take-copter`, `Anywhere Door`, `Gulliver Tunnel`, `Mini Black Hole`, `Time` 계열, `Translation Konjac`, `What-If Phone Booth`, `Voodoo Camera`, `Weather Exchange Map` 등 대표 도구와 다수의 비주류 도구가 포함되어 있습니다.

다음 목표는 일본어 원작 도구 목록을 기준축으로 삼아 **원작 만화 도구 434개 후보군**을 우선 완성하고, 이후 애니메이션·극장판·게임 전용 도구를 병합하는 것입니다.

## 향후 단계

1. 원작 만화 도구 우선 수집
2. 일본어 원작 목록과 현재 공개 데이터셋 교차검증
3. 애니메이션·극장판·게임 공식 도구 병합
4. 한국어/일본어/영어 명칭 정규화
5. 도구별 구현 가능도(A~E) 평가
6. 실제 설계 프로젝트와 연결
