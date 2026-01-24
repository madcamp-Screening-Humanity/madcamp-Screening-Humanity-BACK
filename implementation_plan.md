# Server B (FastAPI Backend) Implementation Plan

## 목표
- FastAPI 기반의 메인 백엔드 서버 (Server B) 구축
- Google OAuth2 로그인 구현 (비동기)
- 비동기 작업 처리 (Async Job Queue 패턴)
- PostgreSQL 데이터베이스 연동
- Server A (GPU 서버) 통신 구조 마련

## 구현 단계

### Phase 1: 프로젝트 초기화 및 환경 설정
- [ ] `server-b/backend` 디렉토리 구조 생성
- [ ] `requirements.txt` 작성 (FastAPI, SQLAlchemy, Pydantic, httpx, fastapi-sso 등)
- [ ] `.env` 설정 관리 (환경 변수 분리)
- [ ] PostgreSQL/SQLite DB 연동 설정 (개발용 SQLite 지원)

### Phase 2: 데이터베이스 모델링
- [ ] User 모델 (Google Login 정보 포함)
- [ ] Character 모델
- [ ] ChatSession 및 Message 모델
- [ ] GenerationJob 모델 (비동기 작업 추적용)

### Phase 3: 인증 시스템 (Google Login)
- [ ] `fastapi-sso`를 이용한 Google OAuth2 구현
- [ ] 로그인/회원가입 로직 (첫 로그인 시 자동 가입)
- [ ] JWT 토큰 발급 및 검증 미들웨어/의존성 구현
- [ ] 보호된 라우트 생성 테스트

### Phase 4: 비동기 작업 시스템 (Async Processing)
- [ ] `generate` API 구현 (Immediate Response with Job ID)
- [ ] `BackgroundTasks`를 이용한 비동기 로직 처리
- [ ] 상태 조회 (`polling`) API 구현
- [ ] (Mock) Server A로의 비동기 요청 시뮬레이션

### Phase 5: API 엔드포인트 구현 (핵심 기능)
- [ ] Chat API (LLM 연동용, 비동기)
- [ ] TTS API (연동용)
- [ ] File/Asset Serving API (NFS/Local path)

### Phase 6: 테스트 및 검증
- [ ] 로컬 실행 스크립트 작성 (`run.bat` / `run.sh`)
- [ ] API 문서 (Swagger UI) 확인

## 기술 스택
- Language: Python 3.10+
- Framework: FastAPI
- DB: PostgreSQL (Production) / SQLite (Dev)
- ORM: SQLAlchemy (Async supported)
- Auth: Google OAuth2 (via fastapi-sso), JWT
