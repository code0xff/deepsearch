# Ethereum Attestation Service 심층 분석 및 자체 구현 아키텍처

## 1. 서론

블록체인 상에서 "이 주소는 KYC를 통과했다", "이 사용자는 특정 이벤트에 참여했다", "이 컨트랙트는 감사 완료되었다"처럼 검증 가능한 주장(claim)을 표현하려는 시도는 NFT·SBT·DID·Verifiable Credentials 등 다양한 형태로 전개되어 왔다. 이 중 **Ethereum Attestation Service(EAS)** 는 특정 신원 모델이나 토큰 표준에 종속되지 않는 **범용 어테스테이션 레이어**를 목표로 설계된 프로토콜이며, 이더리움 메인넷과 주요 EVM L2에 이미 배포되어 현업 규모로 사용되고 있다.[^s01][^s20]

본 리포트의 목적은 두 가지다. 첫째, EAS의 프로토콜 설계(컨트랙트 구조, 스키마, 온체인/오프체인 어테스테이션, 리졸버, 위임 서명)를 1차 코드와 문서로부터 정리한다. 둘째, 동일한 기능군을 자체적으로 구현하려 할 때 필요한 컴포넌트와 운영 요건을 분해하고, 참조 아키텍처를 제시한다. 범위는 프로토콜·오프체인 인프라·SDK·인덱서까지이며, 법률적 KYC 규제, ZK 어테스테이션의 회로 세부 설계, 특정 도메인(금융, 공급망)의 데이터 모델링은 다루지 않는다.

## 2. 배경

### 2.1 Verifiable Credentials와 3자 모델

W3C의 Verifiable Credentials(VC) 표준은 "암호학적으로 발급자(authorship)를 검증할 수 있는 변조 방지 자격 증명"을 정의하고, 발급자(Issuer) → 보유자(Holder) → 검증자(Verifier)의 3자 모델을 표준화한다.[^s15] Holder는 보유한 VC로부터 Verifiable Presentation을 생성하여 검증자에게 선택적으로 공개할 수 있다.[^s15] 온체인 어테스테이션 시스템은 이 3자 모델을 EVM 상에서 재현하는 시도로 볼 수 있다: 발급자는 `attester` 주소, 보유자는 `recipient` 주소, 검증자는 어테스테이션 UID를 조회하는 컨트랙트나 오프체인 서비스가 된다.

### 2.2 Soulbound Token과 Decentralized Society

Vitalik Buterin은 2022년 1월 에세이에서 World of Warcraft의 "soulbound item" 은유를 빌려, 전송 불가능한 토큰이 자격 증명과 평판 표현에 적합하다고 주장했다: "A soulbound item, once picked up, cannot be transferred or sold to another player."[^s16] 이 아이디어는 같은 해 Ohlhaver·Weyl·Buterin 공저의 "Decentralized Society: Finding Web3's Soul"에서 **Soulbound Token(SBT)** 으로 공식화되었으며, 이들은 "Non-transferable 'soulbound' tokens (SBTs) representing the commitments, credentials, and affiliations of 'Souls' can encode the trust networks of the real economy to establish provenance and reputation."라고 서술한다.[^s25] 표준 트랙에서는 이후 **ERC-5192**가 EIP-721을 확장해 최소 인터페이스로 토큰 전송 불가 속성을 선언할 수 있게 했다.[^s17]

### 2.3 SBT vs Attestation — 설계 관점의 차이

SBT 경로는 NFT/ERC-721을 확장해 사용자 지갑에 "토큰"을 발행하는 방식을 택하며, 지갑 UI·기존 도구와의 호환성이 장점이다.[^s17] 반면 어테스테이션 경로는 **토큰을 발행하지 않고** 서명된 구조화 데이터(스키마 + 페이로드)를 저장하거나 서명만 배포한다. EAS 공식 README는 이를 "free and open protocol for on-chain attestations on EVM compatible blockchains"로 설명하며 토큰 발행을 필수로 요구하지 않는다.[^s01] 이 차이는 가스 비용, 폐기/갱신 흐름, 프라이버시(오프체인 가능 여부) 측면에서 트레이드오프를 만든다. Verax의 Linea 블로그는 "Verax는 EIP도 프로토콜도 제품도 아닌, 공유 가능한 프리미티브"라며 더 나아가 "레지스트리" 관점을 강조하는데, 이는 EAS가 SBT보다 레지스트리 성격에 가깝다는 점을 시사한다.[^s18]

