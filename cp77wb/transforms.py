from __future__ import annotations

import math
from typing import Any


def vec3(value: Any) -> tuple[float, float, float] | None:
    if not isinstance(value, dict):
        return None
    try:
        return float(value['x']), float(value['y']), float(value['z'])
    except (KeyError, TypeError, ValueError):
        return None


def euler3(value: Any) -> tuple[float, float, float] | None:
    if not isinstance(value, dict):
        return None
    try:
        return float(value['roll']), float(value['pitch']), float(value['yaw'])
    except (KeyError, TypeError, ValueError):
        return None


def add_vec(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return a[0] + b[0], a[1] + b[1], a[2] + b[2]


def sub_vec(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def mul_vec(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return a[0] * b[0], a[1] * b[1], a[2] * b[2]


def euler_to_quat(roll: float, pitch: float, yaw: float) -> tuple[float, float, float, float]:
    """Quaternion (x, y, z, w) for Rz(yaw) * Ry(pitch) * Rx(roll).

    This matches World Builder's rotatePoint matrix ordering and REDengine's
    world-space group rotation behavior closely enough for offline transforms.
    """
    r, p, y = map(lambda d: math.radians(d) * 0.5, (roll, pitch, yaw))
    cr, sr = math.cos(r), math.sin(r)
    cp, sp = math.cos(p), math.sin(p)
    cy, sy = math.cos(y), math.sin(y)
    return (
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    )


def quat_mul(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def quat_to_euler(q: tuple[float, float, float, float]) -> tuple[float, float, float]:
    x, y, z, w = q
    # Normalize first to avoid accumulated floating-point drift.
    n = math.sqrt(x * x + y * y + z * z + w * w)
    if n:
        x, y, z, w = x / n, y / n, z / n, w / n

    sinr = 2 * (w * x + y * z)
    cosr = 1 - 2 * (x * x + y * y)
    roll = math.atan2(sinr, cosr)

    sinp = 2 * (w * y - z * x)
    if abs(sinp) >= 1:
        pitch = math.copysign(math.pi / 2, sinp)
    else:
        pitch = math.asin(sinp)

    siny = 2 * (w * z + x * y)
    cosy = 1 - 2 * (y * y + z * z)
    yaw = math.atan2(siny, cosy)
    return tuple(math.degrees(v) for v in (roll, pitch, yaw))  # type: ignore[return-value]


def rotate_vector(v: tuple[float, float, float], delta_euler: tuple[float, float, float]) -> tuple[float, float, float]:
    """Rotate a vector with the same ZYX matrix WB's utils.rotatePoint uses."""
    roll, pitch, yaw = map(math.radians, delta_euler)
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)

    x, y, z = v
    return (
        (cy * cp) * x + (cy * sp * sr - sy * cr) * y + (cy * sp * cr + sy * sr) * z,
        (sy * cp) * x + (sy * sp * sr + cy * cr) * y + (sy * sp * cr - cy * sr) * z,
        (-sp) * x + (cp * sr) * y + (cp * cr) * z,
    )


def rotate_point(point: tuple[float, float, float], pivot: tuple[float, float, float], delta_euler: tuple[float, float, float]) -> tuple[float, float, float]:
    return add_vec(pivot, rotate_vector(sub_vec(point, pivot), delta_euler))


def compose_world_euler(current: tuple[float, float, float], delta: tuple[float, float, float]) -> tuple[float, float, float]:
    """Equivalent to WB group leaf rotation: deltaQuat * entryQuat."""
    return quat_to_euler(quat_mul(euler_to_quat(*delta), euler_to_quat(*current)))


def compose_local_euler(current: tuple[float, float, float], delta: tuple[float, float, float]) -> tuple[float, float, float]:
    return quat_to_euler(quat_mul(euler_to_quat(*current), euler_to_quat(*delta)))


def clean_float(value: float, eps: float = 1e-12) -> float:
    if abs(value) < eps:
        return 0.0
    rounded = round(value)
    if abs(value - rounded) < eps:
        return float(rounded)
    return value
