from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from server.collectors import hardware

CHAVES_CONTRATO = {
    "cpu_pct",
    "cpu_temp",
    "ram_pct",
    "ram_usado_gb",
    "ram_total_gb",
    "gpu_nome",
    "gpu_pct",
    "gpu_temp",
    "vram_usado_gb",
    "vram_total_gb",
    "rede_down_kbps",
    "rede_up_kbps",
    "cpu_nome",
    "cpu_nucleos_fisicos",
    "cpu_nucleos",
    "cpu_clock_mhz",
    "cpu_base_mhz",
    "ram_disponivel_gb",
    "swap_pct",
    "gpu_clock_mhz",
    "gpu_clock_max_mhz",
    "gpu_mem_clock_mhz",
    "gpu_power_w",
    "gpu_power_limite_w",
    "gpu_fan_pct",
    "gpu_pstate",
    "gpu_mem_ctrl_pct",
    "gpu_enc_pct",
    "gpu_dec_pct",
    "gpu_pcie_rx_mbps",
    "gpu_pcie_tx_mbps",
    "gpu_temp_limite",
    "gpu_throttle",
    "gpu_driver",
    "disco_leitura_mbps",
    "disco_escrita_mbps",
    "processos_top",
    "uptime_s",
}


class MockProcess:
    def __init__(self, pid, name, rss, cpu_val):
        self.pid = pid
        self._name = name
        self._rss = rss
        self._cpu_val = cpu_val
        self.info = {
            "name": name,
            "memory_info": SimpleNamespace(rss=rss),
        }

    def name(self):
        return self._name

    def memory_info(self):
        return SimpleNamespace(rss=self._rss)

    def cpu_percent(self, interval=None):
        return self._cpu_val


def _setup_mocks(monkeypatch):
    monkeypatch.setattr(
        hardware,
        "_cpu_info",
        lambda: ("AMD Ryzen 5 5600X 6-Core Processor", 3701),
    )
    monkeypatch.setattr(hardware, "_cpu_perf_pct", lambda ctx: 120.2)

    # Mock psutil
    monkeypatch.setattr(
        hardware.psutil,
        "cpu_percent",
        lambda interval=None, percpu=False: (
            [10.0, 20.0, 30.0, 40.0, 5.0, 15.0] if percpu else 15.5
        ),
    )
    monkeypatch.setattr(hardware.psutil, "cpu_count", lambda logical=True: 12 if logical else 6)
    monkeypatch.setattr(
        hardware.psutil,
        "virtual_memory",
        lambda: SimpleNamespace(
            percent=41.2,
            used=13 * (1024**3),
            total=32 * (1024**3),
            available=19 * (1024**3),
        ),
    )
    monkeypatch.setattr(
        hardware.psutil,
        "swap_memory",
        lambda: SimpleNamespace(percent=5.7),
    )
    monkeypatch.setattr(
        hardware.psutil,
        "net_io_counters",
        lambda: SimpleNamespace(bytes_recv=1024 * 1024, bytes_sent=512 * 1024),
    )
    monkeypatch.setattr(
        hardware.psutil,
        "disk_io_counters",
        lambda: SimpleNamespace(read_bytes=10 * 1024 * 1024, write_bytes=5 * 1024 * 1024),
    )
    monkeypatch.setattr(hardware.psutil, "boot_time", lambda: 1700000000.0)

    mock_procs = [
        MockProcess(101, "ollama.exe", 812 * 1024 * 1024, 422.4),
        MockProcess(102, "chrome.exe", 400 * 1024 * 1024, 60.0),
        MockProcess(0, "System Idle Process", 0, 800.0),
    ]
    monkeypatch.setattr(
        hardware.psutil,
        "process_iter",
        lambda attrs=None: mock_procs,
    )

    # Mock pynvml
    mock_pynvml = MagicMock()
    mock_pynvml.NVML_CLOCK_GRAPHICS = 0
    mock_pynvml.NVML_CLOCK_MEM = 2
    mock_pynvml.NVML_TEMPERATURE_GPU = 0
    mock_pynvml.NVML_PCIE_UTIL_TX_BYTES = 0
    mock_pynvml.NVML_PCIE_UTIL_RX_BYTES = 1
    mock_pynvml.NVML_TEMPERATURE_THRESHOLD_SLOWDOWN = 1

    handle = MagicMock()
    mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = handle
    mock_pynvml.nvmlDeviceGetName.return_value = b"NVIDIA GeForce RTX 5060 Ti"
    mock_pynvml.nvmlDeviceGetUtilizationRates.return_value = SimpleNamespace(gpu=7, memory=1)
    mock_pynvml.nvmlDeviceGetTemperature.return_value = 41
    mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = SimpleNamespace(
        used=int(2.3 * (1024**3)),
        total=int(15.9 * (1024**3)),
    )
    mock_pynvml.nvmlDeviceGetClockInfo.side_effect = lambda h, clk: 2602 if clk == 0 else 14001
    mock_pynvml.nvmlDeviceGetMaxClockInfo.return_value = 3090
    mock_pynvml.nvmlDeviceGetPowerUsage.return_value = 27100
    mock_pynvml.nvmlDeviceGetEnforcedPowerLimit.return_value = 180000
    mock_pynvml.nvmlDeviceGetFanSpeed.return_value = 0
    mock_pynvml.nvmlDeviceGetPerformanceState.return_value = 0
    mock_pynvml.nvmlDeviceGetEncoderUtilization.return_value = [0, 100000]
    mock_pynvml.nvmlDeviceGetDecoderUtilization.return_value = [0, 100000]
    mock_pynvml.nvmlDeviceGetPcieThroughput.return_value = 5427
    mock_pynvml.nvmlDeviceGetTemperatureThreshold.return_value = 89
    mock_pynvml.nvmlDeviceGetCurrentClocksEventReasons.return_value = 0x4
    mock_pynvml.nvmlSystemGetDriverVersion.return_value = "616.56"

    monkeypatch.setattr(hardware, "pynvml", mock_pynvml)
    return mock_pynvml


