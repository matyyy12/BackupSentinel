from typing import Annotated

from fastapi import APIRouter, Depends, Query
from starlette import status

from monitoring_app.dependencies import get_service
from monitoring_app.schemas import AlertResponse, AlertDetailsResponse, AlertUpdateRequest
from monitoring_app.service import AlertService

router = APIRouter(prefix="/alerts", tags=["alerts"])

@router.get("/", response_model=list[AlertResponse], status_code=status.HTTP_200_OK)
async def get_alerts(service: Annotated[AlertService,Depends(get_service)],
                     resolved: Annotated[bool | None, Query()] = None) -> list[AlertResponse]:
    return await service.get_alerts(resolved)

@router.patch("/{alert_id}", status_code=status.HTTP_200_OK, response_model=AlertDetailsResponse)
async def update_alert(service: Annotated[AlertService,Depends(get_service)],
                       request: AlertUpdateRequest,
                       alert_id: int) -> AlertDetailsResponse:
    return await service.update_alert(alert_id, request)
@router.get("/{alert_id}", response_model=AlertDetailsResponse, status_code=status.HTTP_200_OK)
async def get_alert_by_id(service: Annotated[AlertService,Depends(get_service)],
                          alert_id: int) -> AlertDetailsResponse:
    return await service.get_alert_by_id(alert_id)
