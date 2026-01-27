"""
TTS API 엔드포인트
Server A의 GPT-SoVITS와 연동하여 텍스트를 음성으로 변환합니다.
"""
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
import httpx
import uuid
import os
import json
import hashlib
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.api.deps import get_db
from app.models.user import User
from app.models.audio import AudioFile
from app.services.audio_analyzer import AudioAnalyzer

router = APIRouter()

# voice_id 매핑 설정 로드
_voices_config = None

def load_voices_config():
    """voice_id 매핑 설정 파일 로드"""
    global _voices_config
    if _voices_config is None:
        config_path = Path(__file__).parent.parent / "config" / "voices.json"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                _voices_config = json.load(f)
        except FileNotFoundError:
            _voices_config = {
                "default_voice_id": "default",
                "voices": []
            }
    return _voices_config

def get_ref_audio_path(voice_id: Optional[str] = None) -> Optional[str]:
    """voice_id로 ref_audio_path 조회 (JSON 파일 기반 - 레거시)"""
    config = load_voices_config()
    
    if voice_id is None:
        voice_id = config.get("default_voice_id", "default")
    
    for voice in config.get("voices", []):
        if voice.get("id") == voice_id:
            return voice.get("ref_audio_path")
    
    return None


async def get_voice_from_db(voice_id: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
    """
    DB에서 voice_id로 음성 정보 조회
    
    Returns:
        음성 정보 딕셔너리 또는 None
    """
    from app.models.voice import Voice
    
    result = await db.execute(
        select(Voice).where(Voice.id == voice_id, Voice.is_active == True)
    )
    voice = result.scalar_one_or_none()
    
    if voice:
        return {
            "id": voice.id,
            "name": voice.name,
            "ref_audio_path": voice.ref_audio_path,
            "prompt_text": voice.prompt_text,
            "prompt_lang": voice.prompt_lang,
            "language": voice.language
        }
    return None


async def get_default_voice_from_db(db: AsyncSession) -> Optional[Dict[str, Any]]:
    """
    DB에서 기본 음성 조회
    
    Returns:
        기본 음성 정보 딕셔너리 또는 None
    """
    from app.models.voice import Voice
    
    result = await db.execute(
        select(Voice).where(Voice.is_default == True, Voice.is_active == True)
    )
    voice = result.scalar_one_or_none()
    
    if voice:
        return {
            "id": voice.id,
            "name": voice.name,
            "ref_audio_path": voice.ref_audio_path,
            "prompt_text": voice.prompt_text,
            "prompt_lang": voice.prompt_lang,
            "language": voice.language
        }
    return None


class TTSRequest(BaseModel):
    """TTS 요청 모델 (GPT-SoVITS API와 호환)"""
    # 필수 필드
    text: str = Field(..., description="합성할 텍스트")
    text_lang: str = Field(default="ko", description="텍스트 언어 (zh, en, ja, ko 등)")
    
    # 참조 오디오 (voice_id 또는 ref_audio_path 중 하나)
    voice_id: Optional[str] = Field(None, description="음성 ID (설정 파일에서 매핑)")
    ref_audio_path: Optional[str] = Field(None, description="참조 오디오 파일 경로 (Server A 내부 경로, 직접 지정)")
    prompt_lang: str = Field(default="ko", description="참조 오디오의 언어")
    prompt_text: Optional[str] = Field("", description="참조 오디오의 텍스트")
    aux_ref_audio_paths: Optional[List[str]] = Field(default=[], description="다화자 톤 융합을 위한 추가 참조 오디오 경로 리스트")
    
    # 추론 및 품질 설정
    top_k: int = Field(default=5, description="Top-K 샘플링")
    top_p: float = Field(default=1.0, description="Top-P 샘플링")
    temperature: float = Field(default=1.0, description="샘플링 온도")
    repetition_penalty: float = Field(default=1.35, description="반복 패널티")
    batch_size: int = Field(default=1, description="추론 배치 크기")
    speed_factor: float = Field(default=1.0, description="발화 속도 조절 (1.0 = 정속)")
    seed: int = Field(default=-1, description="랜덤 시드 (-1 = 무작위)")
    parallel_infer: bool = Field(default=True, description="병렬 추론 사용 여부")
    
    # 텍스트 처리
    text_split_method: str = Field(default="cut5", description="텍스트 분할 방식")
    batch_threshold: float = Field(default=0.75, description="배치 분할 임계값")
    split_bucket: bool = Field(default=True, description="배치를 버킷으로 나눌지 여부")
    
    # 출력 형식
    media_type: str = Field(default="wav", description="응답 포맷 (wav, ogg, aac, raw)")
    streaming_mode: int = Field(default=0, description="스트리밍 모드 (0=비활성화, 1-3=품질별)")
    
    # 스트리밍 세부 설정
    overlap_length: int = Field(default=2, description="스트리밍 시맨틱 토큰 중첩 길이")
    min_chunk_length: int = Field(default=16, description="스트리밍 최소 청크 길이")
    fragment_interval: float = Field(default=0.3, description="오디오 조각 간격 제어")
    
    # VITS 모델 고급 설정
    sample_steps: int = Field(default=32, description="VITS 모델 샘플링 스텝 수")
    super_sampling: bool = Field(default=False, description="VITS 초해상도 사용 여부")
    
    # 응답 형식 선택
    return_binary: bool = Field(default=False, description="오디오 바이너리를 직접 반환할지 여부 (False면 JSON 반환)")
    
    @validator("text")
    def validate_text(cls, v):
        """텍스트 유효성 검사"""
        if not v or not v.strip():
            raise ValueError("텍스트가 비어있습니다")
        
        # 텍스트 길이 제한 확인 (기본값 10000자)
        max_length = int(os.getenv("TTS_MAX_TEXT_LENGTH", "10000"))
        if len(v) > max_length:
            raise ValueError(f"텍스트 길이가 제한을 초과했습니다 (최대 {max_length}자)")
        
        return v.strip()
    
    @validator("media_type")
    def validate_media_type(cls, v):
        """미디어 타입 유효성 검사"""
        allowed_types = ["wav", "ogg", "aac", "raw"]
        if v not in allowed_types:
            raise ValueError(f"지원하지 않는 미디어 타입입니다: {v}. 허용된 타입: {', '.join(allowed_types)}")
        return v
    
    def model_dump_for_gpt_sovits(self) -> Dict[str, Any]:
        """GPT-SoVITS API 호출용 딕셔너리 생성"""
        data = self.model_dump(exclude={"voice_id", "return_binary"})
        
        # ref_audio_path 결정 (voice_id 우선, 없으면 직접 지정한 값)
        if not data.get("ref_audio_path"):
            if self.voice_id:
                ref_path = get_ref_audio_path(self.voice_id)
                if ref_path:
                    data["ref_audio_path"] = ref_path
                else:
                    raise ValueError(f"voice_id '{self.voice_id}'에 해당하는 ref_audio_path를 찾을 수 없습니다")
            else:
                # 기본 voice_id 사용
                ref_path = get_ref_audio_path()
                if ref_path:
                    data["ref_audio_path"] = ref_path
                else:
                    raise ValueError("ref_audio_path 또는 voice_id가 필요합니다")
        
        return data


async def _synthesize_tts_internal(
    request: TTSRequest,
    current_user: User,
    db: AsyncSession
) -> Dict[str, Any]:
    """
    TTS 합성 내부 함수 (다른 모듈에서 직접 호출 가능)
    
    Args:
        request: TTS 요청 (return_binary는 False여야 함)
        current_user: 현재 사용자
        db: 데이터베이스 세션
    
    Returns:
        성공 시: {"success": True, "data": {...}}
        실패 시: HTTPException 발생
    
    Note:
        - return_binary=True는 지원하지 않음 (HTTP 엔드포인트에서만 처리)
        - voice_id를 사용하면 설정 파일에서 ref_audio_path를 자동 매핑
    """
    try:
        # 텍스트 해시 생성 (캐싱용)
        text_hash = hashlib.sha256(request.text.encode("utf-8")).hexdigest()
        
        # 캐싱 확인 (return_binary가 False일 때만)
        cached_audio = None
        if not request.return_binary:
            result = await db.execute(
                select(AudioFile).where(
                    AudioFile.text_hash == text_hash,
                    AudioFile.voice_id == (request.voice_id or "default"),
                    AudioFile.format == request.media_type
                )
            )
            cached_audio = result.scalar_one_or_none()
            
            if cached_audio:
                # 캐시된 파일 반환
                return {
                    "success": True,
                    "data": {
                        "audio_url": cached_audio.file_url,
                        "file_id": cached_audio.id,
                        "duration": cached_audio.duration,
                        "file_size": cached_audio.file_size,
                        "format": cached_audio.format,
                        "voice_id": cached_audio.voice_id,
                        "created_at": cached_audio.created_at.isoformat() if cached_audio.created_at else None,
                        "cached": True
                    }
                }
        
        # GPT-SoVITS API 호출 준비
        gpt_sovits_request = request.model_dump_for_gpt_sovits()
        
        # TTS API URL 구성
        tts_base_url = settings.TTS_BASE_URL.rstrip("/")
        tts_api_path = settings.TTS_API_PATH.lstrip("/")
        tts_url = f"{tts_base_url}/{tts_api_path}"
        
        # 타임아웃 설정
        timeout = settings.TTS_TIMEOUT
        
        # SSL 검증 설정
        verify_ssl = settings.TTS_SSL_VERIFY
        
        # Server A GPT-SoVITS API 호출
        async with httpx.AsyncClient(verify=verify_ssl, timeout=timeout) as client:
            response = await client.post(
                tts_url,
                json=gpt_sovits_request,
                timeout=timeout
            )
            response.raise_for_status()
            
            # 오디오 바이너리 받기
            audio_content = response.content
            
            # 파일 크기 제한 확인
            max_file_size = settings.TTS_MAX_FILE_SIZE
            if len(audio_content) > max_file_size:
                raise HTTPException(
                    status_code=413,
                    detail=f"생성된 오디오 파일 크기가 제한을 초과했습니다 (최대 {max_file_size}바이트)"
                )
            
            # return_binary가 True면 바이너리 직접 반환 (HTTP 엔드포인트에서만 사용)
            # 내부 함수에서는 항상 JSON 반환
            if request.return_binary:
                # 내부 함수에서는 return_binary=True를 지원하지 않음
                # HTTP 엔드포인트에서만 처리
                raise ValueError("내부 함수에서는 return_binary=True를 지원하지 않습니다. HTTP 엔드포인트를 사용하세요.")
            
            # 파일 저장
            file_id = str(uuid.uuid4())
            file_ext = request.media_type
            file_name = f"{current_user.id}_{file_id}.{file_ext}"
            
            # 사용자별 디렉터리 생성
            audio_dir = Path(settings.USER_ASSETS_DIR) / "audio" / current_user.id
            audio_dir.mkdir(parents=True, exist_ok=True)
            
            file_path = audio_dir / file_name
            file_url = f"/assets/audio/{current_user.id}/{file_name}"
            
            # 파일 저장
            with open(file_path, "wb") as f:
                f.write(audio_content)
            
            # 오디오 파일 분석
            analyzer = AudioAnalyzer()
            audio_info = analyzer.analyze_audio(str(file_path))
            
            # 데이터베이스에 메타데이터 저장
            audio_file = AudioFile(
                id=file_id,
                user_id=current_user.id,
                file_path=str(file_path),
                file_url=file_url,
                file_size=audio_info["file_size"],
                duration=audio_info["duration"],
                format=audio_info["format"],
                voice_id=request.voice_id or "default",
                text_hash=text_hash
            )
            db.add(audio_file)
            await db.commit()
            await db.refresh(audio_file)
            
            # JSON 응답 반환
            return {
                "success": True,
                "data": {
                    "audio_url": audio_file.file_url,
                    "file_id": audio_file.id,
                    "duration": audio_file.duration,
                    "file_size": audio_file.file_size,
                    "format": audio_file.format,
                    "voice_id": audio_file.voice_id,
                    "created_at": audio_file.created_at.isoformat() if audio_file.created_at else None,
                    "cached": False
                }
            }
            
    except httpx.HTTPStatusError as e:
        # HTTP 에러 처리
        error_detail = f"TTS 서비스 HTTP 에러: {e.response.status_code}"
        if e.response.status_code == 503:
            error_detail += " (서비스 일시 중지 또는 과부하)"
        elif e.response.status_code == 404:
            error_detail += " (엔드포인트를 찾을 수 없음)"
        elif e.response.status_code == 500:
            error_detail += " (서버 내부 오류)"
        
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"TTS 서비스 HTTP 에러: {error_detail}"
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail=f"TTS 서비스 응답 시간 초과 ({timeout}초)"
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"TTS 서비스에 연결할 수 없습니다. 서비스가 실행 중인지 확인하세요. (URL: {tts_url})"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"TTS 요청 검증 오류: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"TTS 합성 중 오류 발생: {str(e)}"
        )