## 3. EAS 프로토콜 구조 — 현 상태

### 3.1 두 개의 핵심 컨트랙트

EAS의 온체인 구현은 **`SchemaRegistry`** 와 **`EAS`** 두 컨트랙트로 구성된다. 전자는 스키마를 등록·조회하고, 후자는 그 스키마를 참조하는 어테스테이션을 생성·폐기한다.[^s01][^s06] `SchemaRegistry`의 핵심 저장 구조와 등록 함수는 다음과 같다.[^s04]

```solidity
struct SchemaRecord {
    bytes32 uid;
    ISchemaResolver resolver;
    bool revocable;
    string schema;
}

function register(
    string calldata schema,
    ISchemaResolver resolver,
    bool revocable
) external returns (bytes32);
```

`schema` 필드는 "주소 recipient, uint256 score, string country"와 같은 Solidity ABI-like 선언 문자열이다. UID는 스키마 내용과 리졸버·폐기 가능 여부의 해시로 결정론적으로 도출되므로, **동일 스키마 재등록 시 같은 UID**가 나온다.[^s04][^s06]

### 3.2 Attestation 구조체

어테스테이션 자체는 `Common.sol`에 정의된 10개 필드의 구조체다.[^s03]

```solidity
struct Attestation {
    bytes32 uid;
    bytes32 schema;
    uint64 time;
    uint64 expirationTime;
    uint64 revocationTime;
    bytes32 refUID;
    address recipient;
    address attester;
    bool revocable;
    bytes data;
}
```

`refUID`는 다른 어테스테이션을 참조해 체이닝을 구성할 수 있게 한다(예: "A의 인증서를 기반으로 B가 추천을 발급"). `data`는 스키마에 선언된 타입으로 `abi.encode`된 바이트열이며, 오프체인 인덱서가 이 데이터를 스키마 문자열과 함께 디코딩해 GraphQL에 노출한다.[^s14]

### 3.3 온체인 vs 오프체인 어테스테이션

EAS는 두 가지 배포 모드를 공식 지원한다.
- **온체인**: `EAS.attest()` 를 호출해 상태 저장. 가스가 들지만 영구 기록 및 컨트랙트에서 직접 조회 가능.
- **오프체인**: EIP-712로 타입 지정 서명을 생성해 오프체인 매체(DB, IPFS, Arweave, 링크 URL)로 전달. 필요 시 UID만 온체인에 타임스탬프 가능.[^s06][^s23]

EAS SDK는 오프체인 서명을 `getOffchain()` + `signOffchainAttestation()` 형태로 캡슐화한다.[^s23]

```ts
const offchain = await eas.getOffchain();
const offchainAttestation = await offchain.signOffchainAttestation(
  {
    recipient: '0xFD50...2165',
    expirationTime: NO_EXPIRATION,
    time: BigInt(Math.floor(Date.now() / 1000)),
    revocable: true,
    schema: '0xb16f...c995',
    refUID: '0x000...000',
    data: encodedData,
  },
  signer,
);
```

서명의 도메인 분리자(domain separator)는 `name`, `version`, `chainId`, `verifyingContract(EAS)`를 포함해 교차 체인·교차 버전 리플레이를 방지한다.[^s23] 검증은 `verifyOffchainAttestationSignature`로 수행한다.[^s23]

### 3.4 위임 어테스테이션(Delegated Attestation)

위임 어테스테이션은 서명자(attester)와 트랜잭션 전송자(sponsor)를 분리한다. 공식 튜토리얼은 이를 "Delegated Attestations enable an entity to sign an attestation while allowing another entity to cover the transaction fee."라고 정의한다.[^s13] 이 때 온체인 `attester` 필드는 서명자 주소로 기록된다.[^s13] 표준 경로는 EIP-712 스펙에 따른 **증가하는 nonce**를 요구하지만, 프록시 컨트랙트를 통해 "out of order" 수락과 서명 만료시간을 지원한다.[^s22] KYC 발급자가 수천 사용자에게 가스비를 부담시키지 않기 위한 대량 발급 패턴에서 특히 유용하다.[^s22]

