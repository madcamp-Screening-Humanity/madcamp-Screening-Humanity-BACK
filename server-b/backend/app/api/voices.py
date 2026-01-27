"""
Voice 관리 API 엔드포인트
음성 목록 조회, 등록, 수정, 삭제 및 테스트 기능을 제공합니다.
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
import httpx

from app.api.deps import get_db, get_current_user
from app.models.voice import Voice
from app.models.user import User
from app.core.config import settings

router = APIRouter()


# ============ 요청/응답 모델 ============

class VoiceBase(BaseModel):
    """음성 기본 정보"""
    name: str = Field(..., min_length=1, max_length=100, description="음성 이름")
    description: Optional[str] = Field(None, description="음성 설명")
    language: str = Field(default="ko", description="언어 코드")
    ref_audio_path: str = Field(..., description="Server A 내부 참조 오디오 경로")
    prompt_text: Optional[str] = Field(default="", description="참조 오디오의 텍스트")
    prompt_lang: str = Field(default="ko", description="참조 오디오 언어")
    # GPT-SoVITS Fine-tuned 모델 설정
    gpt_weights_path: Optional[str] = Field(None, description="GPT 모델 경로")
    sovits_weights_path: Optional[str] = Field(None, description="SoVITS 모델 경로")
    model_version: str = Field(default="v2", description="모델 버전")
    train_voice_folder: Optional[str] = Field(None, description="훈련 음성 폴더명")
    is_default: bool = Field(default=False, description="기본 음성 여부")
    is_active: bool = Field(default=True, description="활성화 상태")


class VoiceCreateRequest(VoiceBase):
    """음성 생성 요청"""
    pass


class VoiceUpdateRequest(BaseModel):
    """음성 수정 요청 (모든 필드 선택적)"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    language: Optional[str] = None
    ref_audio_path: Optional[str] = None
    prompt_text: Optional[str] = None
    prompt_lang: Optional[str] = None
    gpt_weights_path: Optional[str] = None
    sovits_weights_path: Optional[str] = None
    model_version: Optional[str] = None
    train_voice_folder: Optional[str] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class VoiceResponse(BaseModel):
    """음성 응답 모델"""
    id: str
    name: str
    description: Optional[str]
    language: str
    ref_audio_path: str
    prompt_text: Optional[str]
    prompt_lang: str
    gpt_weights_path: Optional[str] = None
    sovits_weights_path: Optional[str] = None
    model_version: Optional[str] = None
    train_voice_folder: Optional[str] = None
    is_default: bool
    is_active: bool
    created_at: Optional[str]
    updated_at: Optional[str]
    
    class Config:
        from_attributes = True


class VoiceListResponse(BaseModel):
    """음성 목록 응답"""
    voices: List[VoiceResponse]
    total: int


class VoiceTestRequest(BaseModel):
    """음성 테스트 요청"""
    text: str = Field(default="안녕하세요, 반갑습니다.", description="테스트 텍스트")


# ============ 관리자 권한 확인 ============

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    관리자 권한 확인 의존성
    ADMIN_EMAILS 환경변수에 등록된 이메일만 관리자로 인정
    """
    if not current_user or not current_user.email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 필요합니다"
        )
    
    if not settings.is_admin(current_user.email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다"
        )
    
    return current_user


# ============ Server A 파일 관리 API (관리자, 순서 중요: ID 매칭 방지 위해 상단 배치) ============

@router.get("/voices/server-files")
async def get_server_files(
    current_user: User = Depends(require_admin)
):
    """
    Server A의 GPT-SoVITS 파일 목록 조회 (관리자 전용)
    
    Server A의 파일 스캔 API를 호출하여 모델, 훈련 음성, 참조 오디오 목록을 반환합니다.
    URL: /api/files/all
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            api_url = settings.SERVER_A_FILES_API_URL.rstrip("/")
            response = await client.get(f"{api_url}/api/files/all")
            
            if response.status_code == 200:
                return response.json()
            
            # API가 통합 엔드포인트를 지원하지 않는 경우 개별 조회
            models_res = await client.get(f"{api_url}/api/files/models")
            train_voices_res = await client.get(f"{api_url}/api/files/train-voices")
            ref_audio_res = await client.get(f"{api_url}/api/files/ref-audio")
            
            return {
                "models": models_res.json() if models_res.status_code == 200 else {},
                "train_voices": train_voices_res.json() if train_voices_res.status_code == 200 else {},
                "ref_audio": ref_audio_res.json() if ref_audio_res.status_code == 200 else {}
            }
            
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Server A 파일 API({settings.SERVER_A_FILES_API_URL})에 연결할 수 없습니다: {str(e)}"
        )