@router.post("/tts")
async def synthesize(request: TTSRequest):
    """
    텍스트를 음성으로 변환합니다 (인증 없이 사용 가능).
    GPT-SoVITS API를 직접 호출하여 오디오를 생성합니다.
    """
    try:
        # GPT-SoVITS API 호출 준비
        gpt_sovits_request = request.model_dump_for_gpt_sovits()
        
        # TTS API URL 구성
        tts_base_url = settings.TTS_BASE_URL.rstrip("/")
        tts_api_path = settings.TTS_API_PATH.lstrip("/")
        tts_url = f"{tts_base_url}/{tts_api_path}"
        
        # Server A GPT-SoVITS API 호출
        async with httpx.AsyncClient(verify=settings.TTS_SSL_VERIFY, timeout=settings.TTS_TIMEOUT) as client:
            response = await client.post(tts_url, json=gpt_sovits_request)
            response.raise_for_status()
            audio_content = response.content
        
        # return_binary=True면 오디오 바이너리 직접 반환
        if request.return_binary:
            media_type_map = {
                "wav": "audio/wav",
                "ogg": "audio/ogg",
                "aac": "audio/aac",
                "raw": "audio/raw"
            }
            return Response(
                content=audio_content,
                media_type=media_type_map.get(request.media_type, "audio/wav"),
                headers={"Content-Disposition": f"attachment; filename=tts_output.{request.media_type}"}
            )
        
        # JSON 응답 (바이너리 저장 없이 base64로 반환)
        import base64
        audio_base64 = base64.b64encode(audio_content).decode("utf-8")
        return {
            "success": True,
            "data": {
                "audio_base64": audio_base64,
                "format": request.media_type,
                "voice_id": request.voice_id or "default"
            }
        }
        
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"TTS 서비스 오류: {e.response.status_code}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="TTS 서비스 응답 시간 초과")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail=f"TTS 서비스 연결 실패 (URL: {tts_url})")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"TTS 요청 오류: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS 합성 오류: {str(e)}")


@router.get("/tts/voices")
async def list_voices(db: AsyncSession = Depends(get_db)):
    """
    사용 가능한 음성 목록을 조회합니다.
    DB에서 활성화된 음성 목록을 반환합니다.
    """
    from app.models.voice import Voice
    
    # DB에서 활성화된 음성 조회
    result = await db.execute(
        select(Voice).where(Voice.is_active == True).order_by(Voice.is_default.desc(), Voice.name)
    )
    db_voices = result.scalars().all()
    
    voices = []
    default_voice_id = None
    
    for voice in db_voices:
        voices.append({
            "id": voice.id,
            "name": voice.name,
            "language": voice.language,
            "description": voice.description or ""
        })
        if voice.is_default:
            default_voice_id = voice.id
    
    # DB에 음성이 없으면 빈 목록 반환 (기본 음성 없음)
    # 사용자가 직접 음성을 등록해야 함
    
    return {
        "success": True,
        "data": {
            "voices": voices,
            "default_voice_id": default_voice_id
        }
    }
