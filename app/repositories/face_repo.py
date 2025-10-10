from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.models import FaceUser

class FaceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_emp_id(self, emp_id: int) -> List[FaceUser]:
        """Get all face records for an employee"""
        try:
            return self.db.query(FaceUser).filter(FaceUser.face_user_emp_id == emp_id).all()
        except SQLAlchemyError as e:
            raise Exception(f"Database error while fetching face records: {str(e)}")

    def exists_for_employee(self, emp_id: int) -> bool:
        """Check if face records exist for employee"""
        try:
            return self.db.query(FaceUser).filter(FaceUser.face_user_emp_id == emp_id).first() is not None
        except SQLAlchemyError as e:
            raise Exception(f"Database error while checking face existence: {str(e)}")

    def create_face_record(self, emp_id: int, name: str, embedding: List[float]) -> FaceUser:
        """Create a new face record"""
        try:
            face_record = FaceUser(
                name=name,
                face_user_emp_id=emp_id,
                embedding=embedding
            )
            self.db.add(face_record)
            self.db.commit()
            self.db.refresh(face_record)
            return face_record
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error while creating face record: {str(e)}")

    def create_multiple_faces(self, emp_id: int, name: str, embeddings: List[List[float]]) -> List[FaceUser]:
        """Create multiple face records for an employee"""
        try:
            face_records = []
            for embedding in embeddings:
                face_record = FaceUser(
                    name=name,
                    face_user_emp_id=emp_id,
                    embedding=embedding
                )
                self.db.add(face_record)
                face_records.append(face_record)
            
            self.db.commit()
            
            for record in face_records:
                self.db.refresh(record)
            
            return face_records
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error while creating face records: {str(e)}")

    def delete_by_emp_id(self, emp_id: int) -> int:
        """Delete all face records for an employee"""
        try:
            deleted = self.db.query(FaceUser).filter(FaceUser.face_user_emp_id == emp_id).delete()
            self.db.commit()
            return deleted
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error while deleting face records: {str(e)}")