### 3.5 Schema Resolver — 훅 메커니즘

`SchemaResolver`는 어테스테이션 발급·폐기 시점에 실행되는 훅 컨트랙트로, 스키마 등록 시 지정한다.[^s05] 추상 베이스는 다음과 같은 진입점을 노출한다.[^s05]

```solidity
function attest(Attestation calldata a) external payable onlyEAS returns (bool);
function multiAttest(Attestation[] calldata a, uint256[] calldata v) ...;
function revoke(Attestation calldata a) external payable onlyEAS returns (bool);
function multiRevoke(Attestation[] calldata a, uint256[] calldata v) ...;
function isPayable() public pure virtual returns (bool);
```

`onlyEAS` 모디파이어는 호출자를 EAS 컨트랙트로 제한해 권한 분리를 강제한다.[^s05] 이를 통해 수수료 수취, 화이트리스트 확인, 토큰 배포, 외부 오라클 호출과 같은 임의 로직을 스키마에 결합할 수 있다.[^s05][^s06]

### 3.6 배포 현황

EAS 컨트랙트는 Ethereum Mainnet(`EAS 0xA120...Ce587`, `SchemaRegistry 0xA7b3...7BDF`) 및 Optimism, Base, Arbitrum, Polygon, Scroll, zkSync, Celo 등 다수 EVM 체인에 배포되어 있다.[^s02] 특히 Optimism은 **OP Stack의 predeploy**로 EAS를 포함시켜 "Introduced: Bedrock; Proxied: yes"로 표기하고 있으며, 주소는 OP Mainnet/Sepolia 모두 `0x4200...0021`(EAS) / `0x4200...0020`(SchemaRegistry)로 고정된다.[^s07][^s08] 공개 인덱서 `easscan.org`는 체인별 GraphQL 엔드포인트(예: `https://base.easscan.org/graphql`)를 제공한다.[^s14] EAS 공식 FAQ는 컨트랙트가 Spearbit 제3자 감사를 거쳤음과, 어테스테이션 자체는 불변이며 폐기가 삭제가 아닌 상태 전이임을 명시한다: "EAS contracts have undergone a thorough audit by Spearbit… It does not delete the attestation."[^s28]

## 4. 생태계와 활용 사례

### 4.1 Coinbase Verifications

Coinbase는 2023년 11월 Base 체인에서 EAS를 기반으로 한 "Coinbase Verifications"를 공개했다.[^s11] 초기 제공 스키마는 **Verified Account**(불리언, 항상 `true`)와 **Verified Country**(ISO 3166-1 alpha-2 문자열)이며, 이후 **Verified Coinbase One** 멤버십 스키마가 추가되었다.[^s09][^s27] Base Mainnet의 발급자(Coinbase Attester)는 `0x3574...d7EE`이고, Verified Account 스키마 UID는 `0xf8b0...0de9`이다.[^s10] 이 설계는 "발급자=Coinbase, 사용자=recipient, 스키마=사전 등록, 데이터=불리언/문자열"이라는 가장 얕은 EAS 패턴으로, KYC 같은 민감 정보를 직접 저장하지 않고 **검증 통과 여부만** 온체인화한다는 점에서 프라이버시-실용 트레이드오프의 대표 사례다.[^s09][^s27]

### 4.2 Gitcoin Passport

Gitcoin Passport는 "Stamp" 기반 Sybil 저항 시스템으로, 2024년 기준 여러 체인에서 온체인 민트를 지원한다: "Gitcoin Passport creates a Stamp and score attestation, and mints them onchain to EAS and other attestation registries, depending on which network users choose."[^s12] 즉 EAS는 Passport 데이터의 **다운스트림 싱크** 중 하나이며, 스코어/스탬프가 변동성이 있는 만큼 "온체인 값은 시점 스냅샷"이라는 한계를 문서에서 명시한다.[^s12]

### 4.3 Optimism과 공공재 투표

