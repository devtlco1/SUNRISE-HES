from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.modules.consumers.models import ServicePoint
from app.modules.gis.models import Feeder, Region, Sector, Substation, Transformer
from app.modules.meters.models import Meter
from tests.test_commands_foundation import _login_as_super_admin
from tests.test_protocol_runtime_foundation import _create_meter_record


def _create_infrastructure_fixture_graph(
    client,
    db_session: Session,
) -> tuple[str, str, str, str, str]:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    meter = db_session.get(Meter, meter_id)
    assert meter is not None

    suffix = uuid4().hex[:8]
    region = Region(code=f"REG-{suffix}", name=f"North Grid {suffix}")
    db_session.add(region)
    db_session.flush()

    sector = Sector(
        region_id=region.id,
        code=f"SEC-{suffix}",
        name=f"Airport Sector {suffix}",
    )
    db_session.add(sector)
    db_session.flush()

    substation = Substation(
        sector_id=sector.id,
        code=f"SUB-{suffix}",
        name=f"Airport Primary {suffix}",
    )
    db_session.add(substation)
    db_session.flush()

    feeder = Feeder(
        substation_id=substation.id,
        code=f"FDR-{suffix}",
        name=f"Airport Feeder {suffix}",
    )
    db_session.add(feeder)
    db_session.flush()

    transformer = Transformer(
        feeder_id=feeder.id,
        code=f"TX-{suffix}",
        name=f"Transformer {suffix}",
        description="Read-only infrastructure visibility fixture",
    )
    db_session.add(transformer)
    db_session.flush()

    service_point = ServicePoint(
        service_point_code=f"SP-INF-{suffix}",
        sector_id=sector.id,
        transformer_id=transformer.id,
        address_line="Mabela Service Road",
        premises_type="mixed-use",
    )
    db_session.add(service_point)
    db_session.flush()

    meter.transformer_id = transformer.id
    meter.service_point_id = service_point.id
    db_session.commit()
    return token, str(transformer.id), str(substation.id), str(service_point.id), meter_id


def test_transformer_substation_list_returns_compact_infrastructure_visibility(
    client,
    db_session: Session,
) -> None:
    token, transformer_id, substation_id, service_point_id, meter_id = _create_infrastructure_fixture_graph(
        client,
        db_session,
    )

    response = client.get(
        "/api/v1/transformers-substations?offset=0&limit=20&search=TX-",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    item = next(entry for entry in payload["items"] if entry["id"] == transformer_id)
    assert payload["total"] >= 1
    assert item["substation_id"] == substation_id
    assert item["linked_meter_count"] >= 1
    assert item["linked_service_point_count"] >= 1
    assert item["primary_service_point_code"].startswith("SP-INF-")
    assert item["primary_meter_serial_number"]
    assert item["location_hint"] == "Mabela Service Road"


def test_transformer_substation_detail_returns_bounded_linked_context(
    client,
    db_session: Session,
) -> None:
    token, transformer_id, substation_id, service_point_id, meter_id = _create_infrastructure_fixture_graph(
        client,
        db_session,
    )

    response = client.get(
        f"/api/v1/transformers-substations/{transformer_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == transformer_id
    assert payload["substation"]["id"] == substation_id
    assert payload["linked_service_point_count"] >= 1
    assert payload["linked_service_points"][0]["id"] == service_point_id
    assert payload["linked_meter_count"] >= 1
    assert payload["linked_meters"][0]["id"] == meter_id


def test_transformer_substation_detail_returns_not_found_for_unknown_transformer(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)

    response = client.get(
        "/api/v1/transformers-substations/00000000-0000-0000-0000-000000000001",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Transformer not found."
