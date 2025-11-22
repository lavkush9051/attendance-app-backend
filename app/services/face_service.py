from typing import List, Optional, Dict, Any
import numpy as np
from app.repositories.face_repo import FaceRepository
from app.schemas.faces import FaceRegistrationRequest, FaceRegistrationResponse, FaceVerificationRequest, FaceVerificationResponse
from app.face_engine import FaceEngine
import base64

class FaceService:
    def __init__(self, face_repo: FaceRepository):
        self.face_repo = face_repo
        self.face_engine = FaceEngine()

    def register_employee_faces(self, request: FaceRegistrationRequest) -> FaceRegistrationResponse:
        """Register face embeddings for an employee (4 images required)"""
        try:
            # Validate that we have exactly 4 face images
            if len(request.face_images) != 4:
                raise Exception("Exactly 4 face images are required for registration")

            # Check if employee already has faces registered
            existing_faces = self.face_repo.get_by_emp_id(request.emp_id)
            if existing_faces:
                # Delete existing faces before registering new ones
                #self.face_repo.delete_by_emp_id(request.emp_id)
                return FaceRegistrationResponse(
                    success=False,
                    message="Faces already registered for this employee",
                    employee_id=request.emp_id,
                    faces_registered=len(existing_faces)
                )

            # Process each face image and extract embeddings
            face_embeddings = []
            for i, face_image in enumerate(request.face_images):
                try:
                    # Convert base64 to embedding (placeholder implementation)
                    embedding = self._extract_face_embedding(face_image)
                    if embedding is None:
                        raise Exception(f"Could not extract face from image {i+1}")
                    
                    face_embeddings.append(embedding)
                except Exception as e:
                    raise Exception(f"Error processing face image {i+1}: {str(e)}")

            # Validate face quality and consistency
            if not self._validate_face_consistency(face_embeddings):
                raise Exception("Face images are not consistent. Please ensure all images are of the same person with clear face visibility")

            # Store face embeddings in database
            created_faces = self.face_repo.create_multiple_faces(
                emp_id=request.emp_id,
                name=request.employee_name,
                embeddings=face_embeddings,
                # name=request.name
                                        )

            return FaceRegistrationResponse(
                success=True,
                message="Face registration successful",
                employee_id=request.emp_id,
                faces_registered=len(created_faces)
            )

        except Exception as e:
            return FaceRegistrationResponse(
                success=False,
                message=f"Face registration failed: {str(e)}",
                employee_id=request.emp_id,
                faces_registered=0
            )

    def verify_employee_face(self, request: FaceVerificationRequest) -> FaceVerificationResponse:
        """Verify employee face against stored embeddings"""
        try:
            # Check if employee has registered faces
            stored_faces = self.face_repo.get_by_emp_id(request.emp_id)
            if not stored_faces:
                return FaceVerificationResponse(
                    success=False,
                    message="No face data found for employee. Please register faces first",
                    employee_id=request.emp_id,
                    confidence_score=0.0,
                    match_found=False
                )

            # Extract embedding from verification image
            verification_embedding = self._extract_face_embedding(request.face_image)
            if verification_embedding is None:
                return FaceVerificationResponse(
                    success=False,
                    message="Could not extract face from verification image",
                    employee_id=request.emp_id,
                    confidence_score=0.0,
                    match_found=False
                )

            # Compare with stored embeddings
            max_similarity = 0.0
            match_found = False
            
            for stored_face in stored_faces:
                stored_embedding = np.array(stored_face.face_embedding)
                similarity = self._calculate_cosine_similarity(verification_embedding, stored_embedding)
                max_similarity = max(max_similarity, similarity)

            # Threshold for face match (configurable)
            similarity_threshold = 0.75
            match_found = max_similarity >= similarity_threshold

            return FaceVerificationResponse(
                success=True,
                message="Face verification completed",
                employee_id=request.emp_id,
                confidence_score=round(max_similarity, 3),
                match_found=match_found
            )

        except Exception as e:
            return FaceVerificationResponse(
                success=False,
                message=f"Face verification failed: {str(e)}",
                employee_id=request.emp_id,
                confidence_score=0.0,
                match_found=False
            )

    def get_employee_face_status(self, emp_id: int) -> Dict[str, Any]:
        """Get face registration status for an employee"""
        try:
            faces = self.face_repo.get_by_emp_id(emp_id)
            
            return {
                'employee_id': emp_id,
                'has_faces_registered': len(faces) > 0,
                'total_faces': len(faces),
                'registration_complete': len(faces) >= 4,
                'last_updated': max([face.created_at for face in faces]) if faces else None
            }

        except Exception as e:
            raise Exception(f"Service error while fetching face status: {str(e)}")

    def delete_employee_faces(self, emp_id: int) -> bool:
        """Delete all face data for an employee"""
        try:
            exists = self.face_repo.exists_for_employee(emp_id)
            if not exists:
                raise Exception(f"No face data found for employee {emp_id}")

            return self.face_repo.delete_by_emp_id(emp_id)

        except Exception as e:
            raise Exception(f"Service error while deleting face data: {str(e)}")

    def bulk_face_verification(self, verifications: List[FaceVerificationRequest]) -> List[FaceVerificationResponse]:
        """Perform bulk face verification for multiple employees"""
        try:
            results = []
            for verification_request in verifications:
                result = self.verify_employee_face(verification_request)
                results.append(result)
            
            return results

        except Exception as e:
            raise Exception(f"Service error during bulk verification: {str(e)}")

    def get_face_analytics(self) -> Dict[str, Any]:
        """Get analytics about face registration status across all employees"""
        try:
            # This would require getting all employees and checking their face status
            # For now, returning a placeholder implementation
            
            # Get all face records (this is a simplified approach)
            # In a real implementation, you'd want to optimize this query
            
            return {
                'total_employees_with_faces': 0,  # Placeholder
                'total_face_records': 0,  # Placeholder
                'average_faces_per_employee': 0.0,  # Placeholder
                'registration_completion_rate': 0.0  # Placeholder
            }

        except Exception as e:
            raise Exception(f"Service error while generating face analytics: {str(e)}")

    # def _extract_face_embedding(self, face_image_base64: str) -> Optional[np.ndarray]:
    #     """Extract face embedding from base64 image (placeholder implementation)"""
    #     try:
    #         # image_bytes = base64.b64decode(face_image_base64)
    #         # This is a placeholder implementation
    #         # In a real system, you would:
    #         # 1. Decode base64 image
    #         # 2. Use face recognition library (like face_recognition, DeepFace, etc.)
    #         # 3. Extract face embedding/encoding
    #         # 4. Return the embedding as numpy array
            
    #         # For now, returning a random embedding for demonstration
    #         import base64
    #         import hashlib
            
    #         Create a deterministic "embedding" based on image hash
    #         image_data = base64.b64decode(face_image_base64)
    #         image_hash = hashlib.md5(image_data).hexdigest()
            
    #         # Convert hash to numeric values (128 dimensional embedding)
    #         embedding = []
    #         for i in range(0, len(image_hash), 2):
    #             hex_pair = image_hash[i:i+2]
    #             embedding.append(int(hex_pair, 16) / 255.0)  # Normalize to 0-1
            
    #         # Pad or truncate to 128 dimensions
    #         while len(embedding) < 128:
    #             embedding.append(0.0)
    #         embedding = embedding[:128]
            
    #         return np.array(embedding, dtype=np.float32)

    #     except Exception as e:
    #         print(f"Error extracting face embedding: {str(e)}")
    #         return None
    
    def _extract_face_embedding(self, face_image_base64: str) -> Optional[np.ndarray]:
        """Extract 512-D face embedding using InsightFace"""
        try:
            # Decode base64 to bytes
            image_bytes = base64.b64decode(face_image_base64)

            # Extract embedding from FaceEngine
            descriptor = self.face_engine.extract_descriptor(image_bytes)
            if descriptor is None:
                raise Exception("No face detected or extraction failed")

            return np.array(descriptor, dtype=np.float32)

        except Exception as e:
            print(f"[ERROR] _extract_face_embedding failed: {e}")
            return None
        
    def _validate_face_consistency(self, embeddings: List[np.ndarray]) -> bool:
        """Validate that all face embeddings are from the same person"""
        try:
            if len(embeddings) < 2:
                return True

            # Calculate pairwise similarities
            similarities = []
            for i in range(len(embeddings)):
                for j in range(i + 1, len(embeddings)):
                    similarity = self._calculate_cosine_similarity(embeddings[i], embeddings[j])
                    similarities.append(similarity)

            # All similarities should be above threshold
            consistency_threshold = 0.6
            return all(sim >= consistency_threshold for sim in similarities)

        except Exception as e:
            print(f"Error validating face consistency: {str(e)}")
            return False

    def _calculate_cosine_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Calculate cosine similarity between two face embeddings"""
        try:
            # Normalize the embeddings
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            # Calculate cosine similarity
            dot_product = np.dot(embedding1, embedding2)
            similarity = dot_product / (norm1 * norm2)
            
            # Ensure similarity is between -1 and 1, then convert to 0-1 range
            similarity = max(-1.0, min(1.0, similarity))
            return (similarity + 1.0) / 2.0

        except Exception as e:
            print(f"Error calculating cosine similarity: {str(e)}")
            return 0.0