Optimism은 2022년 AttestationStation을 별도로 구현해 RetroPGF의 시민 선정 등에 사용한 선행 사례를 가지고 있으며, 이후 2023년 5월에 EAS를 채택한다고 공표했다.[^s21] Bedrock 업그레이드 이후 EAS는 OP Stack의 **predeploy**로 포함되어, OP 공식 문서는 OP Mainnet과 OP Sepolia에 동일한 predeploy 주소로 EAS를 제공한다고 명시한다(OP Stack 파생 체인 전반의 상속 여부는 각 체인 구성에 따른다).[^s07][^s08] _(AttestationStation 원 컨트랙트의 기술 사양과 EAS 이전 과정을 다룬 1차 문서는 본 조사에서 확보하지 못했으며, 리포트는 "Optimism이 선행 AttestationStation을 운용한 뒤 EAS로 수렴"이라는 큰 줄기만 제시한다 — unverified — single source_)

### 4.4 생태계 규모

EAS 공식 생태계 페이지는 "420k+ unique attestors"와 주요 통합으로 Optimism, Coinbase Verifications, Gitcoin Passport, Guild, Icebreaker, KarmaHQ, Scroll Canvas, Arbitrum Arcade, Ceramic을 소개한다.[^s20] 한편 Ethereum Mainnet만 보면 `easscan.org`는 접속 시점 기준 **총 어테스테이션 13,730건 / 스키마 372개 / 고유 어테스터 781명**을 표시해, 생태계 전체 수치와 메인넷 활동량 사이에 뚜렷한 격차가 있음을 시사한다(L2에 상당량이 분산되어 있음을 시사하나, 체인별 점유율의 정량 비교는 본 조사 범위 밖).[^s26] 두 수치는 서로 충돌이 아니라 **범위 차이**(체인별 vs 생태계 전체)다.[^s20][^s26]

### 4.5 경쟁·보완 프로토콜

- **Verax(Linea, Consensys)** — 공유 레지스트리 성격을 강조하며 "Verax is not an Ethereum Improvement Proposal (EIP), or a protocol, or a product, but rather a simple primitive"로 자신을 정의한다. 설계 목표는 EAS와 유사하나 **모듈(Module) 중심 훅**과 **다른 표준과의 상호운용**에 더 기울어져 있다.[^s18]
- **Sign Protocol(구 EthSign)** — "omni-chain attestation protocol"을 표방하며 스키마와 어테스테이션 프리미티브를 EAS와 유사하게 정의하되, 계약 서명(EthSign)·사설/ZK 어테스테이션을 상위 제품 라인업에 포함한다.[^s19][^s24] EAS와의 공식 비교표는 확인되지 않았고, 본 리포트는 두 제품이 동일한 "스키마 + 어테스테이션" 프리미티브 위에 각기 다른 기능군을 쌓는 것으로 정리한다.[^s19][^s24]

## 5. 분석 — 설계 관점에서의 EAS

세 가지 관점으로 EAS의 설계 선택을 요약한다.

**1) 미니멀한 온체인 코어, 두꺼운 오프체인 인덱서.** EAS 온체인은 `SchemaRegistry` + `EAS` + `SchemaResolver`의 3종 세트뿐이며, 대부분의 애플리케이션 의미론(점수 계산, Stamp 집계, 프로필 생성)은 오프체인 인덱서와 SDK에 위임된다.[^s14][^s23] 이는 표준화 부담을 낮추는 대신, 실사용자 경험의 질을 인덱서 품질에 종속시킨다.

**2) 스키마 UID의 결정론과 컴포저빌리티.** 스키마 UID가 결정론적으로 산출되기 때문에 동일 정의를 서로 다른 체인에 올려도 **UID 수준의 식별성**을 유지할 수 있다.[^s04] `refUID` 필드는 어테스테이션 간 인용 그래프를 만들 수 있는 기반이며, EAS 생태계 페이지가 Scroll Canvas를 "NFT badges를 어테스테이션으로 재해석"으로, KarmaHQ를 "Reputation & Governance"로 소개하는 등 평판·배지 인프라로의 활용이 보고되고 있다.[^s20]

