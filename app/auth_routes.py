# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session
# from pydantic import BaseModel
# from app.models import AppUser, Employee
# from app.database import SessionLocal
# from app.auth import verify_password, get_password_hash, create_access_token

# router = APIRouter()

# class UserCreate(BaseModel):
#     username: str
#     password: str

# class UserLogin(BaseModel):
#     username: str
#     password: str

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

# @router.post("/signup")
# def signup(user: UserCreate, db: Session = Depends(get_db)):
#     print(f"[LOG] /signup attempt for user: {user.username}")
#     try:
#         existing_user = db.query(AppUser).filter(AppUser.username == user.username).first()
#         if existing_user:
#             print(f"[ERROR] /signup user already exists: {user.username}")
#             raise HTTPException(status_code=400, detail="User already exists.")
        
#         hashed_pwd = get_password_hash(user.password)
#         new_user = AppUser(username=user.username, hashed_password=hashed_pwd)
#         db.add(new_user)
#         db.commit()
#         db.refresh(new_user)
        
#         print(f"[LOG] /signup successful for user: {user.username}")
#         return {"message": "User created successfully"}
#     except HTTPException:
#         raise
#     except Exception as e:
#         print(f"[ERROR] /signup exception for user {user.username}: {str(e)}")
#         raise HTTPException(status_code=500, detail="Internal server error")

# @router.post("/login")
# def login(user: UserLogin, db: Session = Depends(get_db)):
#     print(f"[LOG] /login attempt for user: {user.username}")
#     try:
#         db_user = db.query(AppUser).filter(AppUser.username == user.username).first()
#         if not db_user or not verify_password(user.password, db_user.hashed_password):
#             print(f"[ERROR] /login invalid credentials for user: {user.username}")
#             raise HTTPException(status_code=401, detail="Invalid credentials")
        
#         token = create_access_token({"username": db_user.username})

#         # Fetch the employee record
#         employee = db.query(Employee).filter(Employee.emp_id == db_user.app_emp_id).first()
#         if not employee:
#             print(f"[ERROR] /login employee not found for user: {user.username}")
#             raise HTTPException(status_code=404, detail="Employee not found")
#         # Fetch L1 and L2 names
#         l1_manager = db.query(Employee).filter(Employee.emp_id == employee.emp_l1).first() if employee.emp_l1 else None
#         l2_manager = db.query(Employee).filter(Employee.emp_id == employee.emp_l2).first() if employee.emp_l2 else None

#         # Return token AND essential employee info in frontend expected format
#         login_response = {
#             "access_token": token,
#             "token_type": "bearer",
#             "expires_in": 3600,  # 1 hour - you can adjust this
#             "user": {
#                 "id": employee.emp_id,  # Frontend expects "id" field
#                 "emp_id": employee.emp_id,
#                 "emp_name": employee.emp_name,
#                 "emp_department": employee.emp_department,
#                 "emp_designation": employee.emp_designation,
#                 "emp_l1": employee.emp_l1,
#                 "emp_l1_name": l1_manager.emp_name if l1_manager else "", # added this
#                 "emp_l2": employee.emp_l2,
#                 "emp_l2_name": l2_manager.emp_name if l2_manager else "",  # added this
#                 "emp_gender": employee.emp_gender,
#                 "emp_address": employee.emp_address,
#                 "emp_joining_date": str(employee.emp_joining_date) if employee.emp_joining_date else "",
#                 "emp_email": employee.emp_email,
#                 "emp_contact": employee.emp_contact,
#                 "emp_marital_status": employee.emp_marital_status,
#                 "emp_nationality": employee.emp_nationality,
#                 "emp_pan_no": employee.emp_pan_no,
#                 "emp_weekoff": employee.emp_weekoff
#             }
#         }
        
#         print(f"[LOG] /login successful for user: {user.username}, emp_id: {employee.emp_id}")
#         return login_response
#     except HTTPException:
#         raise
#     except Exception as e:
#         print(f"[ERROR] /login exception for user {user.username}: {str(e)}")
#         raise HTTPException(status_code=500, detail="Internal server error")


import base64
import random
import string
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from jose import jwt, JWTError # <--- NEW: For signing the captcha answer
from captcha.image import ImageCaptcha # <--- NEW: For generating the image

from app.models import AppUser, Employee
from app.database import SessionLocal
# Import SECRET_KEY and ALGORITHM to reuse them for Captcha signing
from app.auth import verify_password, get_password_hash, create_access_token, SECRET_KEY, ALGORITHM

router = APIRouter()

# --- NEW: Captcha Configuration ---
image_generator = ImageCaptcha(width=280, height=90)

