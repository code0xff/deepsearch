# Outline — Ethereum Attestation Service 심층 분석 및 자체 구현 아키텍처

1. **Abstract** — EAS의 핵심 개념, 현재 생태계 위치, 자체 구현 시 요구사항의 요약(150–250 단어).
2. **Introduction (서론)** — 온체인 신원·평판·증명 인프라의 필요성, 본 리포트의 범위와 경계(왜 EAS를 다루는가, 자체 구현까지 보는 이유).
3. **Background (배경)** — Attestation의 일반 개념, W3C Verifiable Credentials / DID, Soulbound Token(ERC-5114/ERC-5192) 등 선행 설계, SBT와 Attestation의 차이.
4. **EAS 프로토콜 구조 (Current state)** — 핵심 컨트랙트(`EAS`, `SchemaRegistry`), 온체인/오프체인 어테스테이션, 스키마·리졸버·revocation·timestamp 기능, 배포 네트워크.
5. **생태계와 활용 사례 (Analysis)** — Optimism Attestation Station/Coinbase Verifications/Gitcoin Passport 등 실제 사용 사례, 누적 어테스테이션 규모, 타 프로토콜(예: Verax, Sign Protocol)과 비교.
6. **자체 구현 아키텍처 (Design)** — 자체 서비스를 구축할 때 필요한 기능 분해(스키마 레지스트리, 어테스테이션 엔진, 리졸버, 인덱서, 오프체인 서명/저장소, 폐기, SDK, 운영), 시스템 구성도와 트러스트 모델.
7. **Limitations (한계)** — 본 리포트가 다루지 않은 주제, 증거 부족 영역, 향후 확장 포인트.
8. **References** — `sources.jsonl` 자동 렌더.