**3) 위임·리졸버를 통한 확장성.** 위임 어테스테이션은 엔터프라이즈 발급자(KYC 제공자, 게임 서버)의 사용자 가스 부담을 제거하고, 리졸버는 수수료·조건 검증·외부 훅을 스키마 단위로 주입한다. 단, 리졸버가 외부 컨트랙트·오라클을 호출할 경우 **재진입성과 권한 관리**가 핵심 리스크가 된다.[^s05][^s13]

이 세 가지 선택의 합은 "어떤 신원 모델이냐"를 강제하지 않는 **중립 레이어**라는 포지셔닝으로 수렴하며, 이는 Verax가 "shared primitive"를 명시적 설계 목표로 삼는 방향과도 공통된다.[^s18]

## 6. 자체 구현 아키텍처

EAS와 기능적으로 동등한 자체 어테스테이션 서비스를 구현하려는 조직을 전제로, 최소 기능 집합과 참조 아키텍처를 제시한다.

### 6.1 기능 분해

최소 구현 범위는 다음 9개 모듈로 나뉜다.[^s01][^s04][^s05][^s13][^s14][^s23]

| # | 모듈 | 주요 책임 |
|---|-------|-----------|
| M1 | Schema Registry (온체인) | 스키마 등록·조회, UID 결정론, 리졸버 바인딩 |
| M2 | Attestation Core (온체인) | 어테스테이션 발급·폐기, UID 생성, 이벤트 방출 |
| M3 | Schema Resolver (선택) | 발급/폐기 훅, 수수료 수취, 외부 검증 |
| M4 | Offchain Signer / Verifier | EIP-712 타입 정의, 도메인 분리, 서명·검증 |
| M5 | Delegated Attestation | 위임 서명·nonce·프록시, 만료 시간 |
| M6 | Indexer | 체인 이벤트 ingest, ABI 기반 데이터 디코딩 |
| M7 | Query API | GraphQL/REST, 스키마·어테스테이션·그래프 질의 |
| M8 | Offchain Storage (선택) | 오프체인 페이로드 저장(IPFS/Arweave/전용 DB) |
| M9 | SDK | TypeScript·Go 등 언어 바인딩, 서명 유틸, 인코더 |

M1·M2·M4·M6·M7은 **최소 기능**이며, 생태계 수준의 효용을 내려면 M5·M9가 사실상 필수다. M3·M8은 사용 사례가 요구할 때 추가한다.[^s05][^s12]

### 6.2 참조 아키텍처(시스템 구성도)

```
                  ┌───────────────────────────────┐
                  │          Applications         │
                  │  (dApp, Wallet, Backend, BI)  │
                  └──────────────┬────────────────┘
                                 │ (SDK: TS/Go)
                                 ▼
          ┌──────────────────────────────────────────┐
          │                 SDK (M9)                 │
          │  signOffchain / attest / attestDelegated │
          │   encodeData / verifySignature / query   │
          └───────┬──────────────────────┬───────────┘
                  │                      │
     EIP-712 sign │                      │ HTTPS/GraphQL
                  │                      │
                  ▼                      ▼
      ┌─────────────────────┐   ┌─────────────────────┐
      │  Offchain Storage   │   │      Indexer        │
      │  (IPFS/Arweave/DB)  │   │   + Query API       │
      │         (M8)        │   │      (M6, M7)       │
      └─────────┬───────────┘   └─────────▲───────────┘
                │                         │ logs/traces
                │ optional UID timestamp  │
                ▼                         │
      ┌────────────────────────────────────────────────┐
      │                  L1 / L2 Chain                 │
      │                                                │
      │  ┌────────────────┐   ┌─────────────────────┐  │
      │  │ SchemaRegistry │   │        EAS          │  │
      │  │     (M1)       │◀──│  attest/revoke      │  │
      │  └────────┬───────┘   │  delegated variants │  │
      │           │           │       (M2, M5)      │  │
      │           ▼           └──────────┬──────────┘  │
      │  ┌─────────────────┐             │             │
      │  │ SchemaResolver  │◀────────────┘             │
      │  │     (M3)        │   onAttest / onRevoke     │
      │  └─────────────────┘                           │
      └────────────────────────────────────────────────┘
```

