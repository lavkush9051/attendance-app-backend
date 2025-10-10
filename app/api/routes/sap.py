"""
FastAPI routes for SAP Leave Integration
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging

from app.database import get_db
from app.auth import get_current_user
from app.services.sap_integration.sap_leave_sync import sap_sync_service
from app.services.sap_integration.sap_client import SAPClient

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/sync-leaves")
async def sync_leaves_to_sap(
    background_tasks: BackgroundTasks,
    process_count: int = 5,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Manually trigger SAP leave synchronization
    
    Args:
        background_tasks: FastAPI background tasks
        process_count: Maximum number of leave requests to process (default: 5)
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dictionary containing sync operation results
    """
    try:
        logger.info(f"SAP sync triggered by user {current_user.get('emp_id', 'unknown')}")
        
        # Process the sync operation
        result = await sap_sync_service.process_pending_leave_requests(db, process_count)
        
        return {
            "success": True,
            "data": result,
            "message": f"SAP sync completed. Processed {result.get('processed_count', 0)} requests"
        }
        
    except Exception as e:
        logger.error(f"Error in SAP sync endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SAP sync failed: {str(e)}"
        )

@router.get("/sync-status")
async def get_sap_sync_status(
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get SAP synchronization status summary
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dictionary containing sync status summary
    """
    try:
        result = await sap_sync_service.get_sync_status_summary(db)
        
        return {
            "success": True,
            "data": result,
            "message": "SAP sync status retrieved successfully"
        }
        
    except Exception as e:
        logger.error(f"Error getting SAP sync status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sync status: {str(e)}"
        )

@router.post("/test-connection")
async def test_sap_connection(
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Test SAP API connectivity
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Dictionary containing connection test results
    """
    try:
        logger.info(f"SAP connection test triggered by user {current_user.get('emp_id', 'unknown')}")
        
        sap_client = SAPClient()
        result = await sap_client.test_connection()
        
        return {
            "success": True,
            "data": result,
            "message": "SAP connection test completed"
        }
        
    except Exception as e:
        logger.error(f"Error in SAP connection test: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SAP connection test failed: {str(e)}"
        )

@router.post("/sync-single/{leave_req_id}")
async def sync_single_leave_request(
    leave_req_id: int,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Manually sync a specific leave request to SAP
    
    Args:
        leave_req_id: Leave request ID to sync
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dictionary containing sync operation result
    """
    try:
        from app.models import LeaveRequest
        
        # Get the leave request
        leave_request = db.query(LeaveRequest).filter(
            LeaveRequest.leave_req_id == leave_req_id
        ).first()
        
        if not leave_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Leave request {leave_req_id} not found"
            )
        
        if leave_request.leave_req_status != "Approved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Leave request {leave_req_id} is not approved. Status: {leave_request.leave_req_status}"
            )
        
        logger.info(f"Single SAP sync triggered for leave request {leave_req_id} by user {current_user.get('emp_id', 'unknown')}")
        
        # Process the single request
        result = await sap_sync_service.process_single_leave_request(db, leave_request)
        
        return {
            "success": True,
            "data": result,
            "message": f"SAP sync completed for leave request {leave_req_id}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in single SAP sync for leave request {leave_req_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SAP sync failed for leave request {leave_req_id}: {str(e)}"
        )

@router.get("/pending-requests")
async def get_pending_sap_requests(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get list of leave requests pending SAP synchronization
    
    Args:
        limit: Maximum number of records to return (default: 20)
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dictionary containing pending leave requests
    """
    try:
        # Get pending requests using the service
        pending_requests = sap_sync_service.get_pending_leave_requests(db, limit)
        
        # Convert to response format
        requests_data = []
        for req in pending_requests:
            requests_data.append({
                "leave_req_id": req.leave_req_id,
                "emp_id": req.leave_req_emp_id,
                "leave_type": req.leave_req_type,
                "from_date": req.leave_req_from_dt.isoformat() if req.leave_req_from_dt else None,
                "to_date": req.leave_req_to_dt.isoformat() if req.leave_req_to_dt else None,
                "reason": req.leave_req_reason,
                "status": req.leave_req_status,
                "sap_sync_status": req.sap_sync_status,
                "sap_retry_count": req.sap_retry_count,
                "sap_last_error": req.sap_error_message,
                "applied_date": req.leave_req_applied_dt.isoformat() if req.leave_req_applied_dt else None
            })
        
        return {
            "success": True,
            "data": {
                "pending_requests": requests_data,
                "count": len(requests_data)
            },
            "message": f"Retrieved {len(requests_data)} pending SAP sync requests"
        }
        
    except Exception as e:
        logger.error(f"Error getting pending SAP requests: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pending requests: {str(e)}"
        )