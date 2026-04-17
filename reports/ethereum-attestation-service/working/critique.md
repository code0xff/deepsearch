# Critique — ethereum-attestation-service

## 1. Unsupported claims
모든 사실 주장 단락은 `[^s..]` 인용을 가진다. 검증 결과:
- 서론 §1의 두 번째 문장(목적 설명)은 리포트 내부 선언이라 무인용 허용.
- §2.1 마지막 문장("온체인 어테스테이션 시스템은 이 3자 모델을 EVM 상에서 재현…")은 해석적 재진술이며 s15의 범위 내로 볼 수 있으나, **nit**: "시도로 볼 수 있다" 식의 해석 언어를 유지하면 OK.
- §5 두 번째 단락 후반부 "실제로 Scroll Canvas·KarmaHQ 같은 프로젝트가 어테스테이션을 노드로 한 **소셜 그래프**를 구성하는 방향으로 활용 중이다" — s20은 Scroll Canvas를 "reimagines NFT badges as attestations for ecosystem engagement"로, KarmaHQ를 "Reputation & Governance" 범주로 명시한다. "소셜 그래프"는 s20이 뒷받침하지 않는 의미 확장. **must-fix**: 문구를 "평판·배지 인프라로 활용한다"로 약화.

## 2. Citation integrity
- 드래프트의 모든 `[^s..]` 27개 ID는 sources.jsonl에 존재함(교차 대조 완료).
- `accessed` 날짜는 전부 2026-04-17(90일 이내). OK.
- URL HEAD 체크:
  - `github.com/.../eas-contracts` → 200.
  - `eips.ethereum.org/EIPS/eip-5192` → 200.
  - `microsoft.com/.../decentralized-society-finding-web3s-soul/` → curl 기준 403(Akamai 헤더 검사). WebFetch로는 정상 획득. 인간 브라우저에서는 정상. **nit**: 대체 미러(예: 저자 홈페이지)가 있다면 보조 링크로 추가해도 됨. 현재 유지.
- `quote` 스팟 체크(s03 Attestation struct, s13 위임 어테스테이션 정의, s26 easscan 헤드 숫자): 세 건 모두 WebFetch 결과와 일치.

## 3. Reasoning gaps
- §4.3 "Bedrock 업그레이드 이후 EAS는 OP Stack의 predeploy로 포함되어 OP Stack에서 파생되는 체인들이 기본적으로 EAS를 상속받게 되었다" — s07/s08은 OP Mainnet/Sepolia만 명시. 모든 파생 체인에 대한 일반화는 과잉. **must-fix**: "OP Stack에서 파생되는 체인들은 동일 predeploy 주소로 EAS를 상속받을 수 있다"로 완화.
- §4.4 "활동량이 L2(특히 Base·Optimism)에 집중되어 있음을 시사한다" — s20(생태계 전체)과 s26(메인넷)만으로 "Base·Optimism에 집중"을 단정하긴 어렵다. **must-fix**: "L2에 활동이 더 크게 분산되어 있음을 시사한다"로 약화(특정 체인 단정 제거).
- §6.3 "UID 결정론": `keccak256(schema || resolver || revocable)` 의사코드는 EAS 실제 구현과 논리적으로 일치하나 인용된 코드에는 해시 수식이 없다. **nit**: "해시 방식"으로 일반화하거나 SchemaRegistry 구현 파일을 직접 확인 필요. 현재는 "hash로 결정론적으로 산출"로 축소해도 OK.

## 4. Missing counter-evidence
추가 카운터 검색(§5 Analysis 관련):
- **Spearbit 감사**: EAS 공식 FAQ는 "EAS contracts have undergone a thorough audit by Spearbit, a reputable third-party firm."을 명시. 보안 주장에 균형을 주는 긍정적 반대 증거. **must-fix**: §3 또는 §5에 한 줄 추가하고 s28 소스로 등록.
- **불변성/폐기 모델의 한계**: FAQ는 "폐기는 삭제가 아님"을 명시. 현재 드래프트 §6.3의 "폐기" 항목은 이를 이미 내포하나 명시적 인용이 없다. **nit**: s28 인용 추가 권장.
- EAS 반대론(예: "온체인 어테스테이션은 프라이버시 친화적이지 않다")은 별도 학술 자료가 부족. Limitations에 ZK/프라이버시 섹션이 이미 있으므로 허용.

## 5. Tone and structure
- Abstract는 본문 결론과 정합. "오프체인 인덱서 품질과 리졸버 보안이 자체 구현의 승패를 가르는 지점"은 §5 및 §6에서 근거화됨.
- Limitations가 gaps.md의 remaining soft gaps과 일관. OK.
- 이모지·마케팅 톤 없음. Hedging("arguably", "어쩌면") 없음. OK.
- 6문장 초과 단락: §1 서론(문장 수 OK), §5 단락 나열(짧게 분절됨). OK.

## 6. Must-fix vs nit 집계
- **must-fix** 4건:
  1. §5 "소셜 그래프" 표현 약화.
  2. §4.3 "모든 파생 체인이 EAS를 상속" 일반화 완화.
  3. §4.4 "Base·Optimism 집중" 단정 제거.
  4. Spearbit 감사 한 줄 + s28 소스 추가.
- **nit** 3건: s25 대체 미러(보류), §2.1 해석 언어(유지), §6.3 keccak256 의사코드(현재 표현 유지 가능).

## Summary
- Must-fix: 4
- Nits: 3 (허용)

드래프트 패치 후 critique 재실행 불필요(수정 범위가 사실관계 완화/인용 추가에 국한).
