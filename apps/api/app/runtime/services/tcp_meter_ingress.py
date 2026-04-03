from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
import logging
import socket
import threading
import uuid
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.connectivity.enums import EndpointAssignmentStatus
from app.modules.connectivity.models import MeterEndpointAssignment

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TcpMeterIngressStatusSnapshot:
    listener_enabled: bool
    listen_host: str | None
    listen_port: int | None
    listening: bool
    connected: bool
    active_connection_id: str | None
    remote_addr: str | None
    remote_port: int | None
    connected_at: datetime | None
    bound_meter_id: UUID | None
    bound_endpoint_id: UUID | None
    bound_protocol_association_profile_id: UUID | None
    bound_at: datetime | None
    connection_in_use: bool


@dataclass(frozen=True)
class BorrowedTcpMeterConnection:
    connection_id: str
    socket: socket.socket
    remote_addr: str | None
    remote_port: int | None
    bound_meter_id: UUID
    bound_endpoint_id: UUID


@dataclass(frozen=True)
class BorrowedActiveTcpMeterConnection:
    connection_id: str
    socket: socket.socket
    remote_addr: str | None
    remote_port: int | None


class TcpMeterIngressManager:
    """First-slice listener/registry for one active inbound meter TCP session."""

    def __init__(
        self,
        *,
        enabled: bool,
        host: str,
        port: int,
        socket_timeout_seconds: float,
    ) -> None:
        self._enabled = enabled
        self._host = host
        self._configured_port = port
        self._socket_timeout_seconds = socket_timeout_seconds
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._listener_thread: threading.Thread | None = None
        self._server_socket: socket.socket | None = None
        self._listen_port: int | None = None
        self._connection: socket.socket | None = None
        self._connection_id: str | None = None
        self._connection_addr: tuple[str, int] | None = None
        self._connection_connected_at: datetime | None = None
        self._bound_meter_id: UUID | None = None
        self._bound_endpoint_id: UUID | None = None
        self._bound_protocol_association_profile_id: UUID | None = None
        self._bound_at: datetime | None = None
        self._connection_in_use = False

    def start(self) -> None:
        if not self._enabled:
            logger.info("Runtime TCP meter ingress listener is disabled.")
            return

        with self._lock:
            if self._listener_thread is not None and self._listener_thread.is_alive():
                return
            self._stop_event.clear()
            self._listener_thread = threading.Thread(
                target=self._run_listener_loop,
                name="runtime-tcp-meter-ingress",
                daemon=True,
            )
            self._listener_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        with self._lock:
            connection = self._connection
            server_socket = self._server_socket
            self._clear_connection_state_locked(close_connection=False)
            self._server_socket = None
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass
        if server_socket is not None:
            try:
                server_socket.close()
            except OSError:
                pass
        listener_thread = self._listener_thread
        if listener_thread is not None:
            listener_thread.join(timeout=2.0)
        with self._lock:
            self._listener_thread = None
            self._listen_port = None

    def bind_active_connection(
        self,
        *,
        meter_id: UUID,
        endpoint_id: UUID,
        protocol_association_profile_id: UUID | None = None,
    ) -> TcpMeterIngressStatusSnapshot:
        with self._lock:
            if self._connection is None or self._connection_id is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Runtime TCP meter ingress has no active connection to bind.",
                )
            if self._connection_in_use:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Runtime TCP meter ingress connection is busy. "
                        "Wait for the active runtime operation to finish before rebinding."
                    ),
                )
            self._bound_meter_id = meter_id
            self._bound_endpoint_id = endpoint_id
            self._bound_protocol_association_profile_id = protocol_association_profile_id
            self._bound_at = datetime.now(UTC)
            return self._snapshot_locked()

    def unbind_active_connection(self) -> TcpMeterIngressStatusSnapshot:
        with self._lock:
            self._bound_meter_id = None
            self._bound_endpoint_id = None
            self._bound_protocol_association_profile_id = None
            self._bound_at = None
            return self._snapshot_locked()

    def get_status(self) -> TcpMeterIngressStatusSnapshot:
        with self._lock:
            return self._snapshot_locked()

    @contextmanager
    def borrow_bound_connection(
        self,
        *,
        meter_id: UUID,
        endpoint_id: UUID,
    ) -> Iterator[BorrowedTcpMeterConnection | None]:
        borrowed: BorrowedTcpMeterConnection | None = None
        with self._lock:
            if (
                self._connection is not None
                and self._connection_id is not None
                and self._bound_meter_id == meter_id
                and self._bound_endpoint_id == endpoint_id
                and not self._connection_in_use
            ):
                self._connection_in_use = True
                borrowed = BorrowedTcpMeterConnection(
                    connection_id=self._connection_id,
                    socket=self._connection,
                    remote_addr=self._connection_addr[0]
                    if self._connection_addr is not None
                    else None,
                    remote_port=self._connection_addr[1]
                    if self._connection_addr is not None
                    else None,
                    bound_meter_id=meter_id,
                    bound_endpoint_id=endpoint_id,
                )
        try:
            yield borrowed
        finally:
            with self._lock:
                if borrowed is not None and self._connection_id == borrowed.connection_id:
                    self._connection_in_use = False

    def mark_connection_dead(self, connection_id: str | None) -> None:
        with self._lock:
            if connection_id is None or self._connection_id != connection_id:
                return
            connection = self._connection
            self._clear_connection_state_locked(close_connection=False)
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass

    @contextmanager
    def borrow_active_unbound_connection(self) -> Iterator[BorrowedActiveTcpMeterConnection | None]:
        borrowed: BorrowedActiveTcpMeterConnection | None = None
        with self._lock:
            if (
                self._connection is not None
                and self._connection_id is not None
                and self._bound_meter_id is None
                and self._bound_endpoint_id is None
                and not self._connection_in_use
            ):
                self._connection_in_use = True
                borrowed = BorrowedActiveTcpMeterConnection(
                    connection_id=self._connection_id,
                    socket=self._connection,
                    remote_addr=self._connection_addr[0]
                    if self._connection_addr is not None
                    else None,
                    remote_port=self._connection_addr[1]
                    if self._connection_addr is not None
                    else None,
                )
        try:
            yield borrowed
        finally:
            with self._lock:
                if borrowed is not None and self._connection_id == borrowed.connection_id:
                    self._connection_in_use = False

    def _run_listener_loop(self) -> None:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self._host, self._configured_port))
        server_socket.listen(1)
        server_socket.settimeout(1.0)
        with self._lock:
            self._server_socket = server_socket
            self._listen_port = int(server_socket.getsockname()[1])
        logger.info(
            "Runtime TCP meter ingress listener started on %s:%s",
            self._host,
            self._listen_port,
        )

        try:
            while not self._stop_event.is_set():
                try:
                    connection, addr = server_socket.accept()
                except socket.timeout:
                    continue
                except OSError:
                    if self._stop_event.is_set():
                        break
                    raise

                connection.settimeout(self._socket_timeout_seconds)
                remote_addr = str(addr[0])
                remote_port = int(addr[1])
                connection_id = f"tcp-live:{uuid.uuid4()}"
                accepted = False
                with self._lock:
                    if self._connection is None:
                        self._connection = connection
                        self._connection_id = connection_id
                        self._connection_addr = (remote_addr, remote_port)
                        self._connection_connected_at = datetime.now(UTC)
                        self._bound_meter_id = None
                        self._bound_endpoint_id = None
                        self._bound_protocol_association_profile_id = None
                        self._bound_at = None
                        self._connection_in_use = False
                        accepted = True
                if not accepted:
                    logger.warning(
                        "Runtime TCP meter ingress rejected extra connection from %s:%s",
                        remote_addr,
                        remote_port,
                    )
                    try:
                        connection.close()
                    except OSError:
                        pass
                    continue

                logger.info(
                    "Runtime TCP meter ingress accepted connection %s from %s:%s",
                    connection_id,
                    remote_addr,
                    remote_port,
                )
                while not self._stop_event.is_set():
                    with self._lock:
                        if self._connection_id != connection_id:
                            break
                    self._stop_event.wait(0.5)
                self.mark_connection_dead(connection_id)
                logger.info("Runtime TCP meter ingress connection %s closed", connection_id)
        finally:
            try:
                server_socket.close()
            except OSError:
                pass
            with self._lock:
                if self._server_socket is server_socket:
                    self._server_socket = None

    def _clear_connection_state_locked(self, *, close_connection: bool) -> None:
        connection = self._connection
        self._connection = None
        self._connection_id = None
        self._connection_addr = None
        self._connection_connected_at = None
        self._bound_meter_id = None
        self._bound_endpoint_id = None
        self._bound_protocol_association_profile_id = None
        self._bound_at = None
        self._connection_in_use = False
        if close_connection and connection is not None:
            try:
                connection.close()
            except OSError:
                pass

    def _snapshot_locked(self) -> TcpMeterIngressStatusSnapshot:
        return TcpMeterIngressStatusSnapshot(
            listener_enabled=self._enabled,
            listen_host=self._host if self._enabled else None,
            listen_port=self._listen_port if self._enabled else None,
            listening=self._server_socket is not None and self._listener_thread is not None,
            connected=self._connection is not None,
            active_connection_id=self._connection_id,
            remote_addr=self._connection_addr[0] if self._connection_addr is not None else None,
            remote_port=self._connection_addr[1] if self._connection_addr is not None else None,
            connected_at=self._connection_connected_at,
            bound_meter_id=self._bound_meter_id,
            bound_endpoint_id=self._bound_endpoint_id,
            bound_protocol_association_profile_id=self._bound_protocol_association_profile_id,
            bound_at=self._bound_at,
            connection_in_use=self._connection_in_use,
        )


