from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.models import AppUser, Employee
from app.database import SessionLocal
from app.auth import verify_password, get_password_hash, create_access_token

router = APIRouter()

class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/signup")
def signup(user: UserCreate, db: Session = Depends(get_db)):
    print(f"[LOG] /signup attempt for user: {user.username}")
    try:
        existing_user = db.query(AppUser).filter(AppUser.username == user.username).first()
        if existing_user:
            print(f"[ERROR] /signup user already exists: {user.username}")
            raise HTTPException(
                status_code=400, 
                # detail="User already exists."
                detail={
                      "success": False,
                      "message": "User already exists.",
                      "error_code": "USER_EXISTS"
                      } 
                )
        
        hashed_pwd = get_password_hash(user.password)
        new_user = AppUser(username=user.username, hashed_password=hashed_pwd)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        print(f"[LOG] /signup successful for user: {user.username}")
        return {
            "success": True,
            "message": "User created successfully"
            }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] /signup exception for user {user.username}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    print(f"[LOG] /login attempt for user: {user.username}")
    try:
        db_user = db.query(AppUser).filter(AppUser.username == user.username).first()

        if not db_user:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": "Username does not exist",
                    "error_code": "USER_NOT_FOUND"
                }
            )

        if not verify_password(user.password, db_user.hashed_password):
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": "Incorrect password",
                    "error_code": "INVALID_PASSWORD"
                }
            )


        # if not db_user or not verify_password(user.password, db_user.hashed_password):
            print(f"[ERROR] /login invalid credentials for user: {user.username}")
            # raise HTTPException(status_code=401, detail="Invalid credentials")
        
        token = create_access_token({"username": db_user.username})

        # Fetch the employee record
        employee = db.query(Employee).filter(Employee.emp_id == db_user.app_emp_id).first()
        if not employee:
            print(f"[ERROR] /login employee not found for user: {user.username}")
            raise HTTPException(
                       status_code=404, 
                    #    detail="Employee not found"
                           detail={
                    "success": False,
                    "message": "Employee mapping not found",
                    "error_code": "EMPLOYEE_NOT_FOUND"
                }
                       )
        # Fetch L1 and L2 names
        l1_manager = db.query(Employee).filter(Employee.emp_id == employee.emp_l1).first() if employee.emp_l1 else None
        l2_manager = db.query(Employee).filter(Employee.emp_id == employee.emp_l2).first() if employee.emp_l2 else None

        # Return token AND essential employee info in frontend expected format
        login_response = {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": 3600,  # 1 hour - you can adjust this
            "user": {
                "id": employee.emp_id,  # Frontend expects "id" field
                "emp_id": employee.emp_id,
                "emp_name": employee.emp_name,
                "emp_department": employee.emp_department,
                "emp_designation": employee.emp_designation,
                "emp_l1": employee.emp_l1,
                "emp_l1_name": l1_manager.emp_name if l1_manager else "", # added this
                "emp_l2": employee.emp_l2,
                "emp_l2_name": l2_manager.emp_name if l2_manager else "",  # added this
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