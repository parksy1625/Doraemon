# Doraemon Engineering Project

도라에몽의 비밀도구를 수집하고, 각 도구를 현대 과학·공학 관점에서 분석해 현실 구현 가능성을 연구하는 프로젝트입니다.

## 현재 단계

- Phase 0: 도구 Master Database 구축
- 원작/애니/극장판/게임 출처를 구분
- 별칭과 중복 도구 정규화
- 설명문은 외부 자료를 그대로 복제하지 않고 프로젝트용 요약으로 작성

## 데이터 구조

- `data/gadgets.seed.json` : 초기 대표 도구 목록
- `data/schema.json` : Master Gadget Database 스키마
- `docs/sources.md` : 수집 출처와 규칙

## 향후 단계

1. 원작 만화 도구 우선 수집
2. 애니메이션·극장판·게임 공식 도구 병합
3. 한국어/일본어/영어 명칭 정규화
4. 도구별 구현 가능도(A~E) 평가
5. 실제 설계 프로젝트와 연결