@router.post("/voices/server-files/upload")
async def upload_server_file(
    category: str = Form(..., description="ref_audio, train_voice, gpt_weights, sovits_weights"),
    file: UploadFile = File(...),
    sub_path: Optional[str] = Form(None),
    model_version: str = Form("v2"),
    current_user: User = Depends(require_admin)
):
    """
    Server A에 파일 업로드 (관리자 전용)
    
    대용량 모델 파일 업로드를 지원합니다. 타임아웃은 300초(5분)입니다.
    """
    api_url = settings.SERVER_A_FILES_API_URL.rstrip("/")
    upload_url = f"{api_url}/api/files/upload"
    
    try:
        # 파일 내용을 읽어서 전송 (메모리 효율을 위해 청크 단위 전송 고려 가능하나, httpx는 file-like 객체 지원)
        # UploadFile.file은 SpooledTemporaryFile 이므로 이를 활용
        files = {
            "file": (file.filename, file.file, file.content_type)
        }
        data = {
            "category": category,
            "sub_path": sub_path if sub_path else "",
            "model_version": model_version
        }
        
        # 대용량 파일 전송을 위해 타임아웃 길게 설정 (5분)
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(upload_url, data=data, files=files)
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Upload Failed: {response.text}"
                )
            
            return response.json()
            
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Server A 연결 실패: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"업로드 오류: {str(e)}"
        )


@router.delete("/voices/server-files")
async def delete_server_file(
    path: str,
    current_user: User = Depends(require_admin)
):
    """Server A 파일/폴더 삭제 (관리자 전용)"""
    api_url = settings.SERVER_A_FILES_API_URL.rstrip("/")
    delete_url = f"{api_url}/api/files"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.delete(delete_url, params={"path": path})
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Delete Failed: {response.text}"
                )
            
            return response.json()
            
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Server A 연결 실패: {str(e)}"
        )


@router.post("/voices/server-files/mkdir")
async def create_server_folder(
    path: str = Form(...),
    current_user: User = Depends(require_admin)
):
    """Server A 훈련 음성 폴더 생성 (관리자 전용)"""
    api_url = settings.SERVER_A_FILES_API_URL.rstrip("/")
    mkdir_url = f"{api_url}/api/files/mkdir"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(mkdir_url, data={"path": path})
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Mkdir Failed: {response.text}"
                )
            
            return response.json()
            
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Server A 연결 실패: {str(e)}"
        )


# ============ 공개 API (인증 불필요) ============

@router.get("/voices", response_model=VoiceListResponse)
async def list_voices(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """
    활성화된 음성 목록 조회 (공개 API)
    
    - active_only=True: 활성화된 음성만 조회 (기본값)
    - active_only=False: 모든 음성 조회 (관리자용)
    """
    query = select(Voice)
    if active_only:
        query = query.where(Voice.is_active == True)
    query = query.order_by(Voice.is_default.desc(), Voice.name)
    
    result = await db.execute(query)
    voices = result.scalars().all()
    
    voice_responses = []
    for voice in voices:
        voice_responses.append(VoiceResponse(
            id=voice.id,
            name=voice.name,
            description=voice.description,
            language=voice.language,
            ref_audio_path=voice.ref_audio_path,
            prompt_text=voice.prompt_text,
            prompt_lang=voice.prompt_lang,
            is_default=voice.is_default,
            is_active=voice.is_active,
            created_at=voice.created_at.isoformat() if voice.created_at else None,
            updated_at=voice.updated_at.isoformat() if voice.updated_at else None
        ))
    
    return VoiceListResponse(voices=voice_responses, total=len(voice_responses))


@router.get("/voices/{voice_id}", response_model=VoiceResponse)
async def get_voice(
    voice_id: str,
    db: AsyncSession = Depends(get_db)
):
    """특정 음성 조회"""
    result = await db.execute(
        select(Voice).where(Voice.id == voice_id)
    )
    voice = result.scalar_one_or_none()
    
    if not voice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"음성을 찾을 수 없습니다: {voice_id}"
        )
    
    return VoiceResponse(
        id=voice.id,
        name=voice.name,
        description=voice.description,
        language=voice.language,
        ref_audio_path=voice.ref_audio_path,
        prompt_text=voice.prompt_text,
        prompt_lang=voice.prompt_lang,
        is_default=voice.is_default,
        is_active=voice.is_active,
        created_at=voice.created_at.isoformat() if voice.created_at else None,
        updated_at=voice.updated_at.isoformat() if voice.updated_at else None
    )


# ============ 관리자 API (인증 필요) ============