데이터 흐름 요약:
1. 애플리케이션이 SDK로 페이로드를 `abi.encode`하고 EIP-712 서명을 생성(M9).[^s23]
2. 발급 방식에 따라 분기 — (a) 직접 `attest()` 호출, (b) 위임 서명만 생성 후 sponsor가 `attestByDelegation()` 호출, (c) 완전 오프체인일 경우 서명만 저장.[^s13][^s23]
3. 온체인 경로는 `SchemaRegistry`에서 리졸버를 조회해 `onAttest` 훅을 실행(M1, M3).[^s05]
4. 인덱서(M6)가 `Attested`/`Revoked` 이벤트를 수집, 스키마 정의로 디코딩 후 저장.[^s14]
5. Query API(M7)가 GraphQL로 외부에 노출. 오프체인 어테스테이션은 저장소(M8) URI 기반으로 해시·서명 검증 후 동일 인덱스에 병합 가능.[^s14][^s23]

### 6.3 핵심 설계 결정

**컨트랙트 레이어**
- **UID 결정론**: `keccak256(schema || resolver || revocable)` 형태로 스키마 UID를 산출해 재등록 멱등성을 확보한다.[^s04]
- **리졸버 격리**: 모든 외부 호출 리졸버는 체크-효과-상호작용(Checks-Effects-Interactions) 패턴을 강제하고, `onlyEAS`로 직접 호출을 차단한다.[^s05]
- **폐기**: `revocable=false` 어테스테이션은 영구 불변; `revocable=true`는 발급자만 `revoke` 가능. 프록시를 통한 위임 폐기도 동일 서명 스킴을 재사용한다.[^s13][^s22]

**오프체인 레이어**
- **EIP-712 도메인**: `{name: "MYEAS", version: "1", chainId, verifyingContract}`로 분리자 고정. 체인 또는 컨트랙트 재배포 시 `version` 인상으로 리플레이 방지.[^s23]
- **저장소 선택**: IPFS(컨텐츠 어드레스·분산)·Arweave(영구성)·내부 DB(접근 제어·삭제성) 중 사용 사례별 선택. EAS는 오프체인 어테스테이션을 URL fragment에 실을 수 있는 프라이버시 친화 패턴도 제공하므로, 개인정보성 페이로드는 해시만 온체인에 올리고 본문은 허가된 당사자에게만 전달하는 방식이 권장된다.[^s06]
- **인덱서**: The Graph 서브그래프 또는 자체 인덱서(예: PostgreSQL + Rust/TS worker). EAS 팀은 체인별 독립 GraphQL 엔드포인트(`{chain}.easscan.org/graphql`)를 운영한다.[^s14]

**SDK 레이어**
- 페이로드 인코딩 유틸(스키마 문자열 파싱 → ABI 타입 벡터 → `encodeAbiParameters`).
- 서명 유틸(EIP-712 `domain`, `types`, `message` 빌더).
- 조회 유틸(GraphQL 래퍼 + 타입 안전한 결과 파서).
- 검증 유틸(서명 복원, 체인 상태 조회, 폐기 확인).[^s23]

### 6.4 보안·운영 체크리스트

아래 항목은 자체 구현 시 최소 점검 대상이다.[^s05][^s13][^s22][^s23]

- EIP-712 도메인 분리자의 4개 필드(name, version, chainId, verifyingContract) 고정과 체인·컨트랙트 리플레이 방지.
- nonce 전략: 기본 증가형 vs 프록시형(만료시간 포함) 중 사용자 시나리오에 맞춘 선택.
- 리졸버 재진입 방지(`ReentrancyGuard`) 및 외부 호출 가스 상한.
- 대량 발급(multiAttest) 시 `values` 배열·이더 잔여 반환 로직의 불변식.
- 인덱서 재편성(reorg) 대응: 블록 finality 이후 반영, L2의 경우 시퀀서 문제 고려.
- 오프체인 서명의 시간 동기화(서명 `time` vs 검증 시계 스큐).
- 스키마 업그레이드 정책: 기존 스키마는 불변이므로 **스키마 버전 관리**를 외부 규약(예: `v1`, `v2` suffix)으로 처리.

