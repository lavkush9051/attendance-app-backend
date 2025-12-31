from sqlalchemy import Column, Integer, String, DateTime, Float, Date, ForeignKey, Text, Time, BigInteger, CheckConstraint, Numeric
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base
from sqlalchemy import Interval, Computed, text
from sqlalchemy.orm import relationship
from sqlalchemy import DECIMAL, TIMESTAMP, UniqueConstraint


Base = declarative_base()

class FaceUser(Base):
    __tablename__ = 'face_users'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    embedding = Column(ARRAY(Float), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    face_user_emp_id = Column(Integer, ForeignKey('employee_tbl.emp_id'), primary_key=True)
#    face_user_emp_id = Column(Integer, ForeignKey('employee_tbl.emp_id'), index=True, nullable=False)


# Only for initialization
if __name__ == "__main__":
    from app.database import engine
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created.")



#from .database import Base

class AppUser(Base):
    __tablename__ = "app_users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    app_emp_id = Column(Integer, ForeignKey('employee_tbl.emp_id'), nullable=True)

class Employee(Base):
    __tablename__ = 'employee_tbl'

    emp_id = Column(Integer, primary_key=True, index=True)
    emp_name = Column(String)
    emp_department = Column(String)
    emp_designation = Column(String)
    emp_gender = Column(String)
    emp_address = Column(String)
    emp_joining_date = Column(String)
    emp_email = Column(String)
    emp_contact = Column(String)
    emp_marital_status = Column(String)
    emp_nationality = Column(String)
    emp_pan_no = Column(String)
    emp_weekoff = Column(String)
    emp_l1 = Column(Integer)
    emp_l2 = Column(Integer)


class LeaveRequest(Base):
    __tablename__ = 'leave_request_tbl'
    leave_req_id = Column(Integer, primary_key=True, index=True)
    leave_req_emp_id = Column(Integer, ForeignKey('employee_tbl.emp_id'), nullable=False)
    leave_req_type = Column(String(20))
    leave_req_from_dt = Column(Date)
    leave_req_to_dt = Column(Date)
    leave_req_reason = Column(String(200))
    leave_req_status = Column(String(10))
    leave_req_l1_status = Column(String(10))
    leave_req_l2_status = Column(String(10))
    leave_req_l1_id = Column(Integer)
    leave_req_l2_id = Column(Integer)
    remarks = Column(Text)
    leave_req_applied_dt = Column(Date)
    sap_sync_status = Column(String(20), nullable=False, server_default="PENDING")
    sap_sync_timestamp = Column(DateTime(timezone=True))

class AttendanceRequest(Base):
    __tablename__ = 'attendance_regularization_tbl'
    art_id = Column(Integer, primary_key=True, index=True)
    art_emp_id = Column(Integer, ForeignKey('employee_tbl.emp_id'), nullable=False)
    art_date = Column(Date)
    art_clockin_time = Column(Time)
    art_clockout_time = Column(Time)
    art_reason = Column(String(100))
    art_status = Column(String(20))
    art_l1_id = Column(Integer)
    art_l2_id = Column(Integer)
    art_l1_status = Column(String(20))
    art_l2_status = Column(String(20))
    art_shift = Column(String(20),
                             ForeignKey('emp_shift_tbl.est_shift_abbrv'),
                             nullable=False, index=True)
    art_applied_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class ClockInClockOut(Base):
    __tablename__ = 'clockin_clockout_tbl'
    cct_id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    cct_emp_id = Column(Integer, ForeignKey('employee_tbl.emp_id'), nullable=False)
    cct_date = Column(Date, nullable=False)
    cct_clockin_time = Column(Time)
    cct_clockout_time = Column(Time)
    # FK to emp_shift_tbl.est_shift_abbrv (matches your DB constraint)
    cct_shift_abbrv = Column(String(12),
                             ForeignKey('emp_shift_tbl.est_shift_abbrv'),
                             nullable=False, index=True)
    cct_synced_with_sap = Column(String, nullable=False, server_default="N")
    # relationship to shift
    shift = relationship(
        "EmpShift",
        back_populates="clock_records",
        primaryjoin="EmpShift.est_shift_abbrv == foreign(ClockInClockOut.cct_shift_abbrv)"
    )

class LeaveType(Base):
    __tablename__ = 'leave_type_tbl'
    lt_id = Column(Integer, primary_key=True, autoincrement=True)
    lt_abrev = Column(String(5))
    lt_leave_type = Column(String(30))
    lt_total = Column(Integer)
    sap_leave_id = Column(Integer)

class LeaveBalance(Base):
    __tablename__ = "leave_tbl"

    lt_id = Column(BigInteger, primary_key=True, autoincrement=True)
    lt_emp_id = Column(
        Integer,
        ForeignKey("employee_tbl.emp_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # one row per employee
    )

    lt_casual_leave     = Column(Integer, nullable=False, server_default="0")
    lt_earned_leave     = Column(Integer, nullable=False, server_default="0")
    lt_half_pay_leave   = Column(Integer, nullable=False, server_default="0")
    lt_medical_leave    = Column(Integer, nullable=False, server_default="0")
    lt_optional_holiday = Column(Integer, nullable=False, server_default="2")  # new
    lt_compensatory_off        = Column(Integer, nullable=False, server_default="0")
    # lt_special_leave    = Column(Integer, nullable=False, server_default="0")
    # lt_child_care_leave = Column(Integer, nullable=False, server_default="0")
    # lt_parental_leave   = Column(Integer, nullable=False, server_default="0")

    __table_args__ = (
        CheckConstraint("lt_casual_leave >= 0"),
        CheckConstraint("lt_earned_leave >= 0"),
        CheckConstraint("lt_half_pay_leave >= 0"),
        CheckConstraint("lt_medical_leave >= 0"),
        CheckConstraint("lt_optional_holiday >= 0"),
        CheckConstraint("lt_compensatory_off >= 0"),
        # CheckConstraint("lt_special_leave >= 0"),
        # CheckConstraint("lt_child_care_leave >= 0"),
        # CheckConstraint("lt_parental_leave >= 0"),
    )



    def __repr__(self) -> str:
        return f"<LeaveBalance emp_id={self.lt_emp_id}>"
    

class EmpShift(Base):
    __tablename__ = "emp_shift_tbl"

    est_shift_id = Column(Integer, primary_key=True, index=True)
    est_shift_name = Column(String(12), nullable=False, unique=True)
    est_shift_abbrv = Column(String(12), nullable=False, unique=True)

    est_shift_start_time = Column(Time, nullable=False)
    est_shift_end_time   = Column(Time, nullable=False)

    # duration = (end(+1 day if crosses midnight) - start)
    est_shift_duration = Column(
        Interval,
        Computed(
            text("""
            (
              (
                (TIMESTAMP '2000-01-01' + est_shift_end_time)
                + CASE
                    WHEN est_shift_end_time <= est_shift_start_time THEN INTERVAL '1 day'
                    ELSE INTERVAL '0 day'
                  END
              )
              - (TIMESTAMP '2000-01-01' + est_shift_start_time)
            )
            """),
            persisted=True
        )
    )

    # backref to clock records
    clock_records = relationship(
        "ClockInClockOut",
        back_populates="shift",
        primaryjoin="EmpShift.est_shift_abbrv == foreign(ClockInClockOut.cct_shift_abbrv)"
    )

    def __repr__(self) -> str:
        return f"<EmpShift {self.est_shift_abbrv} {self.est_shift_start_time}-{self.est_shift_end_time}>"

class LeaveLedger(Base):
    __tablename__ = "leave_ledger_tbl"

    ll_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ll_emp_id = Column(Integer, ForeignKey("employee_tbl.emp_id"), nullable=False, index=True)
    ll_leave_type = Column(String(30), nullable=False, index=True)  # e.g. "Sick", "Casual", or your abbrv
    ll_qty = Column(Numeric(5, 2), nullable=False)                  # days, can be 0.5 etc.
    ll_action = Column(String(12), nullable=False, index=True)      # "HOLD" | "RELEASE" | "COMMIT"
    ll_ref_leave_req_id = Column(Integer, ForeignKey("leave_request_tbl.leave_req_id"), nullable=False, index=True)
    ll_created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("ll_qty >= 0", name="ck_leave_ledger_qty_nonneg"),
    )

from sqlalchemy import Column, Integer, BigInteger, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

class LeaveAttachment(Base):
    __tablename__ = "leave_attachment_tbl"

    la_id = Column(BigInteger, primary_key=True, autoincrement=True)
    la_leave_req_id = Column(Integer, ForeignKey("leave_request_tbl.leave_req_id", ondelete="CASCADE"), nullable=False)
    la_filename = Column(Text, nullable=False)
    la_mime_type = Column(Text, nullable=False)
    la_size_bytes = Column(BigInteger, nullable=False)
    la_disk_path = Column(Text, nullable=False)  # e.g. "leave/42/550e8400_report.pdf"
    la_uploaded_by = Column(Integer, nullable=True)
    la_uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    leave_request = relationship("LeaveRequest", backref="attachments")


class GeofenceLocation(Base):
    """Geofence location model for storing office/block locations"""
    __tablename__ = "geofence_location"
    
    id = Column(Integer, primary_key=True, index=True)
    lat = Column(DECIMAL(9, 7), nullable=False)
    lon = Column(DECIMAL(9, 7), nullable=False)
    block = Column(String(100), nullable=False)
    radius = Column(Integer, nullable=False)  # radius in meters
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Relationship to employee access
    employee_access = relationship("EmployeeGeofenceAccess", back_populates="geofence_location")


class EmployeeGeofenceAccess(Base):
    """Employee geofence access mapping"""
    __tablename__ = "employee_geofence_access"
    
    id = Column(Integer, primary_key=True, index=True)
    ega_emp_id = Column(Integer, ForeignKey("employee_tbl.emp_id", ondelete="CASCADE"), nullable=False)
    ega_geofence_id = Column(Integer, ForeignKey("geofence_location.id", ondelete="CASCADE"), nullable=False)
    ega_access_granted_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Relationships
    geofence_location = relationship("GeofenceLocation", back_populates="employee_access")
    
    # Unique constraint to avoid duplicates
    __table_args__ = (
        UniqueConstraint('ega_emp_id', 'ega_geofence_id', name='unique_emp_geofence'),
    )


import os
from sqlalchemy import event
from app.config import UPLOAD_ROOT

@event.listens_for(LeaveAttachment, "after_delete")
def _remove_file_after_delete(mapper, connection, target):
    # target.la_disk_path may be None if partially migrated
    if getattr(target, "la_disk_path", None):
        try:
            os.remove(os.path.join(UPLOAD_ROOT, target.la_disk_path))
        except FileNotFoundError:
            pass
        except Exception:
            pass

