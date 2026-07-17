#!/usr/bin/env python3
"""
Hlohovec Space Program  --  trajectory-cost minimiser.

Each mission: given duration t, free-acceleration threshold a_free,
initial state (p0, v0) and target state (p_t, v_{t+1}), choose the
intermediate positions p_1 .. p_{t-1} to minimise

    sum_{i=0}^{t}  max(||a_i|| - a_free, 0) ** 1.5

The flight is fully determined by the positions:

    v_i = p_i - p_{i-1}          (i = 1..t)
    a_i = v_{i+1} - v_i          (i = 0..t)

with v_0 and v_{t+1} given, i.e.

    a_0     = p_1 - p_0 - v_0
    a_i     = p_{i+1} - 2 p_i + p_{i-1}      (i = 1..t-1)
    a_t     = v_{t+1} - (p_t - p_{t-1})

The problem is convex.  It is modelled directly (power cone for the ^1.5
term, second-order cone for the norm) and solved with CLARABEL.  As a
safety net we also keep the closed-form minimiser of sum ||a_i||^2 (a
banded linear solve) and a damped-Newton polish, and always output the
cheapest trajectory found.

Reads the input file from stdin, writes the required positions to stdout.
"""
import sys
import warnings
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve, splu

warnings.filterwarnings("ignore")   # silence solver "may be inaccurate" notes

try:
    import cvxpy as cp
    _HAVE_CVXPY = True
except Exception:                       # pragma: no cover
    _HAVE_CVXPY = False

HPP_MAX = 1e12
TINY = 1e-12


# --------------------------------------------------------------------------
# Linear acceleration operator:  a = D q + b   (per coordinate)
# --------------------------------------------------------------------------
def build_operator(t, p0, pt, v0, vnext):
    n = t - 1
    rows, cols, vals = [], [], []
    bx = np.zeros(t + 1)
    by = np.zeros(t + 1)

    def coeff(row, pidx, val):
        if 1 <= pidx <= t - 1:
            rows.append(row); cols.append(pidx - 1); vals.append(val)
        elif pidx == 0:
            bx[row] += val * p0[0]; by[row] += val * p0[1]
        elif pidx == t:
            bx[row] += val * pt[0]; by[row] += val * pt[1]

    coeff(0, 1, 1.0)                       # a_0 = p_1 - p_0 - v_0
    bx[0] += -p0[0] - v0[0]; by[0] += -p0[1] - v0[1]
    for i in range(1, t):                  # a_i = p_{i+1} - 2p_i + p_{i-1}
        coeff(i, i + 1, 1.0); coeff(i, i, -2.0); coeff(i, i - 1, 1.0)
    coeff(t, t - 1, 1.0)                    # a_t = v_{t+1} - p_t + p_{t-1}
    bx[t] += vnext[0] - pt[0]; by[t] += vnext[1] - pt[1]

    D = sparse.coo_matrix((vals, (rows, cols)), shape=(t + 1, n)).tocsr()
    return D, bx, by


def cost_of(D, bx, by, qx, qy, af):
    ax = D @ qx + bx
    ay = D @ qy + by
    r = np.sqrt(ax * ax + ay * ay)
    over = np.maximum(r - af, 0.0)
    return float(np.sum(over ** 1.5))


# --------------------------------------------------------------------------
# Warm start: minimiser of sum ||a_i||^2  (banded linear system)
# --------------------------------------------------------------------------
def l2_warmstart(D, bx, by):
    DtD = (D.T @ D).tocsc()
    qx = np.atleast_1d(spsolve(DtD, -(D.T @ bx))).astype(float)
    qy = np.atleast_1d(spsolve(DtD, -(D.T @ by))).astype(float)
    return qx, qy


# --------------------------------------------------------------------------
# CLARABEL conic model
# --------------------------------------------------------------------------
def clarabel_solve(t, af, p0, v0, pt, vnext):
    Pm = cp.Variable((t - 1, 2))
    Full = cp.vstack([np.asarray(p0).reshape(1, 2), Pm,
                      np.asarray(pt).reshape(1, 2)])
    a0 = Full[1] - Full[0] - np.asarray(v0)
    at = np.asarray(vnext) - (Full[t] - Full[t - 1])
    Amid = Full[2:] - 2 * Full[1:-1] + Full[:-2]
    A = cp.vstack([cp.reshape(a0, (1, 2), order='C'), Amid,
                   cp.reshape(at, (1, 2), order='C')])
    cost = cp.sum(cp.power(cp.pos(cp.norm(A, 2, axis=1) - af), 1.5))
    prob = cp.Problem(cp.Minimize(cost))
    prob.solve(solver=cp.CLARABEL)
    if Pm.value is None:
        raise RuntimeError("clarabel returned no solution")
    return np.asarray(Pm.value, dtype=float)


