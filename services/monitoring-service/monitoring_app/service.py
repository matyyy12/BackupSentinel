from datetime import datetime, timezone

from monitoring_app.exceptions import NotFoundError

from monitoring_app.repository import MonitoringRepository
from monitoring_app.schemas import AlertResponse, AlertDetailsResponse, AlertUpdateRequest


class AlertService:
    def __init__(self, repository: MonitoringRepository):
        self.repository = repository

    async def get_alerts(self, resolved: bool | None) -> list[AlertResponse]:
        alerts = await self.repository.get_alerts(resolved)
        return [AlertResponse.model_validate(alert) for alert in alerts]

    async def get_alert_by_id(self, alert_id: int) -> AlertDetailsResponse:
        alert = await self.repository.get_alert_by_id(alert_id)
        if alert is None:
            raise NotFoundError("Alert not found")
        return AlertDetailsResponse.model_validate(alert)

    async def update_alert(self, alert_id: int, request: AlertUpdateRequest) -> AlertDetailsResponse:
        alert = await self.repository.get_alert_for_update(alert_id)
        if alert is None:
            raise NotFoundError("Alert not found")
        try:
            if request.resolved and alert.resolved_at is None:
                alert.resolved_at = datetime.now(timezone.utc)
            await self.repository.commit()
        except Exception:
            await self.repository.rollback()
            raise
        return AlertDetailsResponse.model_validate(alert)
