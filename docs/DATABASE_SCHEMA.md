# 데이터베이스 스키마 명세서

**작성일**: 2026-01-26  
**버전**: 1.0  
**프로젝트명**: Avatar Forge (인생 극장)

---

## 목차

1. [개요](#1-개요)
2. [데이터베이스 설정](#2-데이터베이스-설정)
3. [테이블 상세](#3-테이블-상세)
4. [문서와의 차이점](#4-문서와의-차이점)
5. [Frontend 데이터 구조](#5-frontend-데이터-구조)
6. [ERD 다이어그램](#6-erd-다이어그램)
7. [마이그레이션 가이드](#7-마이그레이션-가이드)
8. [향후 계획](#8-향후-계획)

---

## 1. 개요

### 1.1 데이터베이스 종류

- **개발 환경**: SQLite (비동기, `aiosqlite`)
- **운영 환경**: PostgreSQL (비동기, `asyncpg`)
- **ORM**: SQLAlchemy 2.0.25 (비동기 지원)
- **마이그레이션**: SQLAlchemy `Base.metadata.create_all()` (자동 생성)

### 1.2 데이터베이스 URL

- **개발**: `sqlite+aiosqlite:///./avatar_forge.db`
- **운영**: `postgresql+asyncpg://user:password@host:port/dbname`

### 1.3 현재 구현된 테이블

1. `users` - 사용자 정보
2. `characters` - 캐릭터 정보
3. `generation_jobs` - 생성 작업 추적
4. `audio_files` - TTS 오디오 파일 메타데이터

---

## 2. 데이터베이스 설정

### 2.1 설정 파일

**파일**: `server-b/backend/app/core/database.py`

```python
# Async Engine 생성
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
)

# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
```

### 2.2 테이블 자동 생성

**파일**: `server-b/backend/app/main.py`

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        from app.models import user, generation, audio
        await conn.run_sync(Base.metadata.create_all)
    yield
```

---

## 3. 테이블 상세

### 3.1 users 테이블

**모델 파일**: `app/models/user.py`  
**용도**: 사용자 인증 및 프로필 정보 저장

#### 스키마

| 필드명 | 타입 | 제약조건 | 설명 |
|--------|------|----------|------|
| `id` | String(36) | PK, INDEX | UUID 문자열 (36자) |
| `email` | String(100) | UNIQUE, NOT NULL, INDEX | 이메일 주소 |
| `username` | String(50) | NULLABLE | Google 계정 이름 |
| `picture` | String(255) | NULLABLE | 프로필 사진 URL |
| `is_active` | Boolean | DEFAULT=True | 계정 활성화 여부 |
| `is_superuser` | Boolean | DEFAULT=False | 관리자 여부 |
| `provider` | String(20) | DEFAULT="google" | OAuth 제공자 (현재는 google만) |
| `created_at` | DateTime(timezone=True) | DEFAULT=now() | 생성 시간 |
| `updated_at` | DateTime(timezone=True) | ON UPDATE=now() | 수정 시간 |

#### 인덱스

- `id` (Primary Key)
- `email` (Unique Index)

#### 관계

- `characters.user_id` → `users.id` (Foreign Key, nullable)
- `generation_jobs.user_id` → `users.id` (Foreign Key, nullable)
- `audio_files.user_id` → `users.id` (Foreign Key, NOT NULL)

---

### 3.2 characters 테이블

**모델 파일**: `app/models/generation.py`  
**용도**: 캐릭터 정보 저장 (사전설정 캐릭터 및 사용자 생성 캐릭터)

#### 스키마

| 필드명 | 타입 | 제약조건 | 설명 |
|--------|------|----------|------|
| `id` | String(36) | PK | UUID 문자열 |
| `user_id` | String(36) | FK(users.id), NULLABLE | 소유자 ID (사전설정 캐릭터는 NULL) |
| `name` | String(100) | NOT NULL | 캐릭터 이름 |
| `description` | Text | NULLABLE | 캐릭터 설명 |
| `persona` | Text | NULLABLE | 캐릭터 페르소나 (성격, 말투 등) ✅ **추가됨** |
| `voice_id` | String(50) | NULLABLE, DEFAULT="default" | TTS 음성 ID ✅ **추가됨** |
| `character` | Text | NULLABLE | 캐릭터 속성 (JSON 문자열) ✅ **추가됨** |
| `is_preset` | Boolean | NOT NULL, DEFAULT=False | 사전설정 캐릭터 여부 |
| `category` | String(50) | NULLABLE | 카테고리 (애니메이션, 소설, 영화 등) |
| `tags` | Text | NULLABLE | 태그 목록 (JSON 문자열) |
| `sample_dialogue` | Text | NULLABLE | 샘플 대화 텍스트 |
| `image_url` | String(255) | NULLABLE | 이미지 URL (로컬 assets 경로) |
| `model_url` | String(255) | NULLABLE | 3D 모델 GLB 파일 경로 |
| `thumbnail_url` | String(255) | NULLABLE | 썸네일 이미지 URL |
| `created_at` | DateTime(timezone=True) | DEFAULT=now() | 생성 시간 |
| `updated_at` | DateTime(timezone=True) | NULLABLE | 수정 시간 ✅ **추가됨** |

#### 인덱스

- `id` (Primary Key)

#### 관계

- `user_id` → `users.id` (Foreign Key, nullable)

#### 최근 업데이트 (2026-01-26)

- ✅ `persona` 필드 추가: 캐릭터 페르소나 설명 (텍스트)
- ✅ `voice_id` 필드 추가: TTS 음성 ID (기본값: "default")
- ⚠️ `character` 필드: 현재 모델에는 없으나 API 요청/응답에서 사용 가능 (JSON 문자열)

**상세 구현 내역**: `docs/구현_상태_요약_2026-01-26.md` 참조

#### 특이사항

- `user_id`가 NULL인 경우 사전설정 캐릭터로 간주
- `tags` 필드는 JSON 문자열로 저장 (예: `["태그1", "태그2"]`)
- `is_preset=True`인 캐릭터는 수정/삭제 불가
- `voice_id`는 `app/config/voices.json`에서 매핑됨

---

### 3.3 generation_jobs 테이블

**모델 파일**: `app/models/generation.py`  
**용도**: 비동기 생성 작업 추적 (3D 생성, 스타일 변환, TTS 등)

#### 스키마

| 필드명 | 타입 | 제약조건 | 설명 |
|--------|------|----------|------|
| `id` | String(36) | PK | UUID 문자열 |
| `user_id` | String(36) | FK(users.id), NULLABLE | 작업 요청자 ID |
| `job_type` | String(20) | NOT NULL | 작업 유형 ('3d', 'style', 'tts') |
| `status` | String(20) | DEFAULT='pending' | 작업 상태 ('pending', 'processing', 'completed', 'failed') |
| `input_payload` | Text | NULLABLE | 입력 데이터 (JSON 문자열 또는 파일 경로) |
| `result_url` | String(255) | NULLABLE | 결과 파일 URL |
| `error_message` | Text | NULLABLE | 에러 메시지 (실패 시) |
| `progress` | Integer | DEFAULT=0 | 진행률 (0-100) |
| `created_at` | DateTime(timezone=True) | DEFAULT=now() | 생성 시간 |
| `completed_at` | DateTime(timezone=True) | NULLABLE | 완료 시간 |

#### 인덱스

- `id` (Primary Key)

#### 관계

- `user_id` → `users.id` (Foreign Key, nullable)

#### 특이사항

- `user_id`가 NULL인 경우 익명 사용자 작업
- `input_payload`는 JSON 문자열 또는 파일 경로를 저장
- `progress`는 백분율 (0-100)로 저장

---

### 3.4 audio_files 테이블

**모델 파일**: `app/models/audio.py`  
**용도**: TTS로 생성된 오디오 파일 메타데이터 저장 및 캐싱

#### 스키마

| 필드명 | 타입 | 제약조건 | 설명 |
|--------|------|----------|------|
| `id` | String(36) | PK | UUID 문자열 |
| `user_id` | String(36) | FK(users.id), NOT NULL, INDEX | 소유자 ID |
| `file_path` | String(500) | NOT NULL | 파일 저장 경로 |
| `file_url` | String(500) | NOT NULL | 파일 접근 URL |
| `file_size` | Integer | NOT NULL | 파일 크기 (바이트) |
| `duration` | Float | NULLABLE | 재생 시간 (초) |
| `format` | String(10) | NOT NULL | 파일 포맷 ('wav', 'ogg', 'aac', 'raw') |
| `voice_id` | String(50) | NULLABLE | 사용된 TTS 음성 ID |
| `text_hash` | String(64) | NULLABLE, INDEX | 텍스트 해시 (SHA256, 캐싱용) |
| `created_at` | DateTime(timezone=True) | DEFAULT=now() | 생성 시간 |

#### 인덱스

- `id` (Primary Key)
- `user_id` (Index)
- `text_hash` (Index, 캐싱 조회용)

#### 관계

- `user_id` → `users.id` (Foreign Key, NOT NULL)

#### 특이사항

- `text_hash`와 `voice_id`, `format`을 조합하여 캐싱 조회
- 동일한 텍스트, 음성, 포맷 조합이면 기존 파일 재사용
- `file_path`는 서버 내부 경로, `file_url`은 클라이언트 접근 URL

---

## 4. 문서와의 차이점

### 4.1 문서에만 있는 테이블

#### 4.1.1 chat_sessions 테이블

**문서 위치**: `docs/FINALFINAL.md` (2456-2481줄)

```sql
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    character_id UUID REFERENCES characters(id),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP
);
```

**현재 상태**: ❌ **구현되지 않음**

**이유**: 
- Frontend에서 `ChatHistory`를 localStorage에 저장
- Backend에 세션 저장 기능이 아직 구현되지 않음
- `chat.py`에서 `session_id`는 요청마다 생성되지만 DB에 저장하지 않음

**향후 계획**: 
- Phase 5.2 (컨텍스트 절약) 구현 시 필요할 수 있음
- 백업 및 동기화 목적으로 구현 검토 필요

#### 4.1.2 messages 테이블

**문서 위치**: `docs/FINALFINAL.md` (2484-2492줄)

```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES chat_sessions(id),
    role VARCHAR(20) NOT NULL,  -- 'user' | 'assistant'
    content TEXT NOT NULL,
    audio_url VARCHAR(255),
    model_used VARCHAR(50),  -- 'gemma-3-27b-it' | 'dolphin-2.9-8b'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**현재 상태**: ❌ **구현되지 않음**

**이유**:
- Frontend에서 `Message[]`를 `ChatHistory` 내부에 배열로 저장
- Backend에 메시지 저장 기능이 아직 구현되지 않음
- 현재는 요청마다 메시지 배열을 전송하지만 DB에 저장하지 않음

**향후 계획**:
- Phase 5.2 (컨텍스트 절약) 구현 시 필요할 수 있음
- 개별 메시지 조회 및 분석 목적으로 구현 검토 필요

### 4.2 필드 차이점

#### 4.2.1 users 테이블

| 필드 | 문서 | 실제 구현 | 상태 |
|------|------|----------|------|
| `id` | UUID | String(36) | ✅ 일치 (UUID 문자열) |
| `username` | VARCHAR(50), UNIQUE, NOT NULL | String(50), nullable | ⚠️ 차이 (nullable) |
| `email` | VARCHAR(100), UNIQUE, NOT NULL | String(100), UNIQUE, NOT NULL | ✅ 일치 |
| `created_at` | TIMESTAMP | DateTime(timezone=True) | ✅ 일치 |
| `picture` | 없음 | String(255), nullable | ➕ 추가 (OAuth 프로필 사진) |
| `is_active` | 없음 | Boolean, default=True | ➕ 추가 (계정 활성화) |
| `is_superuser` | 없음 | Boolean, default=False | ➕ 추가 (관리자) |
| `provider` | 없음 | String(20), default="google" | ➕ 추가 (OAuth 제공자) |
| `updated_at` | 없음 | DateTime(timezone=True) | ➕ 추가 (수정 시간) |

**분석**:
- 문서는 기본적인 필드만 포함
- 실제 구현은 OAuth 인증에 필요한 필드 추가
- `username`이 nullable인 이유: Google 계정에서 이름을 제공하지 않을 수 있음

#### 4.2.2 characters 테이블

| 필드 | 문서 | 실제 구현 | 상태 |
|------|------|----------|------|
| `id` | UUID | String(36) | ✅ 일치 |
| `user_id` | UUID, REFERENCES users(id) | String(36), FK, nullable | ✅ 일치 |
| `name` | VARCHAR(100), NOT NULL | String(100), NOT NULL | ✅ 일치 |
| `persona` | TEXT | Text, nullable | ✅ 일치 |
| `model_url` | VARCHAR(255) | String(255), nullable | ✅ 일치 |
| `thumbnail_url` | VARCHAR(255) | String(255), nullable | ✅ 일치 |
| `created_at` | TIMESTAMP | DateTime(timezone=True) | ✅ 일치 |
| `description` | 없음 | Text, nullable | ➕ 추가 |
| `voice_id` | 없음 | String(50), nullable | ➕ 추가 (TTS 음성) |
| `is_preset` | 없음 | Boolean, default=False | ➕ 추가 (사전설정 구분) |
| `category` | 없음 | String(50), nullable | ➕ 추가 (카테고리) |
| `tags` | 없음 | Text, nullable (JSON) | ➕ 추가 (태그) |
| `sample_dialogue` | 없음 | Text, nullable | ➕ 추가 (샘플 대화) |
| `image_url` | 없음 | String(255), nullable | ➕ 추가 (이미지) |

**분석**:
- 문서는 기본 필드만 포함
- 실제 구현은 최근 확장된 필드들 포함 (TTS, 카테고리, 태그 등)
- 캐릭터 선택/생성 기능 구현 시 추가된 필드들

#### 4.2.3 generation_jobs 테이블

| 필드 | 문서 | 실제 구현 | 상태 |
|------|------|----------|------|
| `id` | UUID | String(36) | ✅ 일치 |
| `user_id` | UUID, REFERENCES users(id) | String(36), FK, nullable | ✅ 일치 |
| `status` | VARCHAR(20), DEFAULT='pending' | String(20), default='pending' | ✅ 일치 |
| `created_at` | TIMESTAMP | DateTime(timezone=True) | ✅ 일치 |
| `completed_at` | TIMESTAMP | DateTime(timezone=True), nullable | ✅ 일치 |
| `error_message` | TEXT | Text, nullable | ✅ 일치 |
| `input_image_url` | VARCHAR(255) | 없음 | ❌ 제거 |
| `output_model_url` | VARCHAR(255) | 없음 | ❌ 제거 |
| `job_type` | 없음 | String(20), NOT NULL | ➕ 추가 (작업 유형) |
| `input_payload` | 없음 | Text, nullable | ➕ 추가 (유연한 입력) |
| `result_url` | 없음 | String(255), nullable | ➕ 추가 (결과 URL) |
| `progress` | 없음 | Integer, default=0 | ➕ 추가 (진행률) |

**분석**:
- 문서는 이미지 기반 생성만 가정 (`input_image_url`, `output_model_url`)
- 실제 구현은 다양한 작업 유형 지원 (`job_type`: '3d', 'style', 'tts')
- `input_payload`와 `result_url`로 더 유연한 구조

### 4.3 누락된 테이블

#### 4.3.1 audio_files 테이블

**문서**: ❌ 언급되지 않음  
**실제**: ✅ 구현됨

**이유**: TTS API 구현 시 추가된 테이블로, 문서 작성 시점에는 없었음

---

### 3.5 세션 관리 (향후 구현 예정)

**Phase 5.2에서 구현 예정**

**용도**: 세션별 대화 히스토리 저장 및 컨텍스트 절약 요약 기능

**예상 구조** (Redis 기반):
- 세션 ID: UUID 문자열
- 대화 히스토리: JSON 배열 (메시지 배열)
- 토큰 수: 현재 컨텍스트 토큰 수
- 요약 정보: 이전 턴 요약 텍스트 (슬라이딩 윈도우 전략)

**참고 문서**: `docs/PHASE5_SETUP.md`의 "Phase 5.2: 컨텍스트 절약 요약 기능 구현" 섹션

---

## 5. Frontend 데이터 구조

### 5.1 Zustand Store 구조

**파일**: `madcamp-Screening-Humanity-FRONT/lib/store.ts`

#### 5.1.1 ChatHistory (localStorage 저장)

```typescript
interface ChatHistory {
  id: string                    // Date.now().toString()
  scenario: {
    background: string
    opponent: string
    situation: string
  }
  messages: Message[]
  turnCount: number
  createdAt: Date
  updatedAt: Date
  generatedScript: string
  displayName: string
}
```

**저장 위치**: localStorage (`life-theater-storage`)

**Backend 매핑**: ❌ **없음** (현재는 Frontend에만 저장)

#### 5.1.2 Message

```typescript
interface Message {
  id: string
  role: "user" | "ai" | "system"
  content: string
  emotion?: string
  timestamp: Date
}
```

**Backend 매핑**: 
- `chat.py`의 `Message` 모델과 유사하지만 DB에 저장하지 않음
- 요청 시에만 전송

#### 5.1.3 Character

```typescript
interface Character {
  id: string
  name: string
  description?: string
  persona?: string
  voice_id?: string
  category?: string
  tags?: string[]
  sample_dialogue?: string
  image_url?: string
  is_preset: boolean
  user_id?: string
  created_at?: string
}
```

**Backend 매핑**: ✅ `characters` 테이블과 일치

### 5.2 localStorage 저장 구조

**키**: `life-theater-storage`

**저장 데이터**:
```typescript
{
  chatHistories: ChatHistory[]
  userName: string
  displayName: string
  isLoggedIn: boolean
}
```

**특이사항**:
- `messages`, `scenario` 등은 `chatHistories` 내부에 저장
- Backend와 동기화되지 않음
- 브라우저별로 독립적

---

## 6. ERD 다이어그램

```mermaid
erDiagram
    users ||--o{ characters : "has"
    users ||--o{ generation_jobs : "creates"
    users ||--o{ audio_files : "owns"
    
    users {
        string id PK
        string email UK "NOT NULL"
        string username
        string picture
        boolean is_active
        boolean is_superuser
        string provider
        datetime created_at
        datetime updated_at
    }
    
    characters {
        string id PK
        string user_id FK "nullable"
        string name "NOT NULL"
        text description
        text persona
        string voice_id
        boolean is_preset "NOT NULL"
        string category
        text tags "JSON"
        text sample_dialogue
        string image_url
        string model_url
        string thumbnail_url
        datetime created_at
    }
    
    generation_jobs {
        string id PK
        string user_id FK "nullable"
        string job_type "NOT NULL"
        string status
        text input_payload
        string result_url
        text error_message
        integer progress
        datetime created_at
        datetime completed_at
    }
    
    audio_files {
        string id PK
        string user_id FK "NOT NULL"
        string file_path "NOT NULL"
        string file_url "NOT NULL"
        integer file_size "NOT NULL"
        float duration
        string format "NOT NULL"
        string voice_id
        string text_hash "INDEX"
        datetime created_at
    }
```

---

## 7. 마이그레이션 가이드

### 7.1 문서 스키마에서 현재 스키마로 마이그레이션

#### 7.1.1 users 테이블 마이그레이션

```sql
-- 기존 테이블이 있다면
ALTER TABLE users 
  ADD COLUMN IF NOT EXISTS picture VARCHAR(255),
  ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS is_superuser BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS provider VARCHAR(20) DEFAULT 'google',
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE;

-- username을 nullable로 변경 (이미 nullable이면 무시)
-- SQLite는 ALTER COLUMN을 지원하지 않으므로 테이블 재생성 필요
```

#### 7.1.2 characters 테이블 마이그레이션

```sql
ALTER TABLE characters
  ADD COLUMN IF NOT EXISTS description TEXT,
  ADD COLUMN IF NOT EXISTS voice_id VARCHAR(50),
  ADD COLUMN IF NOT EXISTS is_preset BOOLEAN DEFAULT FALSE NOT NULL,
  ADD COLUMN IF NOT EXISTS category VARCHAR(50),
  ADD COLUMN IF NOT EXISTS tags TEXT,
  ADD COLUMN IF NOT EXISTS sample_dialogue TEXT,
  ADD COLUMN IF NOT EXISTS image_url VARCHAR(255);
```

#### 7.1.3 generation_jobs 테이블 마이그레이션

```sql
-- 기존 필드 제거 (데이터 백업 필요)
-- ALTER TABLE generation_jobs DROP COLUMN input_image_url;
-- ALTER TABLE generation_jobs DROP COLUMN output_model_url;

-- 새 필드 추가
ALTER TABLE generation_jobs
  ADD COLUMN IF NOT EXISTS job_type VARCHAR(20) NOT NULL DEFAULT '3d',
  ADD COLUMN IF NOT EXISTS input_payload TEXT,
  ADD COLUMN IF NOT EXISTS result_url VARCHAR(255),
  ADD COLUMN IF NOT EXISTS progress INTEGER DEFAULT 0;
```

#### 7.1.4 audio_files 테이블 추가

```sql
CREATE TABLE IF NOT EXISTS audio_files (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_url VARCHAR(500) NOT NULL,
    file_size INTEGER NOT NULL,
    duration FLOAT,
    format VARCHAR(10) NOT NULL,
    voice_id VARCHAR(50),
    text_hash VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_audio_files_user_id ON audio_files(user_id);
CREATE INDEX IF NOT EXISTS idx_audio_files_text_hash ON audio_files(text_hash);
```

### 7.2 SQLAlchemy 자동 마이그레이션

현재는 `Base.metadata.create_all()`을 사용하여 자동으로 테이블을 생성합니다.

**주의사항**:
- 기존 테이블이 있어도 새 컬럼은 자동으로 추가되지 않음
- 수동 마이그레이션 또는 Alembic 도입 필요

### 7.3 Alembic 도입 권장

향후 마이그레이션 관리를 위해 Alembic 도입을 권장합니다.

```bash
# Alembic 초기화
alembic init alembic

# 마이그레이션 생성
alembic revision --autogenerate -m "Add character fields"

# 마이그레이션 적용
alembic upgrade head
```

---

## 8. 향후 계획

### 8.1 누락된 테이블 구현

#### 8.1.1 chat_sessions 테이블

**필요성**: 
- Phase 5.2 (컨텍스트 절약) 구현 시 필요
- 세션별 대화 히스토리 관리
- 백업 및 동기화

**예상 스키마**:
```python
class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    character_id = Column(String(36), ForeignKey("characters.id"), nullable=True)
    scenario = Column(Text, nullable=True)  # JSON 문자열
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)
    turn_count = Column(Integer, default=0)
```

#### 8.1.2 messages 테이블

**필요성**:
- Phase 5.2 (컨텍스트 절약) 구현 시 필요
- 개별 메시지 조회 및 분석
- 대화 히스토리 관리

**예상 스키마**:
```python
class Message(Base):
    __tablename__ = "messages"
    
    id = Column(String(36), primary_key=True)
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    audio_url = Column(String(500), nullable=True)
    model_used = Column(String(50), nullable=True)
    emotion = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

### 8.2 Frontend-Backend 동기화

#### 8.2.1 ChatHistory 백업

**현재**: localStorage에만 저장  
**향후**: Backend에 `chat_sessions`와 `messages`로 저장

**구현 계획**:
1. `POST /api/chat/sessions` - 세션 생성
2. `POST /api/chat/sessions/{session_id}/messages` - 메시지 저장
3. `GET /api/chat/sessions` - 사용자 세션 목록 조회
4. `GET /api/chat/sessions/{session_id}/messages` - 세션 메시지 조회

### 8.3 인덱스 최적화

#### 8.3.1 추가 권장 인덱스

```sql
-- characters 테이블
CREATE INDEX idx_characters_user_id ON characters(user_id);
CREATE INDEX idx_characters_is_preset ON characters(is_preset);
CREATE INDEX idx_characters_category ON characters(category);

-- generation_jobs 테이블
CREATE INDEX idx_generation_jobs_user_id ON generation_jobs(user_id);
CREATE INDEX idx_generation_jobs_status ON generation_jobs(status);
CREATE INDEX idx_generation_jobs_job_type ON generation_jobs(job_type);

-- audio_files 테이블 (이미 있음)
-- idx_audio_files_user_id
-- idx_audio_files_text_hash
```

### 8.4 데이터 정합성 검증

#### 8.4.1 Foreign Key 제약조건

현재 SQLAlchemy 모델에는 Foreign Key 관계가 정의되어 있지만, SQLite에서는 제약조건이 제대로 작동하지 않을 수 있습니다.

**PostgreSQL 사용 시**:
- Foreign Key 제약조건이 자동으로 적용됨
- CASCADE 삭제 정책 설정 필요

#### 8.4.2 데이터 검증

- `characters.is_preset=True`일 때 `user_id`는 NULL이어야 함
- `audio_files.text_hash`는 SHA256 해시 형식 (64자)
- `generation_jobs.progress`는 0-100 범위

---

## 9. 요약

### 9.1 현재 상태

- ✅ **4개 테이블 구현됨**: users, characters, generation_jobs, audio_files
- ❌ **2개 테이블 누락**: chat_sessions, messages (문서에만 존재)
- ⚠️ **Frontend-Backend 동기화 없음**: ChatHistory는 localStorage에만 저장

### 9.2 주요 차이점

1. **문서 vs 실제**: 실제 구현이 더 많은 필드를 포함 (최근 기능 추가)
2. **누락된 테이블**: chat_sessions, messages는 문서에만 있고 구현되지 않음
3. **Frontend 저장**: ChatHistory는 Backend에 저장되지 않고 localStorage에만 저장

### 9.3 다음 단계

1. **즉시**: 데이터베이스 스키마 문서화 완료 (이 문서)
2. **단기**: chat_sessions, messages 테이블 구현 검토
3. **중기**: Frontend-Backend 동기화 구현
4. **장기**: Alembic 마이그레이션 도입

---

## 부록

### A. SQLAlchemy 모델 파일 위치

- `app/models/user.py` - User 모델
- `app/models/generation.py` - GenerationJob, Character 모델
- `app/models/audio.py` - AudioFile 모델

### B. 관련 설정 파일

- `app/core/database.py` - 데이터베이스 엔진 및 세션 설정
- `app/core/config.py` - DATABASE_URL 설정
- `.env` - 실제 데이터베이스 연결 정보

### C. 참고 문서

- `docs/FINALFINAL.md` - 원본 스키마 문서 (2456-2505줄)
- `docs/프로젝트_통합_진행상황_명세서.md` - 프로젝트 진행 상황
- `docs/미구현_항목_체크리스트.md` - 미구현 기능 목록

---

**문서 버전**: 1.0  
**최종 수정일**: 2026-01-26  
**작성자**: AI Assistant
