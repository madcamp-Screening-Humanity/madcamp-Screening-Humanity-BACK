"""
오디오 파일 분석 서비스
mutagen 라이브러리를 사용하여 오디오 파일의 메타데이터를 추출합니다.
"""
import os
from typing import Optional, Dict, Any
from mutagen import File as MutagenFile
from mutagen.wave import WAVE
from mutagen.mp3 import MP3
from mutagen.oggvorbis import OggVorbis
from mutagen.mp4 import MP4


class AudioAnalyzer:
    """오디오 파일 분석 클래스"""
    
    @staticmethod
    def analyze_audio(file_path: str) -> Dict[str, Any]:
        """
        오디오 파일을 분석하여 메타데이터를 반환합니다.
        
        Args:
            file_path: 분석할 오디오 파일 경로
            
        Returns:
            {
                "duration": float,  # 재생 시간 (초)
                "format": str,      # 파일 포맷 (wav, ogg, aac, mp3 등)
                "file_size": int,   # 파일 크기 (바이트)
                "bitrate": int,     # 비트레이트 (선택적)
                "sample_rate": int  # 샘플레이트 (선택적)
            }
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {file_path}")
        
        # 파일 크기
        file_size = os.path.getsize(file_path)
        
        try:
            # mutagen으로 파일 분석
            audio_file = MutagenFile(file_path)
            
            if audio_file is None:
                # mutagen이 지원하지 않는 형식인 경우 기본 정보만 반환
                return {
                    "duration": None,
                    "format": os.path.splitext(file_path)[1][1:].lower(),  # 확장자에서 추출
                    "file_size": file_size,
                    "bitrate": None,
                    "sample_rate": None
                }
            
            # 재생 시간 추출
            duration = None
            if hasattr(audio_file, 'info'):
                if hasattr(audio_file.info, 'length'):
                    duration = float(audio_file.info.length)
                elif hasattr(audio_file.info, 'duration'):
                    duration = float(audio_file.info.duration)
            
            # 포맷 추출
            format_type = None
            if isinstance(audio_file, WAVE):
                format_type = "wav"
            elif isinstance(audio_file, MP3):
                format_type = "mp3"
            elif isinstance(audio_file, OggVorbis):
                format_type = "ogg"
            elif isinstance(audio_file, MP4):
                format_type = "aac"  # MP4는 보통 AAC 코덱 사용
            else:
                # 확장자에서 추출
                format_type = os.path.splitext(file_path)[1][1:].lower()
            
            # 비트레이트 및 샘플레이트 추출
            bitrate = None
            sample_rate = None
            if hasattr(audio_file, 'info'):
                if hasattr(audio_file.info, 'bitrate'):
                    bitrate = audio_file.info.bitrate
                if hasattr(audio_file.info, 'sample_rate'):
                    sample_rate = audio_file.info.sample_rate
            
            return {
                "duration": duration,
                "format": format_type,
                "file_size": file_size,
                "bitrate": bitrate,
                "sample_rate": sample_rate
            }
            
        except Exception as e:
            # 분석 실패 시 기본 정보만 반환
            return {
                "duration": None,
                "format": os.path.splitext(file_path)[1][1:].lower(),
                "file_size": file_size,
                "bitrate": None,
                "sample_rate": None
            }