_tcp_meter_ingress_manager = TcpMeterIngressManager(
    enabled=settings.runtime_tcp_meter_ingress_enabled,
    host=settings.runtime_tcp_meter_ingress_host,
    port=settings.runtime_tcp_meter_ingress_port,
    socket_timeout_seconds=settings.runtime_tcp_meter_ingress_socket_timeout_seconds,
)


def start_runtime_tcp_meter_ingress_listener() -> None:
    _tcp_meter_ingress_manager.start()


def stop_runtime_tcp_meter_ingress_listener() -> None:
    _tcp_meter_ingress_manager.stop()


def get_runtime_tcp_meter_ingress_status() -> TcpMeterIngressStatusSnapshot:
    return _tcp_meter_ingress_manager.get_status()


def bind_runtime_tcp_meter_ingress_connection(
    session: Session,
    *,
    meter_id: UUID,
    endpoint_id: UUID | None,
    protocol_association_profile_id: UUID | None = None,
) -> TcpMeterIngressStatusSnapshot:
    resolved_endpoint_id = endpoint_id or _resolve_runtime_bind_endpoint_id(
        session,
        meter_id=meter_id,
    )
    return _tcp_meter_ingress_manager.bind_active_connection(
        meter_id=meter_id,
        endpoint_id=resolved_endpoint_id,
        protocol_association_profile_id=protocol_association_profile_id,
    )


