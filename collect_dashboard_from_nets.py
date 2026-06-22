"""
Build dashboard data from EXISTING .net.xml files (e.g. networks designed by the
generative model and saved by sample_check_monaco.py), instead of random removal.

Baseline ("기존") is the original sparse network (default.net.xml), simulated with
the same route demand, exactly like collect_dashboard_data.py.

Usage:
    python collect_dashboard_from_nets.py \
        --nets sumo/Monaco/gen_3_seed42.net.xml sumo/Monaco/gen_7_seed42.net.xml \
        --names gen_A gen_B \
        --simulation_time 1800 --period 60
"""
import os
import pickle
import argparse

import numpy as np

from collect_dashboard_data import (
    run_sim_with_edgedata, edge_geometry, avg_ratio_per_edge,
    ORIGINAL_NET, DENSE_NET,
)


def build(net_specs, sim_time, period, out_path):
    work_dir = "sumo/Monaco/dashboard"
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    _, map_bounds = edge_geometry(DENSE_NET)
    data = {"networks": {}, "map_bounds": map_bounds}

    # ---- base ("original") network = default (sparse) ----
    print("[base] simulating ORIGINAL (default) network ...")
    base_geom, base_bounds = edge_geometry(ORIGINAL_NET)
    base_metrics, base_ts, base_begins = run_sim_with_edgedata(
        ORIGINAL_NET, sim_time, period, f"{work_dir}/base")
    base_ids = set(base_geom.keys())
    base_avg = avg_ratio_per_edge(base_ts)
    data["base"] = {
        "name": "base", "edges": base_geom, "bounds": base_bounds,
        "metrics": base_metrics, "timeseries": base_ts, "begins": base_begins,
        "avg_ratio": base_avg,
    }
    print(f"  base: {base_metrics['num_arrived']} arrived, "
          f"avg wait {base_metrics['avg_waiting_time']:.1f}s")

    # ---- generative networks ----
    for name, net_file in net_specs:
        print(f"[{name}] simulating {net_file} ...")
        geom, bounds = edge_geometry(net_file)
        metrics, ts, begins = run_sim_with_edgedata(
            net_file, sim_time, period, f"{work_dir}/{name}")
        ids = set(geom.keys())
        removed = sorted(base_ids - ids)
        added = sorted(ids - base_ids)
        avg = avg_ratio_per_edge(ts)
        flow_delta = {e: avg.get(e, np.nan) - base_avg.get(e, np.nan)
                      for e in (ids & base_ids)}
        data["networks"][name] = {
            "name": name, "edges": geom, "bounds": bounds,
            "metrics": metrics, "timeseries": ts, "begins": begins,
            "avg_ratio": avg, "removed_edges": removed, "added_edges": added,
            "num_removed": len(removed), "num_added": len(added),
            "flow_delta": flow_delta,
        }
        print(f"  {name}: removed {len(removed)}, added {len(added)}, "
              f"{metrics['num_arrived']} arrived, "
              f"avg wait {metrics['avg_waiting_time']:.1f}s")

    with open(out_path, "wb") as f:
        pickle.dump(data, f)
    print(f"\nSaved dashboard data to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--nets", nargs="+", required=True,
                        help="paths to .net.xml files (generative networks)")
    parser.add_argument("--names", nargs="+", default=None,
                        help="display names (default: gen_0, gen_1, ...)")
    parser.add_argument("--simulation_time", type=int, default=1800)
    parser.add_argument("--period", type=int, default=60)
    parser.add_argument("--out", type=str,
                        default="results/Monaco/dashboard/dashboard_data.pkl")
    args = parser.parse_args()

    names = args.names or [f"gen_{i}" for i in range(len(args.nets))]
    assert len(names) == len(args.nets), "names and nets length mismatch"
    build(list(zip(names, args.nets)), args.simulation_time, args.period, args.out)
