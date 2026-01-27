from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import get_db
from app.models.user import User
from app.models.generation import GenerationJob
from app.core.config import settings
import uuid
import os
import asyncio
import shutil
import json
from sqlalchemy.sql import func

router = APIRouter()

async def process_generation_task(job_id: str, input_path: str, db_session: AsyncSession):
    """
    Mock/Real background task to process 3D generation.
    In real world: Call Server A API.
    """
    # NOTE: Since BackgroundTasks runs after response, we need a new session or careful management.
    # Actually, SQLAlchemy AsyncSession is not thread-safe and dependency injection session closes after request.
    # So we need to create a new session here or pass the session IF we handle scope correctly. 
    # Better to create a new session factory usage.
    
    from app.core.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(GenerationJob).where(GenerationJob.id == job_id))
        job = result.scalar_one_or_none()
        
        if not job:
            return

        try:
            job.status = "processing"
            job.progress = 10
            await db.commit()
            
            # Simulate processing time (Server A call)
            await asyncio.sleep(5) 
            
            # Mock Result
            job.progress = 50
            await db.commit()
            
            await asyncio.sleep(5)
            
            # Finalize
            job.status = "completed"
            job.progress = 100
            
            # Mock Output path
            # In real system, Server A writes to NFS, valid path is returned.
            output_filename = f"{job_id}.glb"
            output_path = os.path.join(settings.USER_ASSETS_DIR, "models", output_filename)
            
            # Ensure dir exists (Mocking NFS shared folder just locally)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                f.write("mock glb content")
                
            job.result_url = f"/assets/models/{output_filename}"
            job.completed_at = func.now()
            
            await db.commit()
            
        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            await db.commit()


@router.post("/")
async def create_generation_job(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Start implicit async generation job (인증 없이 사용 가능)"""
    job_id = str(uuid.uuid4())
    
    # Save Upload
    input_filename = f"{job_id}_input.png"
    upload_dir = "./uploads"
    os.makedirs(upload_dir, exist_ok=True)
    input_path = os.path.join(upload_dir, input_filename)
    
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)
        
    # Create Job Entry (익명 사용자)
    job = GenerationJob(
        id=job_id,
        user_id="anonymous",  # 인증 없이 사용
        job_type="3d",
        status="pending",
        input_payload=json.dumps({"image_path": input_path})
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # Trigger Background Task
    # Note: We can't pass 'db' (Dependency) to background task easily as it closes.
    # Pass necessary IDs and let the task create its own session.
    background_tasks.add_task(process_generation_task, job_id, input_path, None) 
    
    return {
        "success": True, 
        "data": {
            "job_id": job_id,
            "status_url": f"/api/generate/status/{job_id}"
        }
    }

@router.get("/status/{job_id}")
async def get_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    # current_user: User = Depends(get_current_user) # Optional: restrict to owner
):
    result = await db.execute(select(GenerationJob).where(GenerationJob.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    return {
        "success": True,
        "data": {
            "job_id": job.id,
            "status": job.status,
            "progress": job.progress,
            "result_url": job.result_url,
            "error": job.error_message
        }
    }
