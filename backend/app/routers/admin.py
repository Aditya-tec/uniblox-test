from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas.coupon import CouponListItem, CouponOut
from ..schemas.report import ReportOut
from ..services import coupon_service, report_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/coupons/generate", response_model=CouponOut, status_code=201)
def generate_coupon(db: Session = Depends(get_db)):
    return coupon_service.generate_coupon(db)


@router.get("/coupons", response_model=list[CouponListItem])
def list_coupons(db: Session = Depends(get_db)):
    return coupon_service.list_coupons(db)


@router.get("/report", response_model=ReportOut)
def get_report(db: Session = Depends(get_db)):
    return report_service.build_report(db)
