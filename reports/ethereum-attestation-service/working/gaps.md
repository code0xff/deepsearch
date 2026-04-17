# Gaps after second gather sweep

## Resolved since first sweep
- c04 (DeSoc 논문): MS Research 미러(s25)로 1차 인용 확보. OK.
- c08/c16 (off-chain attestations): EAS SDK README(s23)에서 `getOffchain` / `signOffchainAttestation` 코드 패턴과 EIP-712 도메인 분리 인용 확보.
- c11 (Optimism AttestationStation → EAS): 단독 Attestation Station 1차 문서 없어 CoinDesk(s21) + OP 문서(s07/s08)로 역사 구성. Attestation Station은 2022년 선행 사례로만 간단히 언급.

## Remaining soft gaps (허용 범위)
- **c11 세부**: Attestation Station 원 컨트랙트의 기술 사양 1차 문서 미확보. → Limitations에 "Attestation Station과 EAS의 관계는 개요 수준에서만 다룸" 명시.
- **Statistics**: s20(420k+ attestors, 생태계 전체)과 s26(mainnet 기준 781 attestors) 규모 차이 → "체인별로 활동량 편차가 크다"라는 해석 근거로 사용. 충돌 아님, 범위가 다름.
- **c16 (오프체인 저장소 트레이드오프)**: IPFS/Arweave 구체적 벤치 자료 없음 → 설계 문헌 일반론으로 서술(설계 섹션), 수치는 인용 없이 정성 서술로 한정.

## Conflicts
- "Total unique attestors 420k+" (s20, 생태계 전체) vs "781" (s26, Ethereum mainnet only) → 범위 차. 둘 다 제시 + 주석.

## Decision
Gap ceiling(6회) 이전이지만, 핵심 클레임 c01–c19 중 18개가 최소 trust 1–3 자료로 뒷받침됨.
남은 soft gap은 Limitations에 명시하는 방식으로 수용 → **Phase 5 Draft 진입**.

## Next
- Draft.md 작성.
- 자체 구현 아키텍처 섹션에 ASCII 시스템 다이어그램 포함.