@router.post("/voices", response_model=VoiceResponse)
async def create_voice(
    request: VoiceCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    새 음성 등록 (관리자 전용)
    
    - ref_audio_path: Server A 내부의 참조 오디오 파일 경로
    - is_default=True로 설정 시 기존 기본 음성은 자동으로 False로 변경
    """
    # is_default가 True면 기존 기본 음성 해제
    if request.is_default:
        await db.execute(
            Voice.__table__.update().where(Voice.is_default == True).values(is_default=False)
        )
    
    # 새 음성 생성
    voice = Voice(
        id=str(uuid.uuid4()),
        name=request.name,
        description=request.description,
        language=request.language,
        ref_audio_path=request.ref_audio_path,
        prompt_text=request.prompt_text,
        prompt_lang=request.prompt_lang,
        is_default=request.is_default,
        is_active=request.is_active
    )
    
    db.add(voice)
    await db.commit()
    await db.refresh(voice)
    
    return VoiceResponse(
        id=voice.id,
        name=voice.name,
        description=voice.description,
        language=voice.language,
        ref_audio_path=voice.ref_audio_path,
        prompt_text=voice.prompt_text,
        prompt_lang=voice.prompt_lang,
        is_default=voice.is_default,
        is_active=voice.is_active,
        created_at=voice.created_at.isoformat() if voice.created_at else None,
        updated_at=voice.updated_at.isoformat() if voice.updated_at else None
    )


@router.put("/voices/{voice_id}", response_model=VoiceResponse)
async def update_voice(
    voice_id: str,
    request: VoiceUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """음성 정보 수정 (관리자 전용)"""
    result = await db.execute(
        select(Voice).where(Voice.id == voice_id)
    )
    voice = result.scalar_one_or_none()
    
    if not voice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"음성을 찾을 수 없습니다: {voice_id}"
        )
    
    # is_default가 True로 변경되면 기존 기본 음성 해제
    if request.is_default is True and not voice.is_default:
        await db.execute(
            Voice.__table__.update().where(
                Voice.is_default == True,
                Voice.id != voice_id
            ).values(is_default=False)
        )
    
    # 업데이트할 필드만 적용
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(voice, key, value)
    
    await db.commit()
    await db.refresh(voice)
    
    return VoiceResponse(
        id=voice.id,
        name=voice.name,
        description=voice.description,
        language=voice.language,
        ref_audio_path=voice.ref_audio_path,
        prompt_text=voice.prompt_text,
        prompt_lang=voice.prompt_lang,
        is_default=voice.is_default,
        is_active=voice.is_active,
        created_at=voice.created_at.isoformat() if voice.created_at else None,
        updated_at=voice.updated_at.isoformat() if voice.updated_at else None
    )


@router.delete("/voices/{voice_id}")
async def delete_voice(
    voice_id: str,
    permanent: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    음성 삭제 (관리자 전용)
    
    - permanent=False: 비활성화만 (기본값)
    - permanent=True: 완전 삭제 (연결된 캐릭터의 voice_id가 NULL로 변경됨)
    """
    result = await db.execute(
        select(Voice).where(Voice.id == voice_id)
    )
    voice = result.scalar_one_or_none()
    
    if not voice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"음성을 찾을 수 없습니다: {voice_id}"
        )
    
    if permanent:
        # 완전 삭제
        await db.delete(voice)
        await db.commit()
        return {"success": True, "message": f"음성 '{voice.name}'이(가) 완전히 삭제되었습니다"}
    else:
        # 비활성화
        voice.is_active = False
        await db.commit()
        return {"success": True, "message": f"음성 '{voice.name}'이(가) 비활성화되었습니다"}


@router.post("/voices/{voice_id}/test")
async def test_voice(
    voice_id: str,
    request: VoiceTestRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    음성 테스트 (TTS 생성)
    
    지정된 음성으로 테스트 텍스트를 TTS 변환하여 base64 오디오 반환
    """
    # 음성 조회
    result = await db.execute(
        select(Voice).where(Voice.id == voice_id, Voice.is_active == True)
    )
    voice = result.scalar_one_or_none()
    
    if not voice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"음성을 찾을 수 없습니다: {voice_id}"
        )
    
    # GPT-SoVITS API 호출
    tts_base_url = settings.TTS_BASE_URL.rstrip("/")
    tts_api_path = settings.TTS_API_PATH.lstrip("/")
    tts_url = f"{tts_base_url}/{tts_api_path}"
    
    tts_request = {
        "text": request.text,
        "text_lang": voice.language,
        "ref_audio_path": voice.ref_audio_path,
        "prompt_text": voice.prompt_text or "",
        "prompt_lang": voice.prompt_lang,
        "streaming_mode": 0,
        "media_type": "wav"
    }
    
    try:
        async with httpx.AsyncClient(verify=settings.TTS_SSL_VERIFY, timeout=settings.TTS_TIMEOUT) as client:
            response = await client.post(tts_url, json=tts_request)
            response.raise_for_status()
            audio_content = response.content
        
        # Base64로 인코딩하여 반환
        import base64
        audio_base64 = base64.b64encode(audio_content).decode("utf-8")
        
        return {
            "success": True,
            "data": {
                "audio_base64": audio_base64,
                "format": "wav",
                "voice_id": voice.id,
                "voice_name": voice.name,
                "text": request.text
            }
        }
        
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"TTS 서비스 오류: {e.response.status_code}"
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="TTS 서비스 응답 시간 초과"
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"TTS 서비스 연결 실패: {tts_url}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"TTS 테스트 오류: {str(e)}"
        )