# --------------------------------------------------------------------------
# Damped-Newton (used as a polish / fallback)
# --------------------------------------------------------------------------
def _grad_hess_diag(D, bx, by, qx, qy, af):
    ax = D @ qx + bx
    ay = D @ qy + by
    r = np.sqrt(ax * ax + ay * ay)
    s = r - af
    active = s > TINY
    hp = np.zeros_like(r); hpp = np.zeros_like(r); inv_r = np.zeros_like(r)
    sa = s[active]; ra = r[active]
    hp[active] = 1.5 * np.sqrt(sa)
    hpp[active] = np.minimum(0.75 / np.sqrt(sa), HPP_MAX)
    inv_r[active] = 1.0 / ra
    base = hp * inv_r
    c1 = np.zeros_like(r)
    c1[active] = (hpp[active] - base[active]) * (inv_r[active] ** 2)
    grad_qx = D.T @ (base * ax)
    grad_qy = D.T @ (base * ay)
    hxx = c1 * ax * ax + base
    hyy = c1 * ay * ay + base
    hxy = c1 * ax * ay
    return grad_qx, grad_qy, hxx, hyy, hxy


def _assemble_hessian(Dc, hxx, hyy, hxy, lam):
    Bxx = (Dc.T @ sparse.diags(hxx) @ Dc)
    Byy = (Dc.T @ sparse.diags(hyy) @ Dc)
    Bxy = (Dc.T @ sparse.diags(hxy) @ Dc)
    n = Dc.shape[1]
    ridge = sparse.identity(n, format="csc") * lam
    return sparse.bmat([[Bxx + ridge, Bxy], [Bxy, Byy + ridge]], format="csc")


def newton_polish(D, bx, by, qx, qy, af, max_iter=100):
    Dc = D.tocsc()
    n = D.shape[1]
    qx = qx.copy(); qy = qy.copy()
    f = cost_of(D, bx, by, qx, qy, af)
    lam = 1e-6
    for _ in range(max_iter):
        gx, gy, hxx, hyy, hxy = _grad_hess_diag(D, bx, by, qx, qy, af)
        g = np.concatenate([gx, gy])
        if np.linalg.norm(g) < 1e-9:
            break
        accepted = False
        for _attempt in range(40):
            H = _assemble_hessian(Dc, hxx, hyy, hxy, lam)
            try:
                d = splu(H).solve(-g)
            except Exception:
                lam *= 10.0; continue
            gd = float(g @ d)
            if not np.isfinite(gd) or gd >= 0:
                lam *= 10.0; continue
            alpha = 1.0; ok = False
            while alpha > 1e-15:
                fn = cost_of(D, bx, by, qx + alpha * d[:n], qy + alpha * d[n:], af)
                if np.isfinite(fn) and fn <= f + 1e-4 * alpha * gd:
                    ok = True; break
                alpha *= 0.5
            if ok:
                qx += alpha * d[:n]; qy += alpha * d[n:]
                if alpha >= 1.0:
                    lam = max(lam * 0.5, 1e-12)
                accepted = True
                break
            lam *= 10.0
        if not accepted:
            break
        f = fn
    return qx, qy


# --------------------------------------------------------------------------
def solve_case(t, af, p0, v0, pt, vnext):
    n = t - 1
    if n <= 0:
        return np.zeros((0, 2))

    D, bx, by = build_operator(t, p0, pt, v0, vnext)

    # candidate 1: L2 warm start (always available)
    qx, qy = l2_warmstart(D, bx, by)
    best_q = (qx, qy)
    best_c = cost_of(D, bx, by, qx, qy, af)

    # candidate 2: CLARABEL conic solve
    if _HAVE_CVXPY:
        try:
            Pc = clarabel_solve(t, af, p0, v0, pt, vnext)
            cx, cy = Pc[:, 0], Pc[:, 1]
            cc = cost_of(D, bx, by, cx, cy, af)
            if np.isfinite(cc) and cc < best_c:
                best_q, best_c = (cx, cy), cc
        except Exception:
            pass

    # candidate 3: Newton polish from the current best (cleans up any
    # solver inaccuracy; also the primary method if cvxpy is unavailable)
    try:
        nx, ny = newton_polish(D, bx, by, best_q[0], best_q[1], af)
        nc = cost_of(D, bx, by, nx, ny, af)
        if np.isfinite(nc) and nc < best_c:
            best_q, best_c = (nx, ny), nc
    except Exception:
        pass

    P = np.empty((n, 2))
    P[:, 0], P[:, 1] = best_q
    return P


def fmt(v):
    s = f"{v:.9f}"
    return "0.000000000" if s == "-0.000000000" else s


def main():
    data = sys.stdin.buffer.read().split()
    idx = 0
    T = int(data[idx]); idx += 1
    out = []
    for _ in range(T):
        t = int(float(data[idx])); idx += 1
        af = float(data[idx]); idx += 1
        p0 = np.array([float(data[idx]), float(data[idx + 1])]); idx += 2
        v0 = np.array([float(data[idx]), float(data[idx + 1])]); idx += 2
        pt = np.array([float(data[idx]), float(data[idx + 1])]); idx += 2
        vnext = np.array([float(data[idx]), float(data[idx + 1])]); idx += 2

        P = solve_case(t, af, p0, v0, pt, vnext)
        for row in P:
            out.append(f"{fmt(row[0])} {fmt(row[1])}")
        out.append("")   # blank line after each test case

    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