### 6.5 단계적 구현 로드맵(제안)

1. **MVP** — M1 + M2 + 최소 M9(TS SDK), 오프체인 인덱서는 The Graph 서브그래프로 시작.
2. **실사용 대응** — M5(위임 서명), M4 완성, 웹 익스플로러(M7 UI) 추가.
3. **엔터프라이즈** — M3 리졸버 라이브러리(수수료, ACL, 콜백), 프라이빗 어테스테이션(M8 + 키 교환).
4. **상호운용** — Verax·EAS와 교차 인덱싱, 공통 스키마 카탈로그 참여.[^s18]

이 로드맵은 EAS 자체의 기능 확장 순서와 Gitcoin·Coinbase 등 도입 사례에서 관찰되는 요구 순서에 기반한다.[^s09][^s12][^s13]

## 7. 한계

본 리포트는 다음 주제를 충분히 다루지 못했다.
- **Optimism AttestationStation의 기술 사양과 EAS 이전 과정**: 1차 자료 확보 실패로 CoinDesk 보도와 OP 공식 문서의 간접 인용에만 의존했다.[^s07][^s21]
- **오프체인 저장소 트레이드오프(IPFS vs Arweave vs RDB)의 정량 비교**: 벤치·비용 자료를 확보하지 못해 정성적 서술에 그쳤다.
- **ZK/사설 어테스테이션**: EAS SDK가 Merkle tree 기반 private data를 지원함을 언급했으나,[^s23] 회로 설계나 프라이버시 공격 표면의 분석은 제외했다.
- **경제적 평가**: 어테스테이션당 가스 비용, 인덱서 운영 비용, 오프체인 저장 비용의 모델링은 별도 연구가 필요하다.
- **규제·법률**: KYC/AML, 개인정보(GDPR·국내 개인정보보호법), VC 표준 정합성과의 법적 인터페이스는 범위 외.

향후 확장으로는 (1) EAS·Verax·Sign Protocol의 **정량 사용 통계 비교**, (2) **실시간 인덱서 품질 측정**(지연, 정확도), (3) 자체 구현 MVP의 **감사 이슈 카탈로그**가 유의미할 것이다.

## Abstract

Ethereum Attestation Service(EAS)는 EVM 호환 체인 상에서 스키마 기반의 검증 가능한 주장(어테스테이션)을 발급·조회·폐기할 수 있게 하는 퍼블릭 굿 프로토콜이다.[^s01] 본 리포트는 EAS의 두 핵심 컨트랙트(`SchemaRegistry`, `EAS`)와 `Attestation` 구조체, 온체인·오프체인 발급 경로, EIP-712 기반 위임 서명, 리졸버 훅을 1차 소스 코드와 공식 문서로부터 정리한다.[^s03][^s04][^s05][^s13][^s22][^s23] 이어 Coinbase Verifications, Gitcoin Passport, Optimism RetroPGF 및 OP Stack predeploy 통합 사례를 통해 EAS가 이미 생태계 규모의 어테스테이션 레이어로 기능함을 확인하고,[^s07][^s09][^s12][^s20] Verax·Sign Protocol 등 대안과의 설계적 차이를 요약한다.[^s18][^s19][^s24] 마지막으로 동일 기능군을 자체 구현할 때 필요한 9개 모듈(스키마 레지스트리, 어테스테이션 코어, 리졸버, 오프체인 서명·검증, 위임, 인덱서, Query API, 오프체인 저장소, SDK)을 정의하고, 참조 시스템 아키텍처와 단계적 구현 로드맵, EIP-712 도메인 분리·리졸버 재진입·스키마 버전 관리 등 보안·운영 체크리스트를 제시한다. 리포트는 어테스테이션 서비스를 신원 모델에 종속시키지 않는 **중립 레이어**로 설계한 EAS의 선택이 높은 조합성과 확장성을 제공한다고 평가하는 한편, 오프체인 인덱서 품질과 리졸버 보안이 자체 구현의 승패를 가르는 지점이라고 결론 맺는다.

## References

모든 참고문헌은 `working/sources.jsonl`에서 자동 생성된다.