# Helper to generate random string
def generate_random_text(length=5):
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# --- MODIFIED: Login Model now requires Captcha ---
class UserLogin(BaseModel):
    username: str
    password: str
    captcha_id: str      # The encrypted token we sent to frontend
    captcha_answer: str  # The user's input from the text box

class UserCreate(BaseModel):
    username: str
    password: str

# --- NEW: Response Model for Captcha ---
class CaptchaResponse(BaseModel):
    captcha_id: str
    image_base64: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- NEW: Endpoint to Generate Captcha ---
@router.get("/generate-captcha", response_model=CaptchaResponse)
def generate_captcha():
    # 1. Generate random text (e.g., "AB12")
    captcha_text = generate_random_text()
    
    # 2. Generate Image
    data = image_generator.generate(captcha_text)
    
    # 3. Encode image to Base64 for frontend display
    base64_image = base64.b64encode(data.getvalue()).decode('utf-8')
    
    # 4. Encrypt the REAL answer into a token
    # We use the same SECRET_KEY from your auth.py
    payload = {"captcha_answer": captcha_text}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    
    return {"captcha_id": token, "image_base64": base64_image}

@router.post("/signup")
def signup(user: UserCreate, db: Session = Depends(get_db)):
    print(f"[LOG] /signup attempt for user: {user.username}")
    try:
        existing_user = db.query(AppUser).filter(AppUser.username == user.username).first()
        if existing_user:
            print(f"[ERROR] /signup user already exists: {user.username}")
            raise HTTPException(status_code=400, detail="User already exists.")
        
        hashed_pwd = get_password_hash(user.password)
        new_user = AppUser(username=user.username, hashed_password=hashed_pwd)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        print(f"[LOG] /signup successful for user: {user.username}")
        return {"message": "User created successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] /signup exception for user {user.username}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    print(f"[LOG] /login attempt for user: {user.username}")

    # --- NEW: Verify Captcha BEFORE checking Database ---
    try:
        # Decode the captcha_id token to find the hidden answer
        print(f"[LOG] Decoding captcha token for user: {user.username} captcha_id: {user.captcha_id}")
        payload = jwt.decode(user.captcha_id, SECRET_KEY, algorithms=[ALGORITHM])
        correct_answer = payload.get("captcha_answer")
        print(f"[LOG] Decoded captcha answer: {correct_answer} for user: {user.username}")
    except JWTError:
        print(f"[ERROR] Invalid captcha token for user: {user.username}")
        raise HTTPException(status_code=400, detail="Invalid CAPTCHA or expired")

    # Check if user input matches the hidden answer (Case Insensitive)
    if not correct_answer or user.captcha_answer.upper() != correct_answer:
        print(f"[ERROR] Incorrect captcha for user: {user.username}")
        raise HTTPException(status_code=400, detail="Incorrect CAPTCHA answer")
    # ----------------------------------------------------

    try:
        db_user = db.query(AppUser).filter(AppUser.username == user.username).first()
        if not db_user or not verify_password(user.password, db_user.hashed_password):
            print(f"[ERROR] /login invalid credentials for user: {user.username}")
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        token = create_access_token({"username": db_user.username})

        # Fetch the employee record
        employee = db.query(Employee).filter(Employee.emp_id == db_user.app_emp_id).first()
        if not employee:
            print(f"[ERROR] /login employee not found for user: {user.username}")
            raise HTTPException(status_code=404, detail="Employee not found")
        
        # Fetch L1 and L2 names
        l1_manager = db.query(Employee).filter(Employee.emp_id == employee.emp_l1).first() if employee.emp_l1 else None
        l2_manager = db.query(Employee).filter(Employee.emp_id == employee.emp_l2).first() if employee.emp_l2 else None

        # Return token AND essential employee info
        login_response = {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": 3600,
            "user": {
                "id": employee.emp_id,
                "emp_id": employee.emp_id,
                "emp_name": employee.emp_name,
                "emp_department": employee.emp_department,
                "emp_designation": employee.emp_designation,
                "emp_l1": employee.emp_l1,
                "emp_l1_name": l1_manager.emp_name if l1_manager else "",
                "emp_l2": employee.emp_l2,
                "emp_l2_name": l2_manager.emp_name if l2_manager else "",
                "emp_gender": employee.emp_gender,
                "emp_address": employee.emp_address,
                "emp_joining_date": str(employee.emp_joining_date) if employee.emp_joining_date else "",
                "emp_email": employee.emp_email,
                "emp_contact": employee.emp_contact,
                "emp_marital_status": employee.emp_marital_status,
                "emp_nationality": employee.emp_nationality,
                "emp_pan_no": employee.emp_pan_no,
                "emp_weekoff": employee.emp_weekoff
            }
        }
        
        print(f"[LOG] /login successful for user: {user.username}, emp_id: {employee.emp_id}")
        return login_response
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] /login exception for user {user.username}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")