def test_contrato_chaves_presentes(monkeypatch):
    """(a) Todas as chaves do contrato presentes."""
    _setup_mocks(monkeypatch)
    top = [{"nome": "ollama", "cpu_pct": 35.2, "ram_mb": 812}]
    monkeypatch.setattr(hardware, "_processos_pdh", lambda ctx: top)
    ctx = {"cpu_temp_desligado": True}
    res = hardware.collect({}, ctx)

    assert set(res.keys()) == CHAVES_CONTRATO
    assert len(res.keys()) == 38
    assert res["cpu_nome"] == "AMD Ryzen 5 5600X 6-Core Processor"
    assert res["cpu_base_mhz"] == 3701
    assert res["cpu_clock_mhz"] == round(3701 * 120.2 / 100)
    assert res["cpu_nucleos_fisicos"] == 6
    assert isinstance(res["cpu_nucleos"], list)
    assert res["ram_pct"] == 41.2
    assert res["ram_usado_gb"] == 13.0
    assert res["ram_total_gb"] == 32.0
    assert res["ram_disponivel_gb"] == 19.0
    assert res["swap_pct"] == 5.7
    assert res["gpu_nome"] == "NVIDIA GeForce RTX 5060 Ti"
    assert res["gpu_pct"] == 7
    assert res["gpu_temp"] == 41
    assert res["gpu_clock_mhz"] == 2602
    assert res["gpu_clock_max_mhz"] == 3090
    assert res["gpu_mem_clock_mhz"] == 14001
    assert res["gpu_power_w"] == 27.1
    assert res["gpu_power_limite_w"] == 180.0
    assert res["gpu_fan_pct"] == 0
    assert res["gpu_pstate"] == 0
    assert res["gpu_mem_ctrl_pct"] == 1
    assert res["gpu_enc_pct"] == 0
    assert res["gpu_dec_pct"] == 0
    assert res["gpu_pcie_rx_mbps"] == round(5427 / 1024.0, 1)
    assert res["gpu_pcie_tx_mbps"] == round(5427 / 1024.0, 1)
    assert res["gpu_temp_limite"] == 89
    assert res["gpu_throttle"] == ["power"]
    assert res["gpu_driver"] == "616.56"
    assert res["processos_top"] == top
    assert isinstance(res["uptime_s"], int)


def test_throttle_decodificacao(monkeypatch):
    """(b) Decodificação de throttle 0x4|0x40|0x400|0x1 -> ['power', 'termico']."""
    mock_pynvml = _setup_mocks(monkeypatch)
    motivos = 0x4 | 0x40 | 0x400 | 0x1
    mock_pynvml.nvmlDeviceGetCurrentClocksEventReasons.return_value = motivos

    ctx = {"cpu_temp_desligado": True}
    res = hardware.collect({}, ctx)

    assert res["gpu_throttle"] == ["power", "termico"]
    # Teste direto da função auxiliar
    assert hardware._parse_throttle(motivos) == ["power", "termico"]
    assert hardware._parse_throttle(0) == []
    assert hardware._parse_throttle(None) == []


def test_nvml_excecao_individual(monkeypatch):
    """(c) Leitura NVML que lança exceção (ex.: FanSpeed) dá gpu_fan_pct null sem zerar gpu_clock_mhz."""
    mock_pynvml = _setup_mocks(monkeypatch)
    mock_pynvml.nvmlDeviceGetFanSpeed.side_effect = RuntimeError("Fan speed not supported")

    ctx = {"cpu_temp_desligado": True}
    res = hardware.collect({}, ctx)

    assert res["gpu_fan_pct"] is None
    assert res["gpu_clock_mhz"] == 2602
    assert res["gpu_nome"] == "NVIDIA GeForce RTX 5060 Ti"
    assert ctx.get("nvml_falhou") is not True


def test_taxa_disco_segunda_chamada(monkeypatch):
    """(d) A 2ª chamada calcula a taxa de disco a partir dos contadores falsos."""
    _setup_mocks(monkeypatch)

    leituras = [
        SimpleNamespace(read_bytes=100 * 1024 * 1024, write_bytes=50 * 1024 * 1024),
        SimpleNamespace(read_bytes=110 * 1024 * 1024, write_bytes=52 * 1024 * 1024),
    ]
    contador_idx = 0

    def mock_disk_counters():
        nonlocal contador_idx
        res = leituras[min(contador_idx, len(leituras) - 1)]
        contador_idx += 1
        return res

    monkeypatch.setattr(hardware.psutil, "disk_io_counters", mock_disk_counters)

    tempo_atual = 1000.0

    def mock_monotonic():
        return tempo_atual

    monkeypatch.setattr(hardware.time, "monotonic", mock_monotonic)

    ctx = {"cpu_temp_desligado": True}

    # 1ª chamada: prepara a medição
    res1 = hardware.collect({}, ctx)
    assert res1["disco_leitura_mbps"] == 0.0
    assert res1["disco_escrita_mbps"] == 0.0

    # Avança 1 segundo no tempo simulado
    tempo_atual = 1001.0

    # 2ª chamada: calcula taxa com base no delta
    res2 = hardware.collect({}, ctx)
    assert res2["disco_leitura_mbps"] == 10.0
    assert res2["disco_escrita_mbps"] == 2.0
