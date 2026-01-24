import uvicorn
import os
import shutil

if __name__ == "__main__":
    # Ensure env file exists
    if not os.path.exists(".env"):
        print("Creating .env from .env.example")
        shutil.copy(".env.example", ".env")
        
    # Ensure mock directories exist
    os.makedirs("./shared_models_mock", exist_ok=True)
    os.makedirs("./user_assets_mock", exist_ok=True)
    os.makedirs("./uploads", exist_ok=True)
    
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
