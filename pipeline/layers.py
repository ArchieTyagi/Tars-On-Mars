"""Turn a height map into the layers the planner needs."""
import numpy as np


def slope_deg(dem, cell_m):
    """Steepness in degrees at each point. Gaps (NaN) stay NaN."""
    gy, gx = np.gradient(dem.astype("float64"), cell_m)
    return np.degrees(np.arctan(np.hypot(gx, gy))).astype("float32")


def block_max(a, k):
    """Shrink by k, keeping the worst (largest) value in each k x k block.
    Any gap inside a block makes the whole block a gap."""
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    b = a[:h, :w].reshape(h // k, k, w // k, k)
    out = b.max(axis=(1, 3))
    out[np.isnan(b).any(axis=(1, 3))] = np.nan
    return out


def roughness(dem, k):
    """Height spread (max - min) inside each k x k block, in meters.
    Picks up rocks and small steps that slope alone can smooth over."""
    h, w = (dem.shape[0] // k) * k, (dem.shape[1] // k) * k
    b = dem[:h, :w].reshape(h // k, k, w // k, k)
    return (b.max(axis=(1, 3)) - b.min(axis=(1, 3))).astype("float32")
