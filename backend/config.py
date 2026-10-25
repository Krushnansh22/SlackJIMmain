import os

# Temporal configuration
TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "mauji-cafe-sos")
WORKFLOW_TYPE = "BribeBoardWorkflow"
TEMPORAL_UI_URL = os.getenv("TEMPORAL_UI_URL", "http://localhost:8233").rstrip("/")

# Auto-rescue timer (seconds before Temporal triggers the AI rescue activity)
AUTO_RESCUE_SECONDS = int(os.getenv("AUTO_RESCUE_SECONDS", "60"))

# Jarvis Labs GPU LLM configuration
JARVIS_LLM_BASE_URL = os.getenv("JARVIS_LLM_BASE_URL", "").rstrip("/")
JARVIS_LLM_API_KEY = os.getenv("JARVIS_LLM_API_KEY", "")
JARVIS_LLM_MODEL = os.getenv("JARVIS_LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")
# GPU thermal design power (Watts) for inference energy attribution estimate
# E.g. NVIDIA A100 PCIe ~250-300W, SXM ~400W, RTX 6000 Ada ~300W, L4 ~72W
JARVIS_GPU_TDP_WATTS = float(os.getenv("JARVIS_GPU_TDP_WATTS", "300.0"))

# Eco-Score & Kepler / Prometheus configuration
# Provider mode: "simulated" (local default) or "kepler" (cluster live Prometheus)
ECO_PROVIDER = os.getenv("ECO_PROVIDER", "simulated").lower()
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090").rstrip("/")
APP_NAMESPACE = os.getenv("APP_NAMESPACE", "mauji-cafe-sos")

# India Grid Average Carbon Intensity: 727 gCO2/kWh
# Source: Central Electricity Authority (CEA), Ministry of Power, Govt of India
# CO2 Baseline Database for the Indian Power Sector, Version 20.0 (December 2024)
GRID_CARBON_INTENSITY_G_PER_KWH = float(os.getenv("GRID_CARBON_INTENSITY_G_PER_KWH", "727.0"))

# Kepler metric names verified against CNCF Kepler v0.7.x+
KEPLER_METRIC_CONTAINER_JOULES = os.getenv("KEPLER_METRIC_CONTAINER_JOULES", "kepler_container_joules_total")
