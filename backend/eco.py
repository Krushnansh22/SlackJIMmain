import asyncio
import math
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import httpx
import psutil

import config


class EcoService:
    """Provides real-time pod power metrics (Watts) and per-ticket energy/carbon footprint attribution.

    Supports two modes:
    - 'kepler': Queries live Prometheus scraping CNCF Kepler container_joules_total in Kubernetes.
    - 'simulated': Local realistic power model based on host CPU activity and pod heuristics.
    """

    def __init__(self) -> None:
        self._cache_time: float = 0.0
        self._cached_live_data: Optional[Dict[str, Any]] = None
        self._cache_ttl_seconds: float = 2.0

    async def get_live_metrics(self) -> Dict[str, Any]:
        """Returns live power consumption (Watts) across the Mauji Cafe SOS stack."""
        now = time.time()
        if self._cached_live_data and (now - self._cache_time) < self._cache_ttl_seconds:
            return self._cached_live_data

        if config.ECO_PROVIDER == "kepler":
            data = await self._fetch_kepler_live()
        else:
            data = self._fetch_simulated_live()

        self._cached_live_data = data
        self._cache_time = now
        return data

    async def calculate_window_energy(
        self,
        start_iso: str,
        end_iso: str,
        inference_seconds: float = 0.0,
    ) -> Dict[str, Any]:
        """Calculates energy (mWh) and carbon footprint (gCO2e) attributed to a ticket time window.

        Energy is computed for the app pods during the active period [start, end].
        If an AI fix ran, external Jarvis Labs GPU energy is estimated separately:
            GPU mWh = (JARVIS_GPU_TDP_WATTS * inference_seconds) / 3.6
        """
        try:
            start_dt = datetime.fromisoformat(start_iso)
            end_dt = datetime.fromisoformat(end_iso)
            window_seconds = max(1.0, (end_dt - start_dt).total_seconds())
        except Exception:
            window_seconds = 60.0

        if config.ECO_PROVIDER == "kepler":
            stack_joules, source = await self._fetch_kepler_window_joules(start_iso, end_iso, window_seconds)
        else:
            stack_joules, source = self._fetch_simulated_window_joules(window_seconds)

        # 1 Joule = 1 Watt-second
        # 1 Watt-hour = 3600 Joules => 1 Joule = 1/3600 Wh = 1000/3600 mWh = 1/3.6 mWh
        stack_energy_mwh = round(stack_joules / 3.6, 2)

        # External GPU estimate (Jarvis Labs cloud GPU)
        # Note: Kepler measures pods in-cluster; GPU is external cloud compute.
        gpu_energy_mwh = 0.0
        if inference_seconds > 0.0:
            gpu_joules = config.JARVIS_GPU_TDP_WATTS * inference_seconds
            gpu_energy_mwh = round(gpu_joules / 3.6, 2)

        # Carbon footprint (gCO2e)
        # carbon_g = (total_kWh) * GRID_CARBON_INTENSITY_G_PER_KWH
        total_energy_kwh = (stack_energy_mwh + gpu_energy_mwh) / 1_000_000.0
        carbon_g = round(total_energy_kwh * config.GRID_CARBON_INTENSITY_G_PER_KWH, 4)

        return {
            "window_seconds": round(window_seconds, 1),
            "stack_energy_mwh": stack_energy_mwh,
            "gpu_estimate_mwh": gpu_energy_mwh,
            "total_energy_mwh": round(stack_energy_mwh + gpu_energy_mwh, 2),
            "carbon_g": carbon_g,
            "grid_intensity_g_per_kwh": config.GRID_CARBON_INTENSITY_G_PER_KWH,
            "grid_intensity_source": "Central Electricity Authority (CEA) India Baseline v20.0 (Dec 2024)",
            "measured_source": source,
            "note": "Cluster stack measured via Kepler/Prometheus; Jarvis Labs GPU estimated via TDP (300W)",
        }

    async def _fetch_kepler_live(self) -> Dict[str, Any]:
        """Queries Prometheus for instantaneous power rate (Watts) of pods in APP_NAMESPACE."""
        metric = config.KEPLER_METRIC_CONTAINER_JOULES
        # Query sum by pod/pod_name over a 30s rate window
        query = (
            f'sum by (pod, pod_name) (rate({metric}{{container_namespace=~"{config.APP_NAMESPACE}|default"}}[30s]))'
        )
        url = f"{config.PROMETHEUS_URL}/api/v1/query"

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(url, params={"query": query})
                resp.raise_for_status()
                data = resp.json()

            results = data.get("data", {}).get("result", [])
            per_pod: Dict[str, float] = {}
            total_watts = 0.0

            for item in results:
                metric_labels = item.get("metric", {})
                pod_name = metric_labels.get("pod") or metric_labels.get("pod_name") or "unknown-pod"
                # Simplify pod name for display (strip replica hash if present)
                short_name = self._simplify_pod_name(pod_name)
                val = float(item.get("value", [0, 0])[1])
                per_pod[short_name] = round(per_pod.get(short_name, 0.0) + val, 2)
                total_watts += val

            # If no pods matched the namespace filter, query global cluster pod rate
            if not per_pod:
                query_fallback = f"sum by (pod) (rate({metric}[30s]))"
                async with httpx.AsyncClient(timeout=2.0) as client:
                    resp = await client.get(url, params={"query": query_fallback})
                    if resp.status_code == 200:
                        fb_data = resp.json().get("data", {}).get("result", [])
                        for item in fb_data[:5]:
                            p_name = self._simplify_pod_name(item.get("metric", {}).get("pod", "pod"))
                            v = float(item.get("value", [0, 0])[1])
                            per_pod[p_name] = round(v, 2)
                            total_watts += v

            # Calculate Eco-Score letter grade
            grade, description = self._calculate_grade(total_watts)

            return {
                "source": "kepler",
                "total_watts": round(total_watts, 2),
                "per_pod": per_pod if per_pod else {"backend-stack": round(total_watts, 2)},
                "carbon_intensity_g_per_kwh": config.GRID_CARBON_INTENSITY_G_PER_KWH,
                "eco_grade": grade,
                "eco_grade_reason": description,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            # Degrade gracefully with honest unavailable report
            return {
                "source": "unavailable",
                "error": f"Kepler/Prometheus query failed: {str(e)}",
                "total_watts": 0.0,
                "per_pod": {},
                "carbon_intensity_g_per_kwh": config.GRID_CARBON_INTENSITY_G_PER_KWH,
                "eco_grade": "N/A",
                "eco_grade_reason": "Prometheus/Kepler exporter unreachable",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def _fetch_kepler_window_joules(
        self, start_iso: str, end_iso: str, window_seconds: float
    ) -> Tuple[float, str]:
        """Queries Prometheus for energy increase (Joules) over the ticket window."""
        metric = config.KEPLER_METRIC_CONTAINER_JOULES
        window_int = max(10, int(window_seconds))
        query = (
            f'sum(increase({metric}{{container_namespace=~"{config.APP_NAMESPACE}|default"}}[{window_int}s]))'
        )
        url = f"{config.PROMETHEUS_URL}/api/v1/query"

        try:
            # Evaluate at end time
            end_ts = datetime.fromisoformat(end_iso).timestamp()
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(url, params={"query": query, "time": end_ts})
                resp.raise_for_status()
                res = resp.json().get("data", {}).get("result", [])
                if res:
                    joules = float(res[0].get("value", [0, 0])[1])
                    return max(0.0, joules), "kepler"
        except Exception:
            pass

        # Fallback to simulated if Prometheus failed
        return self._fetch_simulated_window_joules(window_seconds)

    def _fetch_simulated_live(self) -> Dict[str, Any]:
        """Simulates realistic pod power (Watts) driven by host CPU usage and noise model."""
        cpu = psutil.cpu_percent(interval=None) if hasattr(psutil, "cpu_percent") else 15.0
        # Base watts per component + CPU load factor + micro-fluctuation
        jitter = math.sin(time.time() / 5.0) * 0.8 + random.uniform(-0.3, 0.3)

        api_watts = max(1.5, round(2.8 + (cpu * 0.04) + (jitter * 0.4), 2))
        worker_watts = max(1.8, round(3.4 + (cpu * 0.05) + (jitter * 0.3), 2))
        frontend_watts = max(0.8, round(1.2 + random.uniform(-0.1, 0.1), 2))
        temporal_watts = max(3.0, round(5.2 + (cpu * 0.06) + (jitter * 0.5), 2))
        postgres_watts = max(2.0, round(3.1 + (cpu * 0.03) + (jitter * 0.2), 2))

        per_pod = {
            "mauji-api": api_watts,
            "mauji-worker": worker_watts,
            "mauji-frontend": frontend_watts,
            "temporal-server": temporal_watts,
            "temporal-postgres": postgres_watts,
        }
        total_watts = round(sum(per_pod.values()), 2)
        grade, description = self._calculate_grade(total_watts)

        return {
            "source": "simulated",
            "total_watts": total_watts,
            "per_pod": per_pod,
            "carbon_intensity_g_per_kwh": config.GRID_CARBON_INTENSITY_G_PER_KWH,
            "eco_grade": grade,
            "eco_grade_reason": description,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _fetch_simulated_window_joules(self, window_seconds: float) -> Tuple[float, str]:
        """Returns plausible Joules for a window: ~15.7 Watts average * seconds."""
        avg_watts = 15.7 + random.uniform(-0.5, 0.5)
        joules = avg_watts * window_seconds
        return joules, "simulated"

    def _calculate_grade(self, total_watts: float) -> Tuple[str, str]:
        """Computes Eco-Score letter grade based on stack power draw."""
        if total_watts < 20.0:
            return "A+", "Ultra-efficient (<20W). Minimal carbon footprint."
        elif total_watts < 35.0:
            return "A", "Highly efficient (20-35W). Optimized cloud-native execution."
        elif total_watts < 55.0:
            return "B+", "Moderate power draw (35-55W). Normal multi-pod workload."
        elif total_watts < 80.0:
            return "B", "Elevated load (55-80W). Moderate CPU utilization."
        else:
            return "C", "High power draw (>80W). Heavy compute load."

    def _simplify_pod_name(self, name: str) -> str:
        """Strips random deployment replica hashes (e.g. mauji-api-7b8df48479-x2k4j -> mauji-api)."""
        parts = name.split("-")
        if len(parts) >= 3 and len(parts[-1]) >= 4 and len(parts[-2]) >= 4:
            return "-".join(parts[:-2])
        return name


eco_service = EcoService()
