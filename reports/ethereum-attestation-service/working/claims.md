# Claims

## Introduction
- [ ] c01: EAS는 이더리움 및 호환 체인에서 임의 구조화 데이터에 대한 서명된 어테스테이션을 생성·검증·폐기하는 퍼블릭 굿 인프라 프로토콜이다.
  - kind: factual
  - needs: EAS 공식 문서/백서, GitHub 저장소 README
- [ ] c02: EAS는 특정 신원 스키마에 의존하지 않는 "범용" 어테스테이션 레이어를 지향하여 SBT·NFT 기반 신원 시도와 차별화된다.
  - kind: interpretive
  - needs: EAS 공식 설명 + 비교 분석 글 또는 논문

## Background
- [ ] c03: W3C Verifiable Credentials는 발급자-보유자-검증자 3자 모델을 표준화하며, 온체인 어테스테이션은 이 모델을 온체인 검증 가능하게 확장한 사례다.
  - kind: factual
  - needs: W3C VC 표준 문서
- [ ] c04: Soulbound Token(SBT) 및 ERC-5192/ERC-5114는 전송 불가 토큰으로 신원을 표현하려는 시도로서 Vitalik 등이 2022년 "Decentralized Society" 논문에서 제안했다.
  - kind: factual
  - needs: Weyl-Ohlhaver-Buterin 2022 논문, ERC 표준 문서
- [ ] c05: Attestation 모델은 SBT와 달리 토큰(NFT/SBT)을 발행하지 않고 데이터 자체를 서명하므로 가스 비용과 폐기·갱신 측면에서 다른 트레이드오프를 가진다.
  - kind: interpretive
  - needs: EAS docs + SBT 관련 기술 비교 글

## EAS 프로토콜 구조
- [ ] c06: EAS의 핵심 온체인 컴포넌트는 `SchemaRegistry`와 `EAS` 두 컨트랙트이며, 스키마 등록과 어테스테이션 생성이 분리되어 있다.
  - kind: technical
  - needs: EAS 스마트 컨트랙트 소스, 공식 docs
- [ ] c07: 어테스테이션은 UID(고유 해시)를 식별자로 가지며 스키마·어테스터·리시피언트·데이터·만료·폐기·referencedUID 등 필드로 구성된다.
  - kind: technical
  - needs: `Attestation` 구조체 소스
- [ ] c08: EAS는 "오프체인 어테스테이션"을 공식 지원하며, 이는 EIP-712 서명으로 오프체인에 보관되고 필요 시 온체인 타임스탬프 가능하다.
  - kind: technical
  - needs: EAS docs, SDK 소스
- [ ] c09: Schema Resolver 컨트랙트를 통해 어테스테이션 생성·폐기·가치 이체 등 훅에 커스텀 로직(수수료, 화이트리스트, 토큰 발행)을 삽입할 수 있다.
  - kind: technical
  - needs: `SchemaResolver` 컨트랙트, 예제 코드
- [ ] c10: EAS는 Ethereum mainnet·Optimism·Base·Arbitrum 등 다수의 EVM 체인에 배포되어 있으며 공식 GitHub에 배포 주소 리스트가 공개되어 있다.
  - kind: factual
  - needs: eas.eth/docs 배포 주소, GitHub README

## 생태계와 활용 사례
- [ ] c11: Optimism의 "Attestation Station"은 EAS와 별도로 먼저 도입된 네이티브 어테스테이션 레지스트리로서 이후 EAS와 상호운용 혹은 마이그레이션이 논의되었다.
  - kind: factual
  - needs: Optimism 공식 블로그/docs
- [ ] c12: Coinbase는 EAS를 사용해 Base 체인에서 "Verified Account/Country" 등 KYC/검증 어테스테이션을 발급한다.
  - kind: factual
  - needs: Coinbase/Base 공식 발표, EAS 레지스트리
- [ ] c13: Gitcoin Passport 등 평판·Sybil 저항 도구가 EAS 어테스테이션을 데이터 소스로 도입 또는 검토하고 있다.
  - kind: factual
  - needs: Gitcoin 공식 블로그/docs
- [ ] c14: EAS와 경쟁·보완 관계의 대표 프로토콜로 Verax(Linea), Sign Protocol(구 EthSign)이 존재하며 각각 설계 철학이 다르다.
  - kind: interpretive
  - needs: 각 프로젝트 docs/깃허브, 비교 리서치 글

## 자체 구현 아키텍처
- [ ] c15: 자체 Attestation 서비스의 최소 기능 집합은 (a) 스키마 레지스트리, (b) 어테스테이션 발급/조회 API, (c) 폐기, (d) 인덱싱/검색, (e) 서명 검증, (f) SDK를 포함한다.
  - kind: interpretive
  - needs: EAS 기능 세트 + 일반적인 어테스테이션 구현 체크리스트
- [ ] c16: 온체인·오프체인 하이브리드 설계에서 오프체인 저장소로 IPFS/Arweave/전용 DB 중 선택이 필요하며 각각 가용성·비용·영구성 트레이드오프를 가진다.
  - kind: technical
  - needs: EAS docs + 오프체인 저장소 비교 자료
- [ ] c17: 확장성 확보를 위해 어테스테이션 인덱서(subgraph, custom indexer)를 별도 운영하는 것이 일반적이며 EAS 공식 서비스도 GraphQL API를 제공한다.
  - kind: technical
  - needs: EAS GraphQL docs, The Graph 서브그래프 사례
- [ ] c18: 리졸버 컨트랙트 패턴을 자체 구현에 도입하면 수수료·조건부 발급·외부 컨트랙트 연동을 모듈화할 수 있으나 재진입·권한 관리 리스크를 수반한다.
  - kind: interpretive
  - needs: EAS Resolver 예제 + 보안 리뷰/감사 보고
- [ ] c19: 자체 구현 시 키 관리·서명 권한(Delegated Attestation)·EIP-712 도메인 분리 등 암호 설계가 보안의 1차 방어선이다.
  - kind: technical
  - needs: EAS Delegated attestation docs, EIP-712 스펙