def unbind_runtime_tcp_meter_ingress_connection() -> TcpMeterIngressStatusSnapshot:
    return _tcp_meter_ingress_manager.unbind_active_connection()


@contextmanager
def borrow_runtime_tcp_meter_ingress_connection(
    *,
    meter_id: UUID,
    endpoint_id: UUID,
) -> Iterator[BorrowedTcpMeterConnection | None]:
    with _tcp_meter_ingress_manager.borrow_bound_connection(
        meter_id=meter_id,
        endpoint_id=endpoint_id,
    ) as borrowed:
        yield borrowed


@contextmanager
def borrow_runtime_tcp_meter_ingress_unbound_connection() -> Iterator[
    BorrowedActiveTcpMeterConnection | None
]:
    with _tcp_meter_ingress_manager.borrow_active_unbound_connection() as borrowed:
        yield borrowed


def mark_runtime_tcp_meter_ingress_connection_dead(connection_id: str | None) -> None:
    _tcp_meter_ingress_manager.mark_connection_dead(connection_id)


def _resolve_runtime_bind_endpoint_id(
    session: Session,
    *,
    meter_id: UUID,
) -> UUID:
    active_assignments = session.scalars(
        select(MeterEndpointAssignment)
        .where(
            MeterEndpointAssignment.meter_id == meter_id,
            MeterEndpointAssignment.assignment_status == EndpointAssignmentStatus.ACTIVE,
            MeterEndpointAssignment.unassigned_at.is_(None),
        )
        .order_by(
            MeterEndpointAssignment.is_primary.desc(),
            MeterEndpointAssignment.assigned_at.desc(),
        )
    ).all()
    if not active_assignments:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime TCP meter ingress bind requires an active endpoint assignment for the meter.",
        )

    primary_assignments = [assignment for assignment in active_assignments if assignment.is_primary]
    if len(primary_assignments) == 1:
        return primary_assignments[0].endpoint_id
    if len(active_assignments) == 1:
        return active_assignments[0].endpoint_id

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "Runtime TCP meter ingress bind found multiple active endpoint assignments for the meter. "
            "Specify endpoint_id explicitly."
        ),
    